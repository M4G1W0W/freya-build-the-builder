import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { handle } from "../src/bank.js";

const data = JSON.parse(readFileSync(new URL("../data/customers.json", import.meta.url)));
const one = data.customers[0];
const multi = data.customers[1];
const T = 1_000_000;

function run(customer, calls, start = T) {
  let state;
  return calls.map(([tool, body], i) => {
    const r = handle(state, customer, tool, { customer_id: customer.customer_id, ...body }, data.config, start + i);
    state = r.state;
    return r;
  });
}

const right = (c) => Object.entries(c.identity).map(([field, answer]) => ["verify_identity", { field, answer }]);

test("verified customer gets the account, one promise, then close", () => {
  const r = run(one, [...right(one), ["get_account", {}], ["create_promise", { product_id: "p1", amount: 100, date: "2026-10-14" }], ["close_call", { outcome: "promise" }]]);
  assert.equal(r[1].body.all_verified, true);
  assert.equal(r[2].body.products.length, 1);
  assert.equal(r[3].body.promise_id, "pr1");
  assert.equal(r.at(-1).state.outcome, "promise");
});

test("account and promise are refused before verification", () => {
  const r = run(one, [["get_account", {}], ["create_promise", { product_id: "p1", amount: 1, date: "2026-10-14" }]]);
  assert.equal(r[0].status, 403);
  assert.equal(r[1].status, 403);
});

test("three wrong answers lock the check", () => {
  const field = Object.keys(one.identity)[0];
  const r = run(one, [1, 2, 3, 4].map((n) => ["verify_identity", { field, answer: `wrong${n}` }]).concat([["verify_identity", { field, answer: one.identity[field] }]]));
  assert.deepEqual(r.slice(0, 3).map((x) => x.body.wrong_answers_left), [2, 1, 0]);
  assert.equal(r[4].body.locked, true);
  assert.equal(r[4].body.verified, false);
});

test("one promise per product; unknown product refused", () => {
  const r = run(multi, [...right(multi), ["create_promise", { product_id: "p2", amount: 5, date: "2026-10-15" }], ["create_promise", { product_id: "p2", amount: 6, date: "2026-10-16" }], ["create_promise", { product_id: "p9", amount: 1, date: "2026-10-15" }]]);
  const n = Object.keys(multi.identity).length;
  assert.equal(r[n].status, 200);
  assert.equal(r[n + 1].status, 409);
  assert.equal(r[n + 2].status, 400);
});

test("a new call after the idle window starts fresh", () => {
  let r = run(one, right(one));
  const s = r.at(-1).state;
  const later = handle(s, one, "get_account", { customer_id: one.customer_id }, data.config, T + 10_000);
  assert.equal(later.status, 403);
  assert.equal(later.state.calls.length, 1);
});

test("unknown tool is a 404 and every call is in the ledger", () => {
  const r = run(one, [["nope", {}]]);
  assert.equal(r[0].status, 404);
  assert.equal(r[0].state.calls.length, 1);
});
