> Verified research notes, generated 2026-10-10 from the public docs snapshot in `docs/reference/` (the live spec is `docs/reference/freya_openapi_live.json`). Each claim was checked by a separate fact-checking pass against the sources. Tags: **[Confirmed]** = stated in the docs or spec; **[Inferred]** = our reasoning; **[Not documented]** = not in any source. Curated summary: `docs/freya_api_notes.md`.

## Platform basics, authentication and API conventions

Sources: the local doc snapshot from 2026-10-10. "Live spec" means `freya_openapi_live.json` (https://app.freyavoice.ai/api/openapi.json). "Stale spec" means `openapi.json` (https://docs.freyavoice.ai/api-reference/openapi.json).

### 1. Hosts and base URLs

| Host / URL | Purpose | Status |
|---|---|---|
| `https://app.freyavoice.ai/api/v2` | Platform REST API. It is the only `servers` entry in the live spec, labeled "Production" | **[Confirmed]** |
| `https://staging-app.freyavoice.ai/api/openapi.json` | 152 of the 156 API-reference doc pages (every endpoint page) embed this spec. Introduction, Authentication, STT and TTS do not. The spec's own `servers` still lists only app.freyavoice.ai | **[Confirmed]** |
| `https://staging-app.freyavoice.ai/api/v2` as an API base | Nothing documents it as a usable server | **[Not documented]** |
| `https://stt.freyavoice.ai` | `POST /v1/audio/transcriptions`. Streaming over `wss://stt.freyavoice.ai/v1/audio/stream` is in beta | **[Confirmed]** |
| `https://tts.freyavoice.ai` | `POST /v1/audio/speech` | **[Confirmed]** |
| `https://app.freyavoice.ai/freya-client.js` and `{FREYA_BASE_URL}/api/token/embed`, `/api/token/webrtc/ice-servers` | Embed SDK and embed-token minting. These endpoints are outside `/api/v2` and appear in **no** OpenAPI spec **[Confirmed]**. The value to use for `FREYA_BASE_URL` is **[Not documented]** | **[Confirmed]** |
| `https://agents-eu1.freyavoice.ai/telephony/inbound/webhook` | Twilio inbound voice webhook | **[Confirmed]** |
| `https://agent.freyavoice.ai` | Appears only as an example `baseUrl` in the `POST /inbound/web` request example | **[Confirmed]** |
| `https://docs.freyavoice.ai` | Docs site. Its `llms.txt` lists the **stale** spec as "openapi" | **[Confirmed]** |

- The main API also has `POST /audio/transcriptions` and `POST /audio/speech`, both marked "(Closed Beta)". **[Confirmed]**
- The Model APIs (STT/TTS) have their own spec (`model-apis-openapi.json`, v1.0.0) and are "independent of the Freyavoice Call API". **[Confirmed]**
- Support contact in `info.contact`: `support@freyavoice.com`. Note the `.com` domain. The intro page says to send inquiries "on slack". **[Confirmed]**

### 2. Authentication

- **Scheme:** every request sends `Authorization: Bearer <your-api-key>` (https://docs.freyavoice.ai/api-reference/authentication). **[Confirmed]**
- **Spec definition:** `components.securitySchemes.bearerAuth = {type: http, scheme: bearer}`, with no `bearerFormat` and no top-level `security`. 178 of 180 live operations declare `security: [{bearerAuth: []}]`. The other 2 are `POST /webhooks/campaign-call-outcome` and `POST /webhooks/end-of-call-report`, which describe payloads Freya **sends to you**. **[Confirmed]**
- **Scope of a token:** a token is tied to one workspace ("This token is tied to your workspace"), and each workspace has its own API keys. **[Confirmed]**
- **Getting a key from the dashboard:** sidebar, **Settings > API Keys > Create API Key**. Copy the token straight away: "it won't be shown again". **[Confirmed]**
- **Getting a key from the API:** `POST /api-keys` returns the key value only in that response. **[Confirmed]** `POST /api-keys` itself needs a bearer token, so the first key has to come from the dashboard. **[Inferred]**
- **STT WebSocket:** pass the key as the `token` query parameter. Non-browser clients can send the `Authorization: Bearer` header during the handshake instead. **[Confirmed]**
- **Other token types exist:**
  - `GET /api-keys/check` says "Only API key authentication is accepted".
  - The architecture guide says "JWT Tokens: API requests are authenticated using JWT tokens".
  - Embed tokens are a "Short-lived embed JWT".
  - MCP OAuth grants are listed by `GET /oauth-connections`.

  All of the above is **[Confirmed]**. Whether API keys are themselves JWTs is **[Not documented]**.
- **Error codes:** 401 "Missing or invalid token" appears on 178 operations. 403 "Workspace ID mismatch or insufficient permissions" appears on 175. **[Confirmed]** What an expired or `isActive:false` key returns is **[Not documented]**.

### 3. API keys (`API Keys` tag, live spec)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/api-keys` | List keys | `workspaceId` query is required. Each item has `id, key, workspaceId, userId, name, isActive, createdAt, lastUsedAt, creditsUsed, expiresAt, rateLimit, permissions, creator` **[Confirmed]**. Whether `key` is masked is **[Not documented]** |
| POST | `/api-keys` | Create key | Required: `name`, `userId`. Optional: `expiresAt`, `rateLimit`, `permissions`. There is **no `workspaceId`** in the live body **[Confirmed]** |
| PUT | `/api-keys` | Batch update | Body is `apiKeys[] {id (required), name, isActive, rateLimit}`. Returns `updated[]` and `errors[{id, error, details[{field, message}]}]` **[Confirmed]** |
| DELETE | `/api-keys` | Batch delete | Query: `workspaceId` and `apiKeyIds` (comma-separated), both required **[Confirmed]** |
| GET | `/api-keys/check` | Validate the calling key | Returns `valid, workspaceId, name, isActive, expiresAt, rateLimit, apiKeyId, callId, agentId`. `apiKeyId`, `callId` and `agentId` are nullable **[Confirmed]**. This is a way to find the key's `workspaceId` **[Inferred]** |

- **Expiry:** default 90 days, maximum 365 days, must be in the future. It is immutable, and `PUT` ignores any `expiresAt`. **[Confirmed]**
- **Key permissions:** a "Frozen subset of the creator's permissions. Defaults to the creator's full set when omitted.". **[Confirmed]** `PUT` has no `permissions` field, so a key's scopes cannot be changed after creation. **[Inferred]**
- **The `userId` field:** which `userId` to send when you call with an API key is **[Not documented]**. `GET /workspaces` (`ownerId`, `workspaceMembers[].userId`) and `GET /api-keys` (`userId`) do expose user IDs **[Confirmed]**. That one of these is the right value to send is **[Inferred]**.

### 4. Permissions (scopes)

- `GET /permissions` returns `{permissions[], groups{}, labels{}}`. It is "Auth-only — any logged-in user can read.". **[Confirmed]**
- The live enum has **126** permission strings. **[Confirmed]** The ones that matter here:
  - **Agents:** `agents:read`, `agents:write`, `agents:delete`, `agents:sync`, `agents:test`, `agents:resolve`, plus `workflows:read|write|delete|sync|test`, `versions:read`, `versions:publish`, `models:read`.
  - **Chat:** `chat:read`, `calls:chat-message`.
  - **Simulations:** `simulations:read|write|delete|execute|verdict-callback`, `personas:read|write|delete`, `assertions:read|write|delete|assign`.
  - **Unit tests:** there is **no** `unit-tests:*` permission.
  - **Calls:** `calls:read|write|delete|import|export|recording-download|metrics-read|web-token|chat-message|cdr-read|pii|share|register|recording-upload|transfer|resume|status-read|webhook-payload`, `campaign:read|write|delete|execute|resolve-contact`, `inbound:write`, `phone-numbers:*`, `suppression-list:*`.
  - **Admin:** `api-keys:read|write|delete|manage-others`, `billing:read|manage`, `workspace:read|settings-write|mfa-policy|delete|logs-read`.
- **Which permission each endpoint needs is not documented in a systematic way.** The spec has no `x-` extensions. Only these descriptions name a permission **[Confirmed]**:
  - `GET /call` needs `calls:read`, plus `calls:export` when `export=true`.
  - `POST /call/export-raw` needs `calls:export`.
  - `POST /call/import` needs `calls:import`.
  - `calls:pii` is needed for PII values and for row-grain properties in `GET /analytics/properties`.
  - `POST /alerts/events` needs `alerts:ingest`.
  - `PATCH /workspaces/members/role` needs `members:role-change`.
  - The join link from `POST /workspaces/invitations` needs `workspace:settings-write`.
  - `POST /export` needs "the read permission of its list".
  - The embed token needs `calls:web-token` (from the embed guide).
  - Three unit-test GETs say "Requires agents:read or workflows:read".
- What `agents:test` and `workflows:test` control is **[Not documented]**. They may cover running unit tests. **[Inferred]**
- **Roles:** there are 3 system roles (Owner, Admin, Member) plus custom roles. A custom role cannot be given `workspace:delete`, and an actor can only grant permissions they hold themselves. **[Confirmed]**

### 5. Rate limits

- **No numeric platform rate limits are documented anywhere**, in either the guides or the specs. **[Not documented]**
- **Per-key rate-limit fields exist:** `rateLimit {requestsPerMinute, requestsPerDay}`, both integers above 0. You can set them on create and change them with PUT. **[Confirmed]** The default when you leave them out, and how they are enforced, are **[Not documented]**.
- **429 responses:** only 2 of the 180 live operations declare one, and neither has a body schema **[Confirmed]**:
  - `POST /export`: "Too many export requests"
  - `POST /workspaces/invitations`: "Invitation email rate limit reached for this recipient"
- **Response headers:** the live spec declares none for any response. There is no `Retry-After` and no `X-RateLimit-*`. **[Confirmed]**
- **Model API:** STT `POST /v1/audio/transcriptions` returns 429 "Rate limit exceeded." with body `{error:{message, type, code}}`. **[Confirmed]**
- **Guides:** they only give general advice, such as "Respect API rate limits and implement backoff strategies" (best-practices), "API rate limiting prevents abuse" (architecture), and "Call rate is controlled…" (outbound-calls). **[Confirmed]**

### 6. Response envelope and errors

- **Envelope:** success is `{"success": true, "data": {"message": "Success", "result": {…}}}`. Errors are `{"success": false, "data": {"message": "Error description", "result": null}}` (live `info.description`). **[Confirmed]**
- **Responses that don't use the envelope** (174 2xx JSON responses do use it) **[Confirmed]**:
  - `POST /audio/transcriptions` returns JSON `{text, usage}`, or `text/plain`.
  - Binary responses:
    - `GET /call/{callId}/recording` (audio/mpeg)
    - `GET /export/{jobId}/download` (application/zip)
    - `GET /call` (an `application/zip` 200 alternative for export)
    - `POST /audio/speech` (audio/mpeg, audio/wav, audio/ogg)
  - `DELETE /workspaces/{workspaceId}/roles/{roleId}` returns 204.
  - `GET /export/{jobId}/download` returns 202 with no body.
  - The two webhook payload docs declare a 200 with no body.
- **Error bodies:** 712 error responses declare `{success:false, data:{message (required), result:any}}`. 135 error responses have no body schema at all. Most of those are 404s and 409s, plus some 400/403/410/413/422/429/502/503/504. **[Confirmed]**
- **No standard machine-readable error `code` field.** There are only isolated mentions, such as `export_row_cap_exceeded` on the export-download 422 and `SEMANTIC_SEARCH_UNAVAILABLE` on the export-raw 503. **[Confirmed]**
- **Model API error formats differ:** STT uses `{error:{message, type, code}}`, and TTS 400 uses `{error: string}`. **[Confirmed]**
- **Status codes** **[Confirmed]**:
  - 400, 401, 403 and 500 appear on 178 operations.
  - 200 on 162, 201 on 13, 202 on 6.
  - 404 on 92, 409 on 24, 422 on 6, 503 on 5.
- **Request content types:** `application/json` on 74 operations and `multipart/form-data` on 2. **[Confirmed]**
- Idempotency keys and request-ID headers are **[Not documented]**.

### 7. Pagination, sorting and filtering

- **Pagination uses offset and limit.** There is no cursor. `limit` appears on 27 operations and `offset` on 25. **[Confirmed]**
- **Response shapes vary** **[Confirmed]**:
  - `result.pagination {total, limit, offset, hasNext, hasPrevious}`: `/call`, `/workspaces/logs`
  - `result.pagination {total, limit, offset}`: `/campaign`
  - Flat `total, limit, offset`: `/agents`, `/workflow`, `/insights`, `/versions/...`
  - `total` only: `/personas`, `/simulations`, `/unit-tests`
- **Defaults and maximums vary** **[Confirmed]**:
  - `/agents`: default 50, max 100
  - `/call`: default "20", typed as a string
  - `/campaign`: default "25", typed as a string
  - `/unit-tests/overview`: default 200, max 500
  - `/simulations/{id}/iterations`: default 100, max 200
  - `/insights`: default and max 500
  - `GET /export`: default 10, max 50
  - Version graph: default and max 1000
- **Sorting:** `sortBy` with `sortOrder` (`asc|desc`) on 18 operations. The `sortBy` values are per endpoint. For example, `/call` allows `startedAt|duration|sentiment|relativeTime|cost`, with defaults `startedAt` and `desc`. **[Confirmed]**
- **Filtering** **[Confirmed]**:
  - `filters` on 11 operations. 10 describe it as "Base64-encoded filter state", and 1 has no description. **Its format is [Not documented].**
  - `search` on 16 operations, 14 of them described as a "Global search term".
  - `startDate`/`endDate` on 5 operations; 4 of them describe ISO dates. `from`/`to` (date-time) on `/alerts/events`.
  - `include` opts in to heavy fields.
- **List exports:** 8 list operations accept `export`, `exportFormat` and `exportColumns`. **[Confirmed]**

### 8. workspaceId: passed explicitly or resolved from the token?

| Where `workspaceId` goes | Ops | Examples |
|---|---|---|
| Query (required) | 65 | `GET /agents`, `GET /agents/{agentId}`, `DELETE /agents`, `GET /simulations`, `GET /personas`, `GET /unit-tests`, `GET /call`, `GET /api-keys`, `GET /workspaces/logs` |
| Body (required) | 22 | `POST /call`, `PUT /agents/{agentId}`, `POST /unit-tests`, `POST /unit-tests/run-all`, `POST /versions/{entityType}/{entityId}`, `POST /favorites`. The count includes the `POST /webhooks/end-of-call-report` payload doc |
| Body (optional) | 1 | `PUT /workspaces` ("must match the authenticated workspace") |
| Path | 5 | `/workspaces/{workspaceId}/credits`, `/workspaces/{workspaceId}/roles[...]` |
| Not present | 87 | `POST /agents` (body `{name (required), language, config}`), `POST /simulations`, `POST /personas`, `POST /chat/message|fork|end`, `POST|PUT /api-keys`, `/api-keys/check`, all `/alerts/*`, all `/export*`, `GET /workspaces`, `GET /permissions`, plus the `POST /webhooks/campaign-call-outcome` payload doc |

The table is **[Confirmed]** (computed from the live spec).

- **Workspace taken from the token, stated explicitly** **[Confirmed]**:
  - `POST /inbound/web`: "The workspace is resolved from the bearer token — it is not accepted from the request body"
  - `POST /alerts/events`: "The workspace comes from the caller's auth scope, never the body"
- **Account-scoped endpoints:** `GET /oauth-connections` ("Account-scoped: no workspace header required") and `GET /export` ("Scoped to the account rather than the workspace"). **[Confirmed]** The spec defines zero header parameters **[Confirmed]**. What a "workspace header" is, is **[Not documented]**.
- **Operations without `workspaceId`** probably take the workspace from the token. **[Inferred]** The docs state this for only 2 operations. Some operations without `workspaceId` are documented as account-scoped instead (`GET /export`, `GET /oauth-connections`), and `GET /workspaces` returns all workspaces the authenticated user can access. **[Confirmed]**
- **The "Workspace ID mismatch" 403** means a supplied `workspaceId` must equal the token's workspace. **[Inferred]**

### 9. Workspaces, members, invitations, roles

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/workspaces` | List the caller's workspaces | Includes settings and members **[Confirmed]** |
| POST | `/workspaces` | Create a workspace | Caller becomes owner. `name` is 1–100 characters. `workspaceSettings {language (default 'en'), webhooks, dataRetentionDays ≥ 1, requireMfa}`. `integrationVersion` defaults to `'v1'` **[Confirmed]** |
| PUT | `/workspaces` | Update a workspace | **[Confirmed]** |
| DELETE | `/workspaces?workspaceId=` | Delete a workspace | Owner only (403 otherwise) **[Confirmed]** |
| GET / PATCH / DELETE | `/workspaces/members` | List members, update own display name, remove a member | **[Confirmed]** |
| PATCH | `/workspaces/members/role` | Assign a role | Needs `members:role-change` **[Confirmed]** |
| GET / POST / DELETE | `/workspaces/invitations` | List, invite, revoke | Invitations are valid for 7 days. 409 if already a member. 429 and 502 also possible **[Confirmed]** |
| GET / POST | `/workspaces/{workspaceId}/roles` | List and create roles | **[Confirmed]** |
| PATCH / DELETE | `/workspaces/{workspaceId}/roles/{roleId}` | Update and delete custom roles | System roles return 409 **[Confirmed]** |

### 10. Credits and billing through the API

- `GET /workspaces/{workspaceId}/credits` returns `creditsLeft`, `creditUsdRate`, `billingUnit` (`usd|minutes`), `minuteLimit` and `minutePeriodStart`. **[Confirmed]**
- `GET /analytics/credits?workspaceId&startDate&endDate` returns `creditsData {dailyCredits, totalTransactions, totalCreditsUsed, dailyCostByCategory}`. **[Confirmed]**
- **Other cost and credit fields** **[Confirmed]**:
  - API key objects carry a per-key `creditsUsed`.
  - Call objects carry `cost` (number or null).
  - The `billing:read` and `billing:manage` permissions exist, but there are no billing endpoints beyond the two credit endpoints above.
  - STT returns 403 "Authentication failed or insufficient credits."
- What the platform API does when credits run out is **[Not documented]**.

### 11. Audit logs

`GET /workspaces/logs` **[Confirmed]**:
- Query parameters: `workspaceId` (required), `limit`/`offset` (typed as strings), `filters`, `search`, `sortBy`, `sortOrder`, `countBy`, `ids`, and `include=changes` (which caps `limit` at 25).
- Events covered: "login, API key changes, member changes, exports, etc."
- Each item has `{id, workspaceId, eventType, eventDescription, actorId, actorEmail, metadata, hasChanges, createdAt}`, plus `pagination` and `uniqueEventTypes`.

Two related points are **[Inferred]**: `workspace:logs-read` is the permission that controls this endpoint, and the export endpoint's "Enterprise logs" label suggests logs may be an enterprise-tier feature.

### 12. Export, Favorites, Alerts, OAuth connections (live spec)

`POST /export` has a doc page that describes older behaviour. The other 4 Export operations, and all Favorites, Alerts and OAuth Connections operations, have no doc page. **[Confirmed]**

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/export` | Queue an export | 10 list endpoints. Formats `csv|xlsx|markdown|json` (default csv). Delivery `download|email`. Returns `jobId, statusUrl, downloadUrl`. Can return 429 or 503 **[Confirmed]** |
| GET | `/export`, `/export/{jobId}` | The caller's own exports, and job status | Statuses `pending|running|ready|failed|expired` **[Confirmed]** |
| GET | `/export/{jobId}/download` | Download the file | 202 while still generating, 422 if failed, 410 if expired **[Confirmed]** |
| DELETE | `/export/{jobId}` | Delete your own export | **[Confirmed]** |
| GET / POST / DELETE / PUT | `/favorites` | Workspace-shared pinned agents and workflows | `entityType` is `agent|workflow`. `orderedIds` holds at most 50 **[Confirmed]** |
| GET / POST / PATCH / DELETE | `/alerts/destinations`, `/alerts/rules` (+ `/test`, `/rules/defaults`), `/alerts/events` | Error monitoring and alerting | 13 operations. Webhook destinations are signed with `X-Freya-Signature` **[Confirmed]** |
| GET / DELETE | `/oauth-connections` | MCP OAuth grants | Account-scoped. The `OAuth Connections` tag is not declared in the top-level `tags` **[Confirmed]** |

### 13. API versioning

- **Platform API:** the version is in the URL path (`/api/v2`), and `info.version` is "2.0.0". The intro page calls it the "Freyavoice v2 Call API" and warns: "this REST interface is still experimental and the definitions may change without immediate notice". **[Confirmed]**
- **Model APIs:** they use `/v1/` paths and spec version 1.0.0. **[Confirmed]**
- **v1 platform API, deprecation policy, changelog:** none are documented. **[Not documented]**
- `integrationVersion` (`v1`/`v2`) is a workspace setting, not the API version. **[Inferred]**

### 14. Environment-variable names in code examples

- **Only one page names environment variables:** https://docs.freyavoice.ai/guides/embed/overview **[Confirmed]**.
  - The Node example uses `process.env.FREYA_BASE_URL`, `process.env.FREYA_API_KEY` and `process.env.FREYA_AGENT_ID`.
  - The Python example uses the bare names `FREYA_BASE_URL`, `AGENT_ID` and `API_KEY`. The snippet does not show how they are defined.
- **STT examples:** they use `API_KEY = "YOUR_API_KEY"` and `const token = "YOUR_API_KEY"`. **[Confirmed]**
- **Authentication page:** it says "Use environment variables or a secrets manager" without giving any variable names. **[Confirmed]**

### 15. Stale vs live OpenAPI, quantified

| Metric | Stale (`docs…/api-reference/openapi.json`) | Live (`app…/api/openapi.json`) |
|---|---|---|
| OpenAPI version | 3.0.0 | 3.1.0 |
| Paths | 58 (56 URL paths + 2 named webhook keys) | 96 |
| Operations | 105 | 180 |
| Tags | 31 used, 0 declared | 41 declared (+1 used but undeclared) |
| Ops declaring 403 | 4 | 178 |

All rows are **[Confirmed]**.

- **Operation overlap:** 55 operations are shared, 50 exist only in the stale spec, and 125 only in the live spec. **[Confirmed]**
- **Only in the stale spec** **[Confirmed]**:
  - `/problems*` (4 tags: Problems, Problem Assignees, Problem Comments, Problem Status Config)
  - `/solutions*`
  - `/agents/{agentId}/versions*`. The live spec has `/versions/{entityType}/{entityId}` instead; that it is a replacement is **[Inferred]**.
  - `/campaign/{campaignId}/jobs*` and `/campaign/poc`
  - `/export/download`
  - `/integrations/session` and `/integrations/{integrationType}`
  - `/phone-numbers/import/twilio` and `/phone-numbers/resolve`
  - `/workspaces/credits`. The live spec has `/workspaces/{workspaceId}/credits` instead; that it is a replacement is **[Inferred]**.
  - `/workspaces/invitations/accept|token`
  - `POST /call/{callId}/recording`
- **Only in the live spec, by tag** **[Confirmed]**:
  - Alerts 13, Simulations 10, Unit Tests 10, Analytics 8, Branches 8, Personas 6.
  - Versions 5, Insights 5, Feedbacks 5.
  - Export 4, Favorites 4, Workspace Roles 4, Suppression List 4, Phone Aliases 4.
  - Chat 3, Permissions 1, `/api-keys/check` 1, and others.
- **Stale `POST /api-keys`** requires `workspaceId` in the body. It has no `permissions` field and documents no expiry default or maximum. The stale spec also has no `/api-keys/check` and no `/permissions`. **[Confirmed]**
- **Both `llms.txt` and the Introduction page link to the stale spec**. **[Confirmed]**
- **Doc pages vs the live spec** **[Confirmed]**:
  - 152 doc pages come from staging, and 28 live operations have no page.
  - The doc pages' permission enum has 117 values against 126 live. Missing: `alerts:*` (5), `favorites:read|write`, `phone-numbers:sip-ingress-read`, `workspace:mfa-policy`.
  - The `/export` doc page lists 4 endpoints and says `params` must include `workspaceId`. It describes delivery "as a direct download URL or sent via email", with no job ID or status polling. Calling this the old synchronous behaviour is **[Inferred]**.
  - `creditsUsed` is missing from the doc pages.
- **Staging vs app spec:** the same 96 paths, with 39 JSON-level differences. Staging adds fields such as `backgroundSoundVolume` in agent config and `runbookUrl` in alert rules. **[Confirmed]**

### 16. Where the guides contradict the spec

- **Workspace settings:** the guide lists `outboundEnabled`, `creditsMonthlyAllowance`, `resetDayOfMonth` and language `en|cs|es`. The live `workspaceSettings` has only `language`, `webhooks`, `dataRetentionDays` and `requireMfa`. The `displayName` that the creating-workspace guide marks as required is not in `POST /workspaces`. **[Confirmed]**
- **Roles:** the guides list Admin and Member. The spec has Owner, Admin and Member, plus custom roles. **[Confirmed]**
- **`POST /call`:** the description says `callerNumber` is required, but the schema requires only `phoneNumber` and `workspaceId`. **[Confirmed]**