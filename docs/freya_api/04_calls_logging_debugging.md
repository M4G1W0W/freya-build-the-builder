> Verified research notes, generated 2026-10-10 from the public docs snapshot in `docs/reference/` (the live spec is `docs/reference/freya_openapi_live.json`). Each claim was checked by a separate fact-checking pass against the sources. Tags: **[Confirmed]** = stated in the docs or spec; **[Inferred]** = our reasoning; **[Not documented]** = not in any source. Curated summary: `docs/freya_api_notes.md`.

## Calls, telephony, webhooks, observability and debugging (Freya)

**Sources.** The canonical source is the live spec `freya_openapi_live.json` (OpenAPI 3.1.0, `servers: https://app.freyavoice.ai/api/v2`). Each doc page under https://docs.freyavoice.ai/api-reference/... embeds the staging spec (`https://staging-app.freyavoice.ai/api/openapi.json`) and sometimes lags behind the live spec (see Discrepancies) **[Confirmed]**. The spec's `info.description` says all endpoints require a bearer token (`bearerAuth`) and all responses use the envelope `{success, data:{message, result}}` **[Confirmed]**. There are exceptions in the spec itself **[Confirmed]**:
- The two `/webhooks/*` entries declare no security, because they document outgoing payloads.
- Binary responses (the MP3 recording and the ZIP exports) are not wrapped in the envelope.

### 1. Endpoint inventory (live spec)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/call` | List calls | Filters, sort and pagination. `export=true` returns a ZIP **[Confirmed]** |
| POST | `/call` | Initiate outbound call | See §5 **[Confirmed]** |
| PATCH | `/call` | Bulk update | Archive or unarchive only (`callIds`, `archive`) **[Confirmed]** |
| DELETE | `/call` | Bulk delete | `workspaceId`, `callIds` **[Confirmed]** |
| GET | `/call/{callId}` | Call details | `workspaceId` query is required. See §2 **[Confirmed]** |
| PUT | `/call/{callId}/insights` | Set or clear one insight value | No doc page (it is in the live and staging spec) **[Confirmed]** |
| GET | `/call/{callId}/recording` | Download recording | `audio/mpeg`. 404 "Recording not found" **[Confirmed]** |
| POST/PATCH/DELETE | `/call/{callId}/tags` | Add, update or remove a tag | Fields `tag`, `source` (default `user`), `value`, `confidence` 0–1, `metadata` **[Confirmed]** |
| POST | `/call/export-raw` | Queue a raw ZIP export (traces and logs) | Returns 202 with `jobId`. See §8 **[Confirmed]** |
| POST | `/call/import` | Import a raw ZIP | multipart. Needs `calls:import` **[Confirmed]** |
| POST | `/inbound/web` | Register an inbound web call | See §6 **[Confirmed]** |
| POST | `/webhooks/end-of-call-report` | Documents an **outgoing** payload | See §4 **[Confirmed]** |
| POST | `/webhooks/campaign-call-outcome` | Documents an **outgoing** payload | Goes to the campaign `webhookUrl` **[Confirmed]** |
| GET | `/analytics`, `/analytics/structured-data`, `/analytics/credits`, `/analytics/properties` | Aggregates | `/properties` has no doc page **[Confirmed]** |
| GET/POST/PUT/DELETE | `/analytics/widgets[/{widgetId}]` | Dashboard widgets | Probably not useful for debugging **[Inferred]** |
| GET/POST/PATCH/DELETE | `/campaign`, `/campaign/{campaignId}` | Campaign CRUD | PATCH (on `/campaign/{campaignId}`) accepts only `name` and `maxConcurrency` **[Confirmed]** |
| GET | `/campaign/{campaignId}/customers` | Customer rows | Includes `properties` and `retryStatus` **[Confirmed]** |
| POST | `/campaign/jobs/cancel-by-phone` | Cancel scheduled dials for a number | No doc page **[Confirmed]** |
| GET/POST/PUT/DELETE | `/phone-numbers` | Phone number CRUD | `config.inboundAgentId` and `config.outboundAgentId` **[Confirmed]** |
| GET/POST/PUT/DELETE | `/phone-aliases` | Phone book (contact name to numbers) | **[Confirmed]** |
| GET/POST/PUT/DELETE | `/suppression-list` | Do-not-call list | "blocked from outbound dialing" **[Confirmed]** |
| GET/POST/PATCH/DELETE | `/alerts/destinations`, `/alerts/rules` (+`/test`, `/rules/defaults`) | Alerting | None of the 13 Alerts operations has a doc page **[Confirmed]** |
| GET/POST | `/alerts/events` | Error event log and ingest | GET can filter by `callId` and `agentId` **[Confirmed]** |
| POST/GET/DELETE | `/export`, `/export/{jobId}`, `/export/{jobId}/download` | Async export jobs | Only POST has a doc page **[Confirmed]** |
| GET | `/workspaces/logs` | Workspace audit log | Not per call **[Confirmed]** |
| POST | `/chat/message`, `/chat/end`, `/chat/fork` | Text-drive an agent, which creates a call | Related to this topic **[Confirmed]** |

