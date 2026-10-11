"""Tool URL = mock URL + the contract path, deterministic whether the model reads the path
relative to the base or with the base path (readiness review, 11 Oct). Synthetic URLs only."""

import pytest

from freya_builder.contract import join_mock, tools_from_operations


@pytest.mark.parametrize(
    "mock,path,want",
    [
        ("https://h.example/x/v1", "/op", "https://h.example/x/v1/op"),
        ("https://h.example/x/v1", "/x/v1/op", "https://h.example/x/v1/op"),
        ("https://h.example/x/v1/", "x/v1/op/", "https://h.example/x/v1/op/"),
        ("https://h.example/x/v1/", "op", "https://h.example/x/v1/op"),
        ("https://h.example", "/x/v1/op", "https://h.example/x/v1/op"),
        ("https://h.example/", "/op", "https://h.example/op"),
        ("https://h.example/x/v1", "/x/v10/op", "https://h.example/x/v1/x/v10/op"),
        ("https://h.example/x/v1", "/v1/op", "https://h.example/x/v1/v1/op"),
        ("https://h.example/x/v1", "https://bank.example/x/v1/op", "https://h.example/x/v1/op"),
        ("https://h.example", "https://bank.example/x/v1/op", "https://h.example/x/v1/op"),
        (
            "https://h.example/x/v1/",
            "https://bank.example/x/v1/op?a=1",
            "https://h.example/x/v1/op",
        ),
    ],
)
def test_the_mock_path_is_never_repeated(mock, path, want):
    assert join_mock(mock, path) == want


def test_both_readings_give_the_same_tools():
    def op(path):
        return [
            {
                "name": "op",
                "path": path,
                "method": "POST",
                "summary": "",
                "request": [],
                "response": [],
            }
        ]

    a = tools_from_operations(op("/op"), "https://h.example/x/v1")
    b = tools_from_operations(op("/x/v1/op"), "https://h.example/x/v1")
    assert a == b and a[0].url == "https://h.example/x/v1/op"


def test_a_folder_build_gives_single_base_urls_for_mixed_readings(tmp_path, monkeypatch, capsys):
    from test_cli import fake_render

    from freya_builder import cli, llm

    def op(name, path):
        return {
            "name": name,
            "path": path,
            "method": "POST",
            "summary": "",
            "request": [],
            "response": [],
        }

    mixed = [
        op("list_items", "/api/list_items"),
        op("renew_item", "renew_item"),
        op("hand_over", "https://bank.example/api/hand_over"),
    ]
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"operations": mixed})
    case = tmp_path / "Case"
    case.mkdir()
    (case / "BRIEF.md").write_text("synthetic brief")
    seen = {}

    def extract(trace, text, tools):
        seen["urls"] = [t.url for t in tools]
        return {"_prompt_brief": text}

    assert cli.run([str(case), "https://m.example/api", "--dry"], extract, fake_render) == 0
    assert seen["urls"] == [
        "https://m.example/api/list_items",
        "https://m.example/api/renew_item",
        "https://m.example/api/hand_over",
    ]
