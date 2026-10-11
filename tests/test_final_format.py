"""The final's run form `build.py {case_folder} {mock_url}` (hackathon page, Submit tab, 11 Oct):
a folder of .md/.docx/.pdf/.xlsx documents, tools on the team's own mock, a non-English call.
Synthetic documents only; nothing here comes from a final case."""

import io
import json
import zipfile
from pathlib import Path

from test_cli import API, fake_extract, fake_render

from freya_builder import casefolder, cli, contract, language, llm, render
from freya_builder.sandbox import calendar_core, facts
from freya_builder.trace import Trace

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
S_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R_NS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _docx(path: Path, paragraphs: list[str], table: list[list[str]]) -> None:
    ps = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    rows = "".join(
        "<w:tr>"
        + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in r)
        + "</w:tr>"
        for r in table
    )
    xml = f"<w:document {W_NS}><w:body>{ps}<w:tbl>{rows}</w:tbl></w:body></w:document>"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def _xlsx(path: Path) -> None:
    shared = f"<sst {S_NS}><si><t>name</t></si><si><t>Ayşe Çelik</t></si></sst>"
    sheet = (
        f'<worksheet {S_NS}><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c>'
        '<c r="B1" t="inlineStr"><is><t>balance</t></is></c></row>'
        '<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>420.5</v></c></row>'
        "</sheetData></worksheet>"
    )
    wb = (
        f'<workbook {S_NS} {R_NS}><sheets><sheet name="Customers" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", shared)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)


def _pdf(path: Path, text: str) -> None:
    import zlib

    stream = zlib.compress(f"BT /F1 12 Tf ({text}) Tj ET".encode())
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>stream\n" + stream + b"\nendstream\nendobj\n%%EOF")


def _folder(tmp_path: Path) -> Path:
    case = tmp_path / "Case"
    (case / "docs").mkdir(parents=True)
    (case / "README.md").write_text("what each document is")
    (case / "BRIEF.md").write_text("read me first")
    (case / "a-notes.txt").write_text("plain notes")
    _docx(
        case / "docs" / "contract.docx", ["Service contract", "POST /verify"], [["field", "type"]]
    )
    _xlsx(case / "docs" / "customers.xlsx")
    _pdf(case / "docs" / "memo.pdf", "Memo text")
    (case / "docs" / "drawing.png").write_bytes(b"\x89PNG not text")
    (case / ".DS_Store").write_bytes(b"\0")
    return case


def test_folder_reads_every_document_brief_first_and_skips_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(casefolder.shutil, "which", lambda _: None)  # the stdlib PDF path
    warnings: list[str] = []
    docs = casefolder.read_folder(_folder(tmp_path), warnings.append)
    names = [n for n, _ in docs]
    assert names[:2] == ["BRIEF.md", "README.md"]
    text = dict(docs)
    assert "Service contract\nPOST /verify\nfield | type" == text["docs/contract.docx"]
    assert (
        "--- sheet: Customers ---\nname\tbalance\nAyşe Çelik\t420.5" == text["docs/customers.xlsx"]
    )
    assert text["docs/memo.pdf"] == "Memo text"
    assert ".DS_Store" not in names and "docs/drawing.png" not in names
    assert any("drawing.png" in w for w in warnings)


def test_a_broken_office_file_is_a_warning_not_a_crash(tmp_path):
    case = tmp_path / "c"
    case.mkdir()
    (case / "BRIEF.md").write_text("brief")
    (case / "bad.docx").write_bytes(b"not a zip")
    warnings: list[str] = []
    docs = casefolder.read_folder(case, warnings.append)
    assert [n for n, _ in docs] == ["BRIEF.md"]
    assert "bad.docx" in warnings[0]


def test_old_brief_text_is_unchanged():
    # The practice run form must give the extraction exactly the text it gave before.
    brief = Path(API).parents[1] / "briefs" / "brief-a.md"
    assert cli.read_briefs([str(brief)]) == f"===== FILE: brief-a.md =====\n{brief.read_text()}"


def test_operations_become_tools_on_the_mock():
    ops = [
        {
            "name": "create_promise",
            "path": "v1/promise",
            "method": "POST",
            "summary": "record a promise",
            "request": [
                {
                    "name": "amount",
                    "type": "number",
                    "required": True,
                    "description": "",
                    "enum": [],
                },
                {
                    "name": "channel",
                    "type": "string",
                    "required": False,
                    "description": "",
                    "enum": ["a", "b"],
                },
            ],
            "response": [
                {
                    "name": "data",
                    "type": "object",
                    "description": "",
                    "children": [{"name": "id", "type": "string", "description": ""}],
                }
            ],
        },
        {
            "name": "create_promise",
            "path": "/dup",
            "method": "POST",
            "summary": "",
            "request": [],
            "response": [],
        },
    ]
    tools = contract.tools_from_operations(ops, "https://mock.example.dev/")
    assert len(tools) == 1
    t = tools[0]
    assert t.url == "https://mock.example.dev/v1/promise" and t.method == "POST"
    assert t.field("amount").required and t.field("channel").enum == ("a", "b")
    assert t.response[0].children[0].name == "id"


def test_an_openapi_file_in_the_folder_is_used_on_the_mock_without_a_model_call(monkeypatch):
    def no_llm(*a, **k):
        raise AssertionError("no model call expected")

    monkeypatch.setattr(llm, "chat_json", no_llm)
    files = [("BRIEF.md", "x"), ("api/contract.json", Path(API).read_text())]
    tools = contract.contract_tools(Trace(io.StringIO()), files, "https://mock.example.dev")
    assert tools and all(t.url.startswith("https://mock.example.dev/") for t in tools)
    assert "freyavoice" not in json.dumps([t.url for t in tools])


def test_the_folder_and_mock_url_run_form_builds(tmp_path, capsys):
    case = tmp_path / "Case"
    case.mkdir()
    (case / "BRIEF.md").write_text("brief")
    (case / "openapi.json").write_text(Path(API).read_text())
    seen = {}

    def extract(trace, brief_text, tools):
        seen["urls"] = [t.url for t in tools]
        seen["text"] = brief_text
        return fake_extract(trace, brief_text, tools)

    assert cli.run([str(case), "https://mock.example.dev", "--dry"], extract, fake_render) == 0
    assert all(u.startswith("https://mock.example.dev/") for u in seen["urls"])
    assert seen["text"].startswith("===== FILE: BRIEF.md =====\nbrief")
    assert "ok=True" in capsys.readouterr().err


def test_english_prompt_line_is_unchanged_and_other_languages_get_one():
    assert language.speak_line(None) == language.speak_line("English") == "Speak English."
    line = language.speak_line("Spanish")
    assert line.startswith("Speak Spanish") and '"Please go on."' in line
    assert render.GOODBYE == language.GOODBYE_EN


def test_detect_keeps_english_when_the_model_call_fails(monkeypatch):
    def fail(*a, **k):
        raise llm.LLMError("down")

    monkeypatch.setattr(llm, "chat_json", fail)
    out = io.StringIO()
    assert language.detect(Trace(out), "brief") == {
        "language": "English",
        "goodbye": language.GOODBYE_EN,
    }
    assert "call language not detected" in out.getvalue()


def test_detect_returns_the_goodbye_and_month_names(monkeypatch):
    months = (
        "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"
    )
    reply = {"language": "Spanish", "goodbye": "Gracias. Adiós.", "months": months.split()}
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: reply)
    got = language.detect(Trace(io.StringIO()), "brief")
    assert got == {"language": "Spanish", "goodbye": "Gracias. Adiós.", "months": months.split()}


