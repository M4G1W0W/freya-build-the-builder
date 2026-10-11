"""Tool hooks: Python source for `pre_process_code` / `post_process_code` (docs/design.md §4, §9).

Every function returns the source of one hook, built only from the spec (exit rows default to
`identity.failed_row` and `callback.booked_row`). Nothing here knows a brief.

Success follows §9: failure is status_code >= 400, status != success, ok false or no data. Pre
hooks change a value only when its meaning is certain, and clean it both in config['body'] and in
vars[ARG_PREFIX + field] (whichever the engine sends; not yet verified on the platform).

Platform facts (kit/docs/tools-and-code.md, "Pre and post Python hooks"; exp01):
- a post-hook gets `result`, the envelope {status, data, message, status_code, header}. A key added
  to result['data'] reaches the dialogue model, so every post-hook writes `what_to_do_next` there;
- a pre-hook gets `vars` and `config` (the substituted request: url, method, headers, body);
- seen in a test on 10 Oct: a post-hook can read and write workflow variables through `vars`.

Rules for the generated code (the hook sandbox is undocumented):
- no imports, no `def`, no comprehensions: straight-line code behaves the same whether the sandbox
  runs it in one namespace or with separate globals and locals;
- everything inside `try` / `except Exception: pass`, with isinstance checks before use;
- no double curly braces; spec text is embedded with `lit` (an ASCII literal with braces escaped).

Hook-owned workflow variables (written only when the sandbox exposes `vars`; every reader has a
fallback when they are missing): HOOK_VARS.
"""

import string
import textwrap

from .sandbox import CLOSE, OPEN

ASKED_VAR = "hook_verify_question"
PASSED_VAR = "hook_verify_passed"
CB_DATE_VAR = "hook_callback_date"
CB_TIME_VAR = "hook_callback_time"
HOOK_VARS = (ASKED_VAR, PASSED_VAR, CB_DATE_VAR, CB_TIME_VAR)
# toolapi.model_tool gives every model-filled field the default `{{<ARG_PREFIX><field>}}`, so the
# model's value may also sit in `vars` under that name; pre hooks clean it there too.
ARG_PREFIX = "arg_"

MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
# Words that may stand next to a clock time without changing it. Any other word ("quarter",
# "half", "past", "to", "thirty", "or") leaves the time as the model sent it.
TIME_WORDS = [
    "am", "pm", "a", "p", "m", "noon", "midday", "morning", "afternoon", "evening", "night",
    "tonight", "in", "the", "this", "at", "on", "o", "clock", "oclock", "h", "hr", "hrs", "hour",
    "hours", "around", "about", "approximately", "approx", "roughly", "ish", "sharp", "exactly",
    "today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday",
]  # fmt: skip

NEUTRAL = (
    "If this result shows ok false, an error or a failed status, it was NOT done, so do not say "
    "it was done."
)


def lit(value: object) -> str:
    """A Python string literal for `value`: ASCII only, no curly braces and no `$` in the source.

    In ascii() output these characters are never part of an escape, so `\\xNN` is exact.
    """
    out = ascii(str(value))
    return out.replace("{", "\\x7b").replace("}", "\\x7d").replace("$", "\\x24")


def _list_lit(items: list[str]) -> str:
    return "[" + ", ".join(lit(i) for i in items) + "]"


def _tuples_lit(rows: list[tuple]) -> str:
    parts = []
    for row in rows:
        cells = [repr(c) if isinstance(c, bool) else lit(c) for c in row]
        parts.append("(" + ", ".join(cells) + ")")
    return "[" + ", ".join(parts) + "]"


def _row(spec: dict, row_id: str) -> dict:
    for r in spec["rows"]:
        if r["id"] == row_id:
            return r
    raise ValueError(f"unknown row id {row_id!r}")


def _finish(src: str) -> str:
    if OPEN in src or CLOSE in src:
        raise ValueError("hook source must not contain double curly braces")
    compile(src, "<hook>", "exec")
    return src


