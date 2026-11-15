from sqlalchemy import select, delete
from .models import *
from .services import snapshot, record
from .db import now

MAIN_COPY = "Join Digital Future Morocco 2027!\n100% guaranteed employment after graduation.\nRegister today and transform your future."


def seed(db, reset=False):
    if reset:
        for cls in [
            AuditEvent,
            Approval,
            RemediationProposal,
            AuditFinding,
            CampaignRevision,
            Audit,
            CampaignRecipient,
            Campaign,
            Contact,
        ]:
            db.execute(delete(cls))
        db.commit()
    if db.scalar(select(Campaign.id).limit(1)):
        return
    for i in range(1, 101):
        permission = False if i <= 20 else (None if i <= 30 else True)
        db.add(
            Contact(
                id=i,
                name=f"Synthetic Contact {i:03}",
                email=f"contact{i:03}@example.invalid",
                preferred_language="ar" if i % 10 < 3 else "fr",
                marketing_email_consent=permission,
                consent_source=(
                    "Synthetic preference center"
                    if permission is not None
                    else "No record"
                ),
                consent_timestamp=now() if permission is not None else None,
            )
        )
    db.flush()
    contacts = list(db.scalars(select(Contact)))
    campaigns = [
        dict(
            name="Digital Future Morocco 2027",
            description="Synthetic campaign · Digital Future Academy (fictional). No evidence supports the employment guarantee.",
            subject="Votre avenir commence ici",
            marketing_content=MAIN_COPY,
            language="fr",
            recipients=contacts,
            status="draft",
        ),
        dict(
            name="Skills for Tomorrow",
            description="Synthetic campaign · fictional learning newsletter.",
            subject="Votre prochain chapitre",
            marketing_content="Découvrez nos ateliers pratiques. Consultez le programme et les conditions d’inscription.",
            language="fr",
            recipients=[
                c
                for c in contacts
                if c.marketing_email_consent and c.preferred_language == "fr"
            ],
            status="draft",
        ),
        dict(
            name="Career Accelerator Launch",
            description="Synthetic campaign · intentionally unresolved policy risks.",
            subject="Guaranteed success",
            marketing_content="Guaranteed employment. Zero risk. Apply today.",
            language="en",
            recipients=contacts[:45],
            status="draft",
        ),
        dict(
            name="An Accessible Future",
            description="Synthetic campaign · accessibility review required.",
            subject="Des opportunités pour tous",
            marketing_content='<img src="workshop.jpg"> Découvrez notre atelier de compétences et consultez les modalités d’inscription.',
            language="fr",
            recipients=[
                c
                for c in contacts
                if c.marketing_email_consent and c.preferred_language == "fr"
            ][:25],
            status="draft",
        ),
    ]
    for data in campaigns:
        c = Campaign(
            **data,
            channel="email",
            target_audience="Synthetic learning community",
            language_variants={},
            supporting_evidence=[],
        )
        db.add(c)
        db.flush()
        c.original_snapshot = snapshot(c)
        db.add(CampaignRevision(campaign_id=c.id, version=1, snapshot=snapshot(c)))
        record(db, c.id, "campaign_created", {"synthetic": True, "version": 1})
    db.commit()


if __name__ == "__main__":
    import sys
    from .db import Base, engine, Session

    Base.metadata.create_all(engine)
    with Session() as db:
        seed(db, reset="--reset" in sys.argv)
    print("Synthetic demo data ready.")
