# Freya public docs snapshot

Unauthenticated public downloads taken **2026-10-10 ~00:50 Istanbul time** for offline lookup and
spec-drift detection. Re-download and `git diff` to see what changed.

| File | Source | sha256 of download |
|---|---|---|
| `freya_openapi_live.json` | <https://app.freyavoice.ai/api/openapi.json> (OpenAPI 3.1.0, 96 paths / 180 ops; same path set as `staging-app`) | `282b7040…2e5237` |
| `freya_model_apis_openapi.json` | <https://docs.freyavoice.ai/api-reference/model-apis-openapi.json> (STT/TTS, server `https://stt.freyavoice.ai`) | `9618fd80…c2f803` |
| `llms.txt` | <https://docs.freyavoice.ai/llms.txt> (page index) | `3f2061aa…cc088` |
| `llms-full.txt` | <https://docs.freyavoice.ai/llms-full.txt> (all doc pages as text) | `0a523da6…240938` |

Official hackathon page (fetched 2026-10-10 13:38 Istanbul, i.e. after the start):

| File | Source |
|---|---|
| `hackathon_page.md` | <https://www.freyavoice.ai/hackathon>: text extracted from the HTML (diagrams omitted) |
| `hackathon_practice_cases.json` | The 13 practice cases embedded in that page (`<script id="cases-json">`) |
| `hackathon_page_live_2026-10-11.md` | All 7 tabs re-read 2026-10-11 ~16:00 UTC: **the final-case announcement** (one Turkish case as a zip folder, our own mock on Cloudflare Workers, `{case_folder} {mock_url}`, `submission.json`). Each tab hash-checked against the live page. |
| `final_case_2026-10-11.json` | Team-made case entry for the final, quoting only that page (no zip content, ever). Shown first under Case sets on the dashboard. |

**Not saved on purpose:** <https://docs.freyavoice.ai/api-reference/openapi.json> is a *stale*
OpenAPI 3.0.0 spec (58 paths, still has `/problems` and `/solutions`, missing Chat, Simulations,
Personas, Unit Tests, Versions, Branches, Insights…). Use the live spec above instead.

Refresh:

```bash
curl -s https://app.freyavoice.ai/api/openapi.json -o docs/reference/freya_openapi_live.json
curl -s https://docs.freyavoice.ai/llms.txt -o docs/reference/llms.txt
curl -s https://docs.freyavoice.ai/llms-full.txt -o docs/reference/llms-full.txt
git diff --stat docs/reference
```

Find an operation quickly:

```bash
python3 -c "import json;d=json.load(open('docs/reference/freya_openapi_live.json'));[print(m.upper(),p) for p,o in d['paths'].items() for m in o if m in('get','post','put','patch','delete')]"
```