# --- shared blocks (written at column 0, indented when assembled) -------------------------------

# Reads the envelope: sets _d (the data dict, created when missing), _code (HTTP status or 0),
# _fail, _okv (True/False/None), _bank (the bank's error text, ready to append) and _done.
# _done follows docs/design.md §9: failure is status_code >= 400, status != success, ok false or
# no data. A 200 without `ok` counts as done unless it carries an error or a false field.
# Writes a neutral what_to_do_next first.
_ENVELOPE = """
result.pop('header', None)
_d = result.get('data')
_fail = False
_err = ''
if not isinstance(_d, dict):
    if 'ok' in result and 'status' not in result and 'status_code' not in result:
        _d = result
    else:
        if isinstance(_d, str) and _d.strip():
            _err = _d.strip()
        _fail = True
        _d = dict()
        result['data'] = _d
_code = 0
try:
    _code = int(float(str(result.get('status_code') or 0).strip()))
except Exception:
    _code = 0
if _code >= 400:
    _fail = True
_st = result.get('status')
if _st is not None and str(_st).strip().lower() != 'success':
    _fail = True
_ok = _d.get('ok')
_okv = None
if _ok is True or str(_ok).strip().lower() == 'true':
    _okv = True
elif _ok is False or str(_ok).strip().lower() == 'false':
    _okv = False
_e = _d.get('error')
if isinstance(_e, str) and _e.strip():
    _err = _e.strip()
_bank = ''
if _err:
    _bank = ' (bank error: ' + _err[:300] + ')'
_neg = False
for _dk in list(_d.keys()):
    _val = _d.get(_dk)
    if _val is False or (isinstance(_val, str) and _val.strip().lower() == 'false'):
        _neg = True
_done = False
if not _fail:
    if _okv is True or (_okv is None and not _err and not _neg):
        _done = True
_d['what_to_do_next'] = $NEUTRAL
"""

# Sets _vs to the workflow-variable dict, or None (the name `vars` may be the Python builtin).
_VARS = """
_vs = None
try:
    _vs = vars
except Exception:
    _vs = None
if not (hasattr(_vs, 'get') and hasattr(_vs, '__setitem__')):
    _vs = None
"""

