# Salesforce integration boundary

**Local demo is fully operational. Salesforce is not connected without credentials.** No Salesforce org was available during development; actual org calls and object writes are unverified. The connector uses genuine HTTP requests, not simulated Salesforce responses.

`LocalCRMAdapter` and `SalesforceAdapter` form an explicit source boundary. Local campaigns already live in the internal schema; authorized Salesforce records can be conservatively mapped into the same schema through the import endpoint. Synthetic data and actual CRM records must use separate databases. To prepare an isolated connector process, configure `APP_MODE=connected` and a different `DATABASE_URL`. This disables demo seeding, reset, and local unauthenticated campaign/audit/reviewer mutations. Add authenticated permission-aware routes before operating connected governance. No public reset or write endpoint can affect a real org.

## OAuth and reads

Configure an External Client App (or an existing supported Connected App) with client credentials flow, API scope, a dedicated execution user and least-privilege object/field access. Set server-side `SALESFORCE_INSTANCE_URL`, `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`, and supported `SALESFORCE_API_VERSION`. Credentials travel in the token request body; the resulting token is retained only in adapter memory. Never put it in browser variables or source control.

- `POST /api/integrations/salesforce/test`: requests a token, reads `/limits`, and returns verified status only if those calls succeed. Status is request-specific; configuration alone never means connected.
- `GET /api/integrations/salesforce/campaigns`: actual permission-constrained REST query of Campaign.
- `POST /api/integrations/salesforce/import/{external_id}`: connected-mode-only explicit import of one authorized campaign and its Contact CampaignMembers. No automatic overwrite. Pagination and timeouts are handled; rate-limit errors report retry-later without automatic write retries.

Standard Campaign provides Name/Description/Type/Status, not the marketing copy or a Marketing Cloud Journey. Imported copy is empty pending an authenticated editorial workflow. HasOptedOutOfEmail=true maps to false; false maps to **unknown**, because absence of opt-out is not affirmative consent. Language is unknown pending an explicit configured source. No Salesforce email address or consent is seeded or invented. Leads are excluded from this prototype mapping.

## Optional audit storage mapping

Provision custom objects (none are automatically created):

| Object | Fields |
|---|---|
| Fairgate_Audit__c | External_Key__c (unique external ID), Campaign__c (Campaign lookup), Risk_Score__c (number), Version__c (number), Status__c (text) |
| Fairgate_Finding__c | External_Key__c (unique external ID), Audit__c (Fairgate_Audit lookup), Rule__c, Severity__c, Explanation__c |
| Fairgate_Approval__c | External_Key__c (unique external ID), Audit__c (Fairgate_Audit lookup), Decision__c, Reviewer__c |

`SalesforceAdapter.store_approved(campaign, audit, approval)` implements actual composite REST upserts with stable external identifiers and allOrNone rollback, only when `SALESFORCE_WRITE_ENABLED=true` and the referenced version is approved. External-ID relationship references connect child records. It is a trusted server-side extension boundary, **not an operational UI write feature**. The public export endpoint deliberately returns 403 until authenticated governance is integrated. Composite export is capped at 25 subrequests. An org must supply required Name field configuration/defaults and appropriate permissions. No Marketing Cloud send, Journey activation, or messaging API is implemented.

Sources: [Salesforce OAuth REST guidance](https://developer.salesforce.com/docs/platform/api-rest/guide/intro-oauth-and-connected-apps.html), [Integration user and client credentials](https://developer.salesforce.com/blogs/2024/02/invoke-rest-apis-with-the-salesforce-integration-user-and-oauth-client-credentials).
