# Mock bank for the final (Cloudflare Workers) — template

Written before 17:00 UTC on 11 Oct from the practice kit's tool semantics (`kit/tools/openapi.json`); **not** builder code
(the builder must hold nothing from the final case: `docs/hackathon_requirements.md` F4, F9). After 17:00 it is adapted
from the final zip's **service contract** and **test customers**, deployed, and kept up until the results are out.

- `src/bank.js` — pure logic, one state per customer: identity check with wrong-answer counting and lock, account only
  after verification, one promise per product, notes, callbacks, transfers, close, a ledger of every call, and a fresh
  state when a customer calls again after `idleResetSeconds` (each simulated call starts clean).
- `src/worker.js` — routes `POST /v1/<tool>` (JSON body with `customer_id`) to that customer's Durable Object; admin-only
  `GET /v1/ledger/<id>` and `POST /v1/reset/<id>` (header `x-admin-token`); `GET /` health.
- `data/customers.json` — EXAMPLE customers from the public practice set; replace with the final's test customers.
- `test/bank.test.mjs` — `npm test` (Node 18+; no dependencies).

## After 17:00 UTC (adapt, test, deploy)

1. Read the zip's service contract: tool/endpoint names, request and response field names, identity fields and their
   formats, outcome/reason values, error behaviour. Change `HANDLERS` in `src/bank.js` (and the paths if the contract
   uses another base path) so requests and responses match it exactly.
2. Convert the test customers (Excel/Markdown) into `data/customers.json` (`customer_id`, `identity`, `products`, with
   the contract's field names). Adjust `config` (wrong-answer limit) to the contract.
3. `npm test` (update the tests to the contract), then `npx wrangler login` (user), `npx wrangler secret put ADMIN_TOKEN`,
   `npx wrangler deploy`. The printed `https://freya-mock-bank.<subdomain>.workers.dev` + base path is `mock_url`.
4. Smoke-test with `curl` (health, one verify, one get_account), then run the builder with `{case_folder} {mock_url}`.
