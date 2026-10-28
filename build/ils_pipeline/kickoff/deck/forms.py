# Ported from v5 02-Scripts/ils/kickoff_analysis/deck/forms.py at 7ba1e63. Logic unchanged; the one edit is the import of deckkit from kickoff/_v5/.
"""One chart form per analysis, chosen from the forms already built.

The first cut of this deck drew nineteen tables. There are eighty-odd chart
forms in the library and it used none of them, which is the same defect the
deposit deck hit: one layout wearing nineteen headlines.

Every function here takes the analysis table the run already computed and
returns the arguments for ONE form. No two analyses use the same form -- a
test fails if they do -- because a reader who sees the same picture twice
stops reading the second one.

The `Grand Total` row every table carries is a footer, not a category, and
is dropped before anything is plotted.
"""

from __future__ import annotations

from pathlib import Path

from ils_pipeline.kickoff._v5 import deckkit as dk

GRAND_TOTAL = "Grand Total"


def _body(frame):
    """The table without its Grand Total footer."""
    if frame is None or frame.empty:
        return frame
    first = frame.columns[0]
    return frame[frame[first].astype(str) != GRAND_TOTAL]


def _num(frame, col, default=0.0):
    import pandas as pd
    if col not in frame.columns:
        return [default] * len(frame)
    return [float(v) if pd.notna(v) else default for v in frame[col]]


def _key_columns(frame):
    """The leading label columns, i.e. everything before the first measure.

    Most tables are keyed by one column. `Reg E by OD Eligibility` is keyed
    by two -- Eligibility, then Reg E Flag -- and pandas leaves the outer one
    blank on every row but the first of each group.
    """
    keys = []
    for col in frame.columns:
        if col.startswith(("#", "%", "Total", "Avg", "Med", "Pay", "Accounts")):
            break
        keys.append(col)
    return keys or [frame.columns[0]]


def _labels(frame):
    """One label per row, from every key column the table carries.

    Reading only column 0 gave the Reg E eligibility slides two band names
    and four empty strings -- and a headline that asserted 26% of accounts
    were in the band called "". A blank is a merged cell, not a category.
    """
    keys = _key_columns(frame)
    if len(keys) == 1:
        return [str(v) for v in frame[keys[0]]]
    outer = frame[keys[0]].replace("", None).ffill()
    parts = zip(outer, *(frame[k] for k in keys[1:]))
    return [" \u00b7 ".join(t for t in (str(v).strip() for v in row)
                        if t and t.lower() not in ("nan", "none"))
            for row in parts]


def _pct(frame, col):
    """Percent columns arrive as either 0-1 or 0-100. Normalise to 0-100."""
    vals = _num(frame, col)
    if vals and max(vals) <= 1.0001:
        return [v * 100 for v in vals]
    return vals


# ---------------------------------------------------------------------------
# One adapter per analysis. Keyed by the run's sheet name, same join the
# manifest uses.
# ---------------------------------------------------------------------------

def _account_status(f, out):
    """Pay ratio by status, with the account count under each column."""
    b = _body(f)
    rows = [[l, int(n), None, r] for l, n, r in
            zip(_labels(b), _num(b, "# of Accounts"), _pct(b, "Pay Ratio"))]
    # mark_weakest=False: these are core STATUS codes, not performance
    # tiers. Painting closed accounts red for paying 71% against 73% asserts
    # a problem that is not there, and puts a second accent on the chart.
    return dk.rate_bars(rows, out, mark_weakest=False, show_n=True)


def _account_type(f, out):
    """Personal against business as a share of the whole."""
    b = _body(f)
    rows = [[l, int(n)] for l, n in zip(_labels(b), _num(b, "# of Accounts"))]
    return dk.donut(rows, out, center_label="accounts",
                    center_value=f"{int(sum(r[1] for r in rows)):,}")