# Normalises _v by format _fmt into _out (falls back to the stripped text). A value is changed
# only when its meaning is certain: unknown words next to a time, or spoken digits that cannot be
# read, leave it as the model sent it. Numbers keep their JSON type (the model filled the field
# from its schema), except a digits:N number that lost leading zeros.
_NORMALISE = """
_num = isinstance(_v, (int, float)) and not isinstance(_v, bool)
_s = _v
if isinstance(_v, bool):
    _s = str(_v)
elif isinstance(_v, float) and _v == int(_v):
    _s = str(int(_v))
_s = str(_s).strip()
_out = _s
_pad = False
_seq = []
_nums = []
_words = []
_cur = ''
_kind = ''
for _ch in _s + ' ':
    _k = ''
    if _ch in '0123456789':
        _k = 'd'
    elif _ch.isalpha():
        _k = 'a'
    if _k != _kind:
        if _kind == 'd':
            _nums.append(_cur)
            _seq.append(_cur)
        if _kind == 'a':
            _words.append(_cur.lower())
            _seq.append(_cur.lower())
        _cur = ''
        _kind = _k
    if _k:
        _cur = _cur + _ch
if _fmt == 'date':
    _y = 0
    _m = 0
    _dd = 0
    _mon = 0
    for _w in _words:
        if len(_w) >= 3 and _mon == 0:
            _i = 0
            for _name in _MONTHS:
                _i = _i + 1
                if _mon == 0 and _name.startswith(_w):
                    _mon = _i
    if _mon and len(_nums) == 2:
        if len(_nums[0]) == 4 and len(_nums[1]) <= 2:
            _y = int(_nums[0])
            _dd = int(_nums[1])
            _m = _mon
        elif len(_nums[1]) == 4 and len(_nums[0]) <= 2:
            _y = int(_nums[1])
            _dd = int(_nums[0])
            _m = _mon
    elif not _mon and len(_nums) >= 3 and len(_nums[0]) == 4:
        if len(_nums[1]) <= 2 and len(_nums[2]) <= 2:
            _y = int(_nums[0])
            _a = int(_nums[1])
            _c = int(_nums[2])
            if _a <= 12:
                _m = _a
                _dd = _c
            elif _c <= 12:
                _m = _c
                _dd = _a
    elif not _mon and len(_nums) == 3 and len(_nums[2]) == 4:
        if len(_nums[0]) <= 2 and len(_nums[1]) <= 2:
            _y = int(_nums[2])
            _a = int(_nums[0])
            _c = int(_nums[1])
            if _a == _c or (_a > 12 and _c <= 12):
                _m = _c
                _dd = _a
            elif _c > 12 and _a <= 12:
                _m = _a
                _dd = _c
    if 1 <= _m <= 12 and 1 <= _dd <= 31 and 1000 <= _y <= 9999:
        _out = str(_y) + '-' + ('0' + str(_m))[-2:] + '-' + ('0' + str(_dd))[-2:]
elif _fmt == 'time':
    _plain = True
    for _w in _words:
        if _w not in _TIME_WORDS:
            _plain = False
    _h = -1
    _mi = 0
    if not _plain:
        _h = -1
    elif len(_nums) >= 2 and len(_nums[0]) <= 2 and len(_nums[1]) == 2:
        _h = int(_nums[0])
        _mi = int(_nums[1])
    elif len(_nums) == 1 and len(_nums[0]) <= 2:
        _h = int(_nums[0])
    elif len(_nums) == 1 and len(_nums[0]) in (3, 4):
        _h = int(_nums[0][:-2])
        _mi = int(_nums[0][-2:])
    elif not _nums and ('noon' in _words or 'midday' in _words):
        _h = 12
    _pm = False
    _am = False
    _prev = ''
    for _w in _words:
        if _w in ('pm', 'afternoon', 'evening', 'night', 'tonight') or (_prev == 'p' and _w == 'm'):
            _pm = True
        if _w in ('am', 'morning') or (_prev == 'a' and _w == 'm'):
            _am = True
        _prev = _w
    if _pm and 1 <= _h < 12:
        _h = _h + 12
    if _am and _h == 12:
        _h = 0
    if not _pm and not _am and 1 <= _h <= 11 and 0 <= _WIN_START <= _WIN_END:
        _t = _h * 60 + _mi
        if not (_WIN_START <= _t <= _WIN_END) and _WIN_START <= _t + 720 <= _WIN_END:
            _h = _h + 12
    if 0 <= _h <= 23 and 0 <= _mi <= 59:
        _out = ('0' + str(_h))[-2:] + ':' + ('0' + str(_mi))[-2:]
elif _fmt.startswith('digits'):
    _n = 0
    try:
        _n = int(_fmt.split(':')[1])
    except Exception:
        _n = 0
    _dig = ''.join(_nums)
    _mix = ''
    _allnum = True
    for _tk in _seq:
        if _tk[0] in '0123456789':
            _mix = _mix + _tk
        else:
            _i = -1
            _j = 0
            for _name in _NUMBER_WORDS:
                if _tk == _name:
                    _i = _j
                _j = _j + 1
            if _tk in ('oh', 'o'):
                _i = 0
            if _i < 0:
                _allnum = False
            else:
                _mix = _mix + str(_i)
    _res = ''
    if _n:
        if len(_dig) == _n:
            _res = _dig
        elif len(_mix) == _n:
            _res = _mix
        elif not _words:
            _res = _dig
    elif _allnum:
        _res = _mix
    else:
        _res = _dig
    if _res and _n and len(_res) < _n and _num:
        _res = ('0' * _n + _res)[-_n:]
        _pad = True
    if _res:
        _out = _res
elif _fmt == 'year':
    _found = ''
    for _x in _nums:
        if not _found and len(_x) == 4:
            _found = _x
    if _found:
        _out = _found
    elif _nums:
        _out = ''.join(_nums)
elif _fmt == 'alnum':
    _out = ''.join(_s.split()).upper()
if _num and not _pad and _fmt != 'date' and _fmt != 'time':
    _out = _v
    if isinstance(_v, float) and _v == int(_v):
        _out = int(_v)
"""

