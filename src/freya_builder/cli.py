"""Builder entry point: brief file(s) + tool API file -> a published Freya workflow + trace.

    python3 builder/build.py <brief.md> [<more briefs>...] <tool_api.json> [--slot NAME]
                             [--export PATH] [--no-selftest] [--dry]

The last positional argument is the tool API (OpenAPI JSON); everything before it is brief text
(several files are concatenated in order, e.g. Brief A then Brief B). Secrets come from env vars.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from . import llm, platform
from .toolapi import Tool, load_tool_api
from .trace import Trace
from .validate import unsent_required, validate

# The two design-dependent stages. Set by the pipeline module (see pipeline.py).
Extract = Callable[[Trace, str, list[Tool]], dict]
Render = Callable[[dict, list[Tool]], dict]


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="build.py", description=__doc__.splitlines()[0])
    ap.add_argument("inputs", nargs="+", help="brief file(s) followed by the tool API JSON")
    ap.add_argument("--slot", help="workflow slot name (default: derived from the brief names)")
    ap.add_argument("--export", help="write the exported workflow JSON here")
    ap.add_argument("--no-selftest", action="store_true")
    ap.add_argument("--dry", action="store_true", help="render + validate only; no Freya writes")
    ap.add_argument("--save-spec", help="also write the extracted spec JSON here (debugging)")
    ap.add_argument(
        "--spec", help="DEV ONLY: use this spec JSON instead of reading the brief with the LLM"
    )
    a = ap.parse_args(argv)
    if len(a.inputs) < 2:
        ap.error("need at least one brief file and the tool API file")
    a.briefs, a.tool_api = a.inputs[:-1], a.inputs[-1]
    return a


def read_briefs(paths: list[str]) -> str:
    parts = []
    for p in paths:
        parts.append(f"===== FILE: {Path(p).name} =====\n{_read_text(Path(p))}")
    return "\n\n".join(parts)


def _read_text(path: Path) -> str:
    """UTF-8, else cp1252 (pasted e-mails), else UTF-8 with replacement: never crash (audit F79)."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def count_tools(wf: dict) -> int:
    names = set()
    for node in (wf.get("nodes") or {}).values():
        for t in (node.get("tools") or []) + (node.get("pre_actions") or []):
            names.add((t.get("function") or {}).get("name"))
    return len(names - {None, "code_exec"})


def load_dotenv(path: Path = platform.ROOT / ".env") -> None:
    """Convenience for local runs: values from .env, never overriding the real environment."""
    if not path.exists():
        return
    import os

    for line in path.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip())


CODE_PATHS = ("src", "builder", "pyproject.toml")


def code_version() -> tuple[str, bool]:
    """(short commit, uncommitted changes in tracked files), or ("unknown", False) outside git."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=platform.ROOT,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            # the builder's own code only: a re-run's tee rewrites a tracked trace (diff review 19)
            ["git", "status", "--porcelain", "--untracked-files=no", "--", *CODE_PATHS],
            cwd=platform.ROOT,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown", False
    if head.returncode != 0:
        return "unknown", False
    return head.stdout.strip(), bool(status.stdout.strip())


def _sha(path: str) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
    except OSError:
        return "unreadable"


def run(argv: list[str], extract: Extract, render: Render, selftest=None) -> int:
    a = parse_args(argv)
    load_dotenv()
    llm.start_budget()
    trace = Trace()
    commit, dirty = code_version()
    inputs = ",".join(_sha(p) for p in [*a.briefs, a.tool_api])
    trace.start(
        a.briefs,
        a.tool_api,
        f"sha256={inputs} git={commit} dirty={dirty} python={sys.version.split()[0]} "
        f"models={','.join(llm.model_chain())}",
    )
    if dirty:
        trace.warn(
            f"uncommitted changes in the builder code: this run is not exactly commit {commit}"
        )
    ok = False
    try:
        brief_text = read_briefs(a.briefs)
        tools = load_tool_api(a.tool_api)
        trace.step(
            f"read {len(a.briefs)} brief file(s), {len(brief_text)} chars; {len(tools)} tools"
        )

        if a.spec:
            spec = json.loads(Path(a.spec).read_text())
            trace.warn(f"DEV: using provided spec {a.spec}; the brief was not read by the LLM")
        else:
            spec = extract(trace, brief_text, tools)
        spec.setdefault("_prompt_brief", brief_text)
        if a.save_spec:
            Path(a.save_spec).write_text(json.dumps(spec, indent=1))
        workflow = render(spec, tools)
        problems = validate(workflow)
        for p in problems:
            trace.warn(f"validation: {p}")
        trace.test("local workflow validation", not problems, f"{len(problems)} problem(s)")
        for w in unsent_required(workflow, tools):
            trace.warn(f"engine call: {w}")
        if problems:
            return 2
        steps = len(workflow.get("nodes") or {})
        trace.step(f"rendered workflow: {steps} steps, {count_tools(workflow)} tools")
        if a.dry:
            print(json.dumps(workflow, indent=1))
            ok = True
            return 0

        slot = a.slot or "+".join(Path(b).stem for b in a.briefs)
        platform.dry_run(trace, slot, workflow)
        saved = platform.save(trace, slot, workflow)
        trace.created(
            saved["workflow_id"],
            saved["agent_id"],
            steps,
            count_tools(workflow),
            saved.get("version"),
        )
        if a.export:  # first: a required artefact; the smoke test does not change the workflow
            platform.export(trace, saved["workflow_id"], a.export)
        passed = True
        if selftest and not a.no_selftest:
            passed = selftest(trace, saved, spec, tools) is not False
        print(json.dumps(saved))
        ok = passed
        return 0 if passed else 3  # 3: the agent is saved, but its smoke test failed: re-run
    except Exception as e:  # the trace must record why a run failed, redacted (audit F80)
        trace.line("ERROR", f"{type(e).__name__}: {e}")
        for row in traceback.format_exc().rstrip().splitlines():
            trace.line("ERROR", row)
        return 1
    finally:
        trace.end(ok)


def main() -> int:
    from .pipeline import extract, render, selftest

    return run(sys.argv[1:], extract, render, selftest)
