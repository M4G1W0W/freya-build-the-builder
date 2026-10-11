import { test } from "node:test";
import assert from "node:assert/strict";
import { findCard, serve } from "../src/services.js";

// Synthetic pack in the shape of a test-customer file (no case data).
const PACK = {
  customers: [
    {
      customerNo: "10000001",
      services: {
        "lib.list": { http: 200, response: { data: { items: ["A"] } } },
        "lib.item": {
          "111111******2222": { http: 200, response: { data: { due: "01.01.2027" } } },
          "111111******3333": { http: 500, response: { result: { code: "E" } }, delaySeconds: 2 },
        },
        "lib.renew": { "111111******2222": { "2": { http: 200, response: { ok: true } } } },
        "lib.old": { "111111******2222": { http: 200, yanit: { old: true }, gecikmeSaniye: 3 } },
      },
    },
  ],
};
const ROUTES = {
  "lib.list": { method: "POST", path: "/svc/list", customer: "memberNo" },
  "lib.item": { method: "POST", path: "/svc/item", customer: "memberNo", card: "itemNo" },
  "lib.renew": { method: "POST", path: "/svc/{memberNo}/renew", customer: "memberNo", card: "itemNo", week: "week" },
  "lib.old": { method: "GET", path: "/svc/old", customer: "memberNo", card: "itemNo" },
  "lib.unset": { method: "POST", path: "", customer: "memberNo" },
};
const ERR = {
  unknownCustomer: { status: 404, body: { e: "cust" } },
  notAvailable: { status: 404, body: { e: "svc" } },
  unknownCard: { status: 404, body: { e: "card" } },
  unknownWeek: { status: 400, body: { e: "week" } },
};
const call = (m, p, q, b) => serve(PACK, ROUTES, ERR, m, p, q, b);

test("a customer's documented answer, status and body", () => {
  const r = call("POST", "/svc/list", {}, { memberNo: "10000001" });
  assert.deepEqual([r.status, r.body, r.service, r.delaySeconds], [200, { data: { items: ["A"] } }, "lib.list", 0]);
});

test("card by exact key, by last four digits, and an error status with its delay", () => {
  assert.deepEqual(call("POST", "/svc/item", {}, { memberNo: "10000001", itemNo: "111111******2222" }).body, { data: { due: "01.01.2027" } });
  assert.deepEqual(call("POST", "/svc/item", {}, { memberNo: 10000001, itemNo: "1111********2222" }).body, { data: { due: "01.01.2027" } });
  const r = call("POST", "/svc/item", {}, { memberNo: "10000001", itemNo: "3333" });
  assert.deepEqual([r.status, r.delaySeconds], [500, 2]);
  assert.equal(findCard({ "1111": 1, "x1111": 2 }, "991111"), null); // ambiguous last four -> no card
});

test("path params, week key, and the pack's alternative field names (yanit, gecikmeSaniye)", () => {
  assert.deepEqual(call("POST", "/svc/10000001/renew", {}, { itemNo: "2222", week: 2 }).body, { ok: true });
  const r = call("GET", "/svc/old", { memberNo: "10000001", itemNo: "2222" }, null);
  assert.deepEqual([r.body, r.delaySeconds], [{ old: true }, 3]);
});

test("documented errors for unknown customer, card, week, and a service the customer lacks", () => {
  assert.deepEqual(call("POST", "/svc/list", {}, { memberNo: "999" }).body, { e: "cust" });
  assert.deepEqual(call("POST", "/svc/item", {}, { memberNo: "10000001", itemNo: "9999" }).body, { e: "card" });
  assert.deepEqual(call("POST", "/svc/10000001/renew", {}, { itemNo: "2222", week: 5 }).body, { e: "week" });
  const pack2 = { customers: [{ customerNo: "1", services: {} }] };
  assert.deepEqual(serve(pack2, ROUTES, ERR, "POST", "/svc/list", {}, { memberNo: "1" }).body, { e: "svc" });
});

test("no route (or an unset path, or another method) -> null, so the worker falls through", () => {
  assert.equal(call("POST", "/svc/nothing", {}, {}), null);
  assert.equal(call("GET", "/svc/list", {}, {}), null);
});
