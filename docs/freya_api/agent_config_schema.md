# Freya agent config — field-tree reference

Generated 2026-10-10 from the LIVE spec `docs/reference/freya_openapi_live.json` (https://app.freyavoice.ai/api/openapi.json, OpenAPI 3.1.0, API v2.0.0), operations `POST /agents` (createAgent) and `PUT /agents/{agentId}` (updateAgent). The `config` schema is identical (parsed-JSON equality) in POST body, PUT body (except `required`), `GET /agents/{agentId}` response, `POST /agents` 201 response and `GET /agents/defaults` response.

**Legend.** `Req(POST)` / `Req(PUT)` = listed in the parent object's `required` array in that operation ([Confirmed], spec). A child is only required if its parent object is sent. `Default` and `Constraints` are copied verbatim from the spec ([Confirmed]). **`Note` column is [Inferred] unless it quotes a doc**: the live spec has NO `description` on any agent-config property, so every one-liner below is our reading of the field name/shape, not Freya documentation.

## Top-level request bodies

| Path | Type | Req(POST) | Req(PUT) | Default | Constraints | Note |
|---|---|---|---|---|---|---|
| `agentId` | string | — (not in POST) | **yes** | | format=uuid | PUT only; also in path. [Confirmed] |
| `workspaceId` | string | — (not in POST schema; appears in POST *example*) | **yes** | | format=uuid | API key is "tied to your workspace" (docs: api-reference/authentication). |
| `name` | string | **yes** | no | | minLength=1; maxLength=100 | 409 "An agent with this name already exists". |
| `language` | string | no | — (not in PUT) | | maxLength=10 | POST only. Values not enumerated. |
| `config` | object | no | no | | | see tree below; POST requires llmConfig, ttsConfig, sttConfig, complianceConfig *inside* config |
| `commitMessage` | string | — | no | | maxLength=200 | PUT only. Inferred: version commit subject. |
| `commitDescription` | string | — | no | | maxLength=5000 | PUT only. Inferred: version commit body. |

## `config` tree

| Path | Type | Req(POST) | Req(PUT) | Default | Constraints | Note ([Inferred] unless quoted) |
|---|---|---|---|---|---|---|
| `config` | object |  |  |  |  | Agent configuration object (identical schema in POST/PUT/GET/defaults). |
| `config.llmConfig` | object | **yes** |  |  |  | Conversation LLM settings. |
| `config.llmConfig.provider` | string | **yes** | **yes** |  | minLength=1; maxLength=50 | LLM provider id (free string; example "openai"). No enum documented. |
| `config.llmConfig.model` | string | **yes** | **yes** |  | minLength=1; maxLength=100 | LLM model id (free string; example "gpt-4o"). 422 if model outside its allowed hours. |
| `config.llmConfig.baseUrl` | string\|null |  |  |  | maxLength=2048; format="uri" | Custom endpoint for the LLM (BYO / OpenAI-compatible). |
| `config.llmConfig.apiKey` | string\|null |  |  |  | maxLength=500 | API key for custom LLM endpoint. |
| `config.llmConfig.clientType` | string\|null |  |  |  | enum=["freya", "openai", null] | Client protocol for custom endpoint. |
| `config.llmConfig.systemPrompt` | string | **yes** | **yes** |  | minLength=1; maxLength=200000 | THE system prompt / instructions. Supports {{variable}} placeholders (docs: iterating-agents, campaigns). |
| `config.llmConfig.postHistoryPrompt` | string\|null |  |  |  | maxLength=200000 | Prompt text placed after conversation history (semantics not documented). |
| `config.llmConfig.firstMessage` | string\|null |  |  | null | maxLength=2000 | Greeting text spoken first (used with firstMessageMode). |
| `config.llmConfig.firstMessageMode` | string\|null |  |  | "assistant-waits-for-user" | enum=["assistant-speaks-first-with-model-generated-message", "assistant-speaks-first", "assistant-waits-for-user", null] | Who speaks first and how the first message is produced. |
| `config.llmConfig.disableInterruptionsDuringFirstMessage` | boolean |  |  | false |  | If true, caller cannot barge-in during greeting. |
| `config.llmConfig.maxTokens` | integer |  |  | 1000 | minimum=1; maximum=4000 | Max tokens per LLM response. |
| `config.llmConfig.maxContextWindow` | integer\|null |  |  |  | minimum=1024; maximum=10000000 | Context-window cap in tokens. |
| `config.llmConfig.temperature` | number |  |  | 0.7 | minimum=0; maximum=2 | Sampling temperature. |
| `config.llmConfig.tools` | array |  |  | [] |  | Function/tool definitions available to the LLM (only type "function"). |
| `config.llmConfig.tools[]` | object |  |  |  |  |  |
| `config.llmConfig.tools[].type` | string | **yes** | **yes** |  | enum=["function"] | Only allowed value: "function". |
| `config.llmConfig.tools[].function` | object | **yes** | **yes** |  |  | OpenAI-style function definition plus Freya "handler". |
| `config.llmConfig.tools[].function.name` | string | **yes** | **yes** |  |  | Tool name shown to the LLM. |
| `config.llmConfig.tools[].function.handler` | string | **yes** | **yes** |  |  | Executor id for the tool. Allowed values NOT documented in live spec (stale spec lists __function__:end_call / __function__:transfer_call / __function__:reschedule_call for workflow nodes). |
| `config.llmConfig.tools[].function.description` | string | **yes** | **yes** |  |  | Tool description for the LLM. |
| `config.llmConfig.tools[].function.parameters` | object | **yes** | **yes** |  | map of any | JSON-Schema-like parameters object (type required; properties/required/items free-form). |
| `config.llmConfig.tools[].function.parameters.type` | string | **yes** | **yes** |  |  |  |
| `config.llmConfig.tools[].function.parameters.properties` | object |  |  |  | map of any |  |
| `config.llmConfig.tools[].function.parameters.required` | array |  |  |  |  |  |
| `config.llmConfig.tools[].function.parameters.required[]` | string |  |  |  |  |  |
| `config.llmConfig.tools[].function.parameters.items` | any |  |  |  |  |  |
| `config.llmConfig.tools[].function.transition_to` | string |  |  |  |  | Target node to transition to (workflow semantics; meaning in a plain agent not documented). |
| `config.llmConfig.tools[].config` | object |  |  |  |  | Per-tool runtime settings. |
| `config.llmConfig.tools[].config.maxPerNTurns` | integer |  |  |  | exclusiveMinimum=0 | Rate-limit: tool may run at most once per N turns (semantics not documented). |
| `config.llmConfig.tools[].config.alwaysRunsAt` | array |  |  |  |  | Auto-run the tool at these moments regardless of LLM choice. |
| `config.llmConfig.tools[].config.alwaysRunsAt[]` | string |  |  |  | enum=["each_turn", "start_of_call", "end_of_call"] |  |
| `config.llmConfig.tools[].config.timeoutMs` | integer |  |  |  | exclusiveMinimum=0 | Tool execution timeout (ms). |
| `config.llmConfig.tools[].config.maxRetries` | integer |  |  |  | minimum=0; maximum=5 | Tool retry count. |
| `config.llmConfig.tools[].config.preSpeech` | object |  |  |  |  | What the agent says/plays while the tool runs. |
| `config.llmConfig.tools[].config.preSpeech.mode` | string | **yes** | **yes** |  | enum=["static", "auto"] | static = fixed message; auto = generated. |
| `config.llmConfig.tools[].config.preSpeech.message` | string |  |  |  |  |  |
| `config.llmConfig.tools[].config.preSpeech.interruptible` | boolean |  |  |  |  |  |
| `config.llmConfig.tools[].config.preSpeech.audio_asset_id` | string |  |  |  |  |  |
| `config.llmConfig.tools[].config.preSpeech.audio_loop` | boolean |  |  |  |  |  |
| `config.llmConfig.tools[].config.preSpeech.audio_volume` | number |  |  |  |  |  |
| `config.llmConfig.tools[].config.interruptible` | boolean |  |  |  |  | Whether caller can interrupt during tool execution. |
| `config.llmConfig.tools[].response_mapping` | array |  |  |  |  | Map fields of the tool response (path) into named variables. |
| `config.llmConfig.tools[].response_mapping[]` | object |  |  |  |  |  |
| `config.llmConfig.tools[].response_mapping[].path` | string | **yes** | **yes** |  |  |  |
| `config.llmConfig.tools[].response_mapping[].variable` | string | **yes** | **yes** |  |  |  |
| `config.llmConfig.tools[].response_mapping[].description` | string |  |  | "" |  |  |
| `config.llmConfig.tools[].extraction_schema` | array |  |  |  |  | Typed fields to extract/collect for the tool (with validation/retries). |
| `config.llmConfig.tools[].extraction_schema[]` | object |  |  |  |  |  |
| `config.llmConfig.tools[].extraction_schema[].name` | string | **yes** | **yes** |  |  |  |
| `config.llmConfig.tools[].extraction_schema[].type` | string | **yes** | **yes** |  | enum=["string", "integer", "float", "boolean", "date", "datetime", "enum"] |  |
| `config.llmConfig.tools[].extraction_schema[].description` | string |  |  |  |  |  |
| `config.llmConfig.tools[].extraction_schema[].extraction_prompt` | string |  |  |  |  |  |
| `config.llmConfig.tools[].extraction_schema[].validation_pattern` | string |  |  |  |  |  |
| `config.llmConfig.tools[].extraction_schema[].max_retries` | integer |  |  |  | minimum=0 |  |
| `config.llmConfig.tools[].extraction_schema[].required` | boolean |  |  |  |  |  |
| `config.llmConfig.tools[].extraction_schema[].overridable` | boolean |  |  |  |  |  |
| `config.llmConfig.tools[].pre_process_code` | string\|null |  |  |  |  | Code run before the tool call (language/runtime not documented). |
| `config.llmConfig.tools[].post_process_code` | string\|null |  |  |  |  | Code run after the tool call (language/runtime not documented). |
| `config.llmConfig.additionalSettings` | object\|null |  |  | {} | map of any | Free-form provider-specific LLM settings. |
| `config.llmConfig.retryExhaustionMessage` | string\|null |  |  |  | maxLength=2000 | Message when retries are exhausted (which retries: not documented). |
| `config.llmConfig.farewellMessage` | string\|null |  |  |  | maxLength=2000 | Goodbye message (when it is spoken: not documented). |
| `config.ttsConfig` | object | **yes** |  |  |  | Text-to-speech (voice) settings. |
| `config.ttsConfig.provider` | string | **yes** | **yes** |  | minLength=1; maxLength=50 | TTS provider id (free string; example "elevenlabs"). |
| `config.ttsConfig.model` | string\|null |  |  | null | maxLength=100 | TTS model (example "eleven_multilingual_v2"). |
| `config.ttsConfig.voiceId` | string | **yes** | **yes** |  | minLength=1; maxLength=100 | Voice id (example "21m00Tcm4TlvDq8ikWAM"). |
| `config.ttsConfig.language` | string\|null |  |  | "multi" | minLength=1 | TTS language; default "multi". |
| `config.ttsConfig.baseUrl` | string\|null |  |  |  | maxLength=2048; format="uri" |  |
| `config.ttsConfig.apiKey` | string\|null |  |  |  | maxLength=500 |  |
| `config.ttsConfig.clientType` | string\|null |  |  |  | enum=["freya", "openai", null] |  |
| `config.ttsConfig.additionalSettings` | object\|null |  |  | {} | map of any | Free-form provider-specific TTS settings (speed/stability are NOT schema fields in live spec). |
| `config.ttsConfig.startSpeakingPlan` | object\|null |  |  |  |  | Turn-taking: when the agent starts speaking after the user stops. |
| `config.ttsConfig.startSpeakingPlan.waitSeconds` | number |  |  | 0.4 | minimum=0; maximum=5 | Delay before agent starts speaking. |
| `config.ttsConfig.startSpeakingPlan.backgroundNoisePhrases` | array\|null |  |  |  | maxItems=200 | Phrases treated as background noise (not a turn). |
| `config.ttsConfig.startSpeakingPlan.backgroundNoisePhrases[]` | string |  |  |  | minLength=1; maxLength=100 |  |
| `config.ttsConfig.stopSpeakingPlan` | object\|null |  |  |  |  | Interruption: when user speech stops the agent. |
| `config.ttsConfig.stopSpeakingPlan.numberOfWords` | integer |  |  | 1 | minimum=0; maximum=10 | Words user must say to interrupt. |
| `config.ttsConfig.stopSpeakingPlan.voiceSeconds` | number |  |  | 0.4 | minimum=0; maximum=0.5 | Seconds of user voice to interrupt. |
| `config.ttsConfig.stopSpeakingPlan.backOffSeconds` | number |  |  | 0.4 | minimum=0; maximum=3 | Back-off after interruption before resuming. |
| `config.ttsConfig.stopSpeakingPlan.acknowledgementPhrases` | array\|null |  |  |  | maxItems=200 | Backchannel phrases that should NOT interrupt. |
| `config.ttsConfig.stopSpeakingPlan.acknowledgementPhrases[]` | string |  |  |  | minLength=1; maxLength=100 |  |
| `config.ttsConfig.stopSpeakingPlan.interruptionPhrases` | array\|null |  |  |  | maxItems=200 | Phrases that always interrupt. |
| `config.ttsConfig.stopSpeakingPlan.interruptionPhrases[]` | string |  |  |  | minLength=1; maxLength=100 |  |
| `config.ttsConfig.textSubstitutions` | array\|null |  |  |  |  | TTS pronunciation rules (also editable via PUT /custom/abbreviations). |
| `config.ttsConfig.textSubstitutions[]` | object |  |  |  |  |  |
| `config.ttsConfig.textSubstitutions[].pattern` | string | **yes** | **yes** |  | minLength=1; maxLength=500 |  |
| `config.ttsConfig.textSubstitutions[].replacement` | string | **yes** | **yes** |  | maxLength=500 |  |
| `config.ttsConfig.textSubstitutions[].caseInsensitive` | boolean |  |  |  |  |  |
| `config.ttsConfig.speechNormalization` | object\|null |  |  |  |  | Toggles for verbalizing emails/URLs/numbers/etc. before TTS. |
| `config.ttsConfig.speechNormalization.emails` | boolean |  |  | true |  |  |
| `config.ttsConfig.speechNormalization.urls` | boolean |  |  | true |  |  |
| `config.ttsConfig.speechNormalization.emojis` | boolean |  |  | true |  |  |
| `config.ttsConfig.speechNormalization.phoneNumbers` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.identityNumbers` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.generalNumbers` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.names` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced` | object\|null |  |  |  |  |  |
| `config.ttsConfig.speechNormalization.advanced.numbers` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.money` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.dates` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.times` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.percentages` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.fractions` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.units` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.ordinals` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.abbreviations` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.iban` | boolean |  |  | false |  |  |
| `config.ttsConfig.speechNormalization.advanced.symbols` | boolean |  |  | false |  |  |
| `config.ttsConfig.normalizationPrompt` | string\|null |  |  |  | maxLength=8000 | Custom prompt for speech normalization. |
| `config.sttConfig` | object | **yes** |  |  |  | Speech-to-text (transcriber) settings. |
| `config.sttConfig.provider` | string | **yes** | **yes** |  | minLength=1; maxLength=50 | STT provider id (free string; example "deepgram"). |
| `config.sttConfig.model` | string\|null |  |  | null | maxLength=100 | STT model (example "nova-2"). |
| `config.sttConfig.language` | string\|null |  |  | "multi" | minLength=1 | STT language; default "multi". |
| `config.sttConfig.baseUrl` | string\|null |  |  |  | maxLength=2048; format="uri" |  |
| `config.sttConfig.apiKey` | string\|null |  |  |  | maxLength=500 |  |
| `config.sttConfig.clientType` | string\|null |  |  |  | enum=["freya", "openai", null] |  |
| `config.sttConfig.additionalSettings` | object\|null |  |  | {} | map of any | Free-form provider-specific STT settings. |
| `config.sttConfig.confidenceReask` | object\|null |  |  |  |  | Re-ask the caller when transcription confidence is low. |
| `config.sttConfig.confidenceReask.enabled` | boolean |  |  | false |  |  |
| `config.sttConfig.confidenceReask.threshold` | number |  |  | 0.3 | minimum=0; maximum=1 |  |
| `config.sttConfig.confidenceReask.reduction` | string |  |  | "min" | enum=["min"] |  |
| `config.sttConfig.confidenceReask.disableOnDigitNodes` | boolean |  |  | true |  |  |
| `config.sttConfig.confidenceReask.reaskMode` | string |  |  | "phrase" | enum=["phrase", "llm"] |  |
| `config.sttConfig.confidenceReask.reaskPhrases` | array\|null |  |  | null | maxItems=20 |  |
| `config.sttConfig.confidenceReask.reaskPhrases[]` | string |  |  |  | maxLength=2000 |  |
| `config.sttConfig.confidenceReask.maxConsecutiveReasks` | integer |  |  | 2 | minimum=0; maximum=5 |  |
| `config.complianceConfig` | object | **yes** |  |  |  | Compliance flags (effects not documented). |
| `config.complianceConfig.pciDss` | boolean |  |  | false |  |  |
| `config.complianceConfig.mifidIi` | boolean |  |  | false |  |  |
| `config.complianceConfig.euAiAct` | boolean |  |  | false |  |  |
| `config.complianceConfig.soc2` | boolean |  |  | false |  |  |
| `config.callTimeoutSettings` | object\|null |  |  |  |  | Silence handling and max call duration. |
| `config.callTimeoutSettings.silenceTimeout` | integer |  |  | 0 | minimum=0 | Silence timeout (units not documented; 0 default). |
| `config.callTimeoutSettings.maximumDuration` | integer |  |  | 600 | minimum=0; maximum=14400 | Max call duration (default 600, max 14400 => seconds, inferred). |
| `config.callTimeoutSettings.checkInMessage` | string\|null |  |  | null | maxLength=2000 | Message spoken on silence check-in. |
| `config.callTimeoutSettings.closureMessage` | string\|null |  |  | null | maxLength=2000 | Message spoken when ending for silence. |
| `config.callTimeoutSettings.maxRetries` | integer |  |  | 2 | minimum=0; maximum=10 | Silence check-ins before closing. |
| `config.callTimeoutSettings.silenceTimeoutPrompt` | string\|null |  |  | null | maxLength=2000 | LLM prompt for silence check-in. |
| `config.callTimeoutSettings.maxDurationEndCall` | object\|null |  |  | null |  | How the call is closed when max duration is reached. |
| `config.callTimeoutSettings.maxDurationEndCall.messageMode` | string |  |  | "llm" | enum=["llm", "custom", "none"] |  |
| `config.callTimeoutSettings.maxDurationEndCall.spokenMessage` | string\|null |  |  | null | maxLength=2000 |  |
| `config.callTimeoutSettings.maxDurationEndCall.llmPrompt` | string\|null |  |  | null | maxLength=2000 |  |
| `config.callTimeoutSettings.maxDurationEndCall.interruptible` | boolean |  |  | false |  |  |
| `config.callTimeoutSettings.maxDurationEndCall.triggerTimeout` | number\|null |  |  | null | minimum=0 |  |
| `config.callTimeoutSettings.dynamicWait` | object\|null |  |  | null |  | Allow longer waits (e.g., caller fetching something) with VAD-based check-ins. |
| `config.callTimeoutSettings.dynamicWait.enabled` | boolean |  |  | false |  |  |
| `config.callTimeoutSettings.dynamicWait.maxWaitSeconds` | integer |  |  | 300 | minimum=10; maximum=3600 |  |
| `config.callTimeoutSettings.dynamicWait.maxRetries` | integer |  |  | 1 | minimum=0; maximum=10 |  |
| `config.callTimeoutSettings.dynamicWait.checkInMessage` | string\|null |  |  | null | maxLength=2000 |  |
| `config.callTimeoutSettings.dynamicWait.checkInPrompt` | string\|null |  |  | null | maxLength=2000 |  |
| `config.callTimeoutSettings.dynamicWait.vadConfidence` | number\|null |  |  | null | minimum=0; maximum=1 |  |
| `config.callTimeoutSettings.dynamicWait.vadMinVolume` | number\|null |  |  | null | minimum=0; maximum=1 |  |
| `config.callTimeoutSettings.dynamicWait.vadStartSecs` | number\|null |  |  | null | minimum=0; maximum=5 |  |
| `config.callTimeoutSettings.dynamicWait.vadStopSecs` | number\|null |  |  | null | minimum=0; maximum=10 |  |
| `config.voicemailDetection` | object\|null |  |  |  |  | Answering-machine detection and what to do on voicemail. |
| `config.voicemailDetection.enabled` | boolean |  |  | false |  |  |
| `config.voicemailDetection.messageMode` | string |  |  | "detect_only" | enum=["llm", "custom", "none", "detect_only"] | llm = generated message, custom = staticMessage, none, detect_only. |
| `config.voicemailDetection.staticMessage` | string\|null |  |  | null | maxLength=2000 |  |
| `config.voicemailDetection.voicemailResponseDelay` | number |  |  | 2 | minimum=0; maximum=30 | Delay before leaving voicemail message (s). |
| `config.dtmfConfig` | object\|null |  |  |  |  | Keypad (DTMF) input capture; digits are passed to the LLM with prefix. |
| `config.dtmfConfig.enabled` | boolean |  |  | false |  |  |
| `config.dtmfConfig.timeout` | number |  |  | 2 | minimum=0; maximum=30 |  |
| `config.dtmfConfig.terminationDigit` | string |  |  | "#" | enum=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "#", "*"] |  |
| `config.dtmfConfig.prefix` | string |  |  | "DTMF: " | maxLength=100 |  |
| `config.postConversationAnalysis` | object\|null |  |  |  |  | Post-call analysis: summary, structured-data insights, problem detection. |
| `config.postConversationAnalysis.insights` | array |  |  |  | maxItems=200 | Structured-data fields (refs to workspace Insights by numeric id; manage via /insights + PUT /agents/{id}/insights). |
| `config.postConversationAnalysis.insights[]` | object |  |  |  |  |  |
| `config.postConversationAnalysis.insights[].id` | string |  |  |  | pattern="^\\d+$" |  |
| `config.postConversationAnalysis.insights[].name` | string | **yes** | **yes** |  | minLength=1; maxLength=100 |  |
| `config.postConversationAnalysis.summaryPrompt` | string\|null |  |  | null | maxLength=10000 | Prompt for the call summary. |
| `config.postConversationAnalysis.autoDetectProblems` | boolean |  |  | false |  | Auto-detect problems in calls. |
| `config.postConversationAnalysis.problemDetectionPrompt` | string\|null |  |  | null | maxLength=10000 |  |
| `config.postConversationAnalysis.problemDetectionInstructions` | string\|null |  |  | null | maxLength=10000 |  |
| `config.postConversationAnalysis.analysisModel` | string\|null |  |  | null | maxLength=100 | Model used for analysis. |
| `config.privacyConfig` | object\|null |  |  |  |  | Recording and consent settings. |
| `config.privacyConfig.enableRecording` | boolean |  |  | false |  |  |
| `config.privacyConfig.getRecordingConsent` | boolean |  |  | false |  |  |
| `config.privacyConfig.recordingConsentText` | string\|null |  |  | null | maxLength=500 |  |
| `config.privacyConfig.stopSecs` | number |  |  |  | minimum=0 |  |
| `config.privacyConfig.preSpeechMs` | number |  |  |  | minimum=0 |  |
| `config.privacyConfig.maxDurationSecs` | number |  |  |  | minimum=0 |  |
| `config.turnAnalyzerConfig` | object |  |  |  |  | End-of-turn detection model. |
| `config.turnAnalyzerConfig.provider` | string |  |  |  | enum=["local", "fal"] |  |
| `config.turnAnalyzerConfig.url` | string\|null |  |  |  | format="uri" |  |
| `config.turnAnalyzerConfig.modelPath` | string\|null |  |  |  |  |  |
| `config.guardrailsConfig` | object\|null |  |  |  |  | Output/input guardrails (rules, classifier, refuse/regenerate). |
| `config.guardrailsConfig.guardrails_enabled` | boolean |  |  | false |  |  |
| `config.guardrailsConfig.custom_rules_enabled` | boolean |  |  | false |  |  |
| `config.guardrailsConfig.rules` | array |  |  | [] |  |  |
| `config.guardrailsConfig.rules[]` | object |  |  |  |  |  |
| `config.guardrailsConfig.rules[].id` | string\|null |  |  |  |  |  |
| `config.guardrailsConfig.rules[].type` | string |  |  |  | enum=["exact", "regex", "dictionary", "structured", "classifier"] |  |
| `config.guardrailsConfig.rules[].pattern` | string |  |  |  |  |  |
| `config.guardrailsConfig.rules[].action` | string |  |  |  | enum=["refuse", "regenerate", "log_only"] |  |
| `config.guardrailsConfig.rules[].enabled` | boolean |  |  | true |  |  |
| `config.guardrailsConfig.rules[].description` | string\|null |  |  |  |  |  |
| `config.guardrailsConfig.rules[].case_sensitive` | boolean |  |  | false |  |  |
| `config.guardrailsConfig.rules[].classifier_threshold` | number |  |  |  | minimum=0; maximum=1 |  |
| `config.guardrailsConfig.refuse_message` | string |  |  | "I'm sorry, I can't help with that." |  |  |
| `config.guardrailsConfig.max_regenerate_retries` | integer |  |  | 2 | minimum=0; maximum=5 |  |
| `config.guardrailsConfig.regenerate_wait_message` | string |  |  | "One moment, please." |  |  |
| `config.guardrailsConfig.classifier_enabled` | boolean |  |  | false |  |  |
| `config.guardrailsConfig.classifier_provider` | string |  |  |  |  |  |
| `config.guardrailsConfig.classifier_model` | string |  |  |  |  |  |
| `config.guardrailsConfig.input_config` | object |  |  |  |  |  |
| `config.guardrailsConfig.input_config.enabled` | boolean |  |  | false |  |  |
| `config.guardrailsConfig.input_config.normalize` | boolean |  |  | true |  |  |
| `config.guardrailsConfig.input_config.detect_injection` | boolean |  |  | true |  |  |
| `config.guardrailsConfig.input_config.detect_weird_input` | boolean |  |  | true |  |  |
| `config.guardrailsConfig.input_config.run_classifier` | boolean |  |  | true |  |  |
| `config.guardrailsConfig.input_config.refuse_message` | string |  |  | "I'm sorry, I can't help with that." |  |  |
| `config.guardrailsConfig.input_config.max_input_chars` | integer |  |  | 8000 | minimum=1; maximum=100000 |  |
| `config.piiRedactionConfig` | object\|null |  |  |  |  | PII masking (email/phone/card/national id/IBAN + custom regex). |
| `config.piiRedactionConfig.enabled` | boolean |  |  | false |  |  |
| `config.piiRedactionConfig.maskEmail` | boolean |  |  | true |  |  |
| `config.piiRedactionConfig.maskPhone` | boolean |  |  | true |  |  |
| `config.piiRedactionConfig.maskPaymentCard` | boolean |  |  | true |  |  |
| `config.piiRedactionConfig.maskNationalId` | boolean |  |  | true |  |  |
| `config.piiRedactionConfig.maskIban` | boolean |  |  | true |  |  |
| `config.piiRedactionConfig.customRules` | array |  |  | [] |  |  |
| `config.piiRedactionConfig.customRules[]` | object |  |  |  |  |  |
| `config.piiRedactionConfig.customRules[].label` | string | **yes** | **yes** |  | minLength=1; maxLength=40; pattern="^[A-Z0-9_]+$" |  |
| `config.piiRedactionConfig.customRules[].pattern` | string | **yes** | **yes** |  | minLength=1; maxLength=500 |  |
| `config.piiRedactionConfig.customRules[].enabled` | boolean |  |  | true |  |  |
| `config.routingLlmConfig` | object\|null |  |  |  |  | Separate LLM for routing (workflow transitions, inferred). |
| `config.routingLlmConfig.provider` | string | **yes** | **yes** |  | minLength=1; maxLength=50 |  |
| `config.routingLlmConfig.model` | string | **yes** | **yes** |  | minLength=1; maxLength=100 |  |
| `config.routingLlmConfig.baseUrl` | string\|null |  |  |  | maxLength=2048; format="uri" |  |
| `config.routingLlmConfig.apiKey` | string\|null |  |  |  | maxLength=500 |  |
| `config.extractionLlmConfig` | object\|null |  |  |  |  | Separate LLM for extraction (extraction_schema, inferred). |
| `config.extractionLlmConfig.provider` | string | **yes** | **yes** |  | minLength=1; maxLength=50 |  |
| `config.extractionLlmConfig.model` | string | **yes** | **yes** |  | minLength=1; maxLength=100 |  |
| `config.extractionLlmConfig.baseUrl` | string\|null |  |  |  | maxLength=2048; format="uri" |  |
| `config.extractionLlmConfig.apiKey` | string\|null |  |  |  | maxLength=500 |  |
| `config.backgroundSoundUrl` | string\|null |  |  | null | maxLength=200 | Background ambience audio URL. |
| `config.syncSource` | object\|null |  |  |  |  | External source the agent config syncs from (permission agents:sync exists). |
| `config.syncSource.url` | string | **yes** | **yes** |  | maxLength=2048; format="uri" |  |
| `config.syncSource.apiKey` | string | **yes** | **yes** |  | maxLength=500 |  |
| `config.syncSource.syncedAt` | string\|null |  |  |  | format="date-time" |  |
| `config.testVariables` | object |  |  |  | map of string | String map of variable values for testing (semantics not documented). |

Rows where Req(POST) and Req(PUT) differ: `config.llmConfig`, `config.ttsConfig`, `config.sttConfig`, `config.complianceConfig` are required inside `config` on POST but optional on PUT. All nested `required` lists (e.g. llmConfig.provider/model/systemPrompt, ttsConfig.provider/voiceId, sttConfig.provider) are the same in PUT, i.e. if you send `llmConfig` on PUT you must send those three fields. [Confirmed]

`additionalProperties` is not set to `false` on `config` or its sub-objects in the live spec, so the schema itself does not forbid extra keys; whether the server strips or rejects them is **not documented**. [Confirmed absence]

## Response envelope (POST 201 / PUT 200 / GET 200)

`{ success: true, data: { message: string, result: { agent: { id(uuid), workspaceId(uuid), userId(uuid|null), name, entityType("workflow"|null), workflowId(uuid|null), config, isImported(bool, default false), createdAt, updatedAt } } } }` — **no versionId in the agent response** ([Confirmed], spec). `GET /agents/defaults` returns `data.result.config` only (no agent wrapper).

Error codes on POST: 400 validation, 401, 403 "Workspace ID mismatch or insufficient permissions", 409 name exists, 422 "The config selects a model that is outside its allowed hours", 500. PUT adds 404 "Agent not found". [Confirmed]

## Fields present ONLY in the STALE docs spec (`openapi.json`, OpenAPI 3.0.0) — do not use

`workspaceId` (POST body, required), `source` enum [firebase, vapi], `files[]` (fileName/filePath/fileSize/mimeType), `llmConfig.thinkingBudgetEnabled`, `llmConfig.thinkingBudget` (1000-100000), `ttsConfig.speed` (0.25-4), `ttsConfig.stability` (0-1, required), `ttsConfig.similarityBoost` (0-1, required), `config.sstConfig` (typo, with temperature/punctuate/diarize), `postConversationAnalysis.generateSummary`, `.generateStructuredData`, `.structuredDataPrompt`, `.structuredDataSchema[]` (name/type enum [string, number, rating, checkbox, range, enum, array]/description/enums/defaultValue/rangeMin/rangeMax). Stale `systemPrompt.maxLength`=100000 (live 200000); stale `voicemailDetection.messageMode` enum [llm, custom, none] default "none" (live adds detect_only, default "detect_only"); stale agent ids are numeric strings (`^\d+$`) vs live uuid.

## Fields present ONLY in staging spec (`openapi_staging-app.json`), not in live

`config.backgroundSoundVolume`: number|null, min 0, max 2, default null. The POST example in staging also shows `sttConfig.additionalSettings.semanticTurnDetection: false`.

## Related shapes (live spec unless marked)

- `POST /versions/{agent|workflow}/{entityId}` body: `entityId` (req), `workspaceId` (req, uuid), `configSnapshot` (req, free object; validated against the entity's config schema, 422 if invalid), `parentVersionId` (uuid), `description` (≤5000). [Confirmed]
- Version object: `id, entityType, entityId, workspaceId, versionNumber, parentVersionId, branchId, isPublished, publishedAt, publishedBy, configSnapshot, configDiff, name ("Commit subject"), description, sourceRunId, createdBy, createdAt`. [Confirmed]
- `POST /branches` body: `entityType` (req; agent|workflow|persona|kb_document), `entityId` (req, uuid), `name` (req, 1-200), `config` (free object) or `patch` ([{op add|remove|replace|test, path, value}], minItems 1), `description` (≤5000), `baseVersionId`, `closesFeedbackIds` (≤500). [Confirmed]
- `POST /branches/{branchId}/commit` body: `config` | `patch`, `name` (≤200), `description` (≤5000), `expectedHeadVersionId`. [Confirmed]
- `POST /branches/{branchId}/rebase` (Merge) body: `publish` (bool), `force` (bool), `resolutions` ([{path (req), editedValue}]). 200 result: `success, newVersionId, newVersionNumber, published, resolvedFeedbackIds, conflicts[{path, liveValue, baseValue, branchValue, operation set|text_diff}], checksState pass|fail|running|notRun, checks, error`. [Confirmed]
- Workflow definition (`GET /workflow/{id}` → `data.result.workflow.workflow`): untyped `{}` in live spec. STALE spec typed version dumped in `stale_workflow_schema.txt` (initial_node, nodes{role_messages, task_messages, functions[], respond_immediately, context_strategy APPEND|RESET|RESET_WITH_SUMMARY, summary_prompt, agentId}, globals[]; function variants: transition-only {name, transition_to}, custom handler, `__function__:end_call`, `__function__:transfer_call`, `__function__:reschedule_call`, {type:"reference", name}). [Confirmed in stale spec only — treat as historical]
