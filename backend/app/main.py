import os, threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from .db import Base, engine, Session, get_db, now
from .models import *
from .schemas import (
    CampaignCreate,
    CampaignPatch,
    RemediationPatch,
    Apply,
    ApprovalRequest,
    Decision,
    Restore,
)
from .services import *
from .seed import seed
from . import engine as agents
from .integrations import (
    status as integration_status,
    SalesforceAdapter,
    ConnectorError,
)

LOCK = threading.RLock()


def demo_only():
    if os.getenv("APP_MODE", "demo") != "demo":
        raise HTTPException(
            403,
            "Local reviewer mutations and demo reset are disabled in connected mode. Integrate authenticated review before enabling writes.",
        )


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with Session() as db:
        if os.getenv("APP_MODE", "demo") == "demo":
            seed(db)
        for a in db.scalars(
            select(Audit).where(Audit.status.in_(["running", "waiting"]))
        ):
            a.status = "failed"
            a.error = "Execution interrupted by server restart. Run a new audit."
            a.completed_at = now()
            a.agent_states = {
                k: ("failed" if v in ["running", "waiting"] else v)
                for k, v in a.agent_states.items()
            }
        db.commit()
        if os.getenv("APP_MODE", "demo") == "demo":
            seed_baseline_audits(db)
    yield


app = FastAPI(
    title="FAIRGATE AI",
    version="1.0.0",
    lifespan=lifespan,
    description="Synthetic preflight governance. No message delivery. Local demo reviewer is not authenticated.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001"
    ).split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security(request: Request, call_next):
    length = request.headers.get("content-length", "0")
    if not length.isdigit() or int(length) > 1500000:
        return JSONResponse(
            status_code=413, content={"detail": "Request exceeds size limit."}
        )
    # These local routes accept JSON only, so cross-origin forms cannot mutate state.
    if request.method in ["POST", "PATCH"]:
        origin = request.headers.get("origin")
        if origin and origin not in os.getenv(
            "CORS_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001"
        ).split(","):
            return JSONResponse(
                status_code=403, content={"detail": "Origin is not allowed."}
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Database operation unavailable. Retry the request."},
    )


@app.exception_handler(ConnectorError)
async def connector_error(request, exc):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def seed_baseline_audits(db):
    ids = [
        c.id
        for c in db.scalars(select(Campaign))
        if c.name != "Digital Future Morocco 2027" and not c.audits
    ]
    for cid in ids:
        c = db.get(Campaign, cid)
        a = Audit(
            campaign_id=c.id,
            campaign_version=c.version,
            snapshot=snapshot(c),
            agent_states={x: "waiting" for x in agents.AGENTS},
        )
        db.add(a)
        db.commit()
        execute_audit(a.id, a.execution_token)


@app.get("/api/health")
def health(db=Depends(get_db)):
    db.execute(select(1))
    return {
        "status": "ok",
        "mode": os.getenv("APP_MODE", "demo"),
        "delivery_enabled": False,
    }


@app.get("/api/contacts")
def contacts(db=Depends(get_db)):
    return [serialize(c) for c in db.scalars(select(Contact).order_by(Contact.id))]


@app.get("/api/campaigns")
def campaigns(db=Depends(get_db)):
    return [
        campaign_json(db, c) for c in db.scalars(select(Campaign).order_by(Campaign.id))
    ]


@app.get("/api/campaigns/{id}")
def campaign(id: int, db=Depends(get_db)):
    return campaign_json(db, require(db, Campaign, id))


def set_campaign(db, c, data):
    values = data.model_dump(
        exclude={"expected_version"}, exclude_unset=isinstance(data, CampaignPatch)
    )
    if "recipient_ids" in values:
        ids = set(values.pop("recipient_ids"))
        recipients = list(db.scalars(select(Contact).where(Contact.id.in_(ids))))
        if len(recipients) != len(ids):
            raise HTTPException(422, "Unknown recipient IDs.")
        c.recipients = recipients
    for k, v in values.items():
        setattr(c, k, v)


