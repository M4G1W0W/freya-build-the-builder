import { test } from "node:test";
import assert from "node:assert/strict";
import { findCard, serve } from "../src/services.js";

// Synthetic pack and config in the shape of the real ones (no case data).
const PACK = {
  customers: [
    {
      customerNo: "10000001",
      services: {
        "x.list": { http: 200, response: { data: { cards: ["A"] } } },
        "x.balance": {
          "111111******2222": { http: 200, response: { data: { due: "01.01.2027" } } },
          "222222******2222": { http: 500, response: { result: { code: "E" } }, delaySeconds: 2 },
        },
        "x.week": { "111111******2222": { "2": { http: 200, response: { ok: true } } } },
      },
    },
    { customerNo: "10000002", services: { "x.list": { http: 200, yanit: { old: true }, gecikmeSaniye: 3 } } },
  ],
};
const CFG = {
  base: ["/voice/v1", ""],
  errorOrigin: "test",
  services: {
    "x.list": { by: ["customerNo"], required: ["customerNo"], notFound: "NF_LIST" },
    "x.balance": { by: ["cardNumber"], required: ["cardNumber"], notFound: "NF_BAL" },
    "x.week": { by: ["cardNumber", "newStatementWeek"], required: ["cardNumber", "newStatementWeek"], notFound: null },
    "x.mail": { by: ["customerNo"], required: ["customerNo", "kind"], notFound: null },
  },
  fieldLabels: { cardNumber: "card number" },
  codes: {
    INVALID_ARGUMENTS_ERROR: { status: 400, type: "ERROR", message: "invalid" },
    NF_LIST: { status: 404, type: "WARNING", message: "no card" },
    NF_BAL: { status: 404, type: "WARNING", message: "card not found" },
  },
};
const call = (path, data, method = "POST") => serve(PACK, CFG, method, path, { data, call: { ani: "x", lang: "tr" } }, "g");

test("documented answer by customer number (string or number), under every base path", () => {
  for (const p of ["/voice/v1/x.list", "/x.list", "/x.list/"]) {
    const r = call(p, { customerNo: 10000001 });
    assert.deepEqual([r.status, r.body, r.service], [200, { data: { cards: ["A"] } }, "x.list"]);
  }
  const old = call("/x.list", { customerNo: "10000002" });
  assert.deepEqual([old.body, old.delaySeconds], [{ old: true }, 3]);
});

test("card found across customers: exact, then by visible digits; the error entry keeps its status and delay", () => {
  assert.deepEqual(call("/x.balance", { cardNumber: "111111******2222" }).body, { data: { due: "01.01.2027" } });
  assert.deepEqual(call("/x.balance", { cardNumber: "1111********2222" }).body, { data: { due: "01.01.2027" } });
  const r = call("/x.balance", { cardNumber: "222222******2222" });
  assert.deepEqual([r.status, r.delaySeconds], [500, 2]);
  assert.equal(findCard(["111111******2222", "222222******2222"], "2222"), null); // last four alone is ambiguous
  assert.equal(findCard(["111111******2222", "111122******2222"], "1111********2222"), null); // two prefixes fit
});

test("week entry by number or string; the card's current week (no entry) -> 400 INVALID_ARGUMENTS_ERROR", () => {
  assert.deepEqual(call("/x.week", { cardNumber: "111111******2222", newStatementWeek: 2 }).body, { ok: true });
  const r = call("/x.week", { cardNumber: "111111******2222", newStatementWeek: "1" });
  assert.equal(r.status, 400);
  assert.equal(r.body.result.code, "INVALID_ARGUMENTS_ERROR");
  assert.equal(r.body.data, undefined);
});

test("unknown customer or card -> the service's 404 in the contract's error shape", () => {
  const r = call("/x.list", { customerNo: "99" });
  assert.equal(r.status, 404);
  assert.deepEqual(r.body.result, { guid: "g", returnCode: "NF_LIST", messageText: "no card", code: "NF_LIST", message: "no card", type: "WARNING", details: { guid: "g", rootCause: null, errorOrigin: "test" } });
  assert.equal(call("/x.balance", { cardNumber: "999999******9999" }).body.result.code, "NF_BAL");
});

test("missing or empty required field -> 400 naming it; top-level fields accepted; non-services fall through", () => {
  assert.equal(call("/x.balance", { cardNumber: "" }).body.result.message, "card number cannot be empty");
  assert.equal(call("/x.mail", { customerNo: "10000001" }).body.result.message, "kind cannot be empty");
  assert.equal(serve(PACK, CFG, "POST", "/x.list", { customerNo: "10000001" }).status, 200);
  assert.equal(call("/voice/v1/other", {}), null);
  assert.equal(call("/x.list", { customerNo: "10000001" }, "GET").status, 400);
});

test("dotted top-level keys and a data object sent as a JSON string are read; empty never hides filled", () => {
  const dotted = serve(PACK, CFG, "POST", "/x.list", { data: {}, call: {}, "data.customerNo": "10000001", "call.ani": "x" });
  assert.equal(dotted.status, 200);
  const asString = serve(PACK, CFG, "POST", "/x.balance", { data: '{"cardNumber": "111111******2222"}' });
  assert.deepEqual(asString.body, { data: { due: "01.01.2027" } });
  const both = serve(PACK, CFG, "POST", "/x.list", { data: { customerNo: "" }, "data.customerNo": "10000001" });
  assert.equal(both.status, 200);
});

test("the token path answers the documented token response under every base", () => {
  const cfg = { ...CFG, token: { paths: ["/oauth2/token"], response: { access_token: "t", token_type: "Bearer", expires_in: 1800 } } };
  for (const p of ["/voice/v1/oauth2/token", "/oauth2/token"]) {
    const r = serve(PACK, cfg, "POST", p, "grant_type=client_credentials");
    assert.deepEqual([r.status, r.body.token_type, r.service], [200, "Bearer", "token"]);
  }
});

test("configured aliases fill an empty field (the call variable's name for the customer number)", () => {
  const cfg = { ...CFG, aliases: { customerNo: ["customerNumber"] } };
  assert.equal(serve(PACK, cfg, "POST", "/x.list", { data: { customerNumber: "10000001" } }).status, 200);
  assert.equal(serve(PACK, CFG, "POST", "/x.list", { data: { customerNumber: "10000001" } }).status, 400);
});
