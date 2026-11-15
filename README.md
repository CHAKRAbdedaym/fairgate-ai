# FAIRGATE AI — When AI Audits AI

Working local prototype for IT-Minds · Deloitte Salesforce Hackathon PFE 2027.

Independent campaign preflight: **campaign → audit → findings → selected corrections → re-audit → human approval → approved for activation**. There is no message sending or campaign activation API. All seeded organizations, contacts, permissions and campaigns are fictional.

## Run locally

Requires Python 3.11+ and Node 20+ (verified with Python 3.13 and Node 20.18).
Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm install --prefix frontend
cp .env.example .env
.venv/bin/python scripts/dev.py
```

Open **http://localhost:3001/demo**. The launcher selects the next available ports if 3001 or 8000 is occupied and prints the URLs. Both processes stop on Ctrl-C. Keep the app bound to loopback: local reviewer identities are simulated and the local demo API is intentionally unauthenticated.

To start separately in two terminals:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm run dev --prefix frontend
```

Frontend: http://localhost:3001 · Backend: http://127.0.0.1:8000 · OpenAPI: http://127.0.0.1:8000/docs.

## Data and verification

SQLite is persisted in `backend/fairgate.db`, created safely on startup with SQLAlchemy. This initial prototype uses schema initialization, not an upgrade migration system. When changing the schema during development, back up and remove the old demo database before starting. Never do this to an organization's database.

```bash
# Seed only if empty (idempotent)
.venv/bin/python -m backend.app.seed
# Restore the synthetic demonstration (also available through Reset Demo UI)
curl -X POST http://127.0.0.1:8000/api/demo/reset
# Offline reset while server is stopped
.venv/bin/python -m backend.app.seed --reset
# Backend tests use a separate temporary SQLite database
.venv/bin/python -m pytest backend/tests -q
# TypeScript validation and production build
npm run build --prefix frontend
```

For browser verification (optional dev dependency):

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
# If Google Chrome is not installed, install the optional test browser:
# .venv/bin/playwright install chromium
# Start both services first. Uses installed Google Chrome, or Playwright Chromium.
.venv/bin/python scripts/browser_smoke.py
```

The dashboard, campaign forms, audience selection, audit agents, findings, remediation checkboxes, version restore, re-audit comparison, governance, history, integrations, and `/demo` all use the API and persistent database. Startup and demo reset evaluate the three secondary campaigns with the actual agents; the main campaign stays unaudited and ready for the full journey.

## Demonstration data

The main campaign, **Digital Future Morocco 2027**, has 100 synthetic contacts: 20 opted out, 10 without consent, 70 eligible. Exactly 30 prefer Arabic and 70 French; language and consent categories overlap. Its original copy contains an unsupported employment guarantee. A baseline audit produces four findings and risk 100. Applying the three recommended corrections creates v2 with 70 eligible recipients, safer wording and an Arabic variant; re-audit produces risk 0. A human must inspect the language variant before approving. The initial source snapshot and every revision remain in the database. Reset restores the original scenario.

## Technical boundaries

- React + TypeScript + Vite + Tailwind CSS + Lucide + Recharts; FastAPI + Pydantic + SQLAlchemy + SQLite.
- Five explicit modular orchestration stages. Execution states and events are persisted; browser polling reads real progress. Fast agents may finish between polls. No artificial delays or fake agent traces.
- Deterministic policy checks and editorial templates are used; no LLM or paid service is required. Optional LLM augmentation is not implemented. The UI reports this honestly.
- Risk is an internal prototype indicator, not legal advice or a certified compliance score. Supported claims mean **user-supplied, reviewer-attested evidence**, not independent factual verification.
- Current version and audited snapshot must match to request or decide approval. Known consent violations and unsupported/unverified guarantees block regardless of score. Mutations invalidate pending or approved decisions. New audit requests also invalidate prior decisions.
- SQLite transactions, optimistic version checks, a single-process mutation lock and execution tokens guard stale requests/reset races. Run **one backend worker**. For production, replace the local lock with database locking, add authenticated authorization and managed migrations.
- Text is rendered as React text, never executable campaign HTML. CRM errors are sanitized, HTTP calls have timeouts, origins are restricted, no secrets are sent to the browser. This is a local prototype, not hardened public hosting.

[Architecture & policy](docs/architecture.md) · [Salesforce adapter](docs/salesforce.md) · [Proposed Agentforce contract](docs/agentforce.md).