@app.post("/api/campaigns", status_code=201, dependencies=[Depends(demo_only)])
def create(data: CampaignCreate, db=Depends(get_db)):
    with LOCK:
        c = Campaign()
        set_campaign(db, c, data)
        db.add(c)
        db.flush()
        c.original_snapshot = snapshot(c)
        db.add(CampaignRevision(campaign_id=c.id, version=1, snapshot=snapshot(c)))
        record(db, c.id, "campaign_created", {"version": 1})
        db.commit()
        return campaign_json(db, c)


@app.patch("/api/campaigns/{id}", dependencies=[Depends(demo_only)])
def update(id: int, data: CampaignPatch, db=Depends(get_db)):
    with LOCK:
        c = require(db, Campaign, id)
        if c.version != data.expected_version:
            raise HTTPException(409, "Campaign changed. Reload before editing.")
        set_campaign(db, c, data)
        revise(db, c, "campaign_edited")
        db.commit()
        return campaign_json(db, c)


@app.get("/api/campaigns/{id}/revisions")
def revisions(id: int, db=Depends(get_db)):
    require(db, Campaign, id)
    return [
        serialize(r)
        for r in db.scalars(
            select(CampaignRevision)
            .where(CampaignRevision.campaign_id == id)
            .order_by(CampaignRevision.version.desc())
        )
    ]


@app.post(
    "/api/campaigns/{id}/revisions/{version}/restore", dependencies=[Depends(demo_only)]
)
def restore(id: int, version: int, data: Restore, db=Depends(get_db)):
    with LOCK:
        c = require(db, Campaign, id)
        if c.version != data.expected_version:
            raise HTTPException(409, "Campaign version changed.")
        r = db.scalar(
            select(CampaignRevision).where(
                CampaignRevision.campaign_id == id, CampaignRevision.version == version
            )
        )
        if not r:
            raise HTTPException(404, "Revision not found.")
        for k, v in r.snapshot.items():
            if k != "recipients":
                setattr(c, k, v)
        ids = [r["id"] for r in r.snapshot["recipients"]]
        c.recipients = list(db.scalars(select(Contact).where(Contact.id.in_(ids))))
        revise(db, c, "revision_restored")
        db.commit()
        return campaign_json(db, c)


def execute_audit(id, execution_token=None):
    with LOCK, Session() as db:
        a = db.get(Audit, id)
        if not a or (
            execution_token is not None and a.execution_token != execution_token
        ):
            return
        try:
            a.status = "running"
            db.commit()
            findings = []
            for name, analyzer in zip(
                agents.AGENTS[:3], [agents.consent, agents.claims, agents.inclusion]
            ):
                a.agent_states = {**a.agent_states, name: "running"}
                record(db, a.campaign_id, "agent_running", {"agent": name}, a.id)
                db.commit()
                results = analyzer(a.snapshot)
                findings.extend(results)
                for result in results:
                    db.add(AuditFinding(audit_id=a.id, **result))
                a.agent_states = {**a.agent_states, name: "completed"}
                record(
                    db,
                    a.campaign_id,
                    "agent_completed",
                    {"agent": name, "findings": len(results)},
                    a.id,
                )
                db.commit()
            for name in agents.AGENTS[3:]:
                a.agent_states = {**a.agent_states, name: "running"}
                db.commit()
                if name == agents.AGENTS[3]:
                    # Calculate a remediation plan; applying it remains an explicit user action.
                    proposal = agents.remediation(a.snapshot, findings)
                    record(
                        db,
                        a.campaign_id,
                        "remediation_evaluated",
                        {
                            "available_corrections": [
                                x["id"] for x in proposal["corrections"]
                            ]
                        },
                        a.id,
                    )
                else:
                    record(
                        db,
                        a.campaign_id,
                        "governance_evaluated",
                        {
                            "blocking_rules": [
                                f["rule_id"] for f in findings if f["blocking"]
                            ]
                        },
                        a.id,
                    )
                a.agent_states = {**a.agent_states, name: "completed"}
                db.commit()
            a.risk_score = agents.score(findings)
            a.status = "completed"
            a.completed_at = now()
            c = a.campaign
            if c.version == a.campaign_version:
                c.status = (
                    "needs_attention"
                    if any(f["severity"] not in ["info"] for f in findings)
                    else "review_ready"
                )
            record(
                db,
                c.id,
                "audit_completed",
                {
                    "risk_score": a.risk_score,
                    "version": a.campaign_version,
                    "findings": len(findings),
                },
                a.id,
            )
            db.commit()
        except Exception:
            db.rollback()
            a = db.get(Audit, id)
            if a:
                a.status = "failed"
                a.error = "Audit execution failed. No approval can be granted. Retry a new audit."
                a.completed_at = now()
                a.agent_states = {
                    k: ("failed" if v == "running" else v)
                    for k, v in a.agent_states.items()
                }
                record(db, a.campaign_id, "audit_failed", {"message": a.error}, a.id)
                db.commit()


