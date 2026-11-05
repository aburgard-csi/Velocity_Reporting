"""Sheila shows the version in the VERSION file in her header, and the release carries the file."""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "scripts"))
import ars_launcher_web as W  # noqa: E402


def test_the_repo_has_a_version_file_in_the_agreed_shape():
    first = (REPO / "VERSION").read_text(encoding="utf-8-sig").splitlines()[0].strip()
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", first), first
    assert W.app_version() == first


def test_app_version_reads_the_first_line_and_ignores_anything_else(tmp_path):
    f = tmp_path / "VERSION"
    f.write_text("2.1\nnotes nobody asked for\n", encoding="utf-8")
    assert W.app_version(f) == "2.1"
    f.write_text("﻿3.0.2\n", encoding="utf-8")
    assert W.app_version(f) == "3.0.2"


def test_a_missing_or_malformed_file_shows_no_version_not_a_guess(tmp_path):
    assert W.app_version(tmp_path / "nope") == ""
    f = tmp_path / "VERSION"
    f.write_text("", encoding="utf-8")
    assert W.app_version(f) == ""
    for bad in ("two", "v2.0", "2", "2.0 beta", "<b>2.0</b>"):
        f.write_text(bad + "\n", encoding="utf-8")
        assert W.app_version(f) == "", bad


def test_the_corner_carries_the_version(monkeypatch, tmp_path):
    f = tmp_path / "VERSION"
    f.write_text("2.0\n", encoding="utf-8")
    monkeypatch.setattr(W, "VERSION_FILE", f)
    import sheila_hub as H
    assert "Version 2.0" in H.page("T", W.app_version())
    f.write_text("junk\n", encoding="utf-8")
    assert W.app_version() == "" and "Version" not in H.page("T", W.app_version()), "a copy with no usable VERSION shows none, not a guess"
    assert "<b>CSM Sheila</b><small>__VERSION__</small>" in H._PAGE


def test_the_release_script_copies_the_version_file_with_the_code():
    ps = (REPO / "scripts" / "release_launcher.ps1").read_text(encoding="utf-8")
    assert "'VERSION'" in ps and "'clients.md'" in ps
