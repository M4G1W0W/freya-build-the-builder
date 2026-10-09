> Verified research notes, generated 2026-10-10 from the public docs snapshot in `docs/reference/` (the live spec is `docs/reference/freya_openapi_live.json`). Each claim was checked by a separate fact-checking pass against the sources. Tags: **[Confirmed]** = stated in the docs or spec; **[Inferred]** = our reasoning; **[Not documented]** = not in any source. Curated summary: `docs/freya_api_notes.md`.

## Integrations, tools, SDKs and public information

Sources: the doc snapshot (2026-10-10), the live spec `freya_openapi_live.json` (base `https://app.freyavoice.ai/api/v2`), the stale spec `openapi.json` (used only to note discrepancies), `model-apis-openapi.json`, and public web pages.

### Short answers
- **Tool types an agent can use.**
  - `config.llmConfig.tools[]` accepts only `type: "function"` **[Confirmed]**.
  - In the live spec, `function.handler` is a plain string with no description and no example **[Confirmed]**.
  - The stale spec's workflow-node function schema (`GET /workflow/{workflowId}` response) lists three built-in handler values: `__function__:end_call`, `__function__:transfer_call` and `__function__:reschedule_call` **[Confirmed]**.
  - What `handler` means in general is **[Not documented]**. The tool schema has no URL, method or headers field **[Confirmed]**.
  - The guides describe function calls, webhooks and workflow API calls **[Confirmed]**.
  - `GET /integrations?detail=true` returns integration metadata from Nango: available actions, endpoints and connection status **[Confirmed]**.
  - Nothing documents how a Nango action becomes an agent tool **[Not documented]**.
  - MCP shows up only as "MCP OAuth grants" in `/oauth-connections` **[Confirmed]**. The docs never describe MCP as a tool type for agents **[Not documented]**.
- **Knowledge base.**
  - It is a workspace-level beta feature that uses hybrid search **[Confirmed]**.
  - Creating or filling a KB through the public API is **[Not documented]**. Neither spec has a KB path. The only KB entity in the live spec is `kb_document` in the `POST /branches` `entityType` enum **[Confirmed]**.
  - The permission catalog includes `kb:*` permissions, which suggests a private KB API exists **[Inferred]**.
- **Embed SDK.**
  - It is a browser WebRTC client loaded from a script tag at `https://app.freyavoice.ai/freya-client.js` **[Confirmed]**.
  - I found no package on npm or PyPI under the names I checked **[Confirmed]**.
  - It supports `call` (voice) and `chat` (text, via `sendMessage`) modes **[Confirmed]**.
  - Using it outside a browser is **[Not documented]**.
  - For text sessions driven over the API there is `POST /chat/message` **[Confirmed]**.
- **STT/TTS Model APIs.** STT runs at `stt.freyavoice.ai` and TTS at `tts.freyavoice.ai`. Both use a workspace Bearer API key **[Confirmed]**.
- **Python SDK.** None was found. I checked PyPI and npm names, ran a GitHub repo search for "freyavoice", and listed the official GitHub org's repos. The docs mention no SDK install **[Confirmed]**.

### Agent tools and integration mechanisms
- The integrations guide lists these categories **[Confirmed]**:
  - Telephony: Twilio and other SIP providers
  - CRM: HubSpot, Salesforce, or a custom CRM via webhooks and API calls
  - Communication: Slack, email, SMS/MMS
  - Databases and data warehouses
  - APIs: REST, GraphQL, webhooks
  - Source: https://docs.freyavoice.ai/guides/fundamentals/integrations