### 2. `GET /call/{callId}`: what a call record contains
Source: https://docs.freyavoice.ai/api-reference/calls/get-call-details and the live spec `GET /call/{callId}` → `data.result.call`. Only `id` and `workspaceId` are required. Every other field is optional and may be absent, and many fields are also nullable **[Confirmed]**.

- **Linkage.** `assistantId`, `assistantName`, `assistantEntityType` (`workflow`/null), `assistantWorkflowId`, `simulationId`, `campaign{id,assistantId,phoneNumberId,name,description}`, `entityVersionId`, `entityVersionNumber`, `externalCallId`, `originCallId`, `sipCallId`, `isImported`, `phoneNumber`, `phoneNumberId`, `customerNumber`, `customerLabel`, `customer{number, identity{firstName,lastName,email}}` **[Confirmed]**.
- **Classification.** `status`, `type` and `endedReason` are free strings with no enum on the call object **[Confirmed]**. Other schemas suggest likely `type` values: `/inbound/web` returns `webCall|simulationCall`, and the analytics `callType` filter uses `inbound, outbound, web, inboundPhoneCall, outboundPhoneCall, webCall` **[Inferred]**. Other fields: `modality` is `voice|text|null` and `channel` is `whatsapp|api|null` **[Confirmed]**.
- **Transcript and messages.** `transcript` is a string or null. `messages[]` items are `{role* (string), message, duration, secondsFromStart, timestamp, endTime, messageId, wasBlocked/was_blocked, blockedContent/blocked_content}` **[Confirmed]**. The set of `role` values is **[Not documented]**.
- **Tool-call records.** The call schema has no typed field for tool calls: message items carry no tool name or arguments, and `analysis` and `artifact` are untyped (`{}`) **[Confirmed]**. Where tool calls are stored is **[Not documented]**. Hints:
  - Simulation assertion `contextConfig` and unit-test `judgeContext` have `includeToolCalls`, `includeRoutingEvents` and `includeExtractionEvents`.
  - `PUT /call/{callId}/insights` says the platform writes "tool fields, workflow variables" as insights.
  - Together these suggest tool events are recorded, and some tool fields surface in `call.insights` **[Inferred]**.
- **Ended reason.** `endedReason` is a string. Example values from the webhook schema are `customer-ended-call` and `assistant-ended-call` **[Confirmed]**.
  - The campaign `RetryConditions` enum is described as "SipCodeCategory + special endedReason values". Its items are `Rejected, Unreachable, Busy, No Answer, Network Error, Invalid, Timeout, Cancelled, Resource Unavailable, Service Unavailable, Protocol Error, Unspecified, voicemail, exceeded-max-duration, inactivity-ended-call, rescheduled, capacity_exceeded, capacity_wait_abandoned, number_not_configured, never_connected` **[Confirmed]**.
  - The lowercase items appear to be the endedReason values **[Inferred]**. The spec does not say which items are which.
  - The full list of values is **[Not documented]**.