# Copies the cleaned body value _b[_f] to vars[ARG_PREFIX + _f] when that variable exists.
_ARG_SYNC = """
if _vs is not None:
    try:
        _ak = $ARG_PREFIX + str(_f)
        if _f in _b and _ak in _vs:
            _vs[_ak] = _b.get(_f)
    except Exception:
        pass
"""

# Normalises every (field, format) pair in _targets inside the body dict _b.
_TARGET_LOOP = (
    """
for _t in _targets:
    try:
        _f = _t[0]
        _fmt = str(_t[1]).strip().lower()
        if _f in _b and _b.get(_f) is not None:
            _v = _b.get(_f)
"""
    + textwrap.indent(_NORMALISE, " " * 12)
    + """
            _b[_f] = _out
"""
    + textwrap.indent(_ARG_SYNC, " " * 8)
    + """
    except Exception:
        pass
"""
)

_NORMALISE_CONSTS = (
    "_MONTHS = $MONTHS\n_NUMBER_WORDS = $NUMBER_WORDS\n_TIME_WORDS = $TIME_WORDS\n"
    "_WIN_START = -1\n_WIN_END = -1\n"
)


def _post(consts: str, body: str, values: dict[str, str]) -> str:
    inner = textwrap.indent(consts + _ENVELOPE + body, " " * 8)
    src = "try:\n    if isinstance(result, dict):\n" + inner + "except Exception:\n    pass\n"
    return _finish(string.Template(src).substitute({"NEUTRAL": lit(NEUTRAL), **values}))


def _pre(consts: str, body: str, values: dict[str, str], after: str = "") -> str:
    head = _NORMALISE_CONSTS + consts + _VARS
    head += "_b = None\nif isinstance(config, dict):\n    _b = config.get('body')\n"
    src = (
        "try:\n"
        + textwrap.indent(head, " " * 4)
        + "    if isinstance(_b, dict):\n"
        + textwrap.indent(body + _TARGET_LOOP + after, " " * 8)
        + "except Exception:\n    pass\n"
    )
    mapping = {
        "MONTHS": _list_lit(MONTHS),
        "NUMBER_WORDS": _list_lit(NUMBER_WORDS),
        "TIME_WORDS": _list_lit(TIME_WORDS),
        "ARG_PREFIX": lit(ARG_PREFIX),
        **values,
    }
    return _finish(string.Template(src).substitute(mapping))


def _say_then_exit(
    row: dict, first: str, stage: str, who: str, fallback_end: str, default_say: str = ""
) -> str:
    """'Say: <brief lines>. Then thank, goodbye and the exit tool' for an ending row.

    The lines are the brief's own sentences (`first`, then the row's say_before_end); with none,
    `default_say` is an instruction, never an invented quote. The exit tool is named only when the
    row is an ending of `stage`, where the hook's tool lives; otherwise the model would be sent to
    a tool that does not exist in that step.
    """
    lines = [first] if first else []
    lines += [x for x in row["say_before_end"] if x.strip() and x not in first]
    text = "Say: " + " ".join(lines) if lines else default_say
    if stage in row["phases"]:
        end = (
            f"thank the {who}, say goodbye and call transition_to_ev_{row['id']} in the same "
            "message, with no other tool."
        )
    else:
        end = f"thank the {who}, say goodbye and " + fallback_end
    return (text + " Then " + end) if text else end[0].upper() + end[1:]


# --- verify_identity ----------------------------------------------------------------------------

