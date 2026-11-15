# Proposed Agentforce custom action contract

**Proposed — not operational.** No Agentforce org, action registration, Named Credential or authenticated public gateway was available. The local demo does not pretend to execute Agentforce.

An org administrator can wrap the FAIRGATE OpenAPI endpoints with an Apex invocable custom action and Named Credential to an authenticated FAIRGATE gateway. The gateway must authorize org, campaign and reviewer scopes and operate an isolated connected database. Do not expose the unauthenticated loopback demo API publicly.

Suggested action `AuditMarketingCampaign`:

- Input: `campaignId` (internal integer from an authorized CRM mapping), `requestedBy` (authenticated principal, never supplied as an authoritative plain-text reviewer).
- Invoke `POST /api/campaigns/{campaignId}/audits`.
- HTTP 202 result: `id`, `campaign_id`, `campaign_version`, `status=waiting`, `agent_states`.
- Poll `GET /api/audits/{id}`; output completed status, risk score, explainable findings, blocking issues and version.
- Recommend remediation via `POST /api/audits/{id}/remediation`; never apply corrections or approve silently.
- Human review through a separate authenticated UI. An agent cannot grant the human approval action. No send or activation endpoint exists.
- Expected errors: 404 unauthorized/not-found at gateway, 409 stale/invalid transition, 422 validation, 503 persistence unavailable. Connected mode returns 403 on unconfigured local reviewer/audit mutation routes until an authenticated integration is implemented.

Use the deployed OpenAPI as the source of truth, minimize contact fields in action outputs, redact secrets, set HTTP timeouts, and audit the invoking principal. Standard CRM Campaign imports do not imply Marketing Cloud Journey support.