def _product_code(f, out):
    """What the book is made of, as one hundred-percent bar."""
    b = _body(f)
    rows = [[l, int(n)] for l, n in zip(_labels(b), _num(b, "# of Accounts"))]
    # A `full` slide: the full-bleed canvas, not the rail one.
    return dk.composition(rows, out, highlight=rows[0][0] if rows else None,
                          size=(dk.FIG_W_FULL, dk.FIG_H_FULL))


def _personal_deposits(f, out):
    """Accounts by deposit band."""
    b = _body(f)
    bins = [[l, int(n)] for l, n in zip(_labels(b), _num(b, "Accounts"))]
    return dk.histogram(bins, out, xlabel="deposits per month")


def _business_deposits(f, out):
    """Average against median deposits per band -- the gap is the skew.

    Horizontal: these band labels are long and the slide reads fine top to
    bottom. The NSF business slide does not, which is why the two forms
    swapped (James, 2026-09-09).
    """
    b = _body(f)
    rows = [[l, a, int(n), m, int(n)] for l, a, m, n in
            zip(_labels(b), _num(b, "Avg # of Deposits"),
                _num(b, "Med # of Deposits"), _num(b, "Accounts"))]
    return dk.paired_hbars(rows, "average", "median", out, unit="")


def _nsf_strat(f, out):
    """Accounts by NSF tier."""
    b = _body(f)
    rows = [[l, int(n)] for l, n in zip(_labels(b), _num(b, "# of Accounts"))]
    return dk.tier_bars(rows, out, label="accounts")


def _nsf_strat_biz(f, out):
    """Share of accounts against share of items -- concentration, seen twice.

    Vertical: NSF bands are an ordered scale, and a scale reads left to
    right. Drawn top to bottom it read wrong (James, 2026-09-09).
    """
    b = _body(f)
    return dk.grouped_bars(_labels(b), _pct(b, "% of Accounts"),
                           _pct(b, "% of Items Presented"),
                           "of accounts", "of items", out, fmt="{:,.0f}")


def _nsf_pay_ratio(f, out):
    """Pay rate per band against the blended rate for the whole segment.

    gap_area was the first choice and is wrong here: its x axis is numeric
    (it plots months), so NSF band labels came through as arithmetic. The
    band-against-blended form asks the same question and can hold the labels.
    """
    b = _body(f)
    blended = _blended_pay(b)
    rows = [[l, int(n), r] for l, n, r in
            zip(_labels(b), _num(b, "# of Accounts"), _pct(b, "Pay Ratio"))]
    # A pay ratio is a percentage. The form's default unit is dollars.
    return dk.ticket_bars(rows, blended, out, value_fmt="{:,.0f}%",
                          xlabel="OD/NSF items per account")


def _nsf_pay_ratio_biz(f, out):
    """The same two numbers per band, as a connector rather than an area."""
    b = _body(f)
    rows = [[l, p, q, ""] for l, p, q in
            zip(_labels(b), _num(b, "Total OD/NSF Items"),
                _num(b, "# of Items Paid"))]
    # Counts of items, not percentages; the gap between them is the items
    # that were returned, which is not a gain and is not coloured as one.
    return dk.dumbbell(rows, "presented", "paid", out,
                       value_fmt="{:,.0f}", delta_fmt="{:,.0f} returned",
                       delta_color=dk.GREY)


def _nsf_with_deposits(f, out):
    """NSF bands against what actually arrives in the account."""
    b = _body(f)
    return dk.line_series(
        [[l, v] for l, v in zip(_labels(b), _num(b, "Avg $$ Dep/Month"))],
        out, ylabel="average monthly deposits ($)")


def _nsf_with_deposits_biz(f, out):
    """The bands that matter most, called out as blocks."""
    b = _body(f).head(5)
    rows = [[l, f"{int(n):,}", f"{r:.0f}% paid", None] for l, n, r in
            zip(_labels(b), _num(b, "# of Accounts"), _pct(b, "Pay Ratio"))]
    # No note: the caption directly beneath it already says the population,
    # and two grey lines saying the same thing read as a mistake.
    return dk.category_blocks(rows, out)


