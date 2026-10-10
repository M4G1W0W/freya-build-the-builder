"""Date expressions in the spec: a whitelisted Python subset over a fixed helper vocabulary.

Examples (generic, not from any brief):
    add_business_days(today, 10)
    last_business_day_of_week(today) if last_business_day_of_week(today) != today
        else last_business_day_of_week(add_days(today, 7))
    min(deadline, end_of_month(today))

The builder checks every expression here, then inlines it as code into the code-node source
(no eval at run time). Names available: see NAMES; functions: see FUNCS (sandbox/policy_helpers.py).
"""

import ast

NAMES = {"today", "now_date", "deadline", "p_days_late"}
FUNCS = {
    "add_days",
    "add_business_days",
    "next_business_day",
    "business_day_on_or_after",
    "business_day_on_or_before",
    "last_business_day_of_week",
    "last_business_day_of_month",
    "end_of_month",
    "weekday_in_week",
    "is_business_day",
    "date",
    "min",
    "max",
}
ALLOWED = (
    ast.Expression,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.IfExp,
    ast.Compare,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def check_expr(text: str) -> list[str]:
    if not text or not text.strip():
        return ["empty expression"]
    if "{" in text or "}" in text:
        return ["braces are not allowed"]
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as e:
        return [f"syntax error: {e.msg}"]
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            problems.append(f"not allowed: {type(node).__name__}")
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS:
                problems.append(f"unknown function: {ast.unparse(node.func)}")
            if node.keywords:
                problems.append("keyword arguments are not allowed")
        elif isinstance(node, ast.Name) and node.id not in NAMES | FUNCS:
            problems.append(f"unknown name: {node.id}")
        elif isinstance(node, ast.Constant) and not isinstance(node.value, (int, str)):
            problems.append(f"constant not allowed: {node.value!r}")
    return sorted(set(problems))


def normalise(text: str) -> str:
    """Canonical single-line form (used for hashing/comparing specs)."""
    return ast.unparse(ast.parse(text.strip(), mode="eval"))