- **Summary and sentiment.** `summary` is a string or null **[Confirmed]**. The call schema has **no per-call sentiment field** **[Confirmed]**. Sentiment does appear in three places: `GET /call` `sortBy=sentiment`, the analytics sentiment buckets `very-unhappy…very-happy`, and the `/chat/end` text saying the webhook "arrives at the dashboard shortly after with summary, sentiment, themes, problems, and assertions" **[Confirmed]**. Where per-call sentiment is stored (`tags`? `analysis`?) is **[Not documented]**.
- **Assertion results.**
  - `assertionResults[]` items are `{id, name, assertion, success (bool|null), reason, relevantMessages (map string→string), timeTaken, metadata}`.
  - `assertionsSummary` is `{passed, failed, total}`.
  - `successCriteriaResult` has the same shape as one assertion result.
  - `unitTestsCount` is also returned.
  - All **[Confirmed]**.
- **Debug and quality info.**
  - `problems[]` holds AI or user feedback items: `title`, `description`, `proposedSolution`, `type` ∈ {`workflow, decision-llm, stt, tts, vad-nc, latency, platform, ui, general`}, `severity` 0–1, `createdBy` (default `ai`), `messageId`, `status`. The item schema is identical to the `GET /feedbacks` items **[Confirmed]**.
  - `turnLatencyStats{p50,p75,p90,p95,p99,avg,count}`, `cost`, `duration`, `startedAt`/`endedAt`, `recordingUrl`.
  - `tags[]{tag,source,value,confidence,metadata}`, `insights` (an open object).
  - `piiRedactions[]{token,label,value}`. `value` is returned only with the `calls:pii` permission.
  - All **[Confirmed]**.
- The live call object has **no `logs` field**. The stale spec had `logs: array` **[Confirmed]**.

### 3. `GET /call` (list): filters
Query parameters are `workspaceId*`, `limit` (default 20), `offset`, `sortBy` ∈ {`startedAt, duration, sentiment, relativeTime, cost`}, `sortOrder`, `callIds`, `startDate`, `endDate`, `phoneNumberId`, `customerNumber`, `campaignId`, `searchTerm`, `status`, `type`, `endedReason`, `filters` (Base64), `insights` (insight IDs, max 25), `includeStatusCounts`, `countsOnly`, `semanticQuery`, `archivedFilter` (`active|all|archived`), `export`, `exportFormat` (`csv|xlsx|markdown`), `exportColumns`, `additionalData` (`transcript,cxInsights`) and `include` (`summary`, `reviewNotes`) **[Confirmed]**.

- **What is missing.** There is no dedicated query parameter for agent/assistant, version (`entityVersionId`), `simulationId`, modality, or source (chat/simulation/phone) **[Confirmed]**. The encoding of the Base64 `filters` state is **[Not documented]**.
- **Defaults on list rows.** Rows leave out `summary` and carry only the first 280 characters of `reviewNotes`, unless `include` asks for more. Tags carry no `metadata` **[Confirmed]**. Transcripts appear to need `additionalData=transcript` **[Inferred]**.
- **Totals.** `statusCounts{all, live, processing, transferred, successful, failed}`, plus pagination with `hasNext` **[Confirmed]**.
- **Export.** `export=true` returns a ZIP with the chosen format "plus any requested recordings, configs, and logs" and needs `calls:export` **[Confirmed]**. How to request recordings, configs or logs is **[Not documented]**.