def _od_status(f, out):
    """How the book sits across OD status codes."""
    b = _body(f)
    rows = [[l, int(n)] for l, n in zip(_labels(b), _num(b, "# of Accounts"))]
    return dk.health_bars(rows, out)


def _od_status_biz(f, out):
    """The same split as proportion, without a second bar chart."""
    b = _body(f)
    total = sum(_num(b, "# of Accounts")) or 1
    panels = [(l, 100 * n / total, f"{int(n):,} accounts") for l, n in
              zip(_labels(b), _num(b, "# of Accounts"))][:3]
    return dk.waffle(panels, out)


def _od_limit(f, out):
    """The limits in force, ranked, with pay rate beside each."""
    b = _body(f)
    # rows are (name, count, depth, momentum, local) -- five, not four.
    ranked = sorted(zip(_labels(b), _num(b, "# of Accounts"),
                        _pct(b, "Pay Ratio")), key=lambda r: -r[1])
    rows = [[l, int(n), f"{r:.0f}% paid", None, i == 0]
            for i, (l, n, r) in enumerate(ranked)][:8]
    return dk.momentum_bars(rows, out, headers=("OD LIMIT \u00b7 ACCOUNTS",
                                               "PAY RATE", None),
                            mark_label="")


def _od_limit_biz(f, out):
    """The top limit bands as headline numbers."""
    b = _body(f)
    total = sum(_num(b, "# of Accounts")) or 1
    panels = []
    for l, n, r in list(zip(_labels(b), _num(b, "# of Accounts"),
                            _pct(b, "Pay Ratio")))[:3]:
        panels.append((str(l), "accounts", 100 * n / total,
                       [(f"{int(n):,}", "accounts"), (f"{r:.0f}%", "paid")]))
    return dk.split_panels(panels, out)


def _rege_summary(f, out, codes=None):
    """Reg E election as one full-width bar -- the form built for it.

    Reads the CONFIRMED mapping when there is one. The first cut read "Y" as
    opted in and "N" as opted out, which is a guess: 1842 carries only "D".
    With no mapping every value falls in the middle band, which is the honest
    picture of an unconfirmed column rather than a confident wrong one.
    """
    b = _body(f)
    counts = {str(k).strip(): v for k, v in
              zip(_labels(b), _num(b, "# of Accounts"))}
    opt_in = {str(v).strip() for v in (getattr(codes, "rege_opt_in", None) or [])}
    opt_out = {str(v).strip() for v in (getattr(codes, "rege_opt_out", None) or [])}
    blankish = ("", "nan", "none")

    opted = sum(v for k, v in counts.items() if k in opt_in)
    blank = sum(v for k, v in counts.items() if k.lower() in blankish)
    if opt_in:
        # Everything that is not opted in IS opted out. One question, not two.
        out_of = sum(v for k, v in counts.items()
                     if k not in opt_in and k.lower() not in blankish)
        unmapped = 0
    else:
        out_of = sum(v for k, v in counts.items() if k in opt_out)
        unmapped = sum(v for k, v in counts.items()
                       if k not in opt_out and k.lower() not in blankish)
    return dk.rege_split(opted, out_of, unmapped, blank, out)


def _rege_eligibility(f, out):
    """Every eligibility-by-election cell, largest first.

    This table is a CROSS-TAB -- two eligibility groups by three election
    values -- not a funnel, and the rows do not nest. The first cut passed
    the difference between consecutive rows as a funnel drop-off, so the
    slide printed "-2276.0%" between two cells that have no such relation.
    No drop is passed because there is no drop to state. The form itself is
    still the wrong one for a cross-tab and is an open question (#187).
    """
    b = _body(f)
    stages = [[str(l), int(n), None, 0] for l, n in
              zip(_labels(b), _num(b, "# of Accounts"))]
    return dk.funnel(sorted(stages, key=lambda r: -r[1]), out)


