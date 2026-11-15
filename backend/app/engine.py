"""Transparent deterministic agents. No generated findings or fabricated LLM output."""

import re
from html.parser import HTMLParser

AGENTS = [
    "Consent Guardian",
    "Claim Verifier",
    "Inclusion Auditor",
    "Remediation Coordinator",
    "Governance Gate",
]
WEIGHTS = {"critical": 35, "high": 25, "medium": 10, "low": 5, "info": 0}
CLAIMS = [
    r"100\s*%\s*guaranteed\s+employment(?:\s+after\s+graduation)?",
    r"guaranteed\s+(?:success|employment|results)",
    r"zero[ -]risk",
    r"100\s*%\s*(?:de réussite|garanti\w*)",
    r"emploi\s+garanti",
]


def finding(
    agent,
    severity,
    rule,
    title,
    explanation,
    evidence,
    count,
    recommendation,
    blocking=False,
):
    return dict(
        agent_type=agent,
        severity=severity,
        rule_id=rule,
        title=title,
        explanation=explanation,
        evidence=evidence,
        affected_count=count,
        recommendation=recommendation,
        risk_contribution=WEIGHTS[severity],
        blocking=blocking,
    )


def consent(snapshot):
    results = []
    recipients = snapshot["recipients"]
    if snapshot["channel"] != "email" and recipients:
        return [
            finding(
                AGENTS[0],
                "critical",
                "CONSENT_CHANNEL",
                "Channel permission unavailable",
                "Only email permission is recorded. It cannot authorize another channel.",
                {"recipient_ids": [r["id"] for r in recipients]},
                len(recipients),
                "Exclude these recipients or record verifiable channel-specific permission.",
                True,
            )
        ]
    for value, rule, title in [
        (False, "CONSENT_OPTOUT", "Opted-out contacts in audience"),
        (None, "CONSENT_MISSING", "Missing consent in audience"),
    ]:
        ids = [r["id"] for r in recipients if r["marketing_email_consent"] is value]
        if ids:
            results.append(
                finding(
                    AGENTS[0],
                    "critical",
                    rule,
                    title,
                    "Explicit email permission is required. Unknown permission is never treated as approval.",
                    {"recipient_ids": ids, "consent": value},
                    len(ids),
                    "Exclude ineligible contacts from this draft.",
                    True,
                )
            )
    return results


def claim_matches(content):
    return [
        m.group(0)
        for m in re.finditer(
            "|".join(f"(?:{pattern})" for pattern in CLAIMS), content, re.I
        )
    ]


def claims(snapshot):
    results = []
    copies = {
        "primary": snapshot["subject"] + "\n" + snapshot["marketing_content"],
        **snapshot.get("language_variants", {}),
    }
    for locale, content in copies.items():
        for index, claim in enumerate(claim_matches(content)):
            evidence = next(
                (
                    e
                    for e in snapshot.get("supporting_evidence", [])
                    if e["claim"].casefold() == claim.casefold()
                ),
                None,
            )
            verified = bool(evidence and evidence.get("verified"))
            severity = "info" if verified else ("medium" if evidence else "high")
            results.append(
                finding(
                    AGENTS[1],
                    severity,
                    f"CLAIM_{locale}_{index}",
                    (
                        "Supplied evidence supports claim"
                        if verified
                        else (
                            "Claim requires manual verification"
                            if evidence
                            else "Unsupported marketing guarantee"
                        )
                    ),
                    (
                        "Evidence is supplied and marked verified by a local reviewer; FAIRGATE has not independently verified the source."
                        if verified
                        else (
                            "A reference is supplied but requires human verification."
                            if evidence
                            else "A high-risk absolute guarantee was detected. No supporting evidence is supplied. This does not establish that the claim is false."
                        )
                    ),
                    {
                        "quote": claim,
                        "locale": locale,
                        "reference": evidence.get("reference") if evidence else None,
                    },
                    1,
                    "Verify the supplied evidence or replace the guarantee with factual, qualified wording.",
                    not verified,
                )
            )
    if re.search(
        r"best[- ]in[- ]class|industry.leading|double your", copies["primary"], re.I
    ):
        results.append(
            finding(
                AGENTS[1],
                "medium",
                "CLAIM_REVIEW",
                "Performance statement needs review",
                "This qualitative or performance claim requires a human evidence review.",
                {"quote": copies["primary"][:500]},
                1,
                "Supply evidence or qualify the statement.",
            )
        )
    return results


class AccessibilityParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.missing = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img" and "alt" not in dict(attrs):
            self.missing += 1


