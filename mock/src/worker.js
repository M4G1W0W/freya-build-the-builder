// Cloudflare Worker for our mock bank (template; see bank.js for what to adapt after 17:00 UTC).
// POST /v1/<tool>            body JSON with customer_id -> routed to that customer's Durable Object
// GET  /v1/ledger/<id>       debug ledger (header x-admin-token = ADMIN_TOKEN secret)
// POST /v1/reset/<id>        fresh state for one customer (same header)
// POST /v1/practice/sessions {case: <customer_id>}  (header x-team-key = TEAM_KEY secret) -> a fresh session copy of
//                            that test customer; returns {ok, variables: {customer_id: <session id>, ...variables}}
// GET  /v1/practice/ledger/<session id>             (same header) -> the kit scorer's ledger format
//                            (kit/tools/score.py), so kit/tools/run_cases.py can run against this mock
//                            with FREYA_BANK_HOST pointing here.
// GET  /                     health
import { handle } from "./bank.js";
import { resolve } from "./fixtures.js";
import { serve } from "./services.js";
import customers from "../data/customers.json";
import fixtureData from "../data/fixtures.json";
import pack from "../data/test-customers.json";
import routes from "../data/services.json";

// Request headers kept for debugging (which headers does the platform send per call?); credentials and IPs dropped.
const safeHeaders = (request) =>
  Object.fromEntries([...request.headers].filter(([k]) => !/cookie|authorization|token|key|ip$|forwarded/i.test(k)));

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function findCustomer(id) {
  return (customers.customers || []).find((c) => c.customer_id === id);
}

function ledgerView(state) {
  const s = state || { promises: [], notes: [], callbacks: [], transfers: [], calls: [], outcome: null, reason: null };
  return {
    outcome: s.outcome, reason: s.reason, promises: s.promises, notes: s.notes, callbacks: s.callbacks,
    transfers: s.transfers, verified: s.verified || {}, wrong: s.wrong || 0,
    calls: (s.calls || []).map((c) => ({ tool: c.tool, args: c.body, result: c.response })),
  };
}

export class CustomerState {
  constructor(ctx) {
    this.ctx = ctx;
  }

  async fetch(request) {
    const { op, tool, body, customer, headers } = await request.json();
    let state = await this.ctx.storage.get("state");
    if (op === "init") {
      await this.ctx.storage.put("customer", customer);
      await this.ctx.storage.delete("state");
      return json(200, { ok: true });
    }
    if (op === "ledger") return json(200, { ok: true, state: state || null, headers: (await this.ctx.storage.get("headers")) || [] });
    if (op === "practice_ledger") return json(200, { ok: true, ...ledgerView(state) });
    if (op === "reset") {
      await this.ctx.storage.delete("state");
      return json(200, { ok: true });
    }
    const who = customer || (await this.ctx.storage.get("customer"));
    if (!who) return json(404, { ok: false, error: "unknown customer_id" });
    const res = handle(state, who, tool, body, customers.config || {});
    await this.ctx.storage.put("state", res.state);
    if (headers) await this.ctx.storage.put("headers", [...((await this.ctx.storage.get("headers")) || []), { tool, headers }].slice(-20));
    return json(res.status, res.body);
  }
}

// The last requests (method, path, fields, answer), for reading what the phone agent really sent.
export class RequestLog {
  constructor(ctx) {
    this.ctx = ctx;
  }

  async fetch(request) {
    const { op, entry } = await request.json();
    const log = (await this.ctx.storage.get("log")) || [];
    if (op === "add") {
      log.push(entry);
      await this.ctx.storage.put("log", log.slice(-300));
      return json(200, { ok: true });
    }
    if (op === "clear") {
      await this.ctx.storage.put("log", []);
      return json(200, { ok: true });
    }
    return json(200, { ok: true, log });
  }
}

const logStub = (env) => env.REQUEST_LOG.get(env.REQUEST_LOG.idFromName("log"));