def _rege_eligibility_biz(f, out):
    """The same question for business, as share of the whole."""
    b = _body(f)
    rows = [[l, int(n)] for l, n in zip(_labels(b), _num(b, "# of Accounts"))]
    return dk.composition(rows, out)


def _rege_annual(f, out):
    """Each election value against the activity behind it.

    `reg_e.annual` groups by Reg E Flag, not by year -- its own docstring
    says so. The sheet is named "Historical Reg E" and the deck called it
    "how Reg E has moved", over "the periods the extract carries", with
    "most recent year called out". Four claims about a time dimension the
    table does not have.
    """
    b = _body(f)
    rows = [[l, int(n), f"{r:.0f}% paid", None, i == 0]
            for i, (l, n, r) in enumerate(
                zip(_labels(b), _num(b, "# of Accounts"), _pct(b, "Pay Ratio")))][:8]
    return dk.momentum_bars(rows, out,
                            headers=("REG E FLAG \u00b7 ACCOUNTS", "PAY RATE",
                                     None),
                            mark_label="")


# What the reader is looking at, in the concrete: the unit, the window, the
# population. The headline states the finding; the axis cannot say this at
# all. Every sketch in the brand set carries one.
CAPTIONS = {
    "Account Status Analysis": "every account in the extract, by core status",
    "Account Type Analysis": "open accounts only, personal against business",
    "Product Code Distribution": "open accounts, by the product they sit on",
    "Personal Deposit Analysis": "open personal accounts",
    "Business Deposit Analysis": "open business accounts",
    "NSF Stratification": "open personal accounts, banded by OD/NSF items",
    "NSF Stratification (Business)": "open business accounts, banded by OD/NSF items",
    "NSF Pay Ratio": "share of items paid, band against the blended rate",
    "NSF Pay Ratio (Business)": "business accounts, presented against paid",
    "NSF Strat w Deposits": "what arrives monthly, by OD/NSF band",
    "NSF Strat w Deposits (Biz)": "business accounts, the bands that carry the volume",
    "OD Status Stratification": "open personal accounts, by OD status code",
    "OD Status Stratification (Biz)": "open business accounts, by OD status code",
    "OD Limit Stratification": "limits in force today, ranked by accounts",
    "OD Limit Stratification (Biz)": "business limits in force, top bands",
    "Reg E Summary": "open accounts, Reg E election as recorded",
    "Reg E by OD Eligibility": "open personal accounts, each eligibility and election cell",
    "Reg E by OD Eligibility (Biz)": "open business accounts, each eligibility and election cell",
    "Historical Reg E": "each Reg E election value, against the activity behind it",
}


# The join: sheet name -> (adapter, form name). The form name is what the
# distinctness test reads, so a duplicate is caught at test time, not by
# someone noticing two identical pictures in a client meeting.
FORMS = {
    "Account Status Analysis":        (_account_status, "rate_bars"),
    "Account Type Analysis":          (_account_type, "donut"),
    "Product Code Distribution":      (_product_code, "composition"),
    "Personal Deposit Analysis":      (_personal_deposits, "histogram"),
    "Business Deposit Analysis":      (_business_deposits, "paired_hbars"),
    "NSF Stratification":             (_nsf_strat, "tier_bars"),
    "NSF Stratification (Business)":  (_nsf_strat_biz, "grouped_bars"),
    "NSF Pay Ratio":                  (_nsf_pay_ratio, "ticket_bars"),
    "NSF Pay Ratio (Business)":       (_nsf_pay_ratio_biz, "dumbbell"),
    "NSF Strat w Deposits":           (_nsf_with_deposits, "line_series"),
    "NSF Strat w Deposits (Biz)":     (_nsf_with_deposits_biz, "category_blocks"),
    "OD Status Stratification":       (_od_status, "health_bars"),
    "OD Status Stratification (Biz)": (_od_status_biz, "waffle"),
    "OD Limit Stratification":        (_od_limit, "momentum_bars"),
    "OD Limit Stratification (Biz)":  (_od_limit_biz, "split_panels"),
    "Reg E Summary":                  (_rege_summary, "rege_split"),
    "Reg E by OD Eligibility":              (_rege_eligibility, "funnel"),
    "Reg E by OD Eligibility (Biz)":        (_rege_eligibility_biz, "composition_biz"),
    "Historical Reg E":               (_rege_annual, "momentum_bars_annual"),
}