def inclusion(snapshot):
    results = []
    covered = {snapshot["language"], *snapshot.get("language_variants", {}).keys()}
    for language in sorted(
        {r["preferred_language"] for r in snapshot["recipients"]} - covered
    ):
        ids = [
            r["id"]
            for r in snapshot["recipients"]
            if r["preferred_language"] == language
        ]
        results.append(
            finding(
                AGENTS[2],
                "medium",
                f"LANG_{language}",
                f"{language.upper()} language variant missing",
                "Recorded language preferences differ from the available campaign copy. No demographic assumptions are made.",
                {
                    "recipient_ids": ids,
                    "preferred_language": language,
                    "available_languages": sorted(covered),
                },
                len(ids),
                "Prepare a language variant and have a fluent reviewer validate it.",
            )
        )
    for locale, content in {
        "primary": snapshot["marketing_content"],
        **snapshot.get("language_variants", {}),
    }.items():
        parser = AccessibilityParser()
        parser.feed(content)
        if parser.missing:
            results.append(
                finding(
                    AGENTS[2],
                    "medium",
                    f"ALT_{locale}",
                    "Images need alternative text",
                    "One or more image elements do not declare an alt attribute.",
                    {"images_without_alt": parser.missing, "locale": locale},
                    parser.missing,
                    "Add accurate image descriptions or remove decorative image elements.",
                )
            )
        sentences = [
            s
            for s in re.split(r"[.!?\n]+", re.sub("<[^>]+>", " ", content))
            if s.strip()
        ]
        longest = max((len(s.split()) for s in sentences), default=0)
        if longest > 35:
            results.append(
                finding(
                    AGENTS[2],
                    "low",
                    f"READABILITY_{locale}",
                    "Long sentences reduce readability",
                    "A sentence exceeds the prototype heuristic of 35 words; this is not a validated reading-level assessment.",
                    {"longest_sentence_words": longest, "locale": locale},
                    1,
                    "Split long sentences and use plain language.",
                )
            )
    return results


def score(findings):
    return min(100, sum(f["risk_contribution"] for f in findings))


def safe_copy(text):
    for pattern in CLAIMS:
        text = re.sub(
            pattern, "Career-focused learning and practical skills", text, flags=re.I
        )
    # Sentence boundaries only: no invented image descriptions or meaning-changing truncation.
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    return "\n".join(s.strip() for s in sentences if s.strip())


def remediation(snapshot, findings):
    excluded = sorted(
        {
            i
            for f in findings
            if f["agent_type"] == AGENTS[0]
            for i in f["evidence"].get("recipient_ids", [])
        }
    )
    has_claim = any(
        f["agent_type"] == AGENTS[1] and f["severity"] != "info" for f in findings
    )
    has_alt = any(f["rule_id"].startswith("ALT_") for f in findings)
    missing = [
        f["evidence"]["preferred_language"]
        for f in findings
        if f["rule_id"].startswith("LANG_")
    ]
    templates = {
        "ar": "اكتشف فرص التعلم وتطوير المهارات العملية. اطّلع على تفاصيل البرنامج ومتطلبات التسجيل. النتائج المهنية تختلف حسب الظروف الفردية.",
        "fr": "Découvrez des formations et développez vos compétences pratiques. Consultez le programme et les modalités d’inscription. Les résultats professionnels varient selon les parcours individuels.",
        "en": "Explore learning opportunities and build practical skills. Review the program and registration details. Individual career outcomes vary.",
    }
    variants = {
        lang: templates.get(lang, f"[Human translation required: {lang}]")
        for lang in missing
    }
    # Existing language variants are inspected and any guarantees receive traceable edits.
    variants.update(
        {
            lang: safe_copy(copy)
            for lang, copy in snapshot.get("language_variants", {}).items()
        }
    )
    corrections = []
    if excluded:
        corrections.append(
            {
                "id": "audience",
                "title": f"Exclude {len(excluded)} ineligible recipients",
                "selected": True,
                "description": "Permissions remain intact; only campaign membership changes.",
            }
        )
    if has_claim:
        corrections.append(
            {
                "id": "copy",
                "title": "Replace unsupported guarantees",
                "original_subject": snapshot["subject"],
                "proposed_subject": safe_copy(snapshot["subject"]),
                "selected": True,
                "description": "Transparent phrase substitution in the subject and primary copy; inspect the proposed text.",
            }
        )
    if missing or variants != snapshot.get("language_variants", {}):
        corrections.append(
            {
                "id": "languages",
                "title": "Prepare language variants",
                "selected": True,
                "description": "Deterministic editorial templates; fluent human review is required before approval.",
            }
        )
    if has_alt:
        corrections.append(
            {
                "id": "accessibility",
                "title": "Remove campaign images",
                "selected": True,
                "description": "Images are removed from the draft rather than given invented alternative text.",
            }
        )
    return dict(
        original_content=snapshot["marketing_content"],
        proposed_content=(
            re.sub(
                r"<img\b[^>]*>",
                "",
                safe_copy(snapshot["marketing_content"]),
                flags=re.I,
            )
            if has_alt
            else safe_copy(snapshot["marketing_content"])
        ),
        excluded_recipients=excluded,
        proposed_language_variants=variants,
        corrections=corrections,
    )
