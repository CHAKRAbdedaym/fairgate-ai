# Architecture and policy

A single FastAPI process serves the API; Vite proxies `/api` during development. SQLAlchemy maps persistent Campaign, Contact, CampaignRecipient, CampaignRevision, Audit, AuditFinding, RemediationProposal, Approval and AuditEvent records. SQLite foreign keys and WAL are enabled. An original campaign snapshot is retained; every content/audience edit creates a revision and invalidates pending/approved decisions.

## Pipeline

A request stores an audit as `waiting` with an immutable version and full recipient snapshot, returns HTTP 202, and schedules a FastAPI background task. The task records `running`, evaluates Consent Guardian, Claim Verifier, Inclusion Auditor, Remediation Coordinator and Governance Gate, stores findings/risk/events, and completes the audit. Failures persist a safe error; interrupted tasks become failed at restart. Execution tokens prevent a queued pre-reset task from running against a reused audit ID. Polling reads actual states; subsecond runs may only be seen as completed. No manufactured activity or delay.

Consent uses stored recipient records and explicit booleans: false → critical opt-out, null → critical missing permission. Email permission never authorizes SMS; unsupported channels produce a critical channel finding. Language preferences are independent of consent. Claim regexes detect absolute guarantees dynamically across subject, primary copy and language variants. Overlapping regex matches are consolidated. An exact supplied evidence claim with `verified: true` yields an informational finding, explicitly user-attested. A reference without verification produces a blocking manual-review finding. Absent evidence produces a high blocking unsupported-claim finding; FAIRGATE does not assert falsehood. This baseline is limited to documented patterns and is not a semantic truth engine.

Inclusion compares recorded language preferences to actual available variants; detects missing image alt attributes using HTMLParser; flags sentences over 35 words using an explicitly labeled readability heuristic. It makes no demographic inference. Campaign HTML is only rendered as text.

## Risk formula

Each finding stores a raw contribution: critical **35**, high **25**, medium **10**, low **5**, info **0**. Risk = **min(100, sum(raw finding contributions))**. The cap means displayed raw contributions can sum above 100. No normalized or certified compliance claim is made. The main initial campaign yields 35 + 35 + 25 + 10 = 105, capped at 100. Corrected main v2 yields 0. Before/after comparisons use stored completed audits, with resolved rules matched by rule ID.

Approval follows explicit policies independently of score: a completed latest audit of the exact current snapshot/version; no blocking consent or claim findings; an explicit local human decision; human confirmation for any language variants. Other inclusion/readability findings remain inspectable and may be reviewed by humans. No messages are sent, including after approval. There is no activation or delivery adapter.

## Remediation

Proposals are derived from actual findings. Individual corrections can be accepted/rejected, with selections persisted and evented. Explicit apply changes campaign membership, phrase substitutions, language templates, and/or image removal, then stores a new draft revision. No contact's consent is altered. The original snapshot, audit snapshots and previous revisions remain intact. Restoring a revision creates another version and invalidates approval. Deterministic translation/editorial templates are clearly labeled as requiring human review. Complex content, long sentences and unsupported languages can require manual edits; the engine does not invent image descriptions or source evidence.

Mutation operations are serialized by an in-process lock, optimistic campaign version checks and transactional writes. This prototype supports one process, not distributed concurrency. Current state is revalidated before approval, which also detects changed recipient records. Repeating a proposal generation, apply, pending approval request or identical final decision is safe. UI/API errors are visible. JSON input is length-constrained and unknown fields rejected.
