"""Two guards the engine brought with it from v5 (2026-09-18).

No month literal in executable code: every window derives from the anchor, which is read
from the data, so the same code answers for every month. And a structural zero is None,
not 0.0: a rate over an empty base is "not computable", which is not the same as a
measured zero.
"""
import io
import re
import sys
import tokenize
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ENGINE = REPO / "build" / "ars_pipeline" / "engine"
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]

MONTH_LIT = re.compile(r"""['"](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{2}\b""")


def _code_tokens(src):
    """STRING tokens that are executable code: not comments, not docstrings."""
    out, prev = [], None
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, SyntaxError):
        return []
    for t in toks:
        if t.type == tokenize.COMMENT:
            continue
        if t.type == tokenize.STRING and prev not in (None, tokenize.NEWLINE, tokenize.INDENT,
                                                      tokenize.DEDENT, tokenize.NL, tokenize.ENCODING):
            out.append((t.start[0], t.string))
        prev = t.type
    return out


def test_no_month_literal_in_executable_code():
    bad = []
    for p in sorted(ENGINE.rglob("*.py")):
        for line, s in _code_tokens(p.read_text(encoding="utf-8")):
            if MONTH_LIT.search(s):
                bad.append(f"{p.relative_to(REPO)}:{line}: {s[:40]}")
    for p in (REPO / "build" / "ars_pipeline" / "run_analysis.py", REPO / "build" / "ars_pipeline" / "engine_config.py"):
        for line, s in _code_tokens(p.read_text(encoding="utf-8")):
            if MONTH_LIT.search(s):
                bad.append(f"{p.relative_to(REPO)}:{line}: {s[:40]}")
    assert not bad, "month literals in executable code:\n" + "\n".join(bad)


def test_the_anchor_follows_the_file(odd_csv, tmp_path):
    import run_analysis as RA
    r = RA.run(odd_csv, "1441", "2026.08", out_dir=tmp_path, txn=False, tables=None)
    assert r.metrics["anchor_tag"] == "Jul26" and r.metrics["l12m_start"] == "2025-08"


def test_a_structural_zero_is_none_and_a_measured_zero_is_zero():
    from engine.monthly_analysis import attrition
    assert attrition._pct(0, 0) is None
    assert attrition._pct(0, 400) == 0.0
    lift = getattr(attrition, "_lift", None)
    if lift is not None:
        assert lift(None, 4.2) is None
