"""Salesforce boundary: OAuth client credentials, explicit permission-aware imports and opt-in writes."""

import os, re
from urllib.parse import urlparse
from typing import Protocol
import httpx
from .services import snapshot


class CRMAdapter(Protocol):
    def campaigns(self): ...
class LocalCRMAdapter:
    def __init__(self, db):
        self.db = db

    def campaigns(self):
        from sqlalchemy import select
        from .models import Campaign

        return [snapshot(c) for c in self.db.scalars(select(Campaign))]


class ConnectorError(Exception):
    pass


class SalesforceAdapter:
    def __init__(self):
        self.base = os.getenv("SALESFORCE_INSTANCE_URL", "").rstrip("/")
        self.key = os.getenv("SALESFORCE_CLIENT_ID", "")
        self.secret = os.getenv("SALESFORCE_CLIENT_SECRET", "")
        self.version = os.getenv("SALESFORCE_API_VERSION", "v66.0")
        self.token = None
        host = urlparse(self.base)
        if (
            host.scheme != "https"
            or not host.hostname
            or not host.hostname.endswith((".salesforce.com", ".force.com"))
            or host.path
            or host.username
            or host.port
        ):
            raise ConnectorError("Configure an HTTPS Salesforce org domain.")
        if not re.fullmatch(r"v\d{2,3}\.0", self.version):
            raise ConnectorError("Invalid API version.")
        self.client = httpx.Client(timeout=15, follow_redirects=False)

    def close(self):
        self.client.close()

    def authenticate(self):
        if not self.key or not self.secret:
            raise ConnectorError("Salesforce credentials are missing.")
        try:
            r = self.client.post(
                self.base + "/services/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.key,
                    "client_secret": self.secret,
                },
            )
            if r.status_code != 200:
                raise ConnectorError(
                    f"OAuth authentication failed (HTTP {r.status_code}). Verify the execution user and app permissions."
                )
            self.token = r.json()["access_token"]
        except (httpx.HTTPError, ValueError, KeyError):
            raise ConnectorError(
                "Salesforce authentication unavailable or invalid response."
            )

    def request(self, method, path, **kwargs):
        if not path.startswith("/services/data/"):
            raise ConnectorError("Invalid Salesforce API path.")
        if not self.token:
            self.authenticate()
        try:
            r = self.client.request(
                method,
                self.base + path,
                headers={"Authorization": f"Bearer {self.token}"},
                **kwargs,
            )
            if r.status_code == 401:
                self.authenticate()
                r = self.client.request(
                    method,
                    self.base + path,
                    headers={"Authorization": f"Bearer {self.token}"},
                    **kwargs,
                )
            if r.status_code == 429 or (
                r.status_code == 403 and "REQUEST_LIMIT_EXCEEDED" in r.text
            ):
                raise ConnectorError(
                    "Salesforce rate limit reached. Retry later; no automatic write retry was attempted."
                )
            if r.status_code >= 400:
                raise ConnectorError(
                    f"Salesforce returned HTTP {r.status_code}. Verify object and field access for the execution user."
                )
            return r.json() if r.content else {}
        except (httpx.HTTPError, ValueError):
            raise ConnectorError(
                "Salesforce request timed out or returned an invalid response."
            )

    def query(self, soql):
        result = self.request(
            "GET", f"/services/data/{self.version}/query", params={"q": soql}
        )
        rows = result["records"]
        while not result.get("done", True):
            if len(rows) > 10000:
                raise ConnectorError(
                    "Import exceeds prototype limit of 10,000 records."
                )
            result = self.request("GET", result["nextRecordsUrl"])
            rows.extend(result["records"])
        return rows

    def campaigns(self):
        return self.query(
            "SELECT Id, Name, Description, Type, Status FROM Campaign ORDER BY LastModifiedDate DESC LIMIT 100"
        )

    def members(self, id):
        if not re.fullmatch(r"[a-zA-Z0-9]{15,18}", id):
            raise ConnectorError("Invalid Salesforce campaign identifier.")
        # An opt-out flag alone never establishes affirmative permission.
        return self.query(
            f"SELECT Contact.Id, Contact.Name, Contact.Email, Contact.HasOptedOutOfEmail FROM CampaignMember WHERE CampaignId = '{id}' AND ContactId != null LIMIT 10000"
        )

    def store_approved(self, c, a, approval):
        if os.getenv("SALESFORCE_WRITE_ENABLED", "false").lower() != "true":
            raise ConnectorError("Salesforce audit storage is disabled.")
        if (
            approval.decision != "approved"
            or approval.campaign_version != c.version
            or approval.campaign_id != c.id
            or approval.audit_id != a.id
            or a.campaign_id != c.id
            or a.campaign_version != c.version
            or a.status != "completed"
            or a.snapshot != snapshot(c)
            or any(f.blocking for f in a.findings)
        ):
            raise ConnectorError(
                "Only the current approved campaign snapshot and matching audit can be exported."
            )
        if not c.external_id or not re.fullmatch(r"[a-zA-Z0-9]{15,18}", c.external_id):
            raise ConnectorError(
                "A mapped Salesforce campaign is required for storage."
            )
        # Stable external identifier makes repeated exports idempotent. Objects/fields must be provisioned.
        records = [
            {
                "attributes": {"type": "Fairgate_Audit__c"},
                "External_Key__c": f"fairgate-{c.id}-{a.id}",
                "Campaign__c": c.external_id,
                "Risk_Score__c": a.risk_score,
                "Version__c": a.campaign_version,
                "Status__c": "Approved",
            }
        ]
        for f in a.findings:
            records.append(
                {
                    "attributes": {"type": "Fairgate_Finding__c"},
                    "External_Key__c": f"fairgate-finding-{f.id}",
                    "Audit__r": {"External_Key__c": f"fairgate-{c.id}-{a.id}"},
                    "Rule__c": f.rule_id,
                    "Severity__c": f.severity,
                    "Explanation__c": f.explanation,
                }
            )
        records.append(
            {
                "attributes": {"type": "Fairgate_Approval__c"},
                "External_Key__c": f"fairgate-approval-{approval.id}",
                "Audit__r": {"External_Key__c": f"fairgate-{c.id}-{a.id}"},
                "Decision__c": approval.decision,
                "Reviewer__c": approval.reviewer,
            }
        )
        if len(records) > 200:
            raise ConnectorError(
                "Too many export records for a single all-or-none operation."
            )
        # Composite subrequests permit upserts to different custom objects and rollback on error.
        requests = []
        for i, r in enumerate(records):
            type_ = r.pop("attributes")["type"]
            key = r.pop("External_Key__c")
            requests.append(
                {
                    "method": "PATCH",
                    "url": f"/services/data/{self.version}/sobjects/{type_}/External_Key__c/{key}",
                    "referenceId": f"row{i}",
                    "body": r,
                }
            )
        if len(requests) > 25:
            raise ConnectorError(
                "Export exceeds the composite limit of 25 subrequests."
            )
        result = self.request(
            "POST",
            f"/services/data/{self.version}/composite",
            json={"allOrNone": True, "compositeRequest": requests},
        )
        if any(r["httpStatusCode"] >= 400 for r in result["compositeResponse"]):
            raise ConnectorError(
                "Salesforce rejected audit storage; all changes rolled back. Check custom object mappings and permissions."
            )
        return {"stored": True, "records": len(records)}


def status():
    configured = all(
        os.getenv(k)
        for k in [
            "SALESFORCE_INSTANCE_URL",
            "SALESFORCE_CLIENT_ID",
            "SALESFORCE_CLIENT_SECRET",
        ]
    )
    return {
        "mode": os.getenv("APP_MODE", "demo"),
        "local_crm": "Demo Mode — Synthetic Data",
        "salesforce": {
            "configured": configured,
            "connected": False,
            "status": (
                "Configured — connection not verified"
                if configured
                else "Salesforce Not Connected"
            ),
            "write_enabled": os.getenv("SALESFORCE_WRITE_ENABLED", "false").lower()
            == "true",
        },
        "agentforce": {
            "status": "Proposed — not operational",
            "contract": "docs/agentforce.md",
        },
        "llm": {
            "enabled": False,
            "status": "Deterministic policy baseline · no LLM required",
        },
        "delivery_enabled": False,
    }