### 4. Webhooks (outgoing)
**End-of-call report** (https://docs.freyavoice.ai/api-reference/webhooks/end-of-call-report-webhook, schema `EndOfCallReport`):
- Fields: `type` (`end-of-call-report`), `callId`, `workspaceId`, `summary`, `endedReason`, `durationMs`, `transcript`, `status`, `callEndReasonCategory`, `customer` (phone number), `startedAt`, `endedAt`, `recordingUrl`, `timestamp` **[Confirmed]**.
- It has **no** messages array, tool calls, assertions, insights or sentiment **[Confirmed]**.
- Where to set this webhook's URL is **[Not documented]**. `workspaceSettings.webhooks` is an untyped `{string:string}` map, and `/inbound/web` returns a `webhookUrl` **[Confirmed]**. That these are the configuration point is **[Inferred]**.

**Call outcome** (https://docs.freyavoice.ai/api-reference/webhooks/call-outcome-webhook):
- Sent to the campaign `webhookUrl`. Fields: `callId`, `campaignId*`, `phoneNumber*`, `outcome*` (`success|failed`), `failureCategory`, `message`, `willRetry`, `retryScheduledAt`, `retriesRemaining`, `attemptNumber` **[Confirmed]**.
- Failure categories in the op description: `no_answer, busy, voicemail, timeout, api_error, llm_fail, other`. The schema field itself is described as "SipCodeCategory value or 'api_error'" **[Confirmed]**.
- `WebhookApiError` is mentioned but has no schema **[Confirmed]**.
- The description documents campaign *call* retries: check `retryScheduledAt` when `willRetry` is true, and retries respect the campaign schedule **[Confirmed]**.
- Signing and delivery retry for both webhooks are **[Not documented]**. The guides only say generically to "validate webhook signatures" and to handle delivery failures with retries, without naming a header or algorithm (https://docs.freyavoice.ai/guides/fundamentals/integrations). Only alert webhook destinations document `X-Freya-Signature` **[Confirmed]**.

### 5. Initiating outbound calls (`POST /call`)
Docs: https://docs.freyavoice.ai/api-reference/calls/initiate-call. The description reads "Requires phoneNumber, callerNumber, and workspaceId", and calls route "via Asterisk ARI or FreeSWITCH ESL" **[Confirmed]**.

Body fields **[Confirmed]**:
- `phoneNumber*` is the customer's number. `workspaceId*` is a UUID.
- `callerNumber` is the caller ID. It is required for regular calls and derived for campaign calls.
- `callerChannel` is `sip|whatsapp`.
- `campaignId`: its presence triggers the campaign flow.
- **`properties`** is an open object: "Custom properties to pass to the agent".
- `attemptNumber` is surfaced to the agent as the 0-based `call.retry_number`.
- `originCallId` is the ID of the call whose `reschedule_call` tool produced this follow-up dial. It applies to campaign calls only and is ignored without `campaignId`.
- `externalCallId` is 1–255 characters.
- `assistantId`: "Override campaign assistant ID".
- `entityVersionId`, `skipE164Normalization`.

Response: `success, callId, jobUuid/job_uuid, message, error`. Error codes: 404 (campaign, phone number or campaign customer not found) and 503 (voice agent not ready, or call server unreachable) **[Confirmed]**.

**Per-call variables:**
- Campaign guide: prompt variables such as `{{customer_name}}` "appear as columns in the customer table" (https://docs.freyavoice.ai/guides/features/campaigns) **[Confirmed]**.
- Campaign `customers[].properties`: "Custom properties to pass to the agent" **[Confirmed]**.
- The Embed SDK's `customerVariables` is described as "Variables injected into the agent's system prompt at runtime" (https://docs.freyavoice.ai/guides/embed/overview). `POST /chat/message` also accepts `customerVariables` with no description, and its 422 is "customerVariables too large" **[Confirmed]**.
- That `POST /call` `properties` keys fill `{{key}}` placeholders the same way is **[Inferred]**.
- Which agent handles a non-campaign call with no `assistantId` is **[Not documented]**. The guide's "One-Click Call" uses "your configured outbound agent/workflow", so `config.outboundAgentId` is likely **[Inferred]**.

**Prerequisites (getting-started guide):** "Outbound Enabled" in workspace settings, a phone number with an outbound agent or workflow, credits, and Twilio connected **[Confirmed]**. Whether `POST /call` checks the suppression list is **[Not documented]**. The list says only that numbers "are blocked from outbound dialing".

### 6. Inbound web call (`POST /inbound/web`)
- Body: `id*`, `baseUrl*`, `agentId`, `simulationId`, `modality` (`voice|text`), `memberId`, `customerEmail`. The workspace comes from the bearer token **[Confirmed]**.
- Response: `type` ∈ {`webCall`, `simulationCall`}, `phoneNumber`, `properties{workspaceId, customerData{phoneNumber,inboundFrom,email}, assistantId, phoneNumberId, webhookUrl, isCommercial}` **[Confirmed]**.
- The doc page says "LiveKit room metadata", but the live spec says "call session metadata" **[Confirmed]**.
- What `id` and `baseUrl` mean is **[Not documented]**.

### 7. Campaigns
`POST /campaign` (https://docs.freyavoice.ai/api-reference/campaigns/create-campaign) **[Confirmed]**:
- Fields: `name*`, `assistantId` or `assistantName`, `phoneNumber`, `phoneChannel`, `startDate`/`startTime`/`endTime`, `timezone` (default UTC), `activeDays` (0 = Monday), `daySchedules`, `callRetries` (0–10), `retryDelaySeconds` (60–86400, default 300), `retryDelayMode` (`fixed|next_day`), `retryConditions`, `maxConcurrency` (1–50, default 5), `webhookUrl`, `customers[]{phoneNumber*, properties}`, `phoneList`.
- The body has no `workspaceId`.

Status values: `draft, scheduled, active, completed, partially_completed` **[Confirmed]**.

- **`GET /campaign/{id}`** returns `events` (last 100), `customerCount` and `callCount`. Calls are listed through `GET /call?campaignId=` **[Confirmed]**.
- **`GET /campaign/{id}/customers`** returns `properties`, `retryStatus{status (pending, in_progress, retrying, waiting_capacity, rescheduled, human_callback_requested, skipped, success, failed, canceled), attempts, lastAttemptAt, nextRetryAt}`, `successfulCallId` and `propertyKeys` **[Confirmed]**.

### 8. Raw ZIP export, import and export jobs
- **`POST /call/export-raw`** queues a "lossless dump" and returns 202 with `{jobId, callCount, statusUrl, downloadUrl}` **[Confirmed]**.
  - Body: `workspaceId*`, `callIds[]`, `archivedFilter`, `filters`, `search`, `semanticQuery`, `redact`, `combineAudio`.
  - Errors: 404 if no calls match, 413 if the selection exceeds 10,000 calls.
  - The ZIP contains `calls.json, agents.json, workflows.json, versions.json, recordings/<callId>[_user|_assistant].{opus,mp3,wav}` and **`traces/<callId>.json.gz` + `logs/<callId>.json.gz`** ("gzip-compressed OTel traces and application logs, management only").
  - Needs `calls:export`. Only the requesting account can collect the bundle.
- **Not documented:** the schema of the traces and logs, and what "management only" means.
- **Polling:** use `GET /export/{jobId}` (`pending|running|ready|failed|expired`) and `GET /export/{jobId}/download`, which returns 202 while generating, 422 on failure and 410 when expired **[Confirmed]**.
- **`POST /call/import`** takes multipart `workspaceId*` and `file*`. It inserts agents, workflows and versions, then calls, recordings, tags, feedbacks and assertion results. It returns `created/skipped/failed/assertionSkipped/errors[]` and needs `calls:import` **[Confirmed]**.
- **`POST /export`** is the generic export. Allowed `endpoint` values are calls, campaigns, campaign customers, phone numbers, feedbacks, assertions, personas, simulations, simulation runs and workspace ("Enterprise") logs. Formats are `csv|xlsx|markdown|json` and delivery is `download|email` **[Confirmed]**.

### 9. Analytics (aggregates only)
- **`GET /analytics`** (https://docs.freyavoice.ai/api-reference/analytics/get-analytics) **[Confirmed]**:
  - Filters: `assistantId`/`assistantIds`, `campaignIds`, `phoneNumberId`, `callType`, `status` (`successful|failed|transferred`), `sentiment`, duration ranges, `insightFilters`, `granularity`.
  - Metrics: `summary, timeSeries, endedReasons, topCalls, geoDistribution, callThemes, sentimentDistribution`.
- **`/analytics/structured-data`** gives per-insight time series and distributions. **`/analytics/credits`** gives cost **[Confirmed]**.
- The `callType` enum has no "simulation" value **[Confirmed]**. So analytics probably can't isolate simulation calls **[Inferred]**.

### 10. Alerts, logs and live events
- **`GET /alerts/events`** is the workspace error event log. Its `fingerprint` "groups like errors the way a Sentry issue does" **[Confirmed]**.
  - Filters: `callId`, `agentId`, `sources`, `severities`, `fingerprint`, `from`/`to`.
  - Event fields: `{source ∈ llm,tts,stt,tool,latency,telephony,webhook,knowledgebase,system; severity ∈ info,warning,error,critical; code; message; callId; agentId; metadata; occurredAt}`.
- **Rules and destinations** (email, webhook, Slack) are available. `/alerts/rules/defaults` seeds built-in monitors such as "tool failure rate" and "call error rate" **[Confirmed]**.
- **`GET /workspaces/logs`** is an audit log of workspace events (login, API keys, members, exports), not call execution **[Confirmed]**.
- **Embed client events** (https://docs.freyavoice.ai/guides/embed/reference): `toolCallStarted`, `toolCallInProgress` (`function_name`, `tool_call_id`, `arguments`), `toolCallStopped`, plus `botTranscript`, `userTranscript` and `error` give live, client-side tool-call visibility for web sessions **[Confirmed]**.
- **`GET /feedbacks?callId=`** lists feedbacks for a call. They share the item schema of `call.problems` **[Confirmed]**.
- The telephony guides mention "Routing Logs", "Agent Logs" and "Provider Logs" (provider-side) only in general terms. No API for them is documented **[Not documented]**.

### 11. Telephony and phone numbers
- **`POST /phone-numbers`** takes `number*`, `userId*`, `config{inboundAgentId, outboundAgentId, sipInbound{enabled}, sipOutbound{endpoint,port,username,password,fromDomain,transportProtocol UDP|TCP|TLS,…}, cancelCampaignRetriesOnInbound, whatsapp{…}}`, `maxConcurrentCalls` and `channel` **[Confirmed]**.
- **Inbound SIP endpoints:** `sip.us1.freyavoice.ai:5080`, `sip.eu1.freyavoice.ai:5080`, `sip.tr.freyavoice.ai:5060` **[Confirmed]**.
- **Twilio inbound webhook:** `https://agents-eu1.freyavoice.ai/telephony/inbound/webhook` (HTTP POST) **[Confirmed]**.
- **Campaign dropdown:** a number appears there only with outbound SIP **and** an outbound agent configured **[Confirmed]**.

### 12. Which of these let us inspect what an agent did in a simulated conversation?
1. **`GET /call/{callId}`** is the primary per-conversation record. It has `simulationId`, `messages` (with `messageId` and timing), `transcript`, `summary`, `endedReason`, `assertionResults`/`assertionsSummary`/`successCriteriaResult`, AI `problems`, `insights`, `turnLatencyStats` and `entityVersionId` **[Confirmed]**. `insights` may include platform-written tool fields **[Inferred]**. That simulation calls fill these fields is **[Inferred]**. Tool-call detail may sit in the untyped `artifact`/`analysis` **[Not documented]**.
2. **`POST /call/export-raw`** gives OTel traces and application logs for each call **[Confirmed]**. That this is the deepest debugging data available is **[Inferred]**. It is asynchronous, marked "management only", and its format is **[Not documented]**.
3. **`GET /alerts/events?callId=`** returns error events (sources include tool, llm, stt and tts) for a call **[Confirmed]**.
4. **`GET /feedbacks?callId=`** and `call.problems` give AI-diagnosed issues by type **[Confirmed]**.
5. **Finding the calls.** `GET /call` with `callIds`, a date range, `type`, `searchTerm` or `semanticQuery` works, but there is no direct `simulationId` or agent filter **[Confirmed]**. List rows do carry `simulationId` and `assistantId` **[Confirmed]**, so filtering client-side after listing should work **[Inferred]**.
6. **Reproducing a conversation.** `POST /chat/message` (with `customerVariables` and `versionId`) returns a `callId`. `POST /chat/end` then fires the end-of-call lifecycle ("webhook + post-conversation analysis + end-of-call tools"), and analysis "runs async" **[Confirmed]**. That the results (summary, assertions, problems) then show up in `GET /call/{callId}` is **[Inferred]**.
7. **Embed client tool events** give live tool calls with arguments for web sessions **[Confirmed]**.
8. **The end-of-call webhook** carries summary, transcript, endedReason/status/callEndReasonCategory, timing, recordingUrl and the customer number. It has no messages, tool calls, assertions, insights or sentiment **[Confirmed]**.

Whether the organizers' simulated-customer calls will land in our workspace, so that we can read them, is **[Not documented]**.