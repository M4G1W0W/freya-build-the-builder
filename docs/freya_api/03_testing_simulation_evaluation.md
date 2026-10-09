> Verified research notes, generated 2026-10-10 from the public docs snapshot in `docs/reference/` (the live spec is `docs/reference/freya_openapi_live.json`). Each claim was checked by a separate fact-checking pass against the sources. Tags: **[Confirmed]** = stated in the docs or spec; **[Inferred]** = our reasoning; **[Not documented]** = not in any source. Curated summary: `docs/freya_api_notes.md`.

## Testing and evaluating agents programmatically (Freya)

**Sources:** the live spec `freya_openapi_live.json` (OpenAPI 3.1.0, server `https://app.freyavoice.ai/api/v2`, bearer auth), the doc pages on docs.freyavoice.ai, and `llms-full.txt`. Every response uses the envelope `{success, data:{message, result}}` **[Confirmed]**. Field names below refer to `data.result`.

### 0. The four testing surfaces at a glance
| Surface | What it exercises | Execution | How it is judged |
|---|---|---|---|
| Chat API (`/chat/*`) | A text conversation with an agent or workflow that **you** drive turn by turn | One HTTP reply per turn **[Confirmed]**. Analysis after close runs async **[Confirmed]** | Post-call analysis: summary, sentiment, themes, problems and assertions, per the `/chat/end` description **[Confirmed]** |
| Simulations | A simulated customer (persona) talks to the agent for a full conversation, in `voice` or `chat` mode **[Confirmed]** | Queued and async **[Inferred]** | Run counts passed / failed / inconclusive / error. Per-call `assertionResults` and `successCriteriaResult` **[Confirmed]**. The exact pass rule is **[Not documented]** |
| Unit tests | A fixed conversation snapshot goes in and the agent's next response comes out **[Inferred]** | Enqueued and returns 202 **[Confirmed]** | Typed assertions on routing, extraction and tool calls **[Confirmed]**. A judge model exists (`judgeModel`, `judgeLlmOverride`) **[Confirmed]**. That the judge checks the `expectation` text is **[Inferred]** |
| Call details (`GET /call/{callId}`) | Reading the output of a call. Simulation calls carry `simulationId` **[Confirmed]**. Chat calls being readable here is **[Inferred]** | — | `transcript`, `messages`, `assertionResults`, `successCriteriaResult`, `insights`, `problems` **[Confirmed]** |