_VERIFY_POST = (
    _VARS
    + """
_asked = ''
_passed = []
if _vs is not None:
    try:
        _raw = str(_vs.get($ASKED_VAR) or '').strip().lower()
        for _q in _QUESTIONS:
            if _raw and _q[0].lower() == _raw:
                _asked = _q[0]
        for _p in str(_vs.get($PASSED_VAR) or '').split(','):
            if _p.strip():
                _passed.append(_p.strip())
    except Exception:
        _asked = ''
_rejected = _fail and 400 <= _code < 500
_gate = str(_d.get($GATE)).strip().lower() == 'true'
_good = str(_d.get($ANSWER_OK)).strip().lower() == 'true'
_rem = None
_rv = _d.get($REMAINING)
if _rv is not None and not isinstance(_rv, bool):
    try:
        _rem = int(float(str(_rv).strip()))
    except Exception:
        _rem = None
_hint = ''
_hv = _d.get($HINT)
if isinstance(_hv, str):
    _hint = _hv.strip()
_hmsg = ''
for _h in _HINTS:
    if _hint and _hint == _h[0]:
        _hmsg = _h[1]
        if _h[2]:
            _hmsg = _hmsg + ' (This counts as a wrong answer.)'
        else:
            _hmsg = _hmsg + ' (This does not count as a wrong answer.)'
if _fail and not _rejected:
    _msg = $SERVICE_HEAD + _bank + $SERVICE_TAIL
elif _gate and not _fail:
    _msg = $ALL_OK
elif _rem is not None and _rem <= 0:
    _msg = $FAILED
elif _rejected:
    _msg = $REJECTED_HEAD + _bank + $REJECTED_TAIL
elif _hmsg:
    _msg = _hmsg
elif _okv is False:
    _msg = 'The answer could not be read' + _bank + $UNREADABLE_TAIL
elif _good:
    _nxt = ''
    if _asked:
        if _asked not in _passed:
            _passed.append(_asked)
        for _q in _QUESTIONS:
            if not _nxt and _q[0] not in _passed:
                _nxt = _q[1]
        if _vs is not None:
            try:
                _vs[$PASSED_VAR] = ','.join(_passed)
            except Exception:
                pass
    if _nxt:
        _msg = 'Correct. Now ask: ' + _nxt
    else:
        _msg = $GENERIC_NEXT
else:
$WRONG
    if _hint:
        _msg = 'The bank returned hint ' + _hint + '; follow the brief for it. ' + _msg
_d['what_to_do_next'] = _msg
"""
)

_WRONG_ONE = """    _msg = 'Wrong answer; do not say it was correct.'
    if _rem is not None:
        _msg = _msg + ' Wrong answers left: ' + str(_rem) + '.'
    _msg = _msg + ' You may ask that same question again.'"""

# One call checked every answer: the gate failed, so at least one is wrong. A response list that
# holds only question keys (e.g. wrong_fields) names which ones; nothing else is assumed.
_WRONG_ALL = """    _wrong = []
    for _wk in list(_d.keys()):
        _wv = _d.get(_wk)
        if isinstance(_wv, list) and _wv:
            _named = []
            for _w in _wv:
                for _q in _QUESTIONS:
                    if str(_w).strip().lower() == _q[0].lower() and _q[1] not in _named:
                        _named.append(_q[1])
            if len(_named) == len(_wv):
                _wrong = _named
    _msg = $WRONG_HEAD
    if _wrong:
        _msg = _msg + $WRONG_NAMED + ' | '.join(_wrong) + '.'
    if _rem is not None:
        _msg = _msg + ' Failed checks left: ' + str(_rem) + '.'
    if _wrong:
        _msg = _msg + $ASK_NAMED
    else:
        _msg = _msg + $ASK_ALL
    _msg = _msg + $WRONG_TAIL"""


