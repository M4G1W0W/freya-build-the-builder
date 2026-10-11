// Mock bank logic for the final (template written 11 Oct before 17:00 UTC; adapt after 17:00 from the zip's service
// contract and test customers). Pure functions over a per-customer state object, so it runs in a Durable Object and
// in `node --test`. Nothing here is builder code: the builder must hold nothing from the final case (rules F4, F9).
//
// ADAPT AFTER 17:00 (from the case's service contract): the tool names in HANDLERS, the request field names, the
// response field names, the identity fields and how answers compare, outcome/reason values, and wrong-answer limits.

export const DEFAULTS = {
  maxWrongAnswers: 3, // total wrong identity answers before the check is locked
  idleResetSeconds: 600, // a new call for the same customer after this much silence starts from a fresh state
};

export function freshState(customer) {
  return {
    customer_id: customer.customer_id,
    verified: {}, // field -> true
    wrong: 0,
    promises: [],
    notes: [],
    callbacks: [],
    transfers: [],
    outcome: null,
    reason: null,
    calls: [], // every tool call, for the debug ledger
    last_at: 0,
  };
}

const norm = (v) => String(v ?? "").trim().toLowerCase().replace(/\s+/g, "");

function err(status, error) {
  return { status, body: { ok: false, error } };
}

function ok(body) {
  return { status: 200, body: { ok: true, ...body } };
}

function product(customer, id) {
  return (customer.products || []).find((p) => p.product_id === id);
}

function allVerified(state, customer) {
  return Object.keys(customer.identity || {}).every((f) => state.verified[f]);
}

// One handler per tool: (state, customer, body, config) -> {status, body}. Mutates state.
export const HANDLERS = {
  verify_identity(state, customer, body, config) {
    const field = body.field;
    if (!(field in (customer.identity || {}))) return err(400, `unknown field ${field}`);
    if (state.wrong >= config.maxWrongAnswers) {
      return ok({ verified: false, wrong_answers_left: 0, all_verified: false, locked: true });
    }
    const good = norm(body.answer) === norm(customer.identity[field]);
    if (good) state.verified[field] = true;
    else state.wrong += 1;
    return ok({
      verified: good,
      wrong_answers_left: Math.max(0, config.maxWrongAnswers - state.wrong),
      all_verified: allVerified(state, customer),
    });
  },

  get_account(state, customer) {
    if (!allVerified(state, customer)) return err(403, "identity not verified");
    return ok({ products: customer.products || [] });
  },

  create_promise(state, customer, body) {
    if (!allVerified(state, customer)) return err(403, "identity not verified");
    const p = product(customer, body.product_id);
    if (!p) return err(400, `unknown product_id ${body.product_id}`);
    if (state.promises.some((x) => x.product_id === body.product_id)) {
      return err(409, "a promise for this product is already recorded");
    }
    const amount = Number(body.amount);
    if (!(amount > 0)) return err(400, "amount must be positive");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(body.date || ""))) return err(400, "date must be YYYY-MM-DD");
    const promise = { promise_id: `pr${state.promises.length + 1}`, product_id: body.product_id, amount, date: body.date };
    state.promises.push(promise);
    return ok({ promise_id: promise.promise_id });
  },

  add_note(state, customer, body) {
    if (body.product_id && !product(customer, body.product_id)) return err(400, `unknown product_id ${body.product_id}`);
    state.notes.push({ product_id: body.product_id ?? null, reason: body.reason ?? null, text: body.text ?? null });
    return ok({});
  },

  schedule_callback(state, customer, body) {
    if (!body.date || !body.time) return err(400, "date and time are required");
    state.callbacks.push({ date: body.date, time: body.time });
    return ok({});
  },

  transfer_to_agent(state, customer, body) {
    if (!body.queue) return err(400, "queue is required");
    state.transfers.push({ queue: body.queue });
    return ok({});
  },

  close_call(state, customer, body) {
    if (!body.outcome) return err(400, "outcome is required");
    state.outcome = body.outcome;
    state.reason = body.reason ?? null;
    return ok({});
  },
};

// Entry point: one tool call for one customer. Returns {state, status, body}.
export function handle(state, customer, tool, body, config = DEFAULTS, nowSeconds = Date.now() / 1000) {
  const cfg = { ...DEFAULTS, ...config };
  let s = state;
  if (!s || nowSeconds - (s.last_at || 0) > cfg.idleResetSeconds) s = freshState(customer);
  const h = HANDLERS[tool];
  const res = h ? h(s, customer, body || {}, cfg) : err(404, `unknown tool ${tool}`);
  s.last_at = nowSeconds;
  s.calls.push({ at: nowSeconds, tool, body, status: res.status, response: res.body });
  return { state: s, status: res.status, body: res.body };
}
