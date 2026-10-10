"""Experiment 01: platform mechanics the builder design depends on (not a submission).

Questions (kit docs mark these "not confirmed" or don't cover them):
  Q1. In what form does a list mapped from get_account (`data.products`) reach a later code node's `vars`?
  Q2. Deterministic, ordered closing: the model says goodbye AND fires a tool-call transition; the target
      api_request node runs close_call engine-side with a baked outcome; then end_call. Is the goodbye before
      close_call, and is there no race with other tools?
  Q3. A post-hook `what_to_do_next` line on verify_identity steers the model.

Run:  python experiments/exp01_mechanics.py   -> prints workflow_id / agent_id
      make cases AGENT=<agent_id> ONLY=PUB-08,PUB-01
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _kit import RUNS, freya  # noqa: E402

BANK = "https://freya-bank-mock.freyavoice.workers.dev/v1"
JSON_HEADERS = {
    "type": "object",
    "properties": {"Content-Type": {"type": "string", "default": "application/json"}},
}


def request_params(name: str, body_props: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "url": {"type": "string", "default": f"{BANK}/{name}"},
            "method": {"type": "string", "default": "POST"},
            "headers": JSON_HEADERS,
            "body": {"type": "object", "properties": body_props, "required": required},
        },
    }


def model_tool(name: str, desc: str, fields: dict, post: str = "") -> dict:
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    for f, (typ, d) in fields.items():
        props[f] = {"type": typ, "description": d, "default": "{{" + f + "}}"}
    tool = {
        "type": "function",
        "config": {"timeoutMs": 10000, "maxRetries": 0},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": desc,
            "parameters": request_params(name, props, list(fields)),
        },
    }
    if post:
        tool["post_process_code"] = post
    return tool


def engine_call(name: str, baked: dict, retries: int = 0) -> dict:
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    props |= {k: {"type": "string", "default": v} for k, v in baked.items()}
    return {
        "type": "function",
        "config": {"timeoutMs": 10000, "maxRetries": retries},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": name,
            "parameters": request_params(name, props, []),
        },
    }


def always(target: str) -> dict:
    return {"target_node": target, "description": "always", "condition": {"operator": "always"}}


def code_node(name: str, code: str, nxt: str) -> dict:
    return {
        "name": name,
        "node_type": "code",
        "passthrough": True,
        "passthrough_default_transition": nxt,
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "pre_actions": [
            {
                "type": "function",
                "function": {
                    "name": "code_exec",
                    "handler": "__function__:code_exec",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "default": code},
                            "timeout_ms": {"type": "number", "default": 10000},
                        },
                    },
                },
            }
        ],
        "transitions": [always(nxt)],
    }


def close_node(name: str, outcome: str) -> dict:
    return {
        "name": name,
        "node_type": "api_request",
        "passthrough": True,
        "passthrough_default_transition": "hang_up",
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "pre_actions": [engine_call("close_call", {"outcome": outcome})],
        "transitions": [always("hang_up")],
    }


VERIFY_POST = """try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if isinstance(d, dict):
            if str(d.get('all_verified')).lower() == 'true':
                d['what_to_do_next'] = 'Both answers are verified. Ask no more security questions.'
            elif str(d.get('ok')).lower() == 'false':
                d['what_to_do_next'] = 'The answer was not accepted. Ask the customer to say it again.'
            elif str(d.get('verified')).lower() == 'true':
                d['what_to_do_next'] = 'Correct. Now ask the next security question.'
            else:
                d['what_to_do_next'] = 'Wrong answer. Ask the same question once more.'
except Exception:
    pass
"""

FACTS_CODE = """import json
try:
    raw = vars.get('products')
    kind = type(raw).__name__
    items = raw
    if isinstance(raw, str):
        try:
            items = json.loads(raw)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    keys = sorted(k for k in vars.keys() if k.startswith('get_account') or k.startswith('fetch_account'))
    vars['exp_products_kind'] = kind
    vars['exp_result_keys'] = ', '.join(keys[:40])
    lines = []
    for p in items:
        if isinstance(p, dict):
            lines.append(str(p.get('product_id')) + ': ' + str(p.get('type')) + ', past due '
                         + str(p.get('past_due')) + ', ' + str(p.get('days_late')) + ' days late')
    vars['debt_facts'] = '; '.join(lines) or 'NO PRODUCTS PARSED'
except Exception as e:
    vars['debt_facts'] = 'NO PRODUCTS PARSED'
    vars['exp_products_kind'] = 'error ' + str(e)
"""

SETUP_CODE = """try:
    vars['exp_today'] = str(vars.get('now') or '')[:10] or 'unknown'
except Exception:
    vars['exp_today'] = 'unknown'