def start_audit(id, bg, db):
    with LOCK:
        c = require(db, Campaign, id)
        existing = latest(db, c)
        if existing and existing.status in ["waiting", "running"]:
            return audit_json(db, existing)
        a = Audit(
            campaign_id=c.id,
            campaign_version=c.version,
            snapshot=snapshot(c),
            agent_states={x: "waiting" for x in agents.AGENTS},
        )
        db.add(a)
        db.flush()
        c.status = "auditing"
        for p in db.scalars(
            select(Approval).where(
                Approval.campaign_id == id,
                Approval.decision.in_(["pending", "approved"]),
            )
        ):
            p.decision = "invalidated"
        record(db, id, "audit_requested", {"version": c.version}, a.id)
        db.commit()
        bg.add_task(execute_audit, a.id, a.execution_token)
        return audit_json(db, a)


@app.post(
    "/api/campaigns/{id}/audits", status_code=202, dependencies=[Depends(demo_only)]
)
@app.post(
    "/api/campaigns/{id}/reaudit", status_code=202, dependencies=[Depends(demo_only)]
)
def run_audit(id: int, bg: BackgroundTasks, db=Depends(get_db)):
    return start_audit(id, bg, db)


@app.get("/api/audits/{id}")
def audit(id: int, db=Depends(get_db)):
    return audit_json(db, require(db, Audit, id))


@app.get("/api/audits/{id}/findings")
def findings(id: int, db=Depends(get_db)):
    return [serialize(f) for f in require(db, Audit, id).findings]


@app.post("/api/audits/{id}/remediation", dependencies=[Depends(demo_only)])
def propose(id: int, db=Depends(get_db)):
    with LOCK:
        a = require(db, Audit, id)
        if a.status != "completed":
            raise HTTPException(409, "Complete the audit first.")
        if a.campaign.version != a.campaign_version:
            raise HTTPException(409, "Audit is stale. Re-audit the current draft.")
        p = db.scalar(
            select(RemediationProposal).where(RemediationProposal.audit_id == id)
        )
        if not p:
            p = RemediationProposal(
                audit_id=id,
                **agents.remediation(a.snapshot, [serialize(f) for f in a.findings]),
            )
            db.add(p)
            record(db, a.campaign_id, "corrections_proposed", {"audit_id": id}, id)
            db.commit()
        return serialize(p)


@app.patch("/api/remediations/{id}", dependencies=[Depends(demo_only)])
def choose(id: int, data: RemediationPatch, db=Depends(get_db)):
    with LOCK:
        p = require(db, RemediationProposal, id)
        if p.status != "proposed":
            raise HTTPException(
                409,
                "Applied corrections are immutable. Restore a revision to reverse them.",
            )
        if set(data.selections) - {x["id"] for x in p.corrections}:
            raise HTTPException(422, "Unknown correction.")
        p.corrections = [
            {**x, "selected": data.selections.get(x["id"], x["selected"])}
            for x in p.corrections
        ]
        record(
            db,
            require(db, Audit, p.audit_id).campaign_id,
            "corrections_selected",
            data.model_dump(),
            p.audit_id,
        )
        db.commit()
        return serialize(p)