def render(key: str, frame, out_dir: Path, codes=None) -> Path | None:
    """The chart for one analysis, or None if the table cannot support it.

    A form that raises returns None rather than taking the deck down: a
    malformed chart is a missing picture, never a missing slide, and the
    slide falls back to its table with the reason on its face.
    """
    entry = FORMS.get(key)
    if entry is None or frame is None or getattr(frame, "empty", True):
        return None
    adapter, name = entry
    path = Path(out_dir) / f"{name}_{abs(hash(key)) % 10**8}.png"
    try:
        import inspect
        # Set before the form runs: the form saves internally and _save()
        # applies it, so no form needs to know captions exist.
        dk.set_caption(CAPTIONS.get(key))
        if "codes" in inspect.signature(adapter).parameters:
            return Path(adapter(frame, path, codes))
        return Path(adapter(frame, path))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# What each slide ASSERTS, and the three numbers that back it.
#
# The first cut titled every slide with a label -- "Where the accounts and the
# items are" -- and put the raw table beside the chart. That is a workbook tab
# with a picture stapled to it. The house pattern (ars/deck/deposit_slides.py)
# is a headline that states the finding WITH its number, the chart in the main
# slot, and three callout tiles down the right edge. The table stays in the
# workbook, which is what the workbook is for.
# ---------------------------------------------------------------------------

def _sum(b, col):
    return sum(_num(b, col))


def _largest(b, col="# of Accounts"):
    """(label, value) of the biggest row, or ("", 0)."""
    vals = list(zip(_labels(b), _num(b, col)))
    return max(vals, key=lambda r: r[1]) if vals else ("", 0.0)


def _share(part, whole):
    return 100 * part / whole if whole else 0.0


def _presented(b):
    """Items presented, whatever this table calls the column."""
    for col in ("Total OD/NSF Items", "# of Items", "Total Items"):
        if col in b.columns:
            total = _sum(b, col)
            if total:
                return total
    return 0.0


def _paid(b):
    for col in ("# of Items Paid", "Total NSF Items Paid", "# of Paid Items"):
        if col in b.columns:
            total = _sum(b, col)
            if total:
                return total
    return 0.0


def _blended_pay(b):
    return _share(_paid(b), _presented(b))


def _accounts_headline(b, noun="accounts"):
    total = _sum(b, "# of Accounts") or _sum(b, "Accounts")
    label, n = _largest(b, "# of Accounts" if "# of Accounts" in b.columns
                        else "Accounts")
    return (f"{int(total):,} {noun}, {_share(n, total):.0f}% of them in "
            f"\u201c{label}\u201d",
            f"Across {len(b)} bands; the largest holds {int(n):,}")


def _pay_headline(b):
    """A pay rate, or -- when there are no items to rate -- the account
    headline instead. "0% of 0 items were paid" is a confident sentence
    about nothing, which is worse than saying something smaller.
    """
    presented = _presented(b)
    if not presented:
        return _accounts_headline(b)
    return (f"{_blended_pay(b):.0f}% of {int(presented):,} items presented "
            f"were paid",
            "Bands below the blended rate are where the returns concentrate")