def _facts_ns() -> dict:
    ns: dict = {}
    exec(Path(calendar_core.__file__).read_text(), ns)
    exec(Path(facts.__file__).read_text(), ns)
    return ns


def test_a_worded_now_in_another_language_is_read_with_its_month_names():
    ns = _facts_ns()
    german = "januar februar märz april mai juni juli august september oktober november dezember"
    C = {"now_var": "now", "month_words": german.split()}
    when, how = ns["_now"]({"now": "Freitag 13 März 2026 09:15"}, C)
    assert how == "ok" and (when.year, when.month, when.day, when.hour) == (2026, 3, 13, 9)
    _, how = ns["_now"]({"now": "Freitag 13 März 2026 09:15"}, {"now_var": "now"})
    assert how == "clock"
    when, how = ns["_now"]({"now": "Wednesday 14 October 2026 11:00"}, {"now_var": "now"})
    assert how == "ok" and (when.month, when.day, when.hour) == (10, 14, 11)


def _capture(seen: dict):
    def render(spec, tools):
        seen.update(spec)
        return fake_render(spec, tools)

    return render


def _extract_with_rules(rules: str):
    def extract(trace, text, tools):
        out = fake_extract(trace, text, tools)
        return {**out, "_prompt_brief": text, "_consolidated_rules": rules}

    return extract


def test_a_folders_prompt_brief_is_the_consolidated_rules(tmp_path, capsys):
    # Review 16:40 UTC: a clean folder put test customers, example calls and the contract into
    # the agent's BANK BRIEF.
    case = tmp_path / "Case"
    case.mkdir()
    (case / "BRIEF.md").write_text("rules and more")
    (case / "customers.csv").write_text("id,dob\n1,1988-03-14")
    (case / "openapi.json").write_text(Path(API).read_text())
    rules = "1. RULE " * 200
    seen: dict = {}
    assert (
        cli.run([str(case), "https://m.dev", "--dry"], _extract_with_rules(rules), _capture(seen))
        == 0
    )
    assert seen["_prompt_brief"] == rules.strip()
    assert "BANK BRIEF in the prompt = the consolidated rules" in capsys.readouterr().err


def test_short_consolidated_rules_keep_the_full_folder_text(tmp_path, capsys):
    case = tmp_path / "Case"
    case.mkdir()
    (case / "BRIEF.md").write_text("rules")
    (case / "openapi.json").write_text(Path(API).read_text())
    seen: dict = {}
    assert (
        cli.run([str(case), "https://m.dev", "--dry"], _extract_with_rules("1. x"), _capture(seen))
        == 0
    )
    assert seen["_prompt_brief"].startswith("===== FILE: BRIEF.md =====\nrules")
    assert "consolidated rules are 4 chars" in capsys.readouterr().err


def test_brief_files_keep_their_prompt_brief():
    # The practice forms (brief-a.md, or brief-a.md + brief-b.md) are unchanged.
    briefs = Path(API).parents[1] / "briefs"
    for args in ([briefs / "brief-a.md"], [briefs / "brief-a.md", briefs / "brief-b.md"]):
        seen: dict = {}
        argv = [*map(str, args), API, "--dry"]
        assert cli.run(argv, _extract_with_rules("1. RULE " * 200), _capture(seen)) == 0
        assert seen["_prompt_brief"] == cli.read_briefs([str(a) for a in args])
