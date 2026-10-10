"""Read tool results inside a Freya code node.

Verified in experiments/exp01_mechanics.py: an api_request node's result is in `vars` as flattened
keys named after the NODE, e.g. `fetch_account_response.data.products.0.past_due`; a node-level
response_mapping of a list did not set its variable. These helpers rebuild values from the keys,
and also accept a real list or a JSON string in case a mapping does arrive.
Sandbox-safe: imports nothing beyond json/re.
"""

import json
import re


def _value(raw):
    """Flattened values arrive as strings; turn numbers and booleans back into Python values."""
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("none", "null"):
        return None
    try:
        if re.fullmatch(r"-?[0-9]+", text):
            return int(text)
        if re.fullmatch(r"-?[0-9]*\.[0-9]+", text):
            return float(text)
    except Exception:
        return raw
    return raw


def collect_list(vs, prefix):
    """List of dicts stored under `prefix` (flattened `prefix.<i>.<field>`, a list, or JSON text)."""
    direct = vs.get(prefix)
    if isinstance(direct, list):
        return [d for d in direct if isinstance(d, dict)]
    if isinstance(direct, str) and direct.strip().startswith("["):
        try:
            parsed = json.loads(direct)
            if isinstance(parsed, list):
                return [d for d in parsed if isinstance(d, dict)]
        except Exception:
            pass
    items = {}
    head = prefix + "."
    for key in list(vs.keys()):
        if not str(key).startswith(head):
            continue
        rest = str(key)[len(head) :].split(".", 1)
        if len(rest) != 2 or not rest[0].isdigit():
            continue
        items.setdefault(int(rest[0]), {})[rest[1]] = _value(vs.get(key))
    return [items[i] for i in sorted(items)]


def get_value(vs, key):
    return _value(vs.get(key))