"""


def workflow() -> dict:
    identity_task = (
        "If the person confirms they are {{title}} {{last_name}}, ask for the date of birth, then the last "
        "four digits of the phone number on file, one at a time. CALL verify_identity with each answer "
        "(field date_of_birth with the date as YYYY-MM-DD, or field phone_last4 with four digits). "
        "Follow what_to_do_next in every tool result. Do not mention money, debt or payments."
    )
    talk_task = (
        "The customer is verified. Today is {{exp_today}}. Their late products: {{debt_facts}}.\n"
        "Say you are calling from the collections team about a late payment, name the product, the "
        "past-due amount and the days late, then ask: 'Can you make this payment today?'.\n"
        "- If they say they already paid: say payments can take one business day to appear, thank "
        "them and say goodbye, and in the same message call transition_to_close_paid.\n"
        "- If they agree to pay the full amount today: read back the product, amount and date and ask "
        "'Do you confirm?'. After a clear yes CALL create_promise. Only after it returns ok true, say "
        "'You will receive a text message confirming this promise.', thank them, say goodbye, and in "
        "the same message call transition_to_close_promise.\n"
        "After every tool result, speak or call the next tool."
    )
    return {
        "initial_node": "setup",
        "system_prompt": (
            "You are Freya Bank's digital assistant on an outbound phone call. Speak English. "
            "Keep every turn to one or two short sentences."
        ),
        "nodes": {
            "setup": code_node("setup", SETUP_CODE, "identity"),
            "identity": {
                "name": "identity",
                "node_type": "conversation",
                "on_enter": {
                    "type": "tts",
                    "text": "Hello, this is Freya Bank's digital assistant, and this call is recorded. "
                    "Am I speaking with {{title}} {{last_name}}?",
                },
                "on_enter_first_entry_only": True,
                "task_message": identity_task,
                "tools": [
                    model_tool(
                        "verify_identity",
                        "Check one security answer. CALL it every time the customer answers.",
                        {
                            "field": ("string", "date_of_birth or phone_last4"),
                            "answer": ("string", "date as YYYY-MM-DD, or four digits"),
                        },
                        VERIFY_POST,
                    )
                ],
                "max_node_turns": 30,
                "transitions": [
                    {
                        "target_node": "fetch_account",
                        "description": "both security answers verified",
                        "condition": {
                            "logic": "or",
                            "conditions": [
                                {
                                    "variable": "verify_identity_response.data.all_verified",
                                    "operator": "equals",
                                    "operand": v,
                                }
                                for v in ("true", "True")
                            ],
                        },
                    }
                ],
            },
            "fetch_account": {
                "name": "fetch_account",
                "node_type": "api_request",
                "passthrough": True,
                "passthrough_default_transition": "facts",
                "on_enter": {"type": "silent"},
                "disable_inactivity_monitor": True,
                "pre_actions": [engine_call("get_account", {}, retries=2)],
                "response_mapping": [{"path": "data.products", "variable": "products"}],
                "transitions": [always("facts")],
            },
            "facts": code_node("facts", FACTS_CODE, "talk"),
            "talk": {
                "name": "talk",
                "node_type": "conversation",
                "task_message": talk_task,
                "tools": [
                    model_tool(
                        "create_promise",
                        "Record a payment promise. CALL it only after the customer confirmed.",
                        {
                            "product_id": ("string", "product_id, e.g. p1"),
                            "amount": ("number", "amount"),
                            "date": ("string", "YYYY-MM-DD"),
                        },
                    )
                ],
                "max_node_turns": 30,
                "transitions": [
                    {
                        "target_node": "close_paid",
                        "description": "The customer already paid and the agent said goodbye",
                        "is_tool_call": True,
                        "condition": {
                            "operator": "matches_intent",
                            "description": "The customer already paid and the agent said goodbye",
                        },
                    },
                    {
                        "target_node": "close_promise",
                        "description": "A promise was recorded and the agent said goodbye",
                        "is_tool_call": True,
                        "condition": {
                            "operator": "matches_intent",
                            "description": "A promise was recorded and the agent said goodbye",
                        },
                    },
                ],
            },
            "close_paid": close_node("close_paid", "paid"),
            "close_promise": close_node("close_promise", "promise"),
            "hang_up": {
                "name": "hang_up",
                "node_type": "end_call",
                "on_enter": {"type": "silent"},
                "disable_inactivity_monitor": True,
                "transitions": [],
                "terminal": {
                    "type": "function",
                    "function": {
                        "name": "call_closed",
                        "handler": "__function__:end_call",
                        "parameters": {
                            "type": "object",
                            "properties": {"message_mode": {"type": "string", "default": "none"}},
                        },
                    },
                },
            },
        },
        "global_nodes": {},
        "test_variables": {
            "customer_id": "c_test",
            "first_name": "Daniel",
            "last_name": "Reyes",
            "title": "Mr",
            "now": "2026-10-14T11:00",
        },
    }


if __name__ == "__main__":
    wf = workflow()
    if "--print" in sys.argv:
        print(json.dumps(wf, indent=1))
        sys.exit()
    RUNS.mkdir(exist_ok=True)
    freya.validate_workflow("exp01", wf)
    print(json.dumps(freya.save_workflow("exp01", wf, state_file=str(RUNS / "experiments.json"))))
