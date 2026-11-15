from uuid import uuid4
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .db import Base, now


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"
    campaign_id = Column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    contact_id = Column(
        Integer, ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True
    )


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    name = Column(String(160))
    email = Column(String(250), unique=True)
    preferred_language = Column(String(10))
    marketing_email_consent = Column(Boolean, nullable=True)
    consent_source = Column(String(160))
    consent_timestamp = Column(String(40), nullable=True)
    external_id = Column(String(30), nullable=True, unique=True)


class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True)
    name = Column(String(160))
    description = Column(Text)
    channel = Column(String(20))
    subject = Column(String(250))
    marketing_content = Column(Text)
    target_audience = Column(String(500))
    language = Column(String(10))
    status = Column(String(40), default="draft")
    language_variants = Column(JSON, default=dict)
    supporting_evidence = Column(JSON, default=list)
    version = Column(Integer, default=1)
    original_snapshot = Column(JSON)
    external_id = Column(String(30), nullable=True, unique=True)
    created_at = Column(String(40), default=now)
    updated_at = Column(String(40), default=now)
    recipients = relationship(Contact, secondary="campaign_recipients")
    audits = relationship(
        "Audit", back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignRevision(Base):
    __tablename__ = "campaign_revisions"
    __table_args__ = (UniqueConstraint("campaign_id", "version"),)
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"))
    version = Column(Integer)
    snapshot = Column(JSON)
    created_at = Column(String(40), default=now)


class Audit(Base):
    __tablename__ = "audits"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"))
    execution_token = Column(String(40), default=lambda: str(uuid4()), unique=True)
    status = Column(String(20), default="waiting")
    risk_score = Column(Integer, default=0)
    campaign_version = Column(Integer)
    snapshot = Column(JSON)
    agent_states = Column(JSON, default=dict)
    error = Column(String(500), nullable=True)
    created_at = Column(String(40), default=now)
    completed_at = Column(String(40))
    campaign = relationship(Campaign, back_populates="audits")
    findings = relationship("AuditFinding", cascade="all, delete-orphan")


class AuditFinding(Base):
    __tablename__ = "audit_findings"
    id = Column(Integer, primary_key=True)
    audit_id = Column(Integer, ForeignKey("audits.id", ondelete="CASCADE"))
    agent_type = Column(String(60))
    severity = Column(String(20))
    rule_id = Column(String(60))
    title = Column(String(250))
    explanation = Column(Text)
    evidence = Column(JSON)
    affected_count = Column(Integer)
    recommendation = Column(Text)
    risk_contribution = Column(Integer)
    blocking = Column(Boolean, default=False)


class RemediationProposal(Base):
    __tablename__ = "remediation_proposals"
    id = Column(Integer, primary_key=True)
    audit_id = Column(Integer, ForeignKey("audits.id", ondelete="CASCADE"), unique=True)
    original_content = Column(Text)
    proposed_content = Column(Text)
    excluded_recipients = Column(JSON)
    proposed_language_variants = Column(JSON)
    corrections = Column(JSON)
    status = Column(String(20), default="proposed")
    applied_version = Column(Integer, nullable=True)


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"))
    audit_id = Column(Integer, ForeignKey("audits.id", ondelete="CASCADE"))
    campaign_version = Column(Integer)
    decision = Column(String(20), default="pending")
    reviewer = Column(String(120))
    comments = Column(Text)
    timestamp = Column(String(40), default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True
    )
    audit_id = Column(
        Integer, ForeignKey("audits.id", ondelete="CASCADE"), nullable=True
    )
    event_type = Column(String(80))
    details = Column(JSON)
    timestamp = Column(String(40), default=now)
