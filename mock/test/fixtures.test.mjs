import { test } from "node:test";
import assert from "node:assert/strict";
import { matchPath, resolve } from "../src/fixtures.js";

// Synthetic data only (a library service); the real table is data/fixtures.json.
const DATA = {
  endpoints: [
    { method: "POST", path: "/api/loans", default: { status: 404, body: { code: "MEMBER_NOT_FOUND" } } },
    { method: "GET", path: "/api/members/{memberNumber}/loans/{loanId}" },
    { method: "POST", path: "/api/renew" },
  ],
  fixtures: [
    { id: "m1", method: "POST", path: "/api/loans", match: { memberNumber: "1234567" }, status: 200, body: { loans: [{ loanId: "L1" }] } },
    { id: "m2", method: "POST", path: "/api/loans", match: { memberNumber: "7654321" }, status: 200, body: { loans: [] } },
    { id: "g1", method: "GET", path: "/api/members/{memberNumber}/loans/{loanId}", match: { memberNumber: "1234567", loanId: "L1" }, status: 200, body: { title: "A" } },
    { id: "r-any", method: "POST", path: "/api/renew", match: { memberNumber: "1234567" }, status: 200, body: { renewed: true } },
    { id: "r-L9", method: "POST", path: "/api/renew", match: { memberNumber: "1234567", loanId: "L9" }, status: 409, body: { renewed: false, reason: "overdue" } },
  ],
  unmatched: { status: 404, body: { error: "no such service" } },
};

test("path params are extracted and a trailing slash is accepted", () => {
  assert.deepEqual(matchPath("/api/members/{memberNumber}/loans/{loanId}", "/api/members/1234567/loans/L1/"), { memberNumber: "1234567", loanId: "L1" });
  assert.equal(matchPath("/api/loans", "/api/loans/x"), null);
});

test("body field match returns the documented status and body", () => {
  assert.deepEqual(resolve(DATA, "POST", "/api/loans", {}, { memberNumber: "1234567" }), { status: 200, body: { loans: [{ loanId: "L1" }] }, endpoint: "/api/loans", fixture: "m1" });
  assert.equal(resolve(DATA, "post", "/api/loans", {}, { memberNumber: 7654321 }).fixture, "m2"); // number vs string, method case
});

test("no fixture -> endpoint default; unknown path or method -> unmatched", () => {
  assert.deepEqual(resolve(DATA, "POST", "/api/loans", {}, { memberNumber: "0000000" }).body, { code: "MEMBER_NOT_FOUND" });
  assert.equal(resolve(DATA, "GET", "/api/loans", {}, null).status, 404);
  assert.deepEqual(resolve(DATA, "POST", "/nope", {}, {}).body, { error: "no such service" });
  assert.equal(resolve(DATA, "POST", "/nope", {}, {}).endpoint, null);
});

test("path and query params match too; the most specific fixture wins", () => {
  assert.equal(resolve(DATA, "GET", "/api/members/1234567/loans/L1", {}, null).fixture, "g1");
  assert.equal(resolve(DATA, "POST", "/api/renew", {}, { memberNumber: "1234567", loanId: "L9" }).fixture, "r-L9");
  assert.equal(resolve(DATA, "POST", "/api/renew", {}, { memberNumber: "1234567", loanId: "L2" }).fixture, "r-any");
  assert.equal(resolve(DATA, "POST", "/api/renew", { memberNumber: "1234567" }, {}).fixture, "r-any"); // query field
});
