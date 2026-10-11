// Cloudflare Worker for our mock bank (template; see bank.js for what to adapt after 17:00 UTC).
// POST /v1/<tool>            body JSON with customer_id -> routed to that customer's Durable Object
// GET  /v1/ledger/<id>       debug ledger (header x-admin-token = ADMIN_TOKEN secret)
// POST /v1/reset/<id>        fresh state for one customer (same header)
// GET  /                     health
import { handle } from "./bank.js";
import customers from "../data/customers.json";

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function findCustomer(id) {
  return (customers.customers || []).find((c) => c.customer_id === id);
}

export class CustomerState {
  constructor(ctx) {
    this.ctx = ctx;
  }

  async fetch(request) {
    const { op, tool, body, customer } = await request.json();
    let state = await this.ctx.storage.get("state");
    if (op === "ledger") return json(200, { ok: true, state: state || null });
    if (op === "reset") {
      await this.ctx.storage.delete("state");
      return json(200, { ok: true });
    }
    const res = handle(state, customer, tool, body, customers.config || {});
    await this.ctx.storage.put("state", res.state);
    return json(res.status, res.body);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts.length === 0) return json(200, { ok: true, service: "mock-bank" });
    if (parts[0] !== "v1") return json(404, { ok: false, error: "not found" });
    const admin = request.headers.get("x-admin-token");
    if ((parts[1] === "ledger" || parts[1] === "reset") && parts[2]) {
      if (!env.ADMIN_TOKEN || admin !== env.ADMIN_TOKEN) return json(403, { ok: false, error: "forbidden" });
      const stub = env.CUSTOMER_STATE.get(env.CUSTOMER_STATE.idFromName(parts[2]));
      return stub.fetch("https://do/", { method: "POST", body: JSON.stringify({ op: parts[1] }) });
    }
    if (request.method !== "POST" || parts.length !== 2) return json(404, { ok: false, error: "not found" });
    let body;
    try {
      body = await request.json();
    } catch {
      return json(400, { ok: false, error: "body must be JSON" });
    }
    const customer = findCustomer(body.customer_id);
    if (!customer) return json(404, { ok: false, error: "unknown customer_id" });
    const stub = env.CUSTOMER_STATE.get(env.CUSTOMER_STATE.idFromName(body.customer_id));
    return stub.fetch("https://do/", { method: "POST", body: JSON.stringify({ op: "tool", tool: parts[1], body, customer }) });
  },
};
