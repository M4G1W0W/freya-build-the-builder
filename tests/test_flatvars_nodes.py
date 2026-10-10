import json

from freya_builder import nodes
from freya_builder.sandbox import assemble
from freya_builder.validate import validate

# Shape observed on the platform in experiments/exp01_mechanics.py (values arrive as strings).
FLAT = {
    "fetch_account_response.data.ok": "true",
    "fetch_account_response.data.products.0.product_id": "p1",
    "fetch_account_response.data.products.0.type": "credit_card",
    "fetch_account_response.data.products.0.past_due": "420",
    "fetch_account_response.data.products.0.minimum_payment": "126.5",
    "fetch_account_response.data.products.1.product_id": "p2",
    "fetch_account_response.data.products.1.days_late": "21",
    "unrelated": "x",
}

MAIN = """
try:
    items = collect_list(vars, 'fetch_account_response.data.products')
    vars['n'] = len(items)
    vars['first'] = items[0]
    vars['ok'] = get_value(vars, 'fetch_account_response.data.ok')
except Exception as e:
    vars['n'] = -1
    vars['err'] = str(e)
"""


def run(vs):
    exec(assemble(["flatvars"], MAIN, {}), {"vars": vs})
    return vs


def test_rebuilds_list_from_flattened_keys():
    vs = run(dict(FLAT))
    assert vs["n"] == 2
    assert vs["first"] == {
        "product_id": "p1",
        "type": "credit_card",
        "past_due": 420,
        "minimum_payment": 126.5,
    }
    assert vs["ok"] is True


def test_accepts_real_list_and_json_text():
    products = [{"product_id": "p9"}]
    assert run({"fetch_account_response.data.products": products})["n"] == 1
    assert run({"fetch_account_response.data.products": json.dumps(products)})["n"] == 1


def test_node_builders_produce_a_valid_workflow():
    wf = {
        "initial_node": "setup",
        "nodes": {
            "setup": nodes.code_node("setup", "x = 1\n", [nodes.always("talk")]),
            "talk": nodes.conversation(
                "talk",
                "Say hello.",
                [
                    nodes.when_true(
                        "fetch", "verified", "verify_identity_response.data.all_verified"
                    ),
                    nodes.tool_transition("bye", "goodbye said"),
                ],
                max_turn_target="bye",
            ),
            "fetch": nodes.api_node("fetch", [{"type": "function"}], [nodes.always("bye")]),
            "bye": nodes.end_node("bye", "call_closed"),
        },
        "global_nodes": {},
    }
    assert validate(wf) == []
    cond = wf["nodes"]["talk"]["transitions"][0]["condition"]["conditions"]
    assert [c["operand"] for c in cond] == ["true", "True"]
