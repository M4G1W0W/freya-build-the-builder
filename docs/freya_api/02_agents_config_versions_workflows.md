> Verified research notes, generated 2026-10-10 from the public docs snapshot in `docs/reference/` (the live spec is `docs/reference/freya_openapi_live.json`). Each claim was checked by a separate fact-checking pass against the sources. Tags: **[Confirmed]** = stated in the docs or spec; **[Inferred]** = our reasoning; **[Not documented]** = not in any source. Curated summary: `docs/freya_api_notes.md`.

## Agents, versions / branches / publishing, workflows (programmatic configuration)

**Sources.** The canonical source is the live spec `freya_openapi_live.json` ("Freyavoice API" 2.0.0, OpenAPI 3.1.0, base `https://app.freyavoice.ai/api/v2`). Every response is wrapped as `{success, data:{message, result}}` **[Confirmed]**. Auth is a Bearer API key, which the docs say is "tied to your workspace" **[Confirmed]** (https://docs.freyavoice.ai/api-reference/authentication). The API-reference pages (https://docs.freyavoice.ai/api-reference/...) embed operations from the staging spec URL `https://staging-app.freyavoice.ai/api/openapi.json`. They cover 152 of the 180 live operations; for example, `PATCH /branches/{branchId}` has no page. Their schema details can lag the live spec; for example, the create-agent page has no `postHistoryPrompt` **[Confirmed]**.

**Full field tree (241 config paths, each with type, required flag, default and enum):** `docs/freya_api/agent_config_schema.md`. The one-line meanings in that file are **[Inferred]**, because the live spec gives no `description` for any agent-config property.

### 1. Endpoints (live spec)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | /agents | List agents | Query: `workspaceId` (required), `limit` 1-100 (default 50), `offset`, `search`, `sortBy`, `sortOrder`, `entityType` = workflow / agent / all (default all). List items have no `config`. **[Confirmed]** |
| POST | /agents | Create agent | Body: `name` (required, 1-100), `language` (max 10), `config`. Returns 201. Errors: 409 "An agent with this name already exists"; 422 "The config selects a model that is outside its allowed hours". **[Confirmed]** |
| GET | /agents/{agentId} | Get agent with config | Query `workspaceId` is required. **[Confirmed]** |
| PUT | /agents/{agentId} | Update agent | Body: `agentId` and `workspaceId` (both required), plus `name`, `config`, `commitMessage` (max 200), `commitDescription` (max 5000). No PATCH exists on agents. **[Confirmed]** |
| DELETE | /agents | Deletes "an agent and all associated versions" | `agentId` and `workspaceId` are passed as query params. **[Confirmed]** |
| GET | /agents/defaults | Platform default config | Query: `workspaceId` (required), `language` (optional, max 10). **[Confirmed]** |
| GET / PUT | /agents/{agentId}/insights | Read or replace structured-data field IDs | PUT body: `{workspaceId, insightIds:number[]}`. PUT creates a new **unpublished** version. **[Confirmed]** |
| GET | /versions/{entityType}/{entityId} | List versions, plus `openBranches` | `entityType` = agent / workflow. `entityId` is required both in the path and as a query param. `workspaceId` is required. `limit` max 100. **[Confirmed]** |
| POST | /versions/{entityType}/{entityId} | Create a version from `configSnapshot` | Body: `entityId`, `workspaceId`, `configSnapshot` (required), `parentVersionId`, `description`. The snapshot is validated and "applied to the working copy"; 422 if invalid. **[Confirmed]** |
| GET | /versions/{entityType}/{entityId}/{versionId} | Get one version with its full `configSnapshot` | `entityId` and `versionId` are also required as query params. **[Confirmed]** |
| PUT | /versions/{entityType}/{entityId}/{versionId} | "Updates version metadata." | The spec defines **no request body**. Which fields can be changed: **[Not documented]** |
| GET | /versions/{entityType}/{entityId}/graph | Commit graph, branches, check status per node | `limit` max 1000. **[Confirmed]** |
| GET / POST | /branches | List or create a branch | POST requires `entityType` (agent / workflow / persona / kb_document), `entityId` and `name`. Also accepts `config` (full snapshot) or `patch` (ops add / remove / replace / test), `baseVersionId`, `description`, `closesFeedbackIds`. **[Confirmed]** |
| GET / PATCH | /branches/{branchId} | GET: merge view (commits, net change, closed issues, dry-run conflict preview). PATCH: rename or redescribe an open branch | PATCH has no page on the docs site. **[Confirmed]** |
| POST | /branches/{branchId}/commit | Add a full-snapshot commit to the branch | Body: `config` or `patch`, `name`, `description`, `expectedHeadVersionId`. **[Confirmed]** |
| POST | /branches/{branchId}/rebase | **Merge.** "Apply" makes a mainline draft; "Apply & Publish" also publishes | Body: `publish`, `force`, `resolutions[{path, editedValue}]`. Returns `newVersionId`, `published`, `conflicts`, `checksState`. **[Confirmed]** |
| POST / GET | /branches/{branchId}/discard, /activity | Discard a branch; list its commits, simulations and unit-test runs | **[Confirmed]** |
| GET | /workflow, /workflow/{workflowId}, /workflow/templates | List workflows, get one, list templates | **GET only.** **[Confirmed]** |
| GET / PUT | /custom/abbreviations | Read or replace TTS `textSubstitutions` on an agent or workflow | Target by `id` or `name`. PUT replaces the whole list and "creates a new version". **[Confirmed]** |

### 2. Create body (`POST /agents`): required fields and the fields that matter

**Minimum fields per the schema [Confirmed]:**
- `name`.
- If `config` is sent, it must contain:
  - `llmConfig.{provider, model, systemPrompt}`
  - `ttsConfig.{provider, voiceId}`
  - `sttConfig.provider`
  - `complianceConfig` (an object of 4 booleans, all default false)

`config` itself is not in the top-level `required` list. What the server does with a POST that has no config: **[Not documented]**.

The POST schema has no `workspaceId`, although the spec's own example sends one **[Confirmed]**. The workspace presumably comes from the API key **[Inferred]**.

| Concern | Field (under `config`) | Type / enum / default |
|---|---|---|
| System prompt / instructions | `llmConfig.systemPrompt` | string, 1-200000 chars, required **[Confirmed]** |
| Prompt placed after history | `llmConfig.postHistoryPrompt` | string or null, max 200000. What it does: **[Not documented]** |
| Greeting | `llmConfig.firstMessage` | string or null, max 2000, default null **[Confirmed]** |
| Who speaks first | `llmConfig.firstMessageMode` | `assistant-speaks-first`, `assistant-speaks-first-with-model-generated-message`, `assistant-waits-for-user`, or null. **Default: `assistant-waits-for-user`** **[Confirmed]** |
| Interrupting the greeting | `llmConfig.disableInterruptionsDuringFirstMessage` | bool, default false **[Confirmed]** |
| LLM | `llmConfig.provider`, `llmConfig.model` | Free strings (max 50 / max 100), **no enum**. The only example is `openai` / `gpt-4o` **[Confirmed]**. For a custom endpoint: `baseUrl`, `apiKey`, `clientType` = freya / openai / null **[Confirmed]**. List of valid providers and models: **[Not documented]** |
| Sampling | `llmConfig.temperature`, `maxTokens`, `maxContextWindow` | temperature 0-2 (default 0.7); maxTokens 1-4000 (default 1000); maxContextWindow 1024-10000000 **[Confirmed]** |
| Other LLM messages | `llmConfig.farewellMessage`, `llmConfig.retryExhaustionMessage` | max 2000 each. When they are used: **[Not documented]** |
| Voice (TTS) | `ttsConfig.*` | `provider` and `voiceId` are required. Also: `model` (default null), `language` (default "multi"), `additionalSettings` (free-form map), `startSpeakingPlan`, `stopSpeakingPlan`, `textSubstitutions[]`, `speechNormalization{...}`, `normalizationPrompt` **[Confirmed]**. Example: `elevenlabs` / `eleven_multilingual_v2` / `21m00Tcm4TlvDq8ikWAM`. List of valid voices for `ttsConfig`: **[Not documented]**. The standalone `POST /audio/speech` (voice `leyla`) and the Model APIs TTS (leyla, zeynep, alev, ali, alper, mustafa) enumerate their own voices, but neither is documented as valid for `ttsConfig.voiceId` **[Confirmed]** |
| Transcriber (STT) | `sttConfig.*` | `provider` is required. Also: `model` (default null), `language` (default "multi"), `additionalSettings`, and `confidenceReask` {enabled false, threshold 0.3, reaskMode phrase / llm, reaskPhrases, maxConsecutiveReasks 2} **[Confirmed]**. Example: `deepgram` / `nova-2` |
| Language | top-level `language`; `ttsConfig.language`; `sttConfig.language` | Top-level `language` exists on POST only (max 10). TTS and STT language default to "multi". `GET /agents/defaults?language=` returns localized defaults **[Confirmed]**. Allowed language codes for agent config: **[Not documented]** |
| Turn-taking / interruptions | `ttsConfig.startSpeakingPlan`, `ttsConfig.stopSpeakingPlan`, `turnAnalyzerConfig` | `startSpeakingPlan.waitSeconds` 0-5 (default 0.4). `stopSpeakingPlan`: `numberOfWords` 0-10 (1), `voiceSeconds` 0-0.5 (0.4), `backOffSeconds` 0-3 (0.4), `acknowledgementPhrases`, `interruptionPhrases`. `turnAnalyzerConfig.provider` = local / fal **[Confirmed]** |
| Max duration / silence | `callTimeoutSettings.*` | `maximumDuration` 0-14400 (default 600); `silenceTimeout` (default 0); `maxRetries` 0-10 (default 2); `checkInMessage`; `closureMessage`; `silenceTimeoutPrompt`; `maxDurationEndCall.messageMode` = llm / custom / none (default llm); `dynamicWait{...}` **[Confirmed]**. The units are probably seconds **[Inferred]** |
| Voicemail | `voicemailDetection.*` | `enabled` (default false); `messageMode` = llm / custom / none / detect_only (default detect_only); `staticMessage`; `voicemailResponseDelay` 0-30 (default 2) **[Confirmed]** |
| Keypad (DTMF) | `dtmfConfig.*` | `enabled` (false), `timeout` (2), `terminationDigit` ("#"), `prefix` ("DTMF: ") **[Confirmed]** |
| Post-call analysis | `postConversationAnalysis.*` | `insights[{id (digits only), name}]` (max 200), `summaryPrompt`, `autoDetectProblems`, `problemDetectionPrompt`, `problemDetectionInstructions`, `analysisModel` **[Confirmed]** |
| Other sections | see field tree | `privacyConfig` (fields `enableRecording`, `getRecordingConsent`, `recordingConsentText`, ...), `guardrailsConfig`, `piiRedactionConfig`, `routingLlmConfig`, `extractionLlmConfig`, `backgroundSoundUrl`, `syncSource`, `testVariables` (map of string to string) **[Confirmed]** |

### 3. Tools / function calls

- **There is one tool shape [Confirmed]:**
  - `type`: always `"function"`
  - `function`: `{name, handler, description, parameters:{type, properties, required, items}, transition_to?}` (the first four are required)
  - `config?`: `{maxPerNTurns, alwaysRunsAt[each_turn / start_of_call / end_of_call], timeoutMs, maxRetries 0-5, preSpeech{mode static / auto (required), message, interruptible, audio_asset_id, audio_loop, audio_volume}, interruptible}`
  - `response_mapping?`: `[{path, variable, description}]`
  - `extraction_schema?`: `[{name, type string / integer / float / boolean / date / datetime / enum, description, extraction_prompt, validation_pattern, max_retries, required, overridable}]`
  - `pre_process_code?`, `post_process_code?`
- **What `handler` accepts: [Not documented].** It is a free string in the live spec. There is also no URL, method or headers field, so how an HTTP / webhook tool's endpoint is configured is **[Not documented]**.
- **End call / transfer / reschedule.** The live agent schema has no dedicated tool types for these **[Confirmed]**.
  - The stale docs spec lists handlers `__function__:end_call`, `__function__:transfer_call` and `__function__:reschedule_call`, but only in the workflow schema (node `functions[]` and `globals[]`) **[Confirmed, stale spec only]**.
  - Whether those strings also work in `llmConfig.tools[].function.handler` is **[Inferred]** and needs a test.
  - The live spec does confirm that a `reschedule_call` tool exists (in the `originCallId` description on `POST /call`), and that chat replies include `endedByAgent` **[Confirmed]**.
  - Parameters for a transfer destination: **[Not documented]**.
- **Knowledge base.** It needs no per-agent configuration. It is "available to all agents in the same workspace automatically" and is in beta **[Confirmed]** (https://docs.freyavoice.ai/guides/features/knowledgebase). The live spec has no knowledge-base endpoints **[Confirmed]**.

### 4. Dynamic variables

- **Syntax:** `{{variable}}` in the prompt **[Confirmed]** (https://docs.freyavoice.ai/getting-started/iterating-agents, https://docs.freyavoice.ai/guides/features/campaigns).
- **Where per-conversation values go [Confirmed fields]:**
  - `POST /call` → `properties` ("Custom properties to pass to the agent")
  - `POST /campaign` → `customers[].properties`. Per the guide, variables in the prompt become columns in the customer table.
  - `POST /chat/message` → `customerVariables` (returns 422 "customerVariables too large")
  - `POST /simulations` → `customerVariablesMap` {personaId: {variable: string}}
  - Embed SDK → `customerVariables` ("Variables injected into the agent's system prompt at runtime")
- That `/call.properties` and `/chat/message.customerVariables` fill `{{var}}` placeholders is **[Inferred]**. The docs state it only for the campaign UI and the embed SDK.
- `POST /call` `attemptNumber` is "surfaced to the agent as 0-based call.retry_number" **[Confirmed]**. How to reference it in a template: **[Not documented]**.
- Not documented: what `testVariables` is for, and whether variables are substituted in `firstMessage` or in tool parameters **[Not documented]**.
- `response_mapping[].variable` probably saves tool output into variables **[Inferred]**.

### 5. Post-call analysis and success evaluation

- **Structured data uses workspace "Insights" [Confirmed].**
  - Define a field with `POST /insights`: `{name (required), description, type string / number / rating / checkbox / range / enum / array (default string), enums, defaultValue, rangeMin, rangeMax, isRequired (default true), label, valueLabels, source analysis / tool_field, toolName, toolFieldPath}`.
  - Attach fields to an agent with `PUT /agents/{agentId}/insights` **[Confirmed]**. Setting `postConversationAnalysis.insights` directly in the config is probably equivalent **[Inferred]**.
- **No success-evaluation field appears in the agent config schema [Confirmed].** The only trace is a campaign webhook category: "`llm_fail`: LLM evaluation failed (if successPrompt configured)". Where `successPrompt` is configured: **[Not documented]**.

### 6. Update semantics and response shape

- **Updates use `PUT /agents/{agentId}` only.**
  - On PUT every `config` section is optional, but nested required fields still apply (sending `llmConfig` means sending provider, model and systemPrompt) **[Confirmed]**.
  - Whether a section you leave out is kept (merge) or reset (replace): **[Not documented]**. The safe pattern is GET, modify, then PUT the whole `config` **[Inferred]**.
- **Response shape.** Create, update and get all return `data.result.agent{id, workspaceId, userId, name, entityType, workflowId, config, isImported, createdAt, updatedAt}`. **There is no `versionId`** **[Confirmed]**.
  - Version IDs come from `GET /versions/agent/{agentId}` **[Confirmed]**.
  - That a PUT creates a new version is **[Inferred]**, from the `commitMessage` / `commitDescription` fields and from the `/custom/abbreviations` description ("Behaves like a UI save: ... creates a new version").

### 7. Draft vs published, publishing, rollback

- **Published flag.** Versions carry `isPublished`, `publishedAt` and `publishedBy` **[Confirmed]**.
- **Calls run the published version.** This is stated for insights only: "saves the result as a new, unpublished version. Calls use the new set once that version is published" **[Confirmed for that endpoint]**. That the same rule applies to every config edit is **[Inferred]**.
- **Version fields per run.** Fields exist on `POST /call` (`entityVersionId`), `POST /chat/message` (`versionId`), `POST /chat/fork` (`versionId`) and `POST /simulations` (`agentVersionId`) **[Confirmed]**.
  - Only `/chat/fork` says it "retargets a different `versionId`" **[Confirmed]**. `/call` describes `entityVersionId` as the version "active during the call"; the chat and simulation fields have no description. That they select the version that runs is **[Inferred]**.
  - Not documented: which version runs when these are omitted (published or working copy), and what `GET /agents/{agentId}` returns.
- **Publishing through the API.** The only request field in the whole spec named `publish` is on `POST /branches/{id}/rebase` ("Apply & Publish") **[Confirmed]**.
  - The merge returns 409 when the head's checks are "failing, running, or not run unless `force` is true" **[Confirmed]**.
  - The API-key permission `versions:publish` exists **[Confirmed]**. Which endpoint checks it: **[Not documented]**.
  - Not documented: whether `PUT /versions/...`, `POST /versions` or `PUT /agents` can publish.
- **Rollback.**
  - The Versions tag description is "Version history and rollback for agents and workflows" **[Confirmed]**.
  - The live spec has **no rollback or activate endpoint** **[Confirmed]**. The stale spec's `POST /agents/{agentId}/versions/rollback` and "Activate agent version" endpoints are gone.
  - Possible route: fetch the old `configSnapshot`, then either `POST /versions/agent/{id}`, or create a branch from it and merge with `publish:true` **[Inferred]**.

### 8. `GET /agents/defaults`

- The spec describes it as: "Returns the platform default agent configuration (with language localization applied) used by the editor's reset-to-default controls."
- `data.result.config` has exactly the same schema as the POST `config` **[Confirmed]**.
- The actual default values (which provider, model and voice): **[Not documented]**. Finding out probably needs an authenticated call **[Inferred]**.
- It can likely be used as a create template: fetch it, override prompt, greeting and mode, then POST **[Inferred]**.

### 9. Workflows through the API

- **Read only for creation.** The Workflows tag has GET endpoints only, and no workflow path has POST, PUT, PATCH or DELETE **[Confirmed]**. Creating a new workflow by API: **[Not documented]**. The only documented way to insert workflows is `POST /call/import`, which inserts workflows bundled in a `/call/export-raw` ZIP and flags them `is_imported` **[Confirmed]**.
- **Existing workflows can be changed** through `POST /versions/workflow/{id}` (the snapshot is "applied to the working copy"), through branches with `entityType:"workflow"`, and through `PUT /custom/abbreviations` **[Confirmed]**. API-key permissions include `workflows:write` **[Confirmed]**.
- **Definition schema.**
  - The live spec types `workflow.workflow` as `{}` (anything) **[Confirmed]**.
  - The stale spec typed it as `{initial_node, nodes{<id>:{role_messages[], task_messages[], functions[], respond_immediately, context_strategy APPEND / RESET / RESET_WITH_SUMMARY, summary_prompt, agentId}}, globals[]}` **[Confirmed, stale only]**.
- **Workflow-agents.** Workflows also appear as agents with `entityType:"workflow"` and a `workflowId`, and can be driven with `POST /chat/message {workflowId}` **[Confirmed]**.

### 10. Doc and spec discrepancies (details in the discrepancies list)

- **Guide pages disagree with the live schema [Confirmed].** They describe:
  - "Temperature ... (0-1)", but the spec max is 2.
  - Voice Speed and Voice Stability, an agent Description, and a function Endpoint, none of which exist as live schema fields.
- **The live POST example sends fields the schema doesn't define [Confirmed]:** `workspaceId`, `ttsConfig.speed`, `stability`, `similarityBoost`, and `sttConfig.temperature`, `punctuate`, `diarize`.
- **The stale docs spec (`/api-reference/openapi.json`) uses an older agent model [Confirmed]:** `sstConfig`, `thinkingBudget`, `structuredDataSchema`, numeric agent IDs, and a `/agents/{agentId}/versions` API.