def _rail_items(b):
    """Three tiles, derived. Never invented: a column that is not there is
    a tile that is not shown."""
    items = []
    total = _sum(b, "# of Accounts") or _sum(b, "Accounts")
    if total:
        items.append(("Accounts", f"{int(total):,}", "in this cut"))
    label, n = _largest(b, "# of Accounts" if "# of Accounts" in b.columns
                        else "Accounts")
    if n:
        items.append(("Largest band", str(label)[:18],
                      f"{int(n):,} accounts, {_share(n, total):.0f}%"))
    presented = _presented(b)
    if presented:
        items.append(("Pay rate", f"{_blended_pay(b):.0f}%",
                      f"of {int(presented):,} items presented"))
    elif "Avg $$ Deposits" in b.columns or "Avg $$ Dep/Month" in b.columns:
        col = ("Avg $$ Deposits" if "Avg $$ Deposits" in b.columns
               else "Avg $$ Dep/Month")
        avg = _sum(b, col) / len(b) if len(b) else 0
        items.append(("Average deposits", f"${avg:,.0f}", "per account, per month"))
    return items[:3]


# ---------------------------------------------------------------------------
# One headline per slide, stating THAT slide's finding with its number.
#
# Fifteen of nineteen used to call the same function, so the deck said
# "N accounts, X% of them in Y" fifteen times in different nouns -- one
# sentence wearing nineteen hats, which is the chart-form defect a level up.
# The personal/business twins DO share: they ask the same question of a
# different segment, and the noun and the numbers differ.
#
# Each takes (body, codes). `codes` is there because some findings may only
# be stated when the run was told what a code means -- a Reg E opt-in rate
# is a claim about a mapping nobody has confirmed unless they have.
# ---------------------------------------------------------------------------

def _band(b, name):
    """(count, share) for the band with this label, or (0, 0)."""
    total = _sum(b, "# of Accounts") or _sum(b, "Accounts")
    col = "# of Accounts" if "# of Accounts" in b.columns else "Accounts"
    for label, n in zip(_labels(b), _num(b, col)):
        if str(label).strip().lower() == name.lower():
            return n, _share(n, total)
    return 0.0, 0.0


def _totals(b):
    total = _sum(b, "# of Accounts") or _sum(b, "Accounts")
    label, n = _largest(b, "# of Accounts" if "# of Accounts" in b.columns
                        else "Accounts")
    return total, label, n


def _open_book(b, _codes=None):
    """How much of the extract is open. The overview of the FILE."""
    total, label, n = _totals(b)
    opened, share = _band(b, "Open")
    if not opened:
        return _accounts_headline(b)
    return (f"{int(opened):,} of {int(total):,} accounts are open",
            f"{share:.0f}% of the extract; {len(b)} status values in it")


def _personal_share(b, _codes=None):
    total, label, n = _totals(b)
    personal, share = _band(b, "Personal")
    business, _ = _band(b, "Business")
    if not personal:
        return _accounts_headline(b)
    return (f"{share:.0f}% of the open book is personal",
            f"{int(personal):,} personal, {int(business):,} business")


def _spread(b, noun="accounts"):
    """A book spread thin across many bands, or concentrated in a few."""
    total, label, n = _totals(b)
    col = "# of Accounts" if "# of Accounts" in b.columns else "Accounts"
    top3 = sum(sorted(_num(b, col), reverse=True)[:3])
    return (f"{len(b)} products carry the book, the largest "
            f"{_share(n, total):.0f}% of it",
            f"The top three hold {_share(top3, total):.0f}% of "
            f"{int(total):,} {noun}")


def _deposit_band(b, noun):
    """The band most accounts sit in -- for a deposit-frequency distribution."""
    total, label, n = _totals(b)
    return (f"{_share(n, total):.0f}% of {noun} make {label} deposits a month",
            f"{int(total):,} accounts across {len(b)} bands")


