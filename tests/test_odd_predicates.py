"""Eligibility, debit and business are read through odd_rows, and nowhere else (2026-09-18).

The ODD's three flag columns were compared to a literal in nine files. Most read "Yes" in
any case; product_mix_slide, build_ars_gen, build_lift_matrix and excluded_accounts_slide
compared to "Yes" exactly, so a core that wrote YES would have been eligible on one slide
and not on the next. odd_rows now carries the scalar predicates, their pandas forms and
the newest-Elig-column rule; the accessors are pinned to the scalars; and the guard below
fails when a flag column is compared to a literal anywhere under build/, scripts/ or
validation/.
"""
import io
import re
import sys
import tokenize
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
import odd_rows as O  # noqa: E402

YES_FORMS = ["Yes", "yes", "YES", " Yes ", "\x00Yes", "yEs"]
NO_FORMS = ["No", "no", "NO", " no "]
NEITHER = ["", " ", None, "Maybe", "Y", "N", "1", "nan", "Yes No"]


@pytest.mark.parametrize("v", YES_FORMS)
def test_yes_in_any_case_is_a_flag(v):
    assert O.flag_yes(v) and O.has_debit(v) and O.is_eligible(v) and O.is_business(v)
    assert not O.is_personal(v)
    assert O.business_class(v) == "business"


@pytest.mark.parametrize("v", NO_FORMS)
def test_no_in_any_case_is_personal_and_not_a_flag(v):
    assert not (O.flag_yes(v) or O.has_debit(v) or O.is_eligible(v) or O.is_business(v))
    assert O.is_personal(v)
    assert O.business_class(v) == "personal"


@pytest.mark.parametrize("v", NEITHER)
def test_anything_else_is_neither(v):
    """A blank is NEITHER personal nor business (the rule product_mix_slide settled)."""
    assert not (O.flag_yes(v) or O.is_business(v) or O.is_personal(v))
    assert O.business_class(v) == "other"


def test_series_forms_agree_with_the_scalars():
    pd = pytest.importorskip("pandas")
    cells = YES_FORMS + NO_FORMS + NEITHER + [float("nan")]
    s = pd.Series(cells, dtype=object)
    assert list(O.flag_yes_series(s)) == [O.flag_yes(c) for c in cells]
    assert list(O.business_class_series(s)) == [O.business_class(c) for c in cells]


def test_series_forms_on_a_string_dtype_column():
    """pandas 3 keeps NA distinct from 'nan' on str dtype; both must read as neither."""
    pd = pytest.importorskip("pandas")
    s = pd.Series(["Yes", None, "No", pd.NA], dtype="str")
    assert list(O.flag_yes_series(s)) == [True, False, False, False]
    assert list(O.business_class_series(s)) == ["business", "other", "personal", "other"]


@pytest.mark.parametrize("cols,want", [
    (["Acct ID", "Aug25 Elig", "Jul26 Elig", "Jan26 Elig"], "Jul26 Elig"),   # by date, not by text
    (["Dec25 Elig", "Jan26 Elig"], "Jan26 Elig"),
    (["Jul26 Sig #", "Business?"], None),
    ([], None),
])
def test_the_newest_elig_column_is_chosen_by_date(cols, want):
    assert O.latest_elig_col(cols) == want


def test_accessors_bind_the_newest_elig_column():
    H = {"Business?": 0, "Debit?": 1, "Aug25 Elig": 2, "Jul26 Elig": 3}
    odd = O.accessors(H)
    assert odd.iselig(["No", "Yes", "Yes", "No"]) is False      # reads Jul26, not Aug25
    assert odd.iselig(["No", "Yes", "No", "yes"]) is True
    assert odd.iselig(["No"]) is False                           # short row
    assert O.accessors({"Business?": 0}).iselig(["No", "Yes"]) is False   # no Elig column at all


CELLS = YES_FORMS + NO_FORMS + NEITHER


@pytest.mark.parametrize("cell", [c for c in CELLS if c is not None and "\x00" not in c])
def test_the_accessors_are_the_scalar_predicates(cell):
    """The accessors stay inlined for speed; this is what keeps them the same reading.
    NUL is the one difference by design: every row reader strips it before the accessors
    see a cell, so the accessors do not pay for it per row."""
    H = {"Business?": 0, "Debit?": 1, "Jul26 Elig": 2}
    odd = O.accessors(H)
    row = [cell, cell, cell]
    assert odd.personal(row) is O.is_personal(cell)
    assert odd.business(row) is O.is_business(cell)
    assert odd.hascard(row) is O.has_debit(cell)
    assert odd.iselig(row) is O.is_eligible(cell)


# --------------------------------------------------------------------------- the guard
def _code_only(src):
    """Source with comments and docstrings removed, tokens space-separated."""
    out, prev = [], None
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, SyntaxError):
        return src
    for t in toks:
        if t.type == tokenize.COMMENT:
            continue
        if t.type == tokenize.STRING and prev in (None, tokenize.NEWLINE, tokenize.INDENT,
                                                  tokenize.DEDENT, tokenize.NL, tokenize.ENCODING):
            prev = t.type
            continue
        if t.type in (tokenize.NL, tokenize.NEWLINE):
            out.append("\n")
        elif t.type not in (tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER):
            out.append(t.string)
            out.append(" ")
        prev = t.type
    return "".join(out)


# A flag column compared to a QUOTED literal (a count compared to a number is not a reading).
_FLAG_COMPARE = re.compile(
    r"""(Debit\?|Business\?|Elig|ELIG_COL|elig_col|["']elig["'])\s*["']?\s*[\])]?\s*"""
    r"""((==|!=)\s*["']|\.\s*(eq|ne|isin)\s*\(\s*\[?\s*["'])""")


def test_no_file_compares_a_flag_column_to_a_literal():
    offenders = []
    for folder in ("build", "scripts", "validation"):
        for p in (REPO / folder).rglob("*.py"):
            if p.name == "odd_rows.py":
                continue
            code = _code_only(p.read_text(encoding="utf-8", errors="replace"))
            for n, line in enumerate(code.splitlines(), 1):
                if _FLAG_COMPARE.search(line):
                    offenders.append(f"{p.relative_to(REPO)}: {line.strip()[:80]}")
    assert not offenders, "flag columns must be read through odd_rows:\n" + "\n".join(offenders)


def test_the_guard_sees_through_comments_and_docstrings():
    src = '"""Elig == Yes in a docstring"""\nx = 1  # Business? == "Yes"\n'
    assert not _FLAG_COMPARE.search(_code_only(src))
    assert _FLAG_COMPARE.search(_code_only('d["Debit?"].eq("Yes")\n'))
    assert _FLAG_COMPARE.search(_code_only('g(r, f"{latest} Elig") == "Yes"\n'))
    assert _FLAG_COMPARE.search(_code_only('r["elig"] == "Yes"\n'))
    assert _FLAG_COMPARE.search(_code_only('~ch["Business?"].isin(["Yes", "No"])\n'))
    assert not _FLAG_COMPARE.search(_code_only('if len(elig) == 0:\n'))
    assert not _FLAG_COMPARE.search(_code_only('if a["elig"] == 0:\n'))       # a count, not a reading