- The same guide says "Functions are the primary way agents interact with external systems". It also describes incoming and outgoing webhooks and GET/POST/PUT/DELETE calls from workflows **[Confirmed]**. Workflows have Function Nodes **[Confirmed]**.
- The tool item schema in `POST /agents` → `config.llmConfig.tools[]` **[Confirmed]**:
  - Each item requires `type` and `function`.
  - `type`: enum `["function"]`
  - `function`: `{name, handler, description, parameters, transition_to}`. The first four are required.
  - `config`:
    - `maxPerNTurns`
    - `alwaysRunsAt` ∈ {`each_turn`, `start_of_call`, `end_of_call`}
    - `timeoutMs`
    - `maxRetries` (0–5)
    - `preSpeech` {`mode` (required): `static`|`auto`, `message`, `interruptible`, `audio_asset_id`, `audio_loop`, `audio_volume`}
    - `interruptible`
  - `response_mapping[]` {`path`, `variable`, `description`}
  - `extraction_schema[]`, whose `type` ∈ {string, integer, float, boolean, date, datetime, enum}
  - `pre_process_code` and `post_process_code` (string or null)
  - The default is `[]`.
- **`handler`**:
  - In the live spec it is a plain string with no description or example **[Confirmed]**.
  - The stale spec's workflow-node schema gives three built-in constants: `__function__:end_call`, `__function__:transfer_call` and `__function__:reschedule_call` **[Confirmed]**. The live spec has none of them.
  - The general meaning of `handler`, and how to point it at an external HTTP endpoint, are **[Not documented]**.
  - The "Creating Your First Agent" guide (https://docs.freyavoice.ai/getting-started/creating-agent) lists an "Endpoint" field for functions. The spec's tool schema has no endpoint field **[Confirmed]**.
- `llmConfig` also has `provider`, `model`, `baseUrl`, `apiKey` and `clientType` **[Confirmed]**.
- Outgoing webhook payloads are documented as `/webhooks/end-of-call-report` and `/webhooks/campaign-call-outcome` **[Confirmed]**.

| Method | Path (live spec unless noted) | Purpose | Notes |
|---|---|---|---|
| GET | `/integrations` | List integrations | `workspaceId` (required), `detail` (default false), `limit` ≤100 (default 50), `offset`, `search`, `sortBy`, `sortOrder`. With `detail=true` it returns Nango metadata, including actions whose `type` is `action`, `sync` or `webhook` **[Confirmed]** |
| DELETE | `/integrations` | Disconnect an integration | `workspaceId`, `integrationType` (1–50 chars), both required **[Confirmed]** |
| GET | `/integrations/{integrationType}` | Get one connection | **Stale spec only**; not in the live spec **[Confirmed]** |
| POST | `/integrations/session` | Create a Nango OAuth session token (Nango Connect UI) | **Stale spec only**. Connecting an OAuth integration through the live API is **[Not documented]** |
| GET | `/oauth-connections` | Caller's "MCP OAuth grants (connected apps)" | Account-scoped **[Confirmed]**. No doc page exists |
| DELETE | `/oauth-connections?id=` | Revoke an MCP OAuth grant | **[Confirmed]** |
| POST | `/audio/transcriptions` | Platform STT (Closed Beta) | See Model APIs |
| POST | `/audio/speech` | Platform TTS (Closed Beta) | See Model APIs |
| POST | `{FREYA_BASE_URL}/api/token/embed` | Mint an Embed token | Documented in the guide only. **Not in either spec** **[Confirmed]** |
| GET | `{FREYA_BASE_URL}/api/token/webrtc/ice-servers` | TURN credentials | Documented in the guide only. **Not in either spec** **[Confirmed]** |
| POST | `/chat/message` | Run an agent or workflow turn by turn over text | Requires `message`. Omit `callId` and send `agentId` or `workflowId` to start **[Confirmed]** |

### Knowledge base (https://docs.freyavoice.ai/guides/features/knowledgebase)
- It is workspace-level and in **beta**. Search is hybrid (semantic plus keyword and heading) and returns cited results "in under 200ms" **[Confirmed]**.
- There are two content types **[Confirmed]**:
  - **Articles**: written in the editor, uploaded files (PDF, TXT, Markdown, DOCX, up to 10MB; PDFs get OCR), or synced web pages
  - **Snippets**: short texts
  - Processing (extract, chunk, embed, index) runs asynchronously.
- Every agent in the workspace can use the KB automatically, with no per-agent setup. The docs recommend telling the agent to use it in the system prompt. Results include the content, the document title and type, the heading path and, for synced pages, the source URL **[Confirmed]**.
- Documents are Draft, Published or Archived. Editing a published document triggers an automatic reindex. The UI has a live test chat **[Confirmed]**.
- **API access.**
  - Neither spec has a KB path, and every documented KB step is done in the dashboard **[Confirmed]**.
  - The live `POST /branches` `entityType` enum includes `kb_document`, alongside `agent`, `workflow` and `persona` **[Confirmed]**. Branching needs an existing `entityId`.
  - No documented endpoint creates, uploads or lists KB documents. Creating or filling a KB through the API is **[Not documented]**.
- The permission enum has `kb:read`, `kb:write`, `kb:delete`, `kb:upload`, `kb:sync` and `kb:articles-write`, and the alert source enum includes `knowledgebase` **[Confirmed]**. Together these suggest a private KB API **[Inferred]**.
- These are **[Not documented]**: scoping a KB to one agent, the name or tool the agent uses to query the KB, and KB size limits other than the 10MB file limit.

### Embed SDK (https://docs.freyavoice.ai/guides/embed/overview, https://docs.freyavoice.ai/guides/embed/reference)
- **What it is.** The docs call it the "Freya Client SDK" **[Confirmed]**:
  - It is a browser client that handles WebRTC transport, microphone input, remote audio playback and the event stream.
  - You load it with `<script src="https://app.freyavoice.ai/freya-client.js">`, which exposes `window.Freya.FreyaClient`.
  - The docs say no build step or package manager is required.
- **Package.** I found no package under the names I checked **[Confirmed]**:
  - An npm search for "freyavoice" returns 0 results.
  - `freya-client`, `@freyavoice/client`, `@freyavoice/sdk` and `freyavoice` return 404.
- **Token flow.**
  - Your backend calls `POST /api/token/embed` with `{agentId, allowedOrigin, ttlSeconds}` and a Bearer API key that has the `calls:web-token` permission. The response contains `token`, `expiresAt` and `baseUrl` **[Confirmed]**.
  - TURN servers come from a separate, optional call to `GET /api/token/webrtc/ice-servers` **[Confirmed]**.
  - The value of `FREYA_BASE_URL` is **[Not documented]**.
  - Tokens expire after `ttlSeconds` (300 seconds by default) **[Confirmed]**.
  - Each token can establish only one session **[Confirmed]**.
  - WebRTC connections from origins other than `allowedOrigin` are rejected **[Confirmed]**.
- **Options.** `baseUrl`, `token`, `mode` (`"call"` by default, or `"chat"`), `metadata`, `customerVariables` ("Variables injected into the agent's system prompt at runtime") and `iceServers` **[Confirmed]**. In chat mode the microphone stays off, but audio still plays if the agent has TTS configured **[Confirmed]**.
- **API surface.** **[Confirmed]**
  - Methods: `connect`, `disconnect`, `sendMessage`, `mute`, `unmute`, `on` and `off`.
  - Properties: `state` and `isMicEnabled`.
  - Events cover connection state, bot and user speech and transcripts, and media tracks.
  - Tool-call events are `toolCallStarted`, `toolCallInProgress` (with the full arguments) and `toolCallStopped`.
- **Programmatic sessions.** In a browser, chat mode lets code send text with `sendMessage` **[Confirmed]**. Running the SDK in Node, Python or a headless environment is **[Not documented]**. The SDK's version, changelog and TypeScript types are **[Not documented]**.

### Model APIs: STT and TTS (https://docs.freyavoice.ai/model-api-reference/introduction)
- These are standalone endpoints, "independent of the Freyavoice Call API". STT is at `https://stt.freyavoice.ai` and TTS at `https://tts.freyavoice.ai` **[Confirmed]**.
- Auth is `Authorization: Bearer <workspace API key>`. For the WebSocket, put the key in `?token=` or, from non-browser clients, in a Bearer header during the handshake **[Confirmed]**.
- **STT, file upload** (`POST /v1/audio/transcriptions`, multipart) **[Confirmed]**:
  - `file` is required; accepted formats are wav, mp3, flac, ogg, m4a and webm, up to 15 MB
  - `model` defaults to `freya-stt`
  - `response_format` is `json` (default), `text` or `verbose_json`
  - `temperature` defaults to 0
  - Described as "Compatible with the OpenAI audio transcription API"
  - Errors: 400; 403 (auth or insufficient credits); 429
- **STT, streaming** (beta) at `wss://stt.freyavoice.ai/v1/audio/stream` **[Confirmed]**:
  - Send `{"type":"config","sample_rate":16000}` first
  - Then send binary PCM frames (16-bit signed LE, mono)
  - End with `{"type":"eof"}`
  - The server sends `partial`, `final`, `result` and `error` messages, using LocalAgreement with a tick of about 500 ms
- **TTS** (`POST /v1/audio/speech`, JSON) **[Confirmed]**:
  - `input` and `voice` are required
  - Voices: `leyla` (default), `zeynep`, `alev`, `ali`, `alper`, `mustafa`
  - `response_format` defaults to mp3; options are mp3, opus, aac, flac, wav and pcm
  - `model` is `tts-1` (default) or `tts-1-hd`
  - Supported emotion tags: [pause], [eee], [throat clearing], [mm-hmm], [laughter], [deep breath], [hmm], [cough], [breath]
- **Spec inconsistencies** **[Confirmed]**:
  - The TTS 200 response lists only `audio/wav`, although the default `response_format` is mp3.
  - The spec's top-level `servers` lists only `stt.freyavoice.ai`; the TTS operation overrides it to `tts.freyavoice.ai`.
- **Broken link.** The STT guide links to `/model-api-reference/post-v1-audio-transcriptions`, which is not a published page. The real page is `/model-api-reference/speech-to-text` **[Confirmed]**.
- **Platform Audio endpoints** (Closed Beta, under `/api/v2`) are different **[Confirmed]**:
  - STT uses model `freya-transcribe-v1`, accepts a `prompt`, offers `response_format` json, text, srt, verbose_json or vtt, and takes `language` `tr` or `cs`
  - TTS uses model `freya-audio-v1`, offers only the voice `leyla` and only `wav` output

### SDKs and client libraries
- **PyPI** **[Confirmed]**:
  - `freya` exists but is unrelated (v0.0.1, author Ingvar Vilkman, github.com/zeegin/freya)
  - `pyfreya` is unrelated ("Cohort Analysis Tool")
  - `freyavoice`, `freya-voice`, `freyavoice-sdk`, `freya-sdk`, `freyavoice-ai`, `freya-ai`, `freya-client`, `freyavoice-client`, `freya-python`, `freya-api` and `freyavoice-python` all return 404
- **Docs.** The docs mention no Python SDK. Python appears only in examples that use `requests` (minting an embed token) and `websockets` (STT streaming) **[Confirmed]**.
- **GitHub.** The official org https://github.com/freyavoiceai ("Freya Inc", blog freyavoice.ai) has one public repo, FreyaTTS. It is an open-source Turkish TTS model under Apache-2.0, not an API client. A repo search for "freyavoice" returns 0 results **[Confirmed]**.
- **Hugging Face.** The `freyavoice` org has `Freya-TTS` and `pii-ner-model` **[Confirmed]**.
- An OpenAI-style client might work against the STT host because the docs call it OpenAI-compatible. This was not tested and the docs do not say so **[Inferred]**.

### YC "Build the Builder" hackathon (public page)
- **Event page.** https://events.ycombinator.com/AI-FDE-Build-the-Builder26. The freyavoice.ai homepage links to it with the text "Freya × Y Combinator hackathon". Freya (YC S25) hosts it, fully online, on October 10–11, 2026 **[Confirmed]**.
- **Page metadata.** It lists `starts_at` 2026-10-10T10:00Z and `ends_at` 2026-10-11T20:00Z (time zone America/Los_Angeles) **[Confirmed]**.
- **Challenge** **[Confirmed]**:
  - "Your builder should turn a task description and the available tools into a working agent."
  - At the deadline, the organisers give the builder unseen tasks.
  - The generated agents run through benchmark simulations.
  - No manual edits are allowed during evaluation.
- **Schedule** **[Confirmed]**:
  - Day 1 covers "Challenge rules, development tasks and Freya platform setup", then building against a practice benchmark.
  - Day 2 covers submission, the final unseen benchmark and the leaderboard.
  - "Exact start and submission times will be shared with accepted participants."
  - Scoring rules, resource limits and tie-breakers will be shared "before building begins".
- **Judging.** Rankings are based on how the generated agents perform across the final benchmark's tasks and test cases, under the same evaluation conditions for everyone. There are no finalist pitches or presentation scores **[Confirmed]**.
- **Prizes** **[Confirmed]**:
  - 1st place: a YC interview
  - 2nd place: AirPods
  - Top 3: a final interview with Freya
  - Prize pool: $3,000 in Freya credits
- **Who can join.** Solo builders are encouraged and teams can have at most two people. Participants use Freya's platform **[Confirmed]**.
- **Registration.** Page metadata shows that applications closed at 2026-10-09T16:00Z **[Confirmed]**. The researcher reported a "no longer accepting new registrations" notice on the rendered page, but the fact-check could not re-verify it.
- **Submission.** The builder, the exact code version, its dependencies and reproducible run instructions. The page says "We evaluate the agents it creates, not a hand-built agent" **[Confirmed]**.
- **Pre-event preparation.** The page does not explicitly restrict it **[Not documented]**. It says "You build the builder during the weekend." No public starter kit or separate rules document was found.

### Status page, changelog, community and support
- **Status page.** None is documented, and `status.freyavoice.ai` returns NXDOMAIN **[Confirmed]**.
- **Changelog.** None was found **[Confirmed]**:
  - `docs.freyavoice.ai/changelog` and `/api-reference/changelog` return 404.
  - `freyavoice.ai/changelog` redirects to `/tr/changelog`, which returns 404.
  - llms.txt lists no changelog.
- **Discord or Slack.** No community is linked on the homepage or in the docs, and web search found none **[Not documented]**. `discord.gg/freyavoice` could not be reached from the sandbox, so that check is inconclusive.
- **Support contacts** **[Confirmed]**:
  - `support@freyavoice.com` (in the spec's `info.contact` and on the API reference pages)
  - `support@freyavoice.ai` and `hello@freyavoice.ai` (homepage)
  - `founders@freyavoice.ai` (YC company page)
  - `dev@freyavoice.ai` (FreyaTTS README; also on the homepage)
  - The support domains differ: .com vs .ai.
- **Playground and API keys.** The homepage links a Playground at `https://playground.freyavoice.ai` and an API Keys page at `playground.freyavoice.ai/tr/account/api-keys`. The docs instead say to sign up at `app.freyavoice.ai` and open API Keys from the dashboard sidebar **[Confirmed]**.
- **Company.** **[Confirmed]**
  - Freya is in YC's Summer 2025 batch.
  - The YC page lists Tunga Bayrak as Founder/CEO.
  - Freya's YC launch post ("Voice AI Agents For Financial Services") names Tomas Nepala as the other founder ("started Freya as our second startup together").
  - The launch post targets banks, mortgage lenders, fintechs and insurers.
- **Marketing integrations page** (https://www.freyavoice.ai/tr/entegrasyonlar) **[Confirmed]**:
  - It lists SIP, the REST TTS and STT APIs, WebSocket STT, Bearer auth, a webhook on call completion, and CRM, core banking and policy systems.
  - It says API requests defined in the workflow are sent to your system during a call.
  - It offers on-premises or Turkey-cloud deployment.

### Method notes
- The SDK script URL `https://app.freyavoice.ai/freya-client.js` is documented. The researcher reports one unauthenticated GET to it, returning 200 `application/javascript`, about 718 KB, with the body not kept. No artifact was saved and the fact-check did not repeat the request. Whether the URL is publicly reachable is **[Not documented]** in the docs.
- The YC event facts above come from the event JSON embedded in the public event page HTML (fetched 2026-10-10).