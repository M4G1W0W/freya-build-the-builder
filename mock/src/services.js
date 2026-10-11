// The bank's services, answered from the test-customer pack (data/test-customers.json) exactly: status, body, delay.
// Pure logic: no Cloudflare APIs, so `npm test` runs it with plain Node.
//
// data/services.json maps each service of the pack to its HTTP route and request fields (from the service contract):
//   {"<service>": {"method": "POST", "path": "/...", "customer": "<field>", "card": "<field>"?, "week": "<field>"?}}
// A request's fields = path params + query + JSON body (body wins). Lookup: customer -> service -> card -> week.
// A card is found by its exact key first, then by its last four digits (unique among the customer's cards).

import { matchPath, requestFields } from "./fixtures.js";

const str = (v) => (v === null || v === undefined ? "" : String(v).trim());
const digits = (v) => str(v).replace(/\D/g, "");

export function findCard(entries, value) {
  const v = str(value);
  if (v in entries) return v;
  const last4 = digits(v).slice(-4);
  if (last4.length < 4) return null;
  const hits = Object.keys(entries).filter((k) => digits(k).endsWith(last4));
  return hits.length === 1 ? hits[0] : null;
}

const answer = (e) => ({
  status: e.http,
  body: e.response !== undefined ? e.response : e.yanit,
  delaySeconds: Number(e.delaySeconds ?? e.gecikmeSaniye ?? 0) || 0,
});

// -> {status, body, delaySeconds, service, route} or null when no route of services.json matches.
export function serve(pack, routes, errors, method, pathname, query, body) {
  for (const [service, r] of Object.entries(routes)) {
    if (!r.path || str(r.method).toUpperCase() !== method.toUpperCase()) continue;
    const params = matchPath(r.path, pathname);
    if (!params) continue;
    const fields = requestFields(params, query, body);
    const out = (e) => ({ ...e, service, route: r.path });
    const customer = (pack.customers || []).find((c) => str(c.customerNo) === str(fields[r.customer]));
    if (!customer) return out({ ...errors.unknownCustomer, delaySeconds: 0 });
    let e = customer.services[service];
    if (!e) return out({ ...errors.notAvailable, delaySeconds: 0 });
    if (r.card) {
      const key = findCard(e, fields[r.card]);
      if (!key) return out({ ...errors.unknownCard, delaySeconds: 0 });
      e = e[key];
    }
    if (r.week) {
      const week = str(fields[r.week]);
      if (!(week in e)) return out({ ...errors.unknownWeek, delaySeconds: 0 });
      e = e[week];
    }
    return out(answer(e));
  }
  return null;
}
