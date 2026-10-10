"""Smoke tests: the dev environment and repo skeleton are sane.

These make no network calls and need no credentials.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import freya_builder

ROOT = Path(__file__).resolve().parents[1]


def test_python_version():
    assert sys.version_info >= (3, 12)


def test_running_inside_project_venv():
    assert sys.prefix != sys.base_prefix, "not running inside a virtual environment"
    assert Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()


def test_package_imports():
    assert freya_builder.__version__
    assert Path(freya_builder.__file__).is_relative_to(ROOT / "src")


@pytest.mark.parametrize(
    "rel_path",
    [
        "CLAUDE.md",
        "README.md",
        ".env.example",
        ".gitignore",
        "pyproject.toml",
        "src/freya_builder/__init__.py",
        "docs/freya_api_notes.md",
        "docs/hackathon_notes.md",
    ],
)
def test_required_files_exist(rel_path):
    assert (ROOT / rel_path).is_file(), f"missing {rel_path}"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.parametrize("rel_path", [".env", ".env.local", ".venv/", "secrets/x.json"])
def test_secrets_and_venv_are_gitignored(rel_path):
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", rel_path],
        cwd=ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, f"{rel_path} is NOT ignored by git"


@pytest.mark.parametrize(
    "rel_path",
    [".env.example", "traces/hidden-1.log", "submission/hidden-1.workflow.json"],
)
def test_submission_files_are_committable(rel_path):
    """Files the hackathon requires us to commit must never be gitignored."""
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", rel_path],
        cwd=ROOT,
        capture_output=True,
    )
    assert result.returncode == 1, f"{rel_path} must be committable"


def test_env_example_has_no_real_values():
    """Every non-URL value in .env.example must be empty (placeholders only)."""
    for line in (ROOT / ".env.example").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if value.startswith("https://"):
            continue
        assert value == "", f"{key} has a value in .env.example; keep it empty"