@app.post("/api/remediations/{id}/apply", dependencies=[Depends(demo_only)])
def apply(id: int, data: Apply, db=Depends(get_db)):
    with LOCK:
        p = require(db, RemediationProposal, id)
        a = require(db, Audit, p.audit_id)
        c = a.campaign
        if p.status == "applied":
            return campaign_json(db, c)
        if c.version != a.campaign_version or c.version != data.expected_version:
            raise HTTPException(409, "Proposal is stale. Re-audit the current draft.")
        selections = {x["id"] for x in p.corrections if x["selected"]}
        if not selections:
            raise HTTPException(422, "Select at least one correction.")
        if "audience" in selections:
            c.recipients = [
                r for r in c.recipients if r.id not in p.excluded_recipients
            ]
        if "copy" in selections:
            c.marketing_content = agents.safe_copy(c.marketing_content)
            c.subject = agents.safe_copy(c.subject)
        if "accessibility" in selections:
            c.marketing_content = __import__("re").sub(
                r"<img\b[^>]*>", "", c.marketing_content, flags=__import__("re").I
            )
        if "languages" in selections:
            c.language_variants = p.proposed_language_variants
        revise(db, c, "corrections_applied")
        p.status = "applied"
        p.applied_version = c.version
        db.commit()
        return campaign_json(db, c)


@app.post("/api/approvals", status_code=201, dependencies=[Depends(demo_only)])
def request_approval(data: ApprovalRequest, db=Depends(get_db)):
    with LOCK:
        c = require(db, Campaign, data.campaign_id)
        a = require(db, Audit, data.audit_id)
        gate(db, c, a)
        existing = db.scalar(
            select(Approval).where(
                Approval.audit_id == a.id,
                Approval.decision.in_(["pending", "approved"]),
            )
        )
        if existing:
            return serialize(existing)
        p = Approval(**data.model_dump(), campaign_version=c.version)
        db.add(p)
        c.status = "pending_approval"
        record(
            db,
            c.id,
            "approval_requested",
            {"reviewer": p.reviewer, "version": c.version},
            a.id,
        )
        db.commit()
        return serialize(p)


@app.post("/api/approvals/{id}/approve", dependencies=[Depends(demo_only)])
def approve(id: int, data: Decision, db=Depends(get_db)):
    return decide(id, data, "approved", db)


@app.post("/api/approvals/{id}/reject", dependencies=[Depends(demo_only)])
def reject(id: int, data: Decision, db=Depends(get_db)):
    return decide(id, data, "rejected", db)


def decide(id, data, decision, db):
    with LOCK:
        p = require(db, Approval, id)
        c = require(db, Campaign, p.campaign_id)
        a = require(db, Audit, p.audit_id)
        if p.decision == decision:
            return serialize(p)
        if p.decision != "pending":
            raise HTTPException(409, "This approval request is no longer pending.")
        gate(db, c, a)
        if (
            decision == "approved"
            and c.language_variants
            and not data.language_reviewed
        ):
            raise HTTPException(
                422, "Confirm that language variants have been reviewed by a human."
            )
        p.decision = decision
        p.reviewer = data.reviewer
        p.comments = data.comments
        p.timestamp = now()
        c.status = "approved_for_activation" if decision == "approved" else "rejected"
        record(
            db,
            c.id,
            "human_" + decision,
            {
                "reviewer": p.reviewer,
                "comments": p.comments,
                "version": c.version,
                "language_reviewed": data.language_reviewed,
                "messages_sent": 0,
            },
            a.id,
        )
        db.commit()
        return serialize(p)


@app.get("/api/approvals")
def approvals(db=Depends(get_db)):
    return [
        serialize(p) for p in db.scalars(select(Approval).order_by(Approval.id.desc()))
    ]


@app.get("/api/audit-history")
def history(db=Depends(get_db)):
    return {
        "audits": [
            audit_json(db, a)
            for a in db.scalars(select(Audit).order_by(Audit.id.desc()))
        ],
        "events": [
            serialize(e)
            for e in db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()))
        ],
        "approvals": approvals(db),
    }


@app.get("/api/dashboard")
def dashboard(db=Depends(get_db)):
    cs = list(db.scalars(select(Campaign)))
    audits = list(db.scalars(select(Audit).where(Audit.status == "completed")))
    current = [latest(db, c) for c in cs]
    scores = [a.risk_score for a in current if a and a.status == "completed"]
    return {
        "campaign_count": len(cs),
        "audits_completed": len(audits),
        "requiring_attention": sum(c.status == "needs_attention" for c in cs),
        "approval_queue": sum(
            p.decision == "pending" for p in db.scalars(select(Approval))
        ),
        "risk_distribution": [
            {"name": "Low", "value": sum(s < 25 for s in scores)},
            {"name": "Medium", "value": sum(25 <= s < 60 for s in scores)},
            {"name": "High", "value": sum(s >= 60 for s in scores)},
        ],
        "recent_campaigns": [campaign_json(db, c) for c in cs],
        "activity": [
            serialize(e)
            for e in db.scalars(
                select(AuditEvent).order_by(AuditEvent.id.desc()).limit(12)
            )
        ],
    }


