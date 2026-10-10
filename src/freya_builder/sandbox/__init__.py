"""Python that runs inside Freya code nodes, assembled into `code_exec` source by `embed`.

Each module here must stay sandbox-safe (see calendar_core.py) so the exact source we unit-test
is the source the engine runs.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPEN, CLOSE = "{" * 2, "}" * 2


def module_source(name: str) -> str:
    """Source of a sandbox module, minified: docstrings and comments removed (same AST semantics).

    Code nodes carry several modules plus CONFIG; minifying keeps them well under the size we
    have verified on the platform. ast.unparse re-renders equivalent Python.
    """
    import ast

    tree = ast.parse((HERE / f"{name}.py").read_text())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                if isinstance(first.value.value, str):
                    node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def hex_json(value: object) -> str:
    """A Python expression that rebuilds `value` without any brace pairs in the source."""
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True).encode().hex()
    return f"json.loads(bytes.fromhex('{raw}').decode('utf-8'))"


def assemble(modules: list[str], main: str, config: object) -> str:
    """Concatenate sandbox modules + `CONFIG = ...` + a main snippet into one code_exec source."""
    parts = ["import json", "import re", "import datetime"]
    parts += [module_source(m) for m in modules]
    parts.append("CONFIG = " + hex_json(config))
    parts.append(main)
    source = "\n\n".join(parts) + "\n"
    if OPEN in source or CLOSE in source:
        raise ValueError("sandbox source must not contain double curly braces")
    return source
