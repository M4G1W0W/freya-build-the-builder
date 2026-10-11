// The bank's services, answered from the test-customer pack (data/test-customers.json) exactly: status, body, delay.
// Pure logic: no Cloudflare APIs, so `npm test` runs it with plain Node.
//
// data/services.json (from the service contract and the pack's lookup table):
//   base: path prefixes the services are served under, e.g. ["/voice/v1", ""]  (POST <base>/<service>)
//   services: {"<service>": {by: ["customerNo"] | ["cardNumber", "newStatementWeek"?], required: [fields],
//              notFound: "<404 code>" | null}}
//   codes: {"<code>": {status, type, message}}; errorOrigin: string
// Fields come from the request's `data` object (top-level fields are accepted too). `by[0]` = customerNo looks the
// customer up; `by[0]` = cardNumber finds the card among every customer's entries of that service; a second `by`
// field selects the nested entry (the requested week). A card matches by its masked number exactly, else by its
// visible digits (first six + last four) when exactly one card has them. No entry -> the service's 404, or a 400
// INVALID_ARGUMENTS_ERROR when the service has none. A missing required field -> 400 naming the field.

const str = (v) => (v === null || v === undefined ? "" : String(v).trim());
const digits = (v) => str(v).replace(/\D/g, "");

const visible = (masked) => {
  const m = str(masked).match(/^(\d{4,6})\D+(\d{4})$/);
  return m ? [m[1], m[2]] : null;
};

export function findCard(keys, value) {
  const v = str(value);
  if (keys.includes(v)) return v;
  const want = visible(v);
  if (!want) return null;
  const hits = keys.filter((k) => {
    const have = visible(k);
    return have && have[1] === want[1] && (have[0].startsWith(want[0]) || want[0].startsWith(have[0]));
  });
  return hits.length === 1 ? hits[0] : null;
}

export function errorBody(cfg, code, message, guid) {
  const c = cfg.codes[code] || { status: 500, type: "ERROR", message: code };
  const text = message || c.message;
  return {
    status: c.status,
    body: {
      result: {
        guid,
        returnCode: code,
        messageText: text,
        code,
        message: text,
        type: c.type,
        details: { guid, rootCause: c.rootCause || null, errorOrigin: cfg.errorOrigin || null },
      },
    },
    delaySeconds: 0,
  };
}

export function fieldsOf(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return {};
  const data = body.data && typeof body.data === "object" && !Array.isArray(body.data) ? body.data : {};
  return { ...body, ...data };
}

// -> {status, body, delaySeconds, service} or null when the path is not one of the bank's services.
export function serve(pack, cfg, method, pathname, body, guid = "0".repeat(32)) {
  const path = pathname.replace(/\/+$/, "");
  const service = Object.keys(cfg.services).find((s) => (cfg.base || [""]).some((b) => path === `${b}/${s}`));
  if (!service) return null;
  const out = (r) => ({ ...r, service });
  if (method.toUpperCase() !== "POST") return out(errorBody(cfg, "INVALID_ARGUMENTS_ERROR", "only POST is supported", guid));
  const s = cfg.services[service];
  const f = fieldsOf(body);
  for (const name of s.required || []) {
    if (str(f[name]) === "") return out(errorBody(cfg, "INVALID_ARGUMENTS_ERROR", `${cfg.fieldLabels?.[name] || name} cannot be empty`, guid));
  }
  const missing = () => out(s.notFound ? errorBody(cfg, s.notFound, null, guid) : errorBody(cfg, "INVALID_ARGUMENTS_ERROR", "no entry for this request", guid));
  const customers = pack.customers || [];
  let entry;
  const [first, second] = s.by;
  if (first === "customerNo") {
    const c = customers.find((x) => str(x.customerNo) === str(f.customerNo));
    entry = c && c.services[service];
  } else {
    const owners = customers.filter((x) => x.services[service] && typeof x.services[service] === "object");
    const keys = owners.flatMap((x) => Object.keys(x.services[service]));
    const key = findCard(keys, f[first]);
    const owner = key && owners.find((x) => key in x.services[service]);
    entry = owner && owner.services[service][key];
  }
  if (entry && second) entry = entry[str(f[second])];
  if (!entry || entry.http === undefined) return missing();
  return out({
    status: entry.http,
    body: entry.response !== undefined ? entry.response : entry.yanit,
    delaySeconds: Number(entry.delaySeconds ?? entry.gecikmeSaniye ?? 0) || 0,
  });
}