def verify_post(spec: dict, failed_row_id: str | None = None, all_at_once: bool = False) -> str:
    """Post-hook of `verify_identity`: one instruction from the response roles (§4 identity).

    The failed-check exit defaults to `spec.identity.failed_row` (§9 signature `verify_post(spec)`).
    `all_at_once`: one call checks every answer, so only the gate says an answer was right.
    """
    ident = spec["identity"]
    questions = ident["questions"]
    row = _row(spec, failed_row_id or ident["failed_row"])
    asks = " ".join(f"{i}. {q['ask']}" for i, q in enumerate(questions, 1))
    generic = "Correct. Now ask the next security question the brief requires."
    if questions:
        generic = (
            "Correct. Now ask the next security question that has not been answered correctly "
            "yet. The questions in order: " + asks
        )
    both = "Both answers are verified." if len(questions) == 2 else "All answers are verified."
    failed = "The check has FAILED. Do not state any debt or account detail. " + _say_then_exit(
        row,
        ident["failed_line"],
        "identity",
        "customer",
        "end the call the way the brief says for a failed check.",
        "Say that you cannot verify their identity.",
    )
    values = {
        "ASKED_VAR": lit(ASKED_VAR),
        "PASSED_VAR": lit(PASSED_VAR),
        "GATE": lit(ident["gate_field"]),
        "ANSWER_OK": lit("" if all_at_once else ident["answer_ok_field"]),
        "REMAINING": lit(ident["remaining_field"]),
        "HINT": lit(ident["hint_field"]),
        "SERVICE_HEAD": lit("The answer was not checked because of a service error"),
        "SERVICE_TAIL": lit(
            ". This is not a wrong answer. Call verify_identity once more with the same answer."
        ),
        "REJECTED_HEAD": lit("The bank did not accept this request"),
        "REJECTED_TAIL": lit(
            "; the answer was not checked. Send it again in the answer format this step asks "
            "for; if needed, ask the customer to say it again."
        ),
        "ALL_OK": lit(both + " Do not ask more security questions; the account is being loaded."),
        "FAILED": lit(failed),
        "UNREADABLE_TAIL": lit(
            "; ask the customer to say it again (this does not count as wrong)."
        ),
        "GENERIC_NEXT": lit(generic),
        "WRONG_HEAD": lit(
            "The check did not pass: at least one answer is wrong. Do not say any answer was "
            "correct."
        ),
        "WRONG_NAMED": lit(" The bank marked as wrong: "),
        "ASK_NAMED": lit(" You may ask again for those answers only,"),
        "ASK_ALL": lit(" You may ask again for every answer,"),
        "WRONG_TAIL": lit(
            " then CALL verify_identity again with every answer, each new answer in place of the "
            "old one."
        ),
    }
    consts = (
        "_QUESTIONS = "
        + _tuples_lit([(q["key"], q["ask"]) for q in questions])
        + "\n_HINTS = "
        + _tuples_lit(
            [
                (
                    h["value"],
                    h["instruction"].strip()
                    or f"Follow the brief for the bank's hint {h['value']}.",
                    bool(h["counts_as_wrong"]),
                )
                for h in ident["hints"]
            ]
        )
        + "\n"
    )
    body = _VERIFY_POST.replace("$WRONG", _WRONG_ALL if all_at_once else _WRONG_ONE, 1)
    return _post(consts, body, values)


_VERIFY_PRE = """
_targets = []
_key = ''
if _QF and _QF in _b:
    _key = str(_b.get(_QF) or '').strip()
if _vs is not None:
    try:
        _vs[$ASKED_VAR] = _key
    except Exception:
        pass
if _AF and _AF in _b:
    _qfmt = 'text'
    for _q in _QUESTIONS:
        if _q[0].lower() == _key.lower():
            _qfmt = _q[1]
    _targets.append((_AF, _qfmt))
else:
    for _q in _QUESTIONS:
        if _q[0] in _b and _q[0] != _QF:
            _targets.append((_q[0], _q[1]))
"""


def verify_pre(spec: dict) -> str:
    """Pre-hook of `verify_identity`: normalise the answer by the asked question's format.

    Per-answer shape: body[answer_field] by the format of the question in body[question_field].
    All-at-once shape: every body field named like a question key, by that question's format.
    """
    ident = spec["identity"]
    consts = (
        "_QF = "
        + lit(ident["question_field"])
        + "\n_AF = "
        + lit(ident["answer_field"])
        + "\n_QUESTIONS = "
        + _tuples_lit([(q["key"], q["format"]) for q in ident["questions"]])
        + "\n"
    )
    return _pre(consts, _VERIFY_PRE, {"ASKED_VAR": lit(ASKED_VAR)})


