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
