# Freya API notes (pre-kickoff research)

**Snapshot:** public docs and specs downloaded 2026-10-10 ~00:50 Istanbul time (`docs/reference/`).
**Method:** five topic researchers read the full snapshot, an adversarial fact-checker re-verified
every claim against the sources (338 confirmed, 21 corrected, 1 unverifiable and relabelled, 0 refuted), and a
completeness critic checked the result against our research checklist.
**No authenticated Freya API calls were made.** Only public pages and the public spec files were read.

**Tags.** **[C]** Confirmed: stated in the docs or live spec. **[I]** Inferred: our reasoning, needs
testing. **[ND]** Not documented anywhere we could find.

> 🔁 **Corrections after reading the official hackathon page** (<https://www.freyavoice.ai/hackathon>,
> digest in `docs/hackathon_notes.md`):
> - **The phone agent must be a Freya *workflow*** (steps, prompts, tools, conditional routes, code
>   nodes), not a single agent. The kit's `freya.py` "creates a workflow once and updates it on later
>   runs", and the kit's `docs/` describe the workflow format. The public docs below don't document
>   workflow creation, so **for workflows the kit is the authority** and §7's "read-only" statement applies only to the public spec.
> - **Scoring conversations are text, not voice.** TTS/STT settings don't affect the score.
> - **The phone agent's model is fixed** by the kit's `freya.py`. Do not change `llmConfig` provider or model.
> - **Phone agent tools are the kit's bank tool API** (7 tools, a hosted mock bank). Calls to any other service fail the case.
> - **Do not probe or load-test the platform** (official rule). §17 is now "read the kit first".

> ⚠️ The official starter kit and rules override everything here. Freya's own intro page warns that
> the REST API is "still experimental and the definitions may change without immediate notice" [C].
> At kickoff: re-download the live spec and `git diff docs/reference/` (see `docs/reference/README.md`).

**Detail files.** Each topic below has a longer verified write-up in `docs/freya_api/`:
[01 platform/auth](freya_api/01_platform_auth_conventions.md) ·
[02 agents/config/versions/workflows](freya_api/02_agents_config_versions_workflows.md) ·
[03 testing/simulation/evaluation](freya_api/03_testing_simulation_evaluation.md) ·
[04 calls/logging/debugging](freya_api/04_calls_logging_debugging.md) ·
[05 integrations/SDKs/external](freya_api/05_integrations_sdks_external.md) ·
[agent config field tree (241 paths)](freya_api/agent_config_schema.md)

---

## 0. The facts most likely to matter at kickoff

1. **Use the live spec.** <https://app.freyavoice.ai/api/openapi.json> (OpenAPI 3.1.0, 180 operations)
   is the canonical contract [C]. The spec that `llms.txt` and the API intro page link,
   <https://docs.freyavoice.ai/api-reference/openapi.json>, is **stale** (3.0.0, 105 ops, no Chat,
   Simulations, Personas, Unit Tests, Versions or Branches) [C].
2. **Base URL and auth.** `https://app.freyavoice.ai/api/v2` + `Authorization: Bearer <api-key>` [C].
   Every JSON response is wrapped as `{success, data: {message, result}}`, so read `data.result` [C].
3. **An agent can be created fully via the public API.** `POST /agents {name, language?, config}` [C].
   The public spec has only GET endpoints for workflows [C]. **But the hackathon phone agent is a
   workflow**, and the kit's `freya.py` and `docs/` provide workflow create, update and export. Use those.
4. **For a single agent, behaviour is mostly in `config.llmConfig`:** `systemPrompt` (≤200 000 chars),
   `firstMessage`, `firstMessageMode` (default `assistant-waits-for-user`), `temperature`, and `tools[]` [C].
   For the hackathon **workflow**, behaviour is spread across steps: per-step prompts and tools, conditional routes and code
   nodes. Field names come from the kit's `docs/`.
5. **Text test loop exists.** `POST /chat/message` drives an agent turn by turn synchronously.
   `POST /chat/end` closes the conversation and triggers async post-call analysis [C].