# --- create_promise -----------------------------------------------------------------------------

_SIMPLE_POST = """
if _done:
    _d['what_to_do_next'] = $SUCCESS
else:
    _d['what_to_do_next'] = $FAIL_HEAD + _bank + $FAIL_TAIL
"""


def promise_post(spec: dict, k: int) -> str:
    """Post-hook of `create_promise_p<k>`: say the brief's success line only when it was done."""
    if k < 1:
        raise ValueError(f"slot must be >= 1, got {k}")
    line = spec["success_lines"]["promise"]
    rule = spec["failure_rules"]["promise"]
    head = f"Recorded (P{k})."
    if not line:
        success = head + " Tell the customer the promise is recorded."
    else:  # every agent has several product slots (spec.product_slots)
        success = head + " When every agreed promise is recorded, say exactly once: " + line
    tail = ". Do not say it was recorded."
    tail += " Per the brief: " + rule if rule else " Tell the customer it could not be recorded."
    values = {
        "SUCCESS": lit(success),
        "FAIL_HEAD": lit(f"NOT recorded (P{k})"),
        "FAIL_TAIL": lit(tail),
        "FLAG": lit(recorded_flag(k)),
    }
    return _post("", _PROMISE_POST, values)


def recorded_flag(k: int) -> str:
    """Sticky variable set by promise_post on success; finalize reads it (a later duplicate call
    would overwrite <tool>_response with a failure)."""
    return f"p{k}_recorded"


_PROMISE_POST = """
if _done:
    _d['what_to_do_next'] = $SUCCESS
    try:
        vars[$FLAG] = 'yes'
    except Exception:
        pass
else:
    _d['what_to_do_next'] = $FAIL_HEAD + _bank + $FAIL_TAIL
"""


# A string amount is parsed only when it holds exactly one number ("EUR 420,50"); text with
# several numbers ("420 and 50 cents", "1 250") is left as the model sent it.
_PROMISE_PRE = (
    """
_targets = []
if _AMT and _AMT in _b:
    _amt = _b.get(_AMT)
    if isinstance(_amt, float):
        _b[_AMT] = round(_amt, 2)
    elif isinstance(_amt, str):
        _runs = []
        _cur = ''
        for _ch in _amt + ' ':
            if _ch in '0123456789.,':
                _cur = _cur + _ch
            else:
                _hasd = False
                for _c2 in _cur:
                    if _c2 in '0123456789':
                        _hasd = True
                if _hasd:
                    _runs.append(_cur)
                _cur = ''
        if len(_runs) == 1:
            _txt = _runs[0].strip(',').rstrip('.')
            if ',' in _txt and '.' in _txt and _txt.rfind(',') > _txt.rfind('.'):
                _txt = _txt.replace('.', '').replace(',', '.')
            elif ',' in _txt and '.' not in _txt and 1 <= len(_txt.split(',')[-1]) <= 2:
                _txt = _txt.replace(',', '.')
            else:
                _txt = _txt.replace(',', '')
            if ('-' + _runs[0]) in _amt:
                _txt = '-' + _txt
            try:
                _b[_AMT] = round(float(_txt), 2)
            except Exception:
                pass
    _f = _AMT
"""
    + textwrap.indent(_ARG_SYNC, " " * 4)
    + """
if _DATE:
    _targets.append((_DATE, 'date'))
"""
)


def promise_pre(spec: dict) -> str:
    """Pre-hook of `create_promise_p<k>`: amount rounded to 2 decimals, ISO date zero-padded."""
    pf = spec["promise_fields"]
    consts = "_AMT = " + lit(pf["amount_field"]) + "\n_DATE = " + lit(pf["date_field"]) + "\n"
    return _pre(consts, _PROMISE_PRE, {})


