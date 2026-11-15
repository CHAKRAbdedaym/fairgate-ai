from sqlalchemy import select
from backend.app.db import Session
from backend.app.models import Campaign, Audit, AuditEvent
from backend.app import engine


def main(c):
    return c.get("/api/campaigns").json()[0]


def audited(c):
    campaign = main(c)
    r = c.post(f"/api/campaigns/{campaign['id']}/audits")
    assert r.status_code == 202
    a = c.get(f"/api/audits/{r.json()['id']}").json()
    assert a["status"] == "completed"
    return a


def corrected(c):
    a = audited(c)
    p = c.post(f"/api/audits/{a['id']}/remediation").json()
    r = c.post(f"/api/remediations/{p['id']}/apply", json={"expected_version": 1})
    assert r.status_code == 200, r.text
    a = audited(c)
    return a


def requested(c):
    a = corrected(c)
    r = c.post(
        "/api/approvals", json={"campaign_id": a["campaign_id"], "audit_id": a["id"]}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_optout_detection(client):
    f = next(f for f in audited(client)["findings"] if f["rule_id"] == "CONSENT_OPTOUT")
    assert (
        f["affected_count"] == 20
        and len(f["evidence"]["recipient_ids"]) == 20
        and f["blocking"]
    )


def test_missing_consent(client):
    f = next(
        f for f in audited(client)["findings"] if f["rule_id"] == "CONSENT_MISSING"
    )
    assert f["affected_count"] == 10 and f["severity"] == "critical"


def test_eligibility(client):
    c = main(client)
    assert c["eligible_count"] == 70 and c["recipient_count"] == 100
    assert sum(r["preferred_language"] == "ar" for r in c["recipients"]) == 30
    assert sum(r["preferred_language"] == "fr" for r in c["recipients"]) == 70


def test_unsupported_claim(client):
    f = next(
        f for f in audited(client)["findings"] if f["agent_type"] == "Claim Verifier"
    )
    assert (
        f["severity"] == "high"
        and "100% guaranteed employment" in f["evidence"]["quote"]
        and "false" in f["explanation"]
    )


def test_supported_claim(client):
    c = main(client)
    r = client.patch(
        f"/api/campaigns/{c['id']}",
        json={
            "expected_version": 1,
            "supporting_evidence": [
                {
                    "claim": "100% guaranteed employment after graduation",
                    "reference": "Synthetic verified report reference",
                    "verified": True,
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    fs = [f for f in audited(client)["findings"] if f["agent_type"] == "Claim Verifier"]
    assert len(fs) == 1 and fs[0]["severity"] == "info" and not fs[0]["blocking"]


def test_evidence_requires_manual_verification(client):
    c = main(client)
    client.patch(
        f"/api/campaigns/{c['id']}",
        json={
            "expected_version": 1,
            "supporting_evidence": [
                {
                    "claim": "100% guaranteed employment after graduation",
                    "reference": "Unverified report",
                }
            ],
        },
    )
    f = next(
        f for f in audited(client)["findings"] if f["agent_type"] == "Claim Verifier"
    )
    assert f["severity"] == "medium" and f["blocking"]


def test_language_mismatch(client):
    f = next(f for f in audited(client)["findings"] if f["rule_id"] == "LANG_ar")
    assert f["affected_count"] == 30


def test_combined_execution(client):
    a = audited(client)
    assert len(a["findings"]) == 4 and all(
        s == "completed" for s in a["agent_states"].values()
    )
    events = client.get("/api/audit-history").json()["events"]
    assert (
        sum(
            e["event_type"] == "agent_completed" and e["audit_id"] == a["id"]
            for e in events
        )
        == 3
    )


def test_risk_scoring(client):
    a = audited(client)
    assert a["risk_score"] == 100
    assert sorted(f["risk_contribution"] for f in a["findings"]) == [10, 25, 35, 35]
    assert engine.score([{"risk_contribution": 10}, {"risk_contribution": 25}]) == 35


def test_remediation_generation(client):
    a = audited(client)
    p = client.post(f"/api/audits/{a['id']}/remediation").json()
    assert (
        len(p["excluded_recipients"]) == 30 and "ar" in p["proposed_language_variants"]
    )
    assert "100% guaranteed" not in p["proposed_content"]
    assert client.post(f"/api/audits/{a['id']}/remediation").json()["id"] == p["id"]


def test_recipient_exclusion(client):
    corrected(client)
    c = main(client)
    assert c["recipient_count"] == 70 and c["eligible_count"] == 70
    assert len(client.get("/api/contacts").json()) == 100


def test_claim_correction_and_preserved_original(client):
    corrected(client)
    c = main(client)
    assert "100% guaranteed" not in c["marketing_content"]
    assert "100% guaranteed" in c["original_snapshot"]["marketing_content"]
    assert c["version"] == 2


def test_reaudit(client):
    a = corrected(client)
    assert a["risk_score"] == 0 and a["findings"] == []
    assert a["campaign_version"] == 2 and len(a["snapshot"]["recipients"]) == 70


def test_human_approval(client):
    p = requested(client)
    r = client.post(
        f"/api/approvals/{p['id']}/approve",
        json={"reviewer": "Synthetic Reviewer", "language_reviewed": True},
    )
    assert r.status_code == 200, r.text
    assert main(client)["status"] == "approved_for_activation"
    events = client.get("/api/audit-history").json()["events"]
    event = next(e for e in events if e["event_type"] == "human_approved")
    assert event["details"]["messages_sent"] == 0
    assert client.post(f"/api/approvals/{p['id']}/approve", json={}).status_code == 200


def test_language_review_required(client):
    p = requested(client)
    assert client.post(f"/api/approvals/{p['id']}/approve", json={}).status_code == 422


def test_rejection(client):
    p = requested(client)
    r = client.post(
        f"/api/approvals/{p['id']}/reject", json={"comments": "Revise tone"}
    )
    assert (
        r.status_code == 200
        and r.json()["decision"] == "rejected"
        and main(client)["status"] == "rejected"
    )
    assert (
        client.post(
            f"/api/approvals/{p['id']}/approve", json={"language_reviewed": True}
        ).status_code
        == 409
    )


def test_critical_blocks_approval(client):
    a = audited(client)
    r = client.post(
        "/api/approvals", json={"campaign_id": a["campaign_id"], "audit_id": a["id"]}
    )
    assert r.status_code == 409 and len(r.json()["detail"]["blocking_issues"]) == 3


def test_edit_invalidates_approval(client):
    p = requested(client)
    client.post(f"/api/approvals/{p['id']}/approve", json={"language_reviewed": True})
    c = main(client)
    r = client.patch(
        f"/api/campaigns/{c['id']}",
        json={"expected_version": 2, "subject": "Edited subject"},
    )
    assert r.status_code == 200
    assert client.get("/api/approvals").json()[0]["decision"] == "invalidated"
    assert main(client)["status"] == "draft"
    assert (
        client.post(
            "/api/approvals", json={"campaign_id": c["id"], "audit_id": p["audit_id"]}
        ).status_code
        == 409
    )


def test_audit_persistence(client):
    a = audited(client)
    with Session() as db:
        stored = db.get(Audit, a["id"])
        assert (
            stored.status == "completed"
            and len(stored.findings) == 4
            and len(stored.snapshot["recipients"]) == 100
        )
        assert (
            db.scalar(select(AuditEvent).where(AuditEvent.audit_id == a["id"]))
            is not None
        )


def test_demo_reset(client):
    requested(client)
    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    c = main(client)
    assert (
        c["version"] == 1 and c["recipient_count"] == 100 and c["latest_audit"] is None
    )
    assert client.get("/api/approvals").json() == []
    assert len(client.get("/api/campaigns").json()) == 4
    assert client.post("/api/demo/reset").status_code == 200


def test_input_validation(client):
    assert (
        client.post(
            "/api/campaigns", json={"name": "", "marketing_content": "x"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/campaigns",
            json={"name": "A", "marketing_content": "x", "channel": "fax"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/campaigns", json={"name": "A" * 161, "marketing_content": "x"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/campaigns",
            json={"name": "A", "marketing_content": "x", "recipient_ids": [9999]},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/campaigns/1", json={"expected_version": 1, "name": None}
        ).status_code
        == 422
    )


def test_api_errors(client):
    assert client.get("/api/campaigns/99999").status_code == 404
    assert client.get("/api/audits/99999").status_code == 404
    assert (
        client.post(
            "/api/remediations/99999/apply", json={"expected_version": 1}
        ).status_code
        == 404
    )
    assert client.post("/api/campaigns/1/activate").status_code == 404
    assert (
        client.post(
            "/api/campaigns",
            json={"name": "A", "marketing_content": "x"},
            headers={"Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )


def test_no_llm_fallback(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert audited(client)["risk_score"] == 100
    assert client.get("/api/integrations/status").json()["llm"]["enabled"] is False


def test_local_without_salesforce(client, monkeypatch):
    for key in [
        "SALESFORCE_CLIENT_ID",
        "SALESFORCE_CLIENT_SECRET",
        "SALESFORCE_INSTANCE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = client.get("/api/integrations/status").json()
    assert (
        not s["salesforce"]["connected"]
        and s["salesforce"]["status"] == "Salesforce Not Connected"
    )
    assert client.get("/api/health").json()["status"] == "ok"
    from backend.app.integrations import LocalCRMAdapter

    with Session() as db:
        assert len(LocalCRMAdapter(db).campaigns()) == 4


def test_individual_corrections(client):
    a = audited(client)
    p = client.post(f"/api/audits/{a['id']}/remediation").json()
    r = client.patch(
        f"/api/remediations/{p['id']}",
        json={"selections": {"copy": False, "languages": False}},
    )
    assert r.status_code == 200
    client.post(f"/api/remediations/{p['id']}/apply", json={"expected_version": 1})
    a = audited(client)
    assert a["risk_score"] == 35 and len(a["findings"]) == 2
    assert any(
        f["agent_type"] == "Claim Verifier" and f["blocking"] for f in a["findings"]
    )


def test_stale_proposal_and_version_conflict(client):
    a = audited(client)
    p = client.post(f"/api/audits/{a['id']}/remediation").json()
    client.patch("/api/campaigns/1", json={"expected_version": 1, "subject": "Changed"})
    assert (
        client.post(
            f"/api/remediations/{p['id']}/apply", json={"expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        client.patch(
            "/api/campaigns/1", json={"expected_version": 1, "subject": "stale"}
        ).status_code
        == 409
    )


def test_restore_revision(client):
    corrected(client)
    r = client.post(
        "/api/campaigns/1/revisions/1/restore", json={"expected_version": 2}
    )
    assert (
        r.status_code == 200
        and r.json()["version"] == 3
        and r.json()["recipient_count"] == 100
    )
    assert audited(client)["risk_score"] == 100


def test_channel_permission(client):
    client.patch("/api/campaigns/1", json={"expected_version": 1, "channel": "sms"})
    a = audited(client)
    assert any(
        f["rule_id"] == "CONSENT_CHANNEL" and f["affected_count"] == 100
        for f in a["findings"]
    )


def test_create_and_patch(client):
    r = client.post(
        "/api/campaigns",
        json={
            "name": "Synthetic Test",
            "marketing_content": "Learn new skills.",
            "recipient_ids": [31, 32],
        },
    )
    assert r.status_code == 201
    r = client.patch(
        f"/api/campaigns/{r.json()['id']}",
        json={"expected_version": 1, "name": "Updated"},
    )
    assert (
        r.status_code == 200
        and r.json()["marketing_content"] == "Learn new skills."
        and r.json()["recipient_count"] == 2
    )


def test_accessibility_dynamic(client):
    cs = client.get("/api/campaigns").json()
    c = next(c for c in cs if c["name"] == "An Accessible Future")
    r = client.post(f"/api/campaigns/{c['id']}/audits")
    a = client.get(f"/api/audits/{r.json()['id']}").json()
    assert any(f["rule_id"].startswith("ALT_") for f in a["findings"])
    p = client.post(f"/api/audits/{a['id']}/remediation").json()
    client.post(f"/api/remediations/{p['id']}/apply", json={"expected_version": 1})
    r = client.post(f"/api/campaigns/{c['id']}/audits")
    a = client.get(f"/api/audits/{r.json()['id']}").json()
    assert a["risk_score"] == 0


def test_connected_mode_safeguards(client, monkeypatch):
    monkeypatch.setenv("APP_MODE", "connected")
    for path in [
        "/api/demo/reset",
        "/api/campaigns/1/audits",
        "/api/approvals/1/approve",
    ]:
        assert client.post(path, json={}).status_code == 403
    assert client.post("/api/integrations/salesforce/export/1").status_code == 403


def test_new_audit_invalidates_decision(client):
    p = requested(client)
    client.post(f"/api/approvals/{p['id']}/approve", json={"language_reviewed": True})
    audited(client)
    assert client.get("/api/approvals").json()[0]["decision"] == "invalidated"


def test_untrusted_copy_not_executed(client):
    client.patch(
        "/api/campaigns/1",
        json={
            "expected_version": 1,
            "marketing_content": "<script>alert(1)</script><img src=x onerror=alert(1)>",
        },
    )
    a = audited(client)
    assert any(f["rule_id"].startswith("ALT_") for f in a["findings"])


def test_no_delivery_routes(client):
    spec = client.get("/openapi.json").json()
    assert not any("send" in p or "activate" in p for p in spec["paths"])


def test_queued_audit_token_cannot_run_against_reused_id(client):
    from backend.app.main import execute_audit
    from backend.app.services import snapshot

    with Session() as db:
        c = db.get(Campaign, main(client)["id"])
        a = Audit(
            campaign_id=c.id,
            campaign_version=c.version,
            snapshot=snapshot(c),
            agent_states={name: "waiting" for name in engine.AGENTS},
        )
        db.add(a)
        db.commit()
        id = a.id
        token = a.execution_token
    execute_audit(id, "stale-before-reset-token")
    with Session() as db:
        assert db.get(Audit, id).status == "waiting"
    execute_audit(id, token)
    with Session() as db:
        assert db.get(Audit, id).status == "completed"