6. **Built-in evaluation exists.** Personas (simulated customers), Simulations (full conversations,
   `voice` or `chat` mode, async, pass/fail counts) and Unit Tests (fixed conversation input, typed
   routing/extraction/tool-call assertions, LLM judge) all have APIs [C].
7. **Per-conversation evidence.** `GET /call/{callId}?workspaceId=` returns the transcript, messages,
   `endedReason`, `assertionResults`, `successCriteriaResult`, `problems` and `insights` [C].
8. **Big unknowns, now workflow-level** (settle from the kit's `docs/` first) [ND]:
   - How steps reference `now`, `first_name`, `last_name` and `title`.
   - How the bank tools and the team key are wired.
   - The code-node runtime.
   - Which version `run_cases.py` and `export_workflow` use after an in-place update.
   - How the workflow id relates to the agent id.

   The agent-level questions (`handler` strings, `PUT /agents` merge) are probably irrelevant now.
9. **No official SDK** for Python or JS on PyPI, npm or GitHub [C]. **For the hackathon, use the kit's
   `freya.py`** (stdlib-only: create and update workflow, `export_workflow`) rather than writing our own client.
10. **The official evaluation is the kit's `tools/run_cases.py`** (hosted mock bank plus judge). Freya's own
   Personas and Simulations are a secondary tool at most. If we use them, set `mode: "chat"`, and expect them to
   compete for the single simulation slot [I].
11. **No numeric rate limits are documented** [C]. Build in backoff anyway. The **hackathon limits** are
   10 workflows per workspace (update in place), 1 practice simulation at a time, and a 30-minute builder run [C: page].

---

## 1. Sources of truth and hosts

| Source | Status |
|---|---|
| `https://app.freyavoice.ai/api/openapi.json`: live spec, saved as `docs/reference/freya_openapi_live.json` | **Canonical** [C]. Same path set as `staging-app` [C] |
| API reference pages (`docs.freyavoice.ai/api-reference/...`) | Render the **staging** spec. They cover 152 of 180 live ops and lag in places (for example, persona prompt truncation in staging, and `maxCallDurationSeconds` default 60 on the page vs 240 in the live response schema) [C] |
| `https://docs.freyavoice.ai/api-reference/openapi.json` | **Stale**: still has `/problems`, `/solutions`, `/agents/{id}/versions` [C]. Don't use it |
| Guides (`docs.freyavoice.ai/guides/...`, `getting-started/...`) | UI-oriented. Several contradict the live schema (temperature "0-1" vs spec max 2; "Endpoint" field on functions that the spec doesn't have; workspace settings fields that don't exist) [C] |

| Host | Use |
|---|---|
| `https://app.freyavoice.ai/api/v2` | Platform REST API (the only `servers` entry) [C] |
| `https://stt.freyavoice.ai`, `https://tts.freyavoice.ai` | Standalone STT/TTS model APIs (same Bearer key) [C] |
| `https://app.freyavoice.ai` | Dashboard / sign-up per the docs [C]. The marketing homepage also links `playground.freyavoice.ai` for API keys [C]. Which one hackathon participants use: [ND] |

## 2. API authentication (checklist 1)

- **Header.** `Authorization: Bearer <api-key>` on every request. The spec defines `bearerAuth`
  (http/bearer) on 178 of 180 operations [C]. Source: <https://docs.freyavoice.ai/api-reference/authentication>
- **Getting a key.** Dashboard → Settings → **API Keys** → Create API Key. It is shown **once** [C].
  The token is "tied to your workspace" [C].
- **Expiry.** Keys expire after 90 days by default (max 365). This is set at creation and cannot be changed [C].
  Source: <https://docs.freyavoice.ai/api-reference/api-keys/create-api-key>
- **Permissions.** A key's permissions are "a frozen subset of the creator's permissions", defaulting to the creator's
  full set [C]. Relevant ones include `agents:read|write|delete|test`, `versions:read|publish`,
  `chat:read`, `calls:chat-message`, `calls:read`, `simulations:read|write|execute`,
  `personas:read|write`, `assertions:*` [C]. Which endpoint needs which permission is mostly [ND].
- **Bootstrap call.** `GET /api-keys/check` takes no parameters and returns `valid, workspaceId, name,
  isActive, expiresAt, rateLimit, …` for the calling key. Only API-key auth is accepted [C].
  This is the documented way to discover the key's `workspaceId` [I].
- **Errors.** 401 "Missing or invalid token". 403 "Workspace ID mismatch or insufficient
  permissions". The 403 doesn't say which of the two applies [C].

## 3. API conventions

- **Envelope.** Success is `{success: true, data: {message, result}}`. Errors are
  `{success: false, data: {message, result: null}}` [C]. There is **no machine-readable error code**
  field in general [C]. Binary responses (recordings, ZIPs, audio) are not wrapped [C].
- **`workspaceId`.** It is a required query param on 65 ops (e.g. `GET /agents`, `GET /agents/{id}`,
  `GET /call/{id}`) and a required body field on 22 (e.g. `PUT /agents/{id}`, `POST /unit-tests`,
  `POST /versions/...`). It is **absent** on 87, including `POST /agents`, `POST /personas`,
  `POST /simulations` and all `/chat/*` [C]. For those, the workspace comes from the token [I]. The docs
  say so explicitly only for `POST /inbound/web` and `POST /alerts/events` [C].
- **Pagination.** `limit`/`offset`, no cursors. Response shapes and maximums differ per endpoint [C].
  `filters` params are "Base64-encoded filter state" with an [ND] format.
- **Status codes differ.** `POST /agents` → 201, `POST /versions/...` → 200, `POST /simulations` → 200,
  `POST /unit-tests/run-all` → 202. Treat any 2xx as success [C].
- **Idempotency keys and request-ID headers** are [ND].

## 4. Agent creation endpoints (checklist 2)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/agents` | Create agent | Body `{name*, language?, config?}`. **No `workspaceId` in the schema.** Returns 201 `data.result.agent{id, workspaceId, name, config, …}`, **no `versionId`** [C]. 409 if the name already exists. 422 "The config selects a model that is outside its allowed hours" [C] |
| GET | `/agents/defaults?workspaceId=&language=` | Platform default config | Same schema as `config`. This is the only documented source of valid provider/model/voice values [C]/[I] |
| GET | `/agents/{agentId}?workspaceId=` | Agent with config | [C] |
| PUT | `/agents/{agentId}` | Update | Body `{agentId*, workspaceId*, name?, config?, commitMessage?, commitDescription?}`. There is **no PATCH** [C]. Merge vs replace of omitted config sections is [ND]. The safe pattern is GET → modify → PUT the full config [I] |
| DELETE | `/agents?agentId=&workspaceId=` | Delete agent and all its versions | [C] |
| GET | `/agents?workspaceId=` | List (no config in rows) | `limit` ≤100 [C] |
| GET/PUT | `/agents/{agentId}/insights` | Structured-data fields for the agent | The PUT creates a new **unpublished** version [C] |

- **Required config.** If `config` is sent on POST it must contain `llmConfig{provider, model, systemPrompt}`,
  `ttsConfig{provider, voiceId}`, `sttConfig{provider}` and `complianceConfig` (4 booleans, all
  default false) [C]. What POST does with **no** config is [ND]. The UI creates agents "with default
  settings" [C].
- **Provider, model and voice values.** `provider`, `model` and `voiceId` are free strings with **no enum and no
  models endpoint** [C]. The only example in the spec is `openai`/`gpt-4o`,
  `elevenlabs`/`eleven_multilingual_v2`, `deepgram`/`nova-2` [C].
- **Unknown keys.** No level of the config schema sets `additionalProperties: false`. The spec's own
  example sends undefined keys. Whether unknown keys are stored, stripped or rejected is [ND].
- **Unique names.** Agent names are unique per workspace (409), so repeated builder runs need unique names or
  cleanup [C]/[I].

## 5. Agent configuration (checklist 3)

The full field tree, with types, defaults and enums, is in [agent_config_schema.md](freya_api/agent_config_schema.md).
The live spec has **no descriptions** on agent-config fields, so field meanings are [I] unless a guide says otherwise.

| Concern | Field (under `config`) | Key facts [C] unless tagged |
|---|---|---|
| Instructions | `llmConfig.systemPrompt` | string, 1–200 000 chars, required |
| Post-history prompt | `llmConfig.postHistoryPrompt` | ≤200 000. Purpose [ND] |
| Greeting | `llmConfig.firstMessage` | ≤2000, default null |
| Who speaks first | `llmConfig.firstMessageMode` | `assistant-speaks-first` · `assistant-speaks-first-with-model-generated-message` · `assistant-waits-for-user` (**default**) |
| LLM | `llmConfig.provider`, `.model`, `.temperature` (0–2, default 0.7), `.maxTokens` (1–4000, default 1000) | Custom endpoints via `baseUrl`, `apiKey`, `clientType` (`freya`/`openai`) |
| Other messages | `llmConfig.farewellMessage`, `.retryExhaustionMessage` | ≤2000 each. When used: [ND] |
| Tools | `llmConfig.tools[]` | See §8 |
| Voice / STT | `ttsConfig{provider*, voiceId*, model, language="multi", …}`, `sttConfig{provider*, model, language="multi", confidenceReask…}` | Valid voice IDs [ND] |
| Turn-taking | `ttsConfig.startSpeakingPlan`, `.stopSpeakingPlan`, `turnAnalyzerConfig` | |
| Call limits | `callTimeoutSettings{maximumDuration (0–14400, default 600), silenceTimeout, maxRetries, …}` | Units probably seconds [I] |
| Voicemail / DTMF | `voicemailDetection{…}`, `dtmfConfig{…}` | |
| Post-call analysis | `postConversationAnalysis{insights[] (≤200), summaryPrompt, autoDetectProblems, problemDetectionPrompt, analysisModel, …}` | |
| Safety | `guardrailsConfig{rules[], refuse_message, …}`, `piiRedactionConfig{…}`, `privacyConfig{…}`, `complianceConfig{pciDss, mifidIi, euAiAct, soc2}` | Runtime effect of each [ND] |
| Misc | `routingLlmConfig`, `extractionLlmConfig`, `testVariables` (string map), `backgroundSoundUrl`, `syncSource` | Purpose of `testVariables` [ND] |

## 6. System prompts, instructions and variables (checklist 4)

- **The system prompt** is `config.llmConfig.systemPrompt` [C].
- **Template syntax** `{{variable}}` is documented in the guides only
  (<https://docs.freyavoice.ai/getting-started/iterating-agents>,
  <https://docs.freyavoice.ai/guides/features/campaigns>). The live spec contains no `{{` at all [C].
- **Where per-conversation values go** [C]:
  - `POST /chat/message` → `customerVariables`
  - `POST /call` → `properties` ("Custom properties to pass to the agent")
  - `POST /campaign` → `customers[].properties`
  - `POST /simulations` → `customerVariablesMap {personaId: {var: value}}`
  - Embed SDK → `customerVariables` ("injected into the agent's system prompt at runtime")
- **Untested points.** That API chats and calls actually fill `{{var}}` is [I]. Built-in variables, behaviour on
  missing variables, and substitution in `firstMessage` or tools are all [ND]. **The call record does not echo the
  variables it received** [C], so a misspelled variable would fail silently [I].
- **AI Studio** (the prompt-improvement assistant) is **UI only**, with no API [C].

## 7. Conversation workflows (checklist 5)

- **API.** The API is **read-only for workflows**: `GET /workflow`, `GET /workflow/{id}`,
  `GET /workflow/templates`. There is no POST, PUT or DELETE [C]. The live spec types the workflow definition as `{}` [C].
- **Changing existing workflows.** Workflows that already exist can be changed through `POST /versions/workflow/{id}` (snapshot
  "applied to the working copy") and through branches [C]. They can be chatted with via
  `POST /chat/message {workflowId}` [C].
- **UI model.** The guides describe a UI node model: Agent, Function, Condition, Transfer, Wait and Loop nodes [C]
  (<https://docs.freyavoice.ai/guides/fundamentals/workflows>).
- **Runtime.** The stale spec's workflow schema (`initial_node`, `nodes{role_messages, task_messages, functions,
  context_strategy…}`) matches Pipecat Flows, and `/chat/end` mentions "pipecat" [C]. So the runtime is
  probably Pipecat [I].
- **Superseded.** We earlier concluded that a single agent is the only entity creatable through the
  *public* API. The hackathon requires a **workflow**, and the kit's `freya.py` creates and updates one,
  so the kit documents what the public spec omits. Check the kit's `docs/` before relying on anything here.

## 8. Tools and function calls (checklist 6)

- **Tool shape.** `config.llmConfig.tools[]` items [C]:
  ```
  { type: "function",
    function: { name*, handler*, description*, parameters* {type, properties, required, items}, transition_to? },
    config?: { maxPerNTurns, alwaysRunsAt: [each_turn|start_of_call|end_of_call], timeoutMs,
               maxRetries 0–5, preSpeech {mode* static|auto, message, …}, interruptible },
    response_mapping?: [{path, variable, description}],
    extraction_schema?: [{name, type string|integer|float|boolean|date|datetime|enum, …}],
    pre_process_code?, post_process_code? }
  ```
- **`handler`.** It is a free string. **Allowed values are [ND].** The tool schema has **no URL, method or headers
  field**, so how an HTTP or webhook tool is wired is [ND] [C]. The stale spec lists
  `__function__:end_call`, `__function__:transfer_call` and `__function__:reschedule_call`, but only for
  workflow nodes [C]. Whether they work as agent tool handlers is [I] and needs a test.
- **End call / transfer.** There are no dedicated tool types for these in the live agent schema [C]. Chat replies include
  `endedByAgent` [C].
- **Integrations.** The guides say "Functions are the primary way agents interact with external systems" [C].
  `GET /integrations?detail=true` lists Nango-backed integrations and their actions [C]. How an integration
  becomes an agent tool is [ND].
- **Knowledge base.** Workspace-level, beta, automatically available to all agents [C]. **There is no API
  to create or upload KB content** [C].
- **Importance.** The public event page says the builder turns "a task description and the available
  tools" into an agent (see `docs/hackathon_notes.md`). The tool format must come from the starter kit or from
  experiments.

## 9. Versions and publishing

- **Endpoints.** `GET|POST /versions/{agent|workflow}/{entityId}`, `GET /versions/.../{versionId}`, `GET .../graph` [C].
  `POST` creates a version from a `configSnapshot`, returning 422 if the snapshot is invalid, and applies it to the working copy [C].
- **Published flag.** Versions carry `isPublished`, `publishedAt` and `publishedBy` [C].
- **Publishing.** The **only documented publish path** is `POST /branches/{branchId}/rebase {publish: true, force?}`.
  It returns 409 if the head's checks are failing, running or not run, unless `force` is true [C].
- **What runs.** For insights the docs say "Calls use the new set once that version is published" [C]. Whether that applies to
  all config edits is [I]. **Which version runs** in chat, simulations and calls when no version ID is given is [ND].
  Version selectors exist: `chat/message.versionId`, `simulations.agentVersionId`,
  `call.entityVersionId` [C].
- **Rollback.** The live spec has no rollback endpoint (the stale spec had one) [C].

## 10. Simulation capabilities (checklist 7)

- **Personas.**
  - `POST /personas` creates 1–200 at a time. Fields: `name*`, `prompt*`, `successCriteria`, `systemPrompt`,
    `evaluationPrompt`, `tags`, `agentIds` [C]. The role of each prompt field is [ND] ([I]: `prompt` = scenario,
    `successCriteria` = judged goal).
  - `POST /personas/preview {agentId, prompt, count 1–50}` generates personas with AI but doesn't save them [C]/[I].
- **Create a simulation.** `POST /simulations` takes:
  - `name*`, `agentId*`, `selectedPersonaIds*`
  - `agentVersionId`
  - `mode` voice|chat (default voice)
  - `assertions` (uuid[])
  - `customerVariablesMap`
  - `runsPerPersona` 1–50, `maxConcurrentCalls`, `maxCallDurationSeconds` 60–3600, `maxRetries`
  - `start` (false → draft; then `POST /simulations/{id}/start`)
  - LLM overrides for assistant, persona and analysis [C]

  Live response defaults: concurrency 1, 240 s per call, 3 retries, 1 run per persona [C].
- **Results are async.**
  - `GET /simulations/{id}` gives status `draft|running|paused|completed`, metrics and `latestPassRate`.
  - **A simulation can get stuck in `running`** after all its calls ended (10 Oct, 1f458199: calls ended 21:16 UTC,
    status still `running` at 21:55). It blocks every new simulation ("concurrent simulations"), and the kit's
    `run_simulation` polls with no timeout. `PUT /simulations/{id}` with `{"status": "paused"}` (live spec; not in the
    kit) set it to `paused`, keeping its data, and the next queued simulation started 1 s later [C, user-approved].
  - **Pause does not stop the platform's own retries** (11 Oct, 6d0c9464): runs carry `attempts`/`maxAttempts`
    (`maxAttempts` 4 = 3 retries, the default; the kit's `run_simulation` does not set `maxRetries`). During the
    09:38-12:07 UTC degradation a simulation paused at 11:22 restarted runs 11:38-12:06, and after a second
    `PUT status=paused` (12:08:11, status read back `paused`) it still started a retry at 12:09:28. Retries stop only
    when each run reaches `maxAttempts`. The live spec's PUT also accepts `status: completed` and `maxRetries`;
    their effect on queued retries is [ND] (untested) [C: GET /simulations/{id}/iterations/{it} 12:14 UTC,
    `runs/dev/r4/6d0c9464-iteration-1214.json`].
  - `GET /simulations/{id}/iterations` gives passed, failed, inconclusive, error and analyzing counts, `passRate` and `agentVersionId`.
  - `GET /simulations/version-checks` and `GET /simulations/version-persona-runs` take `workspaceId` and `entityVersionId`.
  - `POST /simulations/{id}/rerun` starts a new iteration [C].
- **Assertions** appear on `GET /simulations/{id}` as `{id, name, prompt, contextConfig}`, but **no API
  creates or lists them** [C]. The pass/fail/inconclusive rule is [ND].
- **Finding the calls.** `GET /call` has **no `simulationId` filter**, but list rows include `simulationId` [C]. Bulk run data is
  available via `POST /export` on the simulation-iteration endpoint [C].

## 11. Evaluation and testing endpoints (checklist 8)

**Chat API** (<https://docs.freyavoice.ai/api-reference/chat/send-a-chat-message>) [C]:
- **Sending turns.** `POST /chat/message {message* (1–10 000), agentId|workflowId (first turn), callId (later turns),
  versionId?, customerVariables?, fromMessageId? (branch)}` returns `{response, callId, messageId,
  endedByAgent?, warning?}`.
  - Each turn is answered synchronously.
  - Possible errors: 502/503/504 (agent service unreachable, not configured or timed out), 409 (no resume anchor), 422 (variables too large).
- **Forking.** `POST /chat/fork {parentCallId*, fromMessageId*, versionId?|agentId?|workflowId?}` copies a conversation
  prefix onto another version or entity.
- **Closing.** `POST /chat/end {callId}` is idempotent. It fires "webhook + post-conversation analysis + end-of-call
  tools". Analysis runs async.
- **Open questions.** `message` is required even on the first turn, so a chat always starts with the user. How
  `firstMessage` behaves in chat is [ND]. Whether tools execute during chat turns is [ND].

**Unit tests** [C]:
- **Create.** `POST /unit-tests {workspaceId*, entityType* agent|workflow, entityId*, input* {schemaVersion: 1, callType
  web|voice, messages[]≥1, customerVariables?}, expectation?, assertions? (≤50)}`. Assertion types are
  `routing`, `extraction` and `tool_call`.
- **Run.** `POST /unit-tests/run-all {workspaceId, entityType, entityId, entityVersionId?, mockToolResults?,
  repeat 1–20}` returns 202 with `runIds`.
- **Poll.** Poll `GET /unit-tests/runs/{runId}` until `outcome` is `pass|fail|error`. The response includes `verdictReason`,
  `agentResponse` and `assertionResults`.

**Insights (structured data)** [C]:
- `POST /insights {name, type string|number|rating|checkbox|range|enum|array, …}` defines a field.
- `PUT /agents/{id}/insights` assigns fields to an agent.
- Values appear in `call.insights`.

**Per-call results.** `GET /call/{callId}?workspaceId=` returns `assertionResults[{name, success, reason, …}]`,
`assertionsSummary`, `successCriteriaResult`, `problems[]`, `summary` and `endedReason` [C]. That chat calls
appear there is [I].

## 12. Python SDKs (checklist 9)

- **No official SDK found** [C]:
  - **PyPI.** `freya` and `pyfreya` exist but are unrelated. `freyavoice`, `freya-voice`, `freyavoice-sdk` and similar names → 404.
  - **npm.** Searching "freyavoice" returns 0 results.
  - **GitHub.** The official GitHub org `freyavoiceai` has only `FreyaTTS`, a TTS model.
- **Docs examples** use plain `requests` and `websockets` (Python) and `fetch` (Node) [C].
- **Code generation.** The spec has unique `operationId`s, but only 28 named component schemas. Agent, chat and simulation schemas are
  inline, so generated clients would have anonymous models [C]. A thin hand-written client is
  likely simpler [I].
- **Embed SDK.** It is a browser WebRTC client loaded from `https://app.freyavoice.ai/freya-client.js`, not
  a backend SDK [C].

## 13. API limitations and hard caps (checklist 10)

- **Missing APIs** [C]:
  - Workflow creation. Missing from the *public* spec only; the kit's `freya.py` provides create, update and export
  - Assertion creation or listing
  - Knowledge-base management
  - Models or voices list
  - Rollback
  - Per-endpoint permission map
- **Hard caps** [C]:
  - **Agent fields.** Name 1–100 (unique). `systemPrompt` ≤200 000. `firstMessage` ≤2000. `maxTokens` ≤4000.
    `temperature` 0–2. `maximumDuration` ≤14 400. Insights per agent ≤200.
  - **Chat and simulations.** Chat `message` ≤10 000. Personas 1–200 per POST, preview `count` ≤50. Simulations: personas
    ≤1000, `runsPerPersona` ≤50, `maxCallDurationSeconds` 60–3600, `maxConcurrentCalls` ≤1000.
  - **Unit tests.** ≤50 assertions per test. `run-all`: `unitTestIds` ≤200, `repeat` ≤20.
  - **Export.** `export-raw` ≤10 000 calls.
- **Model availability** can depend on time ("model … outside its allowed hours", 422) [C].
- **Credit cost** of chats, simulations and unit tests is [ND]. Balance: `GET /workspaces/{id}/credits` [C].

## 14. Rate limits (checklist 11)

- **No numeric platform rate limits are documented** in either the guides or the spec [C].
- **Per-key limits.** API keys can carry an optional `rateLimit {requestsPerMinute, requestsPerDay}`. The defaults are [ND] [C].
- **429s.** Only `POST /export` and `POST /workspaces/invitations` declare a 429. No `Retry-After` or `X-RateLimit-*`
  headers are declared [C]. The STT model API declares 429 [C].
- **Concurrency caps.** Simulations: `maxConcurrentCalls` 1–1000, default 1. Campaigns: `maxConcurrency` 1–50, default 5 [C].
- **Guidance.** The best-practices page says to "Respect API rate limits and implement backoff strategies" [C].

## 15. Logging and debugging (checklist 12)

- **`GET /call/{callId}`.** This is the main per-conversation record [C]:
  - **Content:** `transcript`, `messages[]` (role, message, timing, `messageId`), `summary` and `endedReason` (free string).
  - **Evaluation:** `assertionResults`, `successCriteriaResult` and `problems[]` (AI-diagnosed issues by type).
  - **Linkage and measurement:** `insights`, `turnLatencyStats`, `entityVersionId`, `simulationId` and `cost`.
  - **Gaps:** the record has no typed tool-call field (`analysis` and `artifact` are untyped) and no `logs` field [C]. Message
    `role` values are [ND].
- **`POST /call/export-raw {workspaceId, callIds[]}`.** Returns 202 and a `jobId` [C]:
  - The ZIP contains `traces/<callId>.json.gz` and `logs/<callId>.json.gz` ("gzip-compressed OTel traces and
    application logs, management only").
  - Poll `GET /export/{jobId}`, then download with `GET /export/{jobId}/download`.
- **`GET /alerts/events?callId=&sources=tool,llm,stt,tts`** returns runtime error events per call [C].
- **`GET /feedbacks?callId=`** returns AI or user feedback on a call [C].
- **End-of-call webhook.** It carries summary, transcript, `endedReason`, timing and recording URL. It has no assertions or tool calls [C].
  How to configure its URL is [ND].
- **Audit log.** `GET /workspaces/logs` covers workspace events, not call execution [C].
- **Our own run artefacts.** Nothing on Freya's side replaces saving our own request/response pairs under
  `runs/` [I].

## 16. Contradictions found in the docs

- **Temperature range.** The guides say temperature 0–1; the spec says 0–2. The guide fields "Voice Speed/Stability" and function "Endpoint" don't
  exist in the spec [C].
- **`maxCallDurationSeconds` default.** The doc page says 60; the live response schema says 240 [C].
- **Required fields for `POST /call`.** The description says `callerNumber` is required; the schema requires only `phoneNumber` and
  `workspaceId` [C].
- **Workspace settings.** The guide's `outboundEnabled` and credit allowances are not in the live
  `workspaceSettings` schema [C].
- **Platform TTS output format.** `POST /audio/speech` declares `response_format` enum `["wav"]`, but its 200 response
  lists mpeg, wav and ogg [C].
- **Support email domain.** It is `support@freyavoice.com` in the spec but `support@freyavoice.ai` on the website [C].

- **`nodePositions`.** kit/docs/workflow-format.md lists it as an optional top-level key ("Layout for the visual
  editor"). A dry-run POST with it in the definition returns 400 `Unrecognized key: "nodePositions"` (2026-10-10). GET
  returns `nodePositions` and `canvasViewport` on the workflow record, outside the definition. No documented write
  path; the dashboard's ⋮ → Organize lays the nodes out [C].

## 17. Open questions → answer from the kit first

The official rules say **"Do not probe or load-test the platform"** and allow **one key per team**, so
we answer these by reading the kit's `docs/`, `freya.py` and `examples/minimal_builder.py` first. Only
then, if still needed, do we make a few deliberate calls through the kit's own client, logged under `runs/`:

1. The workflow format: steps, per-step prompts and tools, conditional routes, and the code-node language and runtime.
2. How tools bind to the bank's tool API (the kit's `tools/openapi.json`). This replaces the unknown `handler` question for
   workflows.
3. How the `now` variable and per-case customer variables reach the workflow.
4. Create vs update semantics and which version the simulator runs (published vs draft).
5. The ids `run_cases.py` expects (`<agent_id>`) vs the workflow id; what `export_workflow` produces.
6. Whether any Freya-side test tool (chat, unit tests) is permitted and useful for the builder's own
   self-tests within the 30-minute budget.