@app.get("/api/integrations/status")
def integrations():
    return integration_status()


@app.post("/api/integrations/salesforce/test")
def test_salesforce():
    adapter = SalesforceAdapter()
    try:
        adapter.authenticate()
        adapter.request("GET", f"/services/data/{adapter.version}/limits")
        return {
            "connected": True,
            "status": "OAuth verified for this request; execution-user permissions apply.",
        }
    finally:
        adapter.close()


@app.get("/api/integrations/salesforce/campaigns")
def sf_campaigns():
    adapter = SalesforceAdapter()
    try:
        return adapter.campaigns()
    finally:
        adapter.close()


@app.post("/api/integrations/salesforce/import/{external_id}")
def sf_import(external_id: str, db=Depends(get_db)):
    if os.getenv("APP_MODE", "demo") != "connected":
        raise HTTPException(
            403,
            "Import is restricted to isolated connected mode. Synthetic demo data must not be mixed with real records.",
        )
    if db.scalar(select(Campaign.id).where(Campaign.external_id.is_(None)).limit(1)):
        raise HTTPException(
            409,
            "Connected imports require an isolated database without synthetic campaigns.",
        )
    adapter = SalesforceAdapter()
    try:
        campaigns = adapter.campaigns()
        row = next((r for r in campaigns if r["Id"] == external_id), None)
        if not row:
            raise HTTPException(
                404, "Campaign not found in authorized Salesforce results."
            )
        members = adapter.members(external_id)
        with LOCK:
            c = db.scalar(select(Campaign).where(Campaign.external_id == external_id))
            if c:
                raise HTTPException(
                    409, "Campaign already imported; automatic overwrite is disabled."
                )
            c = Campaign(
                name=row["Name"],
                description=row.get("Description") or "",
                channel="email",
                subject="",
                marketing_content="",
                target_audience="Authorized Salesforce campaign members",
                language="en",
                language_variants={},
                supporting_evidence=[],
                external_id=external_id,
            )
            for item in members:
                r = item.get("Contact")
                if not r:
                    continue
                contact = db.scalar(
                    select(Contact).where(Contact.external_id == r["Id"])
                )
                if not contact:
                    contact = Contact(
                        external_id=r["Id"],
                        name=r["Name"],
                        email=r.get("Email"),
                        preferred_language="unknown",
                        marketing_email_consent=(
                            False if r.get("HasOptedOutOfEmail") else None
                        ),
                        consent_source="Salesforce HasOptedOutOfEmail — affirmative permission unavailable",
                    )
                    db.add(contact)
                    db.flush()
                c.recipients.append(contact)
            db.add(c)
            db.flush()
            c.original_snapshot = snapshot(c)
            db.add(CampaignRevision(campaign_id=c.id, version=1, snapshot=snapshot(c)))
            record(db, c.id, "salesforce_imported", {"external_id": external_id})
            db.commit()
            return campaign_json(db, c)
    finally:
        adapter.close()


@app.post("/api/integrations/salesforce/export/{approval_id}")
def sf_export(approval_id: int, db=Depends(get_db)):
    # No unauthenticated local write path to an organization's CRM.
    raise HTTPException(
        403,
        "External write endpoint disabled until authenticated governance is integrated. SalesforceAdapter.store_approved is available for a trusted server-side integration.",
    )


@app.post("/api/demo/reset", dependencies=[Depends(demo_only)])
def reset(db=Depends(get_db)):
    with LOCK:
        seed(db, reset=True)
        seed_baseline_audits(db)
    return {
        "status": "reset",
        "synthetic": True,
        "main_campaign_id": db.scalar(select(Campaign.id).order_by(Campaign.id)),
    }
