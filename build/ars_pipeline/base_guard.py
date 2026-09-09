"""
base_guard.py — refuse an ARS workbook whose formulas were never evaluated.

The data team's workbook can land with its formulas unevaluated. openpyxl reads
cached values only, so what comes out is the template's defaults — "Months in the
Program: 1", "Mailings to date: 0", every revenue cell 0 — and nothing downstream
can tell that from a client with no revenue. 1539 Marine FCU's 2026.08 workbook
arrived that way (2026-09-08); the performance dashboard rebuilt from it showed
$0 and a deck built from it would have said the same, in prose, on slide 6.

Opening the workbook in Excel and saving it evaluates the formulas. That is the
fix; this module only makes sure the alternative is a stopped build rather than
a plausible deck of zeros. One definition, used by both ARS extractors, the ARS
builder and the dashboard refresh — a guard in one of them and not the others is
how the dashboard caught it while the builder would not have.
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def uncalculated(base):
    """True when an extracted base looks like the template's defaults: at most
    one month in the program, no lifetime revenue and no current revenue. A live
    client has months and revenue; a brand-new one (one month, some revenue) is
    not caught, and should not be."""
    return (_num(base.get("months")) <= 1
            and not _num(base.get("ltd_revenue"))
            and not _num(base.get("cur_revenue")))


def message(workbook):
    return ("%s carries no calculated values (1 month, 0 mailings, $0 in every "
            "revenue cell). The workbook was saved without evaluating its formulas. "
            "Open it in Excel, save, and rebuild — do not build from this file."
            % workbook)


def check(base, workbook):
    """Raise SystemExit with the message when `base` is uncalculated."""
    if uncalculated(base):
        raise SystemExit("UNEVALUATED WORKBOOK: " + message(workbook))
    return base