# --- add_note -----------------------------------------------------------------------------------


def note_post(spec: dict) -> str:
    """Post-hook of `add_note_p<k>`: saved, or not saved (never claim a failed note).

    It names no exit tool: the step's ENDINGS list (render.py) holds the ones that exist.
    """
    del spec  # same text for every brief; the signature matches the other hooks
    values = {
        "SUCCESS": lit(
            "Note saved. If another product still needs a note, call its add_note tool now. If a "
            "product is still open (no promise and no note), go on with it and do not say goodbye: "
            "the call closes by itself once every product has a promise or a note. Never reply "
            "with an empty message."
        ),
        "FAIL_HEAD": lit("The note was NOT saved"),
        "FAIL_TAIL": lit(". Do not say it was saved."),
    }
    return _post("", _SIMPLE_POST, values)


# --- schedule_callback --------------------------------------------------------------------------

_CALLBACK_POST = (
    _VARS
    + """
if _done:
    _when = ''
    if _vs is not None:
        try:
            _when = str(_vs.get($CB_DATE) or '') + ' ' + str(_vs.get($CB_TIME) or '')
            _when = _when.strip()
        except Exception:
            _when = ''
    _head = 'Booked.'
    if _when:
        _head = 'Booked for ' + _when + '.'
    _d['what_to_do_next'] = _head + ' ' + $SUCCESS_TAIL
else:
    _d['what_to_do_next'] = 'The callback was NOT booked' + _bank + $FAIL_TAIL
"""
)


def callback_post(spec: dict, callback_row_id: str | None = None) -> str:
    """Post-hook of `schedule_callback`: on success, say goodbye and fire the callback exit.

    The exit defaults to `spec.callback.booked_row` (§9 signature `callback_post(spec)`).
    """
    row = _row(spec, callback_row_id or spec["callback"]["booked_row"])
    values = {
        "CB_DATE": lit(CB_DATE_VAR),
        "CB_TIME": lit(CB_TIME_VAR),
        "SUCCESS_TAIL": lit(
            _say_then_exit(row, "", "third_party", "person", "end the call the way the brief says.")
        ),
        "FAIL_TAIL": lit(". Do not say it was booked; follow the brief."),
    }
    return _post("", _CALLBACK_POST, values)


_CALLBACK_PRE = """
_targets = []
if _DATE:
    _targets.append((_DATE, 'date'))
if _TIME:
    _targets.append((_TIME, 'time'))
"""

_CALLBACK_PRE_AFTER = """
if _vs is not None:
    try:
        _vs[$CB_DATE] = str(_b.get(_DATE) or '') if _DATE else ''
        _vs[$CB_TIME] = str(_b.get(_TIME) or '') if _TIME else ''
    except Exception:
        pass
"""


def _clock(text: str) -> int:
    """Minutes after midnight for "HH:MM", or -1."""
    parts = str(text).strip().split(":")
    try:
        h, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return -1
    return h * 60 + m if len(parts) == 2 and 0 <= h <= 24 and 0 <= m <= 59 else -1


def callback_pre(spec: dict) -> str:
    """Pre-hook of `schedule_callback`: time to HH:MM, date zero-padded. It also stores both in
    workflow variables for the post-hook's "Booked for <date> <time>".

    A bare hour with no am/pm ("2") is read in the afternoon only when the morning reading is
    outside the spec's callback window and the afternoon one is inside it.
    """
    cb = spec["callback"]
    consts = (
        "_DATE = "
        + lit(cb["date_field"])
        + "\n_TIME = "
        + lit(cb["time_field"])
        + f"\n_WIN_START = {_clock(cb['start'])}\n_WIN_END = {_clock(cb['end'])}\n"
    )
    values = {"CB_DATE": lit(CB_DATE_VAR), "CB_TIME": lit(CB_TIME_VAR)}
    return _pre(consts, _CALLBACK_PRE, values, after=_CALLBACK_PRE_AFTER)