---
### 1. Chat API ("Stateful text chat with agents and workflows" **[Confirmed]**)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/chat/message` | Send one user turn and get the agent's reply | [send-a-chat-message](https://docs.freyavoice.ai/api-reference/chat/send-a-chat-message) |
| POST | `/chat/fork` | Make a new call by copying a parent call up to an anchor message | [fork-a-chat-call-at-an-anchor](https://docs.freyavoice.ai/api-reference/chat/fork-a-chat-call-at-an-anchor) |
| POST | `/chat/end` | Close the call and trigger the end-of-call lifecycle | [close-a-chat-call](https://docs.freyavoice.ai/api-reference/chat/close-a-chat-call) |

**Request body for `POST /chat/message`** **[Confirmed]**:
- `message` (required, string, 1–10000)
- `callId`, `agentId`, `workflowId`, `versionId` (uuid)
- `fromMessageId` (string)
- `customerVariables` (object of free-form values)

There is no field called `variables`. The variables field is `customerVariables` **[Confirmed]**.

**Response** **[Confirmed]**: `response` (the reply text, required), `callId` (required), `messageId` (required), plus optional `warning` and `endedByAgent` (boolean).

**Errors** **[Confirmed]**:
- 404: call not found
- 409: "Call has no resume anchor (no prior assistant turn)"
- 422: "customerVariables too large". The size limit itself is **[Not documented]**.
- 502: no response from the agent service
- 503: agent service not configured
- 504: agent service timed out

**How a multi-turn chat works** **[Confirmed]**: the first call omits `callId` and passes `agentId` or `workflowId`. The response returns a `callId`, which you send on every later turn.
- **Synchronous:** each request returns the reply text in its own 200 body **[Confirmed]**. No streaming or job-based variant of the REST Chat API is documented **[Not documented]**. Separately, the Embed SDK guide documents a browser-side WebRTC `mode: 'chat'` with a real-time event stream **[Confirmed]** ([embed overview](https://docs.freyavoice.ai/guides/embed/overview)). Its token endpoint `POST /api/token/embed` is not in the live spec **[Confirmed]**.
- **Branching:** pass `fromMessageId` "pointing at an earlier assistant turn" **[Confirmed]**. Whether that rewinds the same call or returns a new `callId` is **[Not documented]**.
- **`versionId`:** the field exists **[Confirmed]**. What it does (for example, pinning an unpublished version) is **[Not documented]**. It probably selects which agent version answers **[Inferred]**.

**Fork (`POST /chat/fork`)**:
- Body **[Confirmed]**: `parentCallId` (required), `fromMessageId` (required), plus optional `versionId`, `agentId` or `workflowId`.
- Behaviour **[Confirmed]**: it copies the parent's messages "up to and including `fromMessageId`" and can point the copy at a different version or entity. The new call stays dormant until you drive it with `/chat/message`. Forks across entities are allowed, but the inherited workflowSnapshot "may be partially incompatible".
- Response **[Confirmed]**: `callId`, `messageId`, `parentCallId`, `parentAnchorMessageId`, `entityVersionId` (nullable).
- Errors **[Confirmed]**: 404 when the parent call, anchor or target version is not found. 422 "Parent has no agent or workflow to inherit".

**Close (`POST /chat/end`, body `{callId}`)** **[Confirmed]**:
- It fires "webhook + post-conversation analysis + end-of-call tools".
- Analysis runs async. The webhook "arrives at the dashboard shortly after with summary, sentiment, themes, problems, and assertions".
- It is idempotent: closing an already-ended call returns `alreadyEnded: true`.
- Response: `callId`, `ended: true`, `endedReason`, `alreadyEnded`.

**Tools and ending the call:**
- Whether function tools run during `/chat/message` turns is **[Not documented]**.
- "End-of-call tools" probably means agent tools with `config.llmConfig.tools[].config.alwaysRunsAt` containing `end_of_call`. That enum (`each_turn | start_of_call | end_of_call`) is **[Confirmed]** in `POST /agents`. The link to `/chat/end` is **[Inferred]**.
- `endedByAgent` probably means the agent ended the conversation itself **[Inferred]**. Only the field name is documented.

**Reading the chat afterwards:** `/chat/end` returns 404 "Call not found", so a chat is treated as a call. `GET /call/{callId}` has `modality: voice|text|null`. The transcript and analysis are therefore probably readable through `GET /call/{callId}?workspaceId=` **[Inferred]**.

**Other notes:**
- The documented `end-of-call-report` webhook schema has no assertion or insight fields **[Confirmed]**.
- The permissions `calls:chat-message` and `chat:read` exist **[Confirmed]**. Which endpoint needs which is **[Not documented]**.
- Chat endpoints take no `workspaceId`. The workspace is probably resolved from the token **[Inferred]**, which `POST /inbound/web` states explicitly for itself.

---
### 2. Personas ("Simulation personas for agent testing" **[Confirmed]**)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/personas` | List personas | `workspaceId` required. `prompt` and `successCriteria` are previewed at 280 chars, and `systemPrompt`, `evaluationPrompt` and `simulationVariables` are omitted, unless `include` asks for them. `include` caps `limit` at 100 **[Confirmed]** |
| POST | `/personas` | Bulk create | 1–200 personas per request. Returns 201 **[Confirmed]** |
| POST | `/personas/preview` | Generate personas with AI | Body `{agentId*, prompt*, count}`. `count` defaults to 3, range 1–50 **[Confirmed]** |
| GET | `/personas/{personaId}` | Get the full persona | **[Confirmed]** |
| PUT | `/personas/{personaId}` | Update | **[Confirmed]** |
| DELETE | `/personas/{personaId}` | Delete | Returns 409 while a simulation uses it. `force=true` deletes it and removes it from those simulations **[Confirmed]** |

**Persona schema** **[Confirmed]**:
- `name` (required)
- `prompt` (required, max 100000)
- `successCriteria`, `systemPrompt`, `evaluationPrompt` (each max 100000)
- `tags[]`, `agentIds[]`
- Response-only fields, absent from the create and update bodies: `simulationVariables` ("Most-recently-used simulation variable values, keyed by simulated agentId") and `versionNumber`

What `prompt`, `systemPrompt` and `evaluationPrompt` each do is **[Not documented]**. A likely reading **[Inferred]**: `prompt` is the simulated customer's scenario, `successCriteria` is the goal a run is judged on, and `evaluationPrompt` holds instructions for the judge.

**Preview** returns `personas[] {name, prompt, successCriteria, tags}` with no `id` **[Confirmed]**. So previews are probably not saved, and you need `POST /personas` to keep them **[Inferred]**.

---
### 3. Simulations ("Agent simulation testing" **[Confirmed]**)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/simulations` | Create a simulation. With `start=false` it is created as a draft | Returns 200 "Simulation created" **[Confirmed]**. Behaviour when `start` is omitted is **[Not documented]** |
| POST | `/simulations/{simulationId}/start` | Start a draft | In the live and staging specs, but not in llms.txt or the stale `openapi.json`, and there is no doc page **[Confirmed]** |
| POST | `/simulations/{simulationId}/rerun` | Start a new iteration | No request body **[Confirmed]** |
| GET | `/simulations/{simulationId}` | Get simulation, personas, assertions, metrics and `publishedVersionId` | **[Confirmed]** |
| PUT | `/simulations/{simulationId}` | Update | **[Confirmed]** |
| DELETE | `/simulations/{simulationId}` | "Deletes a simulation and all associated data" | **[Confirmed]** |
| GET | `/simulations` | List | Params: `workspaceId` (required), `status`, `search`, `filters`, `sortBy`/`sortOrder`, `limit`/`offset` **[Confirmed]** |
| GET | `/simulations/tags` | List distinct tags | **[Confirmed]** |
| GET | `/simulations/{simulationId}/iterations` | Iteration history | Newest first. `limit` defaults to 100, max 200 **[Confirmed]** |
| GET | `/simulations/version-checks` | One row per simulation for a version | Params `workspaceId`, `entityVersionId` (both required) **[Confirmed]** |
| GET | `/simulations/version-persona-runs` | One row per persona for a version | Same params **[Confirmed]** |

**Create request** **[Confirmed]**:
- `name` (required), `description`
- `tags` (up to 50, each 1–100 chars)
- `agentId` (required, uuid) and `agentVersionId` (uuid)
- `mode`: `voice | chat`, default `voice`
- `selectedPersonaIds` (required, 1–1000)
- `assertions`: a uuid[]. That these are IDs of assertion entities (as returned by `GET /simulations/{id}`) is **[Inferred]**.
- `customerVariablesMap`: `{personaId: {var: string}}`. Per the spec, these are "Per-persona variable values for this run… Saved as the persona's most-recently-used values".
- `maxConcurrentCalls` 1–1000, `maxCallDurationSeconds` 60–3600, `maxRetries` 0–10, `runsPerPersona` 1–50
- `start` (boolean). Per the spec: "When false, the simulation is created as a draft and no calls are placed until POST /simulations/{id}/start."
- LLM overrides: `assistantLlmOverride`, `personaLlmOverride`, `analysisLlmOverride`, `routingLlmOverride`, `extractionLlmOverride`. Each takes `{provider*, model*}`. The persona and analysis overrides also accept `reasoningEffort` (`none|minimal|low|medium|high|xhigh`).

**Gaps in the create request:**
- Valid provider and model values are **[Not documented]**. There is no models endpoint.
- Behaviour when `start` is omitted is **[Not documented]**.
- Which version runs when `agentVersionId` is omitted is **[Not documented]**.

**Settings defaults** **[Confirmed]**: `maxConcurrentCalls` 1, `maxCallDurationSeconds` **240**, `maxRetries` 3, `runsPerPersona` 1. These are in the live spec's response schema `simulation.settings`; the request fields carry no defaults. The doc pages show `maxCallDurationSeconds` default 60 **[Confirmed]**, which is a discrepancy.

**Simulation object** **[Confirmed]**:
- `status`: `draft|running|paused|completed`
- `metrics`: `{totalRuns, passedRuns, failedRuns, averageLatencyMs, averageDurationSeconds, agentSpeakingPercent}`
- `latestPassRate` (0–1), `personaCount`

**What PUT can change** **[Confirmed]**: name, description, tags, status, agentId, selectedPersonaIds, assertions, the four limits, and metrics. It **cannot** change `agentVersionId`, `mode`, the LLM overrides or `customerVariablesMap`.

**Execution:**
- Simulations place calls: "no calls are placed until…" **[Confirmed]**, and `GET /call/{callId}` has a `simulationId` field **[Confirmed]**.
- Execution is async **[Inferred]**: create and rerun return immediately with a status or iteration, and results arrive later through the `running` status, `analyzingRuns` and `runsStarted`.
- Start "Dispatches the initial iteration" **[Confirmed]**. It returns 409 if the simulation is not a draft or has no pending iteration.

**Rerun** returns `{success, iteration{id, simulationId, iterationIndex, label, status}, runsStarted}` **[Confirmed]**. Which agent version a rerun uses is **[Not documented]**, and neither rerun nor PUT accepts a version.

**Polling for results** **[Confirmed]**:
- **Iterations:** `iterationIndex`, `status`, `source`, and run counts (`totalRuns`, `passedRuns`, `failedRuns`, `inconclusiveRuns`, `errorRuns`, `analyzingRuns`). Also `passRate` (0–1 or null), `agentVersionId`, `agentVersionNumber`, `agentLlm`, `runAssistantLlms`, `params`, and `startedAt`/`completedAt`. The value sets for iteration `status` and `source` are **[Not documented]**.
- **version-checks:** `{simulationId, name, status: passed|failed|running|not_run, failedRuns, score 0–1, latestIterationId, latestAt}`, using the latest iteration of each simulation.
- **version-persona-runs:** `{personaId, personaName, simulationId, simulationName, tags, status (same enum), runId|null, latestAt}`.

**Assertions:**
- `GET /simulations/{id}` returns `assertions[] {id, name, prompt, contextConfig{includeRoutingEvents, includeExtractionEvents, includeToolCalls, includeOtherEvents}}` **[Confirmed]**.
- They are probably natural-language checks judged by the analysis LLM **[Inferred]**, based on the `prompt` field, `analysisLlmOverride`, and the per-call `reason`.
- **No API path exists to create or list assertions** in the live, staging or stale spec. The export enum includes `/api/v2/assertions`, and the permissions `assertions:read/write/delete/assign` exist **[Confirmed]**. How to create assertions through the API is **[Not documented]**.

**Pass/fail semantics:**
- Each `GET /call/{callId}` carries **[Confirmed]**:
  - `assertionResults[] {id, name, assertion, success (bool|null), reason, relevantMessages, timeTaken, metadata}`
  - `successCriteriaResult` (same shape)
  - `assertionsSummary {passed, failed, total}`
- The rule that maps these to a run's passed, failed, inconclusive or error state is **[Not documented]**.

**Transcript access:**
- `GET /call/{callId}?workspaceId=` returns `transcript`, `messages[] (role, message, messageId, secondsFromStart, …)`, `summary`, `problems`, `insights`, `entityVersionId`, `cost` and `turnLatencyStats` **[Confirmed]**.
- `GET /call` has **no** `simulationId` query parameter **[Confirmed]**. Its generic `filters` parameter is a "Base64-encoded filter state" whose format is **[Not documented]**. Its list rows do include `simulationId`, and it accepts a comma-separated `callIds` parameter **[Confirmed]**.
- How `runId` maps to `callId` is **[Not documented]**.
- The documented way to get run-level data in bulk **[Confirmed]**:
  1. `POST /export` with `endpoint: "/api/v2/simulations/[simulationId]/iterations/[iterationId]"`, path params in `params`, and `format: json|csv|xlsx|markdown` (default `csv`).
  2. Poll `GET /export/{jobId}` until `status` is `ready`. The statuses are `pending|running|ready|failed|expired`.
  3. Download with `GET /export/{jobId}/download`.
  - `POST /export` returns 429 "Too many export requests".
  - The exported columns are **[Not documented]**.

**Branches:**
- `GET /branches/{branchId}/activity` lists the branch's commits, its simulation iterations (`passRate`, `baseline`) and its unit-test runs (`outcome`, `baseline`), also grouped `byCommit` **[Confirmed]**.
- Merging (`POST /branches/{branchId}/rebase`) returns 409 with `checksState: pass|fail|running|notRun` when the head's checks are "failing, running, or not run", unless `force` is true **[Confirmed]**. "Checks" probably means simulations and unit tests **[Inferred]**.

**UI guides:**
- The guides tell you to use the **Simulations** page in the UI to "Create a test simulation" **[Confirmed]**.
- Best practices say to test in simulation before going live, and "Automate Testing" **[Confirmed]**.
- The linked pages `/guides/features/simulations` and `/guides/features/ai-studio` return "Page Not Found" and are not in llms.txt **[Confirmed]**.

---
### 4. Unit tests ("Behavioural unit tests for agents and workflows" **[Confirmed]**)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/unit-tests` | Create | Returns 201 **[Confirmed]** |
| GET / PATCH / DELETE | `/unit-tests/{unitTestId}` | Get, update, or archive (soft delete) | After archiving, the test's historical runs stay queryable **[Confirmed]** |
| POST | `/unit-tests/run-all` | Enqueue runs | Returns 202 **[Confirmed]** |
| GET | `/unit-tests/runs/{runId}` | One run with its verdict | **[Confirmed]** |
| GET | `/unit-tests/{unitTestId}/runs` | Non-stale runs for one (test, version) | `workspaceId` and `entityVersionId` required. `limit` max 500 **[Confirmed]** |
| GET | `/unit-tests` | Tests for one entity, plus the latest run per (test, version) | Rows omit `input`, `assertions` and `judgeContext` **[Confirmed]** |
| GET | `/unit-tests/version-runs` | Counts per version | Includes `passCount`, `failCount`, `errorCount`, `runningCount` and `simPassCount`, `simFailCount`, `simRunningCount`, `simPendingCount` **[Confirmed]** |
| GET | `/unit-tests/overview` | All non-archived tests in the workspace, with each test's latest run aggregated against the mainline head | **[Confirmed]** |

**Create body** **[Confirmed]**:
- `workspaceId` (required), `entityType` (required, `agent|workflow`), `entityId` (required)
- `name` (1–180), `expectation` (max 50000), `assertions` (up to 50), `tags`
- `input` (required):
  - `schemaVersion: 1`, `callType: web|voice`
  - `messages[]` (at least 1), each with `role` (required), `message|content`, `messageId`, `nodeId`, …
  - `customerVariables`, `authoredAgainstVersionId`
- `judgeContext` (the same 4 flags as an assertion's `contextConfig`)
- `seedCallId` and `seedMessageId`. The fields exist **[Confirmed]**. That they seed the test from a real call is **[Inferred]**.

**Typed assertions** **[Confirmed]**:
- `routing {signal: node_entered|route_target (default node_entered), target, negate}`
- `extraction {name, match: exists|equals|contains|regex|absent (default exists), value, minConfidence 0–1}`
- `tool_call {tool, args, argsMatch: subset|exact (default subset), negate}`

**`POST /unit-tests/run-all`** **[Confirmed]**:
- Body: `workspaceId`, `entityType`, `entityId` (uuid), which are required, plus optional `entityVersionId`, `unitTestIds` (1–200), `onlyFailed`, `mockToolResults` (a free-form object), `judgeLlmOverride`, `assistantLlmOverride`, and `repeat` (1–20, default 1).
- "Enqueues a run for every active unit test… deduping against pending jobs."
- Returns `{enqueued[{unitTestId, runIds[], jobIds[]}], skipped[]}`.
- The default `entityVersionId` when omitted is **[Not documented]**, and so is the format of `mockToolResults`.

**Run verdict** **[Confirmed]**:
- `outcome`: `queued|running|pass|fail|error`
- `verdictReason`, `agentResponse`, `agentResponseMessageId`
- `latencyMs`, `judgeLatencyMs`, `judgeModel`
- `messages`
- `assertionResults[] {index, type, passed, detail, observed}`
- `isStale`. What makes a run stale is **[Not documented]**.

**How unit tests differ from simulations** **[Inferred]**:
- A unit test replays a fixed message prefix and checks the agent's **single next response** (`agentResponse`) against `expectation`, using an LLM judge plus deterministic checks on routing, extraction and tool calls. Tools can be mocked.
- A simulation runs **whole conversations** against an LLM-driven persona, by voice or chat, and judges the finished call.

---
### 5. Insights (structured data fields)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET / POST | `/insights` | List or create definitions | Duplicate name returns 409. `limit` max 500 **[Confirmed]** |
| GET / PUT / DELETE | `/insights/{insightId}` | Read, update or delete one definition | `insightId` is a numeric string. `type` cannot change after creation. Delete also removes all stored values **[Confirmed]** |
| GET / PUT | `/agents/{agentId}/insights` | Read or replace an agent's insight IDs (`number[]`) | PUT "saves the result as a new, unpublished version. Calls use the new set once that version is published." **[Confirmed]** |
| PUT | `/call/{callId}/insights` | Set or clear one value on one call | Body `{name, value: string≤1000|number|boolean|null}`. Returns 409 for values the platform writes. Audit-logged **[Confirmed]** |

**Definition fields** **[Confirmed]**:
- `name` (max 100), `description`
- `type`: `string|number|rating|checkbox|range|enum|array`
- `enums`, `defaultValue`, `rangeMin`/`rangeMax`
- `isRequired` (default true), `label`, `valueLabels`
- `source`: `analysis|tool_field` on create. The response enum also includes `workflow_variable`.
- `toolName`, `toolFieldPath`

**How values get filled:**
- Agent config `config.postConversationAnalysis` holds `insights[{id,name}]` (up to 200), `summaryPrompt`, `autoDetectProblems` (default false), `problemDetectionPrompt`, `problemDetectionInstructions` and `analysisModel` **[Confirmed]**.
- Values with `source=analysis` are probably extracted by that post-conversation analysis **[Inferred]**.
- Tool-field and workflow-variable values are "Insights the platform writes" **[Confirmed]**.

**Reading values** **[Confirmed]**: use `call.insights` on `GET /call/{callId}`, or `GET /call?insights=<ids, max 25>`. Whether simulation pass/fail can use insight values is **[Not documented]**.

---
### 6. Feedbacks, reviews and alerts
**Feedbacks** **[Confirmed]**:
- Create with `{callId, agentId, title*, description, proposedSolution, type, severity 0–1, status, dismissReason}`. `dismissReason` is required when the status is dismissed.
- On the feedback record (response schema), `createdBy` defaults to `"ai"`. It is not a create field.
- PATCH can set `resolvedByVersionId`, which is accepted only with status resolved.
- `GET /feedbacks/open-for-agent?agentId=` lists unresolved feedbacks for an agent.
- References link a feedback to an entity: `persona|simulation|call|version|agent|workflow|branch|external`, with relation `concerns|caused_by|relates`.
- A branch merge returns `resolvedFeedbackIds`.

**AI-generated problems** **[Inferred]**: `call.problems` has the feedback shape, and calls carry `unresolvedAiFeedbacksCount`. Post-call analysis probably creates AI feedbacks when `autoDetectProblems` is on.

**Reviews** **[Confirmed]**: `GET /reviews?workspaceId&callId` and `PUT /reviews {callId, reviewStatus, reviewTag: Successful|Failed|Technical Issue|Wrong Number|No Answer|Needs Review, reviewNotes}`. These are manual QA labels, and nothing documented ties them to simulation scoring **[Inferred]**.

**Alerts** **[Confirmed]**: monitor rules over the error event log, with sources `llm|tts|stt|tool|latency|telephony|webhook|knowledgebase|system`, thresholds and windows. They have no doc pages. They are for production monitoring, not testing **[Inferred]**.

---
### 7. A test loop built only from documented endpoints
Every step below exists in the live spec **[Confirmed]**. Chaining them into a loop is **[Inferred]**, and this is not a solution design.

1. **Create a version:** `POST /versions/agent/{agentId}` with body `{entityId, workspaceId, configSnapshot}` (all required) returns `version.id`. An invalid snapshot returns 422.
2. **Optional chat smoke test:**
   - Send `POST /chat/message {agentId, versionId, message, customerVariables}`, then repeat it with the returned `callId`. What `versionId` does is **[Not documented]**.
   - Close with `POST /chat/end {callId}`.
   - After the async analysis finishes, read `GET /call/{callId}?workspaceId=`. Whether chat calls are readable there is **[Inferred]**.
3. **Simulation:**
   - Create personas with `POST /personas`. You can generate drafts first with `POST /personas/preview`.
   - Create the simulation with `POST /simulations {name, agentId, selectedPersonaIds, agentVersionId?, assertions?, mode?, runsPerPersona?}`.
   - Poll `GET /simulations/{id}`, `/iterations`, `/simulations/version-checks?workspaceId=&entityVersionId=` and `/version-persona-runs`.
   - Get the run details through the export job, or through `GET /call/{callId}` when you know the call IDs.
4. **Unit tests:**
   - Create tests with `POST /unit-tests`.
   - Run them with `POST /unit-tests/run-all {workspaceId, entityType, entityId, entityVersionId?}`.
   - Poll `GET /unit-tests/runs/{runId}` until `outcome` is `pass`, `fail` or `error`.
5. **Compare versions:** `GET /unit-tests/version-runs` gives unit-test and simulation counts per version **[Confirmed]**. It lists only versions "that has at least one non-stale run" **[Confirmed]**, so a version with only simulation results may be missing **[Inferred]**.

### 8. Costs and limits
- **Credits:** no credit cost is documented for simulations, chat or unit tests **[Not documented]**.
  - Workspace balance: `GET /workspaces/{workspaceId}/credits` returns `creditsLeft`, `creditUsdRate`, `billingUnit: usd|minutes`, `minuteLimit` and `minutePeriodStart` **[Confirmed]**.
  - Usage: `GET /analytics/credits` returns daily usage, and each call has a `cost` field **[Confirmed]**.
- **Rate limits:** API keys can be created with an optional `rateLimit {requestsPerMinute, requestsPerDay}` **[Confirmed]**. The default values, and the limits when `rateLimit` is omitted, are **[Not documented]**.
- **Hard caps:** the schema caps are listed in sections 2–4 **[Confirmed]**.