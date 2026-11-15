from sqlalchemy import select
from fastapi import HTTPException
from .models import *
from .db import now


def record(db, campaign_id, event_type, details, audit_id=None):
    db.add(
        AuditEvent(
            campaign_id=campaign_id,
            audit_id=audit_id,
            event_type=event_type,
            details=details,
        )
    )


def snapshot(c):
    return {
        k: getattr(c, k)
        for k in [
            "name",
            "description",
            "channel",
            "subject",
            "marketing_content",
            "target_audience",
            "language",
            "language_variants",
            "supporting_evidence",
        ]
    } | {
        "recipients": [
            {
                k: getattr(r, k)
                for k in [
                    "id",
                    "name",
                    "email",
                    "preferred_language",
                    "marketing_email_consent",
                    "consent_source",
                    "consent_timestamp",
                ]
            }
            for r in sorted(c.recipients, key=lambda r: r.id)
        ]
    }


def revise(db, c, reason):
    c.version += 1
    c.updated_at = now()
    c.status = "draft"
    for approval in db.scalars(
        select(Approval).where(
            Approval.campaign_id == c.id, Approval.decision.in_(["pending", "approved"])
        )
    ):
        approval.decision = "invalidated"
    db.add(CampaignRevision(campaign_id=c.id, version=c.version, snapshot=snapshot(c)))
    record(db, c.id, reason, {"version": c.version, "snapshot": snapshot(c)})


def require(db, model, id):
    obj = db.get(model, id)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


def latest(db, c):
    return db.scalars(
        select(Audit).where(Audit.campaign_id == c.id).order_by(Audit.id.desc())
    ).first()


def gate(db, c, a):
    if (
        a.campaign_id != c.id
        or a.status != "completed"
        or a.campaign_version != c.version
        or a.snapshot != snapshot(c)
    ):
        raise HTTPException(
            409, "A completed audit of the current campaign version is required."
        )
    if latest(db, c).id != a.id:
        raise HTTPException(409, "Only the latest audit can be approved.")
    blocks = [f.title for f in a.findings if f.blocking]
    if blocks:
        raise HTTPException(
            409,
            {
                "message": "Unresolved policy violations block approval.",
                "blocking_issues": blocks,
            },
        )


def serialize(obj):
    return {col.name: getattr(obj, col.name) for col in obj.__table__.columns}


def campaign_json(db, c):
    a = latest(db, c)
    return serialize(c) | {
        "recipient_count": len(c.recipients),
        "eligible_count": sum(
            r.marketing_email_consent is True and c.channel == "email"
            for r in c.recipients
        ),
        "recipients": [serialize(r) for r in sorted(c.recipients, key=lambda r: r.id)],
        "latest_audit": audit_json(db, a) if a else None,
    }


def audit_json(db, a):
    if not a:
        return None
    proposal = db.scalars(
        select(RemediationProposal).where(RemediationProposal.audit_id == a.id)
    ).first()
    return serialize(a) | {
        "findings": [serialize(f) for f in a.findings],
        "remediation": serialize(proposal) if proposal else None,
    }
