// Fixture-driven mock: the bank's documented answers, served exactly (status + JSON body).
// Pure logic, no Cloudflare APIs, so `npm test` runs it with plain Node.
//
// data/fixtures.json:
//   endpoints: [{method, path, default?: {status, body}}]   path may hold {params}, e.g. /cards/{cardId}/debt
//   fixtures:  [{method, path, match: {field: value}, status, body}]
//   unmatched: {status, body}   answer when no endpoint matches (method + path)
// A request's fields = path params + query params + JSON body fields (body wins). A fixture applies when every
// field in `match` equals the request's field (compared as trimmed strings, case-sensitive); the fixture with the
// most `match` fields wins, ties go to the earlier one. No fixture -> the endpoint's `default`.

const norm = (v) => (v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v).trim());

export function compilePath(path) {
  const names = [];
  const rx = path.replace(/[.*+?^$()|[\]\\]/g, "\\$&").replace(/\\?\{(\w+)\\?\}/g, (_, n) => {
    names.push(n);
    return "([^/]+)";
  });
  return { rx: new RegExp("^" + rx.replace(/\/+$/, "") + "/?$"), names };
}

export function matchPath(pattern, pathname) {
  const { rx, names } = compilePath(pattern);
  const m = rx.exec(pathname);
  if (!m) return null;
  return Object.fromEntries(names.map((n, i) => [n, decodeURIComponent(m[i + 1])]));
}

export function requestFields(params, query, body) {
  const out = { ...params };
  for (const [k, v] of Object.entries(query || {})) out[k] = v;
  if (body && typeof body === "object" && !Array.isArray(body)) for (const [k, v] of Object.entries(body)) out[k] = v;
  return out;
}

export function resolve(data, method, pathname, query, body) {
  const m = method.toUpperCase();
  for (const ep of data.endpoints || []) {
    if (ep.method.toUpperCase() !== m) continue;
    const params = matchPath(ep.path, pathname);
    if (!params) continue;
    const fields = requestFields(params, query, body);
    let best = null;
    for (const f of data.fixtures || []) {
      if (f.method.toUpperCase() !== m || f.path !== ep.path) continue;
      const keys = Object.keys(f.match || {});
      if (!keys.every((k) => norm(fields[k]) === norm(f.match[k]))) continue;
      if (!best || keys.length > Object.keys(best.match || {}).length) best = f;
    }
    if (best) return { status: best.status, body: best.body, endpoint: ep.path, fixture: best.id ?? null };
    const d = ep.default || { status: 404, body: { error: "not found" } };
    return { status: d.status, body: d.body, endpoint: ep.path, fixture: null };
  }
  const u = data.unmatched || { status: 404, body: { error: "not found" } };
  return { status: u.status, body: u.body, endpoint: null, fixture: null };
}
