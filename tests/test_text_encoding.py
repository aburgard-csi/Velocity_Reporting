"""Text I/O names its encoding — the check that would have caught the Windows build break.

`open()` in text mode without `encoding=` uses the platform default: UTF-8 on the
Mac this pipeline was written on, cp1252 on the CSI/Cowork Windows machine. The
difference is invisible until a non-ASCII character reaches the file, and then it
is fatal rather than subtle.

It reached one on 2026-08-31: `scripts/oddd_optimize.py` wrote `oddd_pack.md`
with an unqualified `open(..., "w")`, and the arrow in "Reg E Opt In -> ..." raised
`UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`. The ARS
chain died at the first step on Windows while passing on the Mac. The read side
fails the same way, and worse: cp1252 decodes most UTF-8 bytes into mojibake
without raising, so a client name with an accent or an em-dash would ship into a
deck silently corrupted.

So the rule is the whole class, not the one file: every text-mode `open()` under
build/, scripts/, validation/ and tests/ states its encoding. Binary opens are
skipped — `encoding=` is an error there.
"""
import ast
import io
import os

import pytest

import rpe_env

REPO = rpe_env.REPO_ROOT
ROOTS = ("build", "scripts", "validation", "tests")


def _sources():
    for root in ROOTS:
        for dirpath, _, names in os.walk(os.path.join(REPO, root)):
            if "__pycache__" in dirpath:
                continue
            for n in sorted(names):
                if n.endswith(".py"):
                    yield os.path.join(dirpath, n)


def _bare_opens(path):
    """Text-mode `open()` calls in `path` that do not pass `encoding=`."""
    tree = ast.parse(io.open(path, encoding="utf-8").read(), filename=path)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "open"):
            continue
        mode = "r"
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = kw.value.value
        if "b" in str(mode):
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        yield node.lineno, mode


@pytest.mark.parametrize("path", list(_sources()),
                         ids=lambda p: os.path.relpath(p, REPO).replace(os.sep, "/"))
def test_text_open_states_its_encoding(path):
    bare = list(_bare_opens(path))
    rel = os.path.relpath(path, REPO).replace(os.sep, "/")
    assert not bare, (
        "text-mode open() without encoding= (cp1252 on Windows, UTF-8 on Mac):\n"
        + "\n".join(f"  {rel}:{ln}  mode={m!r}" for ln, m in bare))
