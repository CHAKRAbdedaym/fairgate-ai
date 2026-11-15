# Executed verification

Verified locally on 2026-11-15 with Python 3.13, Node 20.18, SQLite, and headless Google Chrome.

- `python -m pytest backend/tests -q`: **42 passed**, one upstream Starlette/AnyIO deprecation warning. Separate temporary SQLite database; includes dynamic consent, supported/unsupported/unverified claims, inclusion, scoring, selected corrections, exclusion, re-audit, approval/rejection, stale version invalidation, revision restoration, persistence, reset, input errors, no-key fallback, connected-mode restrictions, reset execution tokens, and mocked Salesforce HTTP transport failure handling.
- `npm run build --prefix frontend`: **passed**, TypeScript and Vite production assets generated; chart dependencies split into a separate chunk.
- `python scripts/browser_smoke.py`: **passed** using actual Chrome and both running services. Verified all eight navigation destinations, honest integration state, the full main campaign journey, persisted checkbox selections, audience 100 → 70, risk 100 → 0, human approval and reload persistence, audit trail, campaign creation/search/edit, and reset. No JavaScript page errors. Screenshots captured at 1920×1080 and a 390px mobile viewport; no horizontal page overflow on the mobile dashboard.
- API health and generated OpenAPI both returned **HTTP 200**.
- Demo reset leaves the main campaign in its original unaudited v1 state, with secondary campaigns evaluated by the actual engine.

Browser artifacts are generated in ignored `artifacts/`. The browser test resets local demonstration data by design. Salesforce transport tests use explicit unit-test mock responses; these are not live org verification. No Salesforce or Agentforce connection was available, no LLM was used, and no marketing communications were sent.