def _no_activity(b, noun):
    """The share with NO OD/NSF item, and where the items actually are."""
    total, label, n = _totals(b)
    clean, share = _band(b, "0")
    items = _presented(b)
    if not clean or not items:
        return _accounts_headline(b, noun)
    return (f"{share:.0f}% of {noun} had no OD/NSF item",
            f"The other {int(total - clean):,} carry all "
            f"{int(items):,} items presented")


def _deposits_against_activity(b, noun):
    """Whether what arrives rises with the number of items presented."""
    col = ("Avg $$ Dep/Month" if "Avg $$ Dep/Month" in b.columns
           else "Avg $$ Deposits")
    vals = _num(b, col)
    labels = _labels(b)
    if not vals or max(vals) <= 0:
        return _accounts_headline(b, noun)
    hi, lo = vals[-1], vals[0]
    direction = "more" if hi >= lo else "less"
    return (f"The heaviest OD/NSF band deposits ${hi:,.0f} a month, "
            f"{direction} than the lightest at ${lo:,.0f}",
            f"Average monthly deposits across {len(b)} bands of {noun}")


def _sits_on(b, noun):
    """How the book distributes across OD status codes."""
    total, label, n = _totals(b)
    return (f"{_share(n, total):.0f}% of {noun} sit on "
            f"\u201c{label}\u201d",
            f"{len(b)} OD status codes in force across {int(total):,} accounts")


def _no_limit(b, noun):
    """How much of the book has no overdraft limit at all."""
    total, label, n = _totals(b)
    none, share = _band(b, "0")
    if not none:
        return (f"The largest limit band holds {_share(n, total):.0f}% of "
                f"{noun}", f"{len(b)} limits in force")
    return (f"{share:.0f}% of {noun} have no overdraft limit",
            f"{len(b) - 1} limits in force across the other "
            f"{int(total - none):,}")


def _rege_election(b, codes=None):
    """An opt-in rate is a claim about a mapping. Only made when confirmed."""
    total, label, n = _totals(b)
    opt_in = {str(v).strip() for v in (getattr(codes, "rege_opt_in", None) or [])}
    if not opt_in:
        return (f"{len(b)} Reg E values across {int(total):,} accounts, "
                f"none of them confirmed",
                "Nobody has said which value means opted in, so this deck "
                "does not say either")
    col = "# of Accounts" if "# of Accounts" in b.columns else "Accounts"
    elected = sum(v for l, v in zip(_labels(b), _num(b, col))
                  if str(l).strip() in opt_in)
    return (f"{_share(elected, total):.0f}% of open accounts have opted in "
            f"to Reg E",
            f"{int(elected):,} of {int(total):,}, on the mapping this run "
            f"was given")


def _rege_against_eligibility(b, codes=None):
    """The question the slide asks: does election differ by eligibility?"""
    total, label, n = _totals(b)
    opt_in = {str(v).strip() for v in (getattr(codes, "rege_opt_in", None) or [])}
    col = "# of Accounts" if "# of Accounts" in b.columns else "Accounts"
    if not opt_in:
        return (f"{int(total):,} accounts split six ways across eligibility "
                f"and election",
                f"The largest cell is \u201c{label}\u201d with "
                f"{int(n):,}; the election mapping is unconfirmed")
    groups = {}
    for lab, v in zip(_labels(b), _num(b, col)):
        head, _, tail = str(lab).partition(" \u00b7 ")
        g = groups.setdefault(head.strip(), [0.0, 0.0])
        g[0] += v
        if tail.strip() in opt_in:
            g[1] += v
    parts = [(g, _share(v[1], v[0])) for g, v in groups.items()]
    if len(parts) < 2:
        return _accounts_headline(b)
    parts.sort(key=lambda r: -r[1])
    return (f"{parts[0][0]} accounts opt in at {parts[0][1]:.0f}%, "
            f"{parts[-1][0]} at {parts[-1][1]:.0f}%",
            f"Across {int(total):,} accounts and {len(b)} cells")