export default {
  // The bank's services: fixtures (data/fixtures.json) first; the practice-kit routes below stay for kit tests.
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/") return json(200, { ok: true, service: "mock-bank" });
    if (url.pathname === "/__admin/log") {
      if (!env.ADMIN_TOKEN || request.headers.get("x-admin-token") !== env.ADMIN_TOKEN) return json(403, { ok: false, error: "forbidden" });
      const op = request.method === "DELETE" ? "clear" : "list";
      return logStub(env).fetch("https://do/", { method: "POST", body: JSON.stringify({ op }) });
    }
    const query = Object.fromEntries(url.searchParams);
    let body = null;
    if (request.method !== "GET" && request.method !== "HEAD") {
      const raw = await request.clone().text();
      try {
        body = raw ? JSON.parse(raw) : null;
      } catch {
        body = raw;
      }
    }
    const sv = serve(pack, routes.services || {}, routes.errors || {}, request.method, url.pathname, query, body);
    if (sv) {
      if (sv.delaySeconds > 0) await new Promise((done) => setTimeout(done, sv.delaySeconds * 1000));
      const entry = { at: new Date().toISOString(), method: request.method, path: url.pathname, query, body, status: sv.status, service: sv.service, delaySeconds: sv.delaySeconds, response: sv.body, headers: safeHeaders(request) };
      ctx.waitUntil(logStub(env).fetch("https://do/", { method: "POST", body: JSON.stringify({ op: "add", entry }) }));
      return json(sv.status, sv.body);
    }
    const r = resolve(fixtureData, request.method, url.pathname, query, body);
    if (r.endpoint) {
      const entry = { at: new Date().toISOString(), method: request.method, path: url.pathname, query, body, status: r.status, fixture: r.fixture, response: r.body, headers: safeHeaders(request) };
      ctx.waitUntil(logStub(env).fetch("https://do/", { method: "POST", body: JSON.stringify({ op: "add", entry }) }));
      return json(r.status, r.body);
    }
    return practice(request, env, url);
  },
};

async function practice(request, env, url) {
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts[0] !== "v1") return json(fixtureData.unmatched?.status || 404, fixtureData.unmatched?.body || { ok: false, error: "not found" });
  const admin = request.headers.get("x-admin-token");
  if ((parts[1] === "ledger" || parts[1] === "reset") && parts[2]) {
    if (!env.ADMIN_TOKEN || admin !== env.ADMIN_TOKEN) return json(403, { ok: false, error: "forbidden" });
    const stub = env.CUSTOMER_STATE.get(env.CUSTOMER_STATE.idFromName(parts[2]));
    return stub.fetch("https://do/", { method: "POST", body: JSON.stringify({ op: parts[1] }) });
  }
  if (parts[1] === "practice") {
    if (!env.TEAM_KEY || request.headers.get("x-team-key") !== env.TEAM_KEY) return json(403, { ok: false, error: "forbidden" });
    if (parts[2] === "sessions" && request.method === "POST") {
      const { case: id } = await request.json().catch(() => ({}));
      const base = findCustomer(id);
      if (!base) return json(404, { ok: false, error: "unknown case" });
      const sid = "s_" + crypto.randomUUID().replace(/-/g, "").slice(0, 12);
      const stub = env.CUSTOMER_STATE.get(env.CUSTOMER_STATE.idFromName(sid));
      await stub.fetch("https://do/", { method: "POST", body: JSON.stringify({ op: "init", customer: { ...base, customer_id: sid } }) });
      return json(200, { ok: true, variables: { ...(base.variables || {}), customer_id: sid } });
    }
    if (parts[2] === "ledger" && parts[3]) {
      const stub = env.CUSTOMER_STATE.get(env.CUSTOMER_STATE.idFromName(parts[3]));
      return stub.fetch("https://do/", { method: "POST", body: JSON.stringify({ op: "practice_ledger" }) });
    }
    return json(404, { ok: false, error: "not found" });
  }
  if (request.method !== "POST" || parts.length !== 2) return json(404, { ok: false, error: "not found" });
  let body;
  try {
    body = await request.json();
  } catch {
    return json(400, { ok: false, error: "body must be JSON" });
  }
  const customer = findCustomer(body.customer_id) || null; // null: a practice session, its customer is in the DO
  if (!customer && !String(body.customer_id || "").startsWith("s_")) return json(404, { ok: false, error: "unknown customer_id" });
  const stub = env.CUSTOMER_STATE.get(env.CUSTOMER_STATE.idFromName(body.customer_id));
  return stub.fetch("https://do/", { method: "POST", body: JSON.stringify({ op: "tool", tool: parts[1], body, customer, headers: safeHeaders(request) }) });
}