def _pay_rate_by_election(b, _codes=None):
    """Whether the pay rate moves with the Reg E value at all."""
    rates = [r for r in _pct(b, "Pay Ratio") if r]
    total, label, n = _totals(b)
    if not rates:
        return _accounts_headline(b)
    return (f"Pay rate is {min(rates):.0f}% to {max(rates):.0f}% whichever "
            f"Reg E value an account carries",
            f"{len(b)} election values across {int(total):,} accounts")


HEADLINES = {
    # The overview of the FILE -- how many accounts, and how they distribute.
    # It asserted a pay rate once, which was both the wrong subject and the
    # one that came out at 100% (James, 2026-09-09).
    "Account Status Analysis": _open_book,
    "Account Type Analysis": _personal_share,
    "Product Code Distribution": lambda b, c=None: _spread(b),
    "Personal Deposit Analysis":
        lambda b, c=None: _deposit_band(b, "personal accounts"),
    "Business Deposit Analysis":
        lambda b, c=None: _deposit_band(b, "business accounts"),
    "NSF Stratification":
        lambda b, c=None: _no_activity(b, "personal accounts"),
    "NSF Stratification (Business)":
        lambda b, c=None: _no_activity(b, "business accounts"),
    "NSF Pay Ratio": lambda b, c=None: _pay_headline(b),
    "NSF Pay Ratio (Business)": lambda b, c=None: _pay_headline(b),
    "NSF Strat w Deposits":
        lambda b, c=None: _deposits_against_activity(b, "personal accounts"),
    "NSF Strat w Deposits (Biz)":
        lambda b, c=None: _deposits_against_activity(b, "business accounts"),
    "OD Status Stratification":
        lambda b, c=None: _sits_on(b, "personal accounts"),
    "OD Status Stratification (Biz)":
        lambda b, c=None: _sits_on(b, "business accounts"),
    "OD Limit Stratification":
        lambda b, c=None: _no_limit(b, "personal accounts"),
    "OD Limit Stratification (Biz)":
        lambda b, c=None: _no_limit(b, "business accounts"),
    "Reg E Summary": _rege_election,
    "Reg E by OD Eligibility": _rege_against_eligibility,
    "Reg E by OD Eligibility (Biz)": _rege_against_eligibility,
    "Historical Reg E": _pay_rate_by_election,
}


# The run is TOLD which raw code means personal, business and open. Where it
# was told, the deck says the word; where it was not, the code stands as it is.
# `88% of them in "O"` is not a sentence anyone can read out in a client
# meeting, and inventing a word for a code nobody confirmed is how the Reg E
# guess got made. Reg E flags stay raw for exactly that reason.
_SPOKEN = {
    "Account Status Analysis": lambda c: {c.open_status_code: "Open"},
    "Account Type Analysis": lambda c: {c.personal_code: "Personal",
                                        c.business_code: "Business"},
}


def _spoken(key: str, frame, codes):
    """The table with its key column read as words, where the run knows them."""
    mapping = _SPOKEN.get(key)
    if mapping is None or codes is None or frame is None:
        return frame
    try:
        words = {str(k): v for k, v in mapping(codes).items() if k}
    except AttributeError:
        return frame
    col = frame.columns[0]
    out = frame.copy()
    out[col] = [words.get(str(v).strip(), v) for v in out[col]]
    return out


def panel(key: str, frame, out_dir: Path, codes=None):
    """Everything one slide needs: chart, headline, subtitle, rail.

    Returns None when the analysis cannot support a slide at all.
    """
    if frame is None or getattr(frame, "empty", True):
        return None
    frame = _spoken(key, frame, codes)
    b = _body(frame)
    if b is None or b.empty:
        return None

    try:
        headline, subtitle = HEADLINES[key](b, codes)
    except Exception:
        headline, subtitle = key, f"{len(b)} rows"

    return {"chart": render(key, frame, out_dir, codes),
            "headline": headline,
            "subtitle": subtitle,
            "rail": _rail_items(b)}
