"""
Deposit Score output-analysis slides, native to the 20 x 11.25 in canvas.

One set per scored account type: a divider, the output distribution, risk
categorisation against observed charge-off experience, the variables the score
uses and whether each is populated, then one alignment slide per variable, the
closure/charge-off validation, and the RDI cohort when it is populated.
"""
from __future__ import annotations

import os

from pptx.enum.text import PP_ALIGN

from . import ds_analysis as DS
from . import theme as T
from .ils_data import count, money, pct

X = 0.42
W = T.SLIDE_W - 2 * X


def add_ds_section(dk, A, *, section, divider=True, progress=None):
    """Every Deposit Score slide for one analysis scope. Returns notes."""
    say = progress or (lambda m: None)
    if not A.available:
        return [A.reason]

    say(f"  rendering Deposit Score charts — {A.overall_scope_label}…")
    img_dir = os.path.join(dk.chart_dir, "deposit_score_" + str(A.overall_scope_label).replace(" ", "_").replace("/", "_"))
    os.makedirs(img_dir, exist_ok=True)
    A.charts = DS.render_charts(A, img_dir)

    if divider:
        _divider(dk, A, section=section)
    _distribution(dk, A, section=section)
    _risk(dk, A, section=section)
    _variables(dk, A, section=section)
    for b in A.variables:
        _alignment(dk, A, b, section=section)
    _outcomes(dk, A, section=section)
    if A.rdi:
        _rdi(dk, A, section=section)
    return list(A.notes)


# ── slides ──────────────────────────────────────────────────────────────────
def _divider(dk, A, *, section):
    blurb = (f"{pct(A.pct_scored)} of {count(A.overall_n)} {A.overall_scope_label} carry a "
             f"1–5 Deposit Score, at a mean of {A.mean_score:.2f}.")
    if A.active_rules_label:
        blurb += f"  Regression tree: {A.active_rules_label}."
    dk.divider("Deposit Score\nOutput Analysis",
               eyebrow=f"{dk.client} — {A.overall_scope_label.title()}",
               blurb=blurb, section=section)


def _distribution(dk, A, *, section):
    slide = dk.content("Deposit Score — output distribution",
                       f"The 0–5 score across {A.overall_scope_label}, as of {dk.date_str}",
                       section=section)
    cards = [
        (f"{A.mean_score:.2f}", "Mean Deposit Score", "Across scored accounts (1–5)"),
        (pct(A.pct_scored), "Scored", f"{count(A.overall_n)} accounts in scope"),
    ]
    strong = sum(A.overall_dist.get(k, 0) for k in (4, 5))
    weak = sum(A.overall_dist.get(k, 0) for k in (1, 2))
    n_scored = sum(A.overall_dist.get(k, 0) for k in (1, 2, 3, 4, 5)) or 1
    cards.append((pct(strong / n_scored * 100), "Strong (4–5)", f"{count(strong)} accounts"))
    cards.append((pct(weak / n_scored * 100), "Weak (1–2)", f"{count(weak)} accounts"))
    cards.append((pct(A.overall_dist.get(0, 0) / max(1, A.overall_n) * 100),
                  "Not scored", f"{count(A.overall_dist.get(0, 0))} accounts"))
    T.kpi_cards(slide, T.MARGIN_L, T.CONTENT_TOP + 0.05, T.CONTENT_W, 2.25, cards)

    y = T.CONTENT_TOP + 2.55
    h = T.CONTENT_BOTTOM - y
    if A.charts.get("score_dist"):
        T.image(slide, A.charts["score_dist"], X, y, 11.6, h)
    if A.charts.get("score_by_type"):
        T.image(slide, A.charts["score_by_type"], X + 11.9, y, 7.2, h)
    else:
        T.band_label(slide, X + 11.9, y, 7.2, "  DISTRIBUTION DETAIL")
        rows = [[DS.SCORE_LABEL[k], count(A.overall_dist.get(k, 0)),
                 pct(A.overall_dist.get(k, 0) / max(1, A.overall_n) * 100)]
                for k in DS.SCORE_ORDER if A.overall_dist.get(k, 0)]
        tbl = dk.table(slide, X + 11.9, y + 0.55, 7.2, [2.6, 2.3, 2.3], len(rows) + 1,
                       row_h=0.42)
        T.fill_table(tbl, ["Score", "Accounts", "% of scope"], rows,
                     align=[PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT])
    return slide


def _risk(dk, A, *, section):
    slide = dk.content("Deposit Score — risk categorisation",
                       "Each score tiered by its observed charge-off rate, so the "
                       "categorisation cannot contradict the data beside it",
                       section=section)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, 12.4, "  OUTCOME EXPERIENCE BY SCORE")
    headers = ["Score", "Risk tier", "Accounts", "% of portfolio", "Charge-off rate",
               "Mean ILS limit"]
    rows = []
    for r in A.risk_rows:
        rows.append([r["label"], r["tier"], count(r["n"]), pct(r["pct"]),
                     pct(r["co_rate"], 2), money(r["mean_odl"])])
    if A.outcome_totals:
        rows.append(["All", "—", count(A.outcome_totals["n"]), "100.0%",
                     pct(A.outcome_totals["co_rate"], 2), "—"])
    tbl = dk.table(slide, X, y + 0.50, 12.4, [1.4, 2.8, 2.0, 2.2, 2.2, 2.2],
                   len(rows) + 1, row_h=0.44)

    def colour(i, j, v):
        if j != 0 or i >= len(A.risk_rows):
            return None
        return T.WHITE

    T.fill_table(tbl, headers, rows, size=15,
                 align=[PP_ALIGN.CENTER, PP_ALIGN.LEFT] + [PP_ALIGN.RIGHT] * 4)
    for i, r in enumerate(A.risk_rows, 1):
        c = tbl.cell(i, 0)
        c.fill.solid()
        c.fill.fore_color.rgb = T.hex_rgb(DS.SCORE_COLORS[r["score"]])
        for p in c.text_frame.paragraphs:
            for run in p.runs:
                run.font.color.rgb = T.WHITE
                run.font.bold = True
    if len(rows) > len(A.risk_rows):
        last = tbl.cell(len(rows), 0)
        last.fill.solid()
        last.fill.fore_color.rgb = T.NAVY
        for p in last.text_frame.paragraphs:
            for run in p.runs:
                run.font.color.rgb = T.WHITE
                run.font.bold = True

    rx = X + 12.4 + 0.5
    rw = T.SLIDE_W - rx - X
    if A.charts.get("risk_bands"):
        T.image(slide, A.charts["risk_bands"], rx, y + 0.1, rw, 1.7)
    read = _risk_read(A)
    T.band_label(slide, rx, y + 2.05, rw, "  WHAT IT MEANS")
    T.bullets(slide, rx + 0.05, y + 2.67, rw - 0.1, T.CONTENT_BOTTOM - y - 2.75, read, 15)
    return slide


def _risk_read(A):
    out = []
    scored = [r for r in A.risk_rows if r["score"] in (1, 2, 3, 4, 5)]
    if not scored:
        return ["No scored accounts to interpret."]
    worst = max(scored, key=lambda r: r["co_rate"])
    best = min(scored, key=lambda r: r["co_rate"])
    # Only quote a ratio when the denominator is big enough to make one
    # meaningful; near-zero rates otherwise produce nonsense like '1x'.
    if best["co_rate"] >= 0.05 and worst["co_rate"] > best["co_rate"]:
        out.append(f"Score {worst['label']} carries the highest charge-off rate at "
                   f"{pct(worst['co_rate'], 2)} — "
                   f"{worst['co_rate'] / best['co_rate']:.1f}x score {best['label']} "
                   f"at {pct(best['co_rate'], 2)}.")
    elif worst["co_rate"] >= 0.005:
        out.append(f"Score {worst['label']} carries the highest charge-off rate at "
                   f"{pct(worst['co_rate'], 2)}; score {best['label']} is the lowest at "
                   f"{pct(best['co_rate'], 2)}.")
    else:
        out.append(f"Charge-off experience is negligible across every scored band "
                   f"(highest {pct(worst['co_rate'], 2)} at score {worst['label']}), so "
                   f"the risk tiers below rest on very few realised losses.")
    ordered = sorted(scored, key=lambda r: r["score"])
    rates = [r["co_rate"] for r in ordered]
    monotone = all(a >= b for a, b in zip(rates, rates[1:]))
    out.append("Charge-off rate falls monotonically as the score rises, so the score is "
               "ordering risk correctly across every band."
               if monotone else
               "Charge-off rate does not fall monotonically across every band — the "
               "inversions are worth reviewing against the rule logic.")
    lower = A.risk_bands.get("Lower risk (3–5)", {})
    higher = A.risk_bands.get("Higher risk (1–2)", {})
    if lower and higher:
        out.append(f"Scores 3–5 hold {pct(lower.get('pct', 0))} of the portfolio at a "
                   f"{pct(lower.get('co_rate', 0), 2)} charge-off rate; scores 1–2 hold "
                   f"{pct(higher.get('pct', 0))} at {pct(higher.get('co_rate', 0), 2)}.")
    if A.outcome_totals.get("co_amt_365"):
        out.append(f"{money(A.outcome_totals['co_amt_365'])} charged off across the scope "
                   f"in the trailing 365 days.")
    return out


def _variables(dk, A, *, section):
    slide = dk.content("Deposit Score — variables used",
                       "Which data column each regression input maps to, and whether it is "
                       "populated in this export",
                       section=section)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, W, "  REGRESSION INPUTS")
    headers = ["Variable", "Source column", "Populated?", "Note"]
    rows = [[name, src, "Yes" if pop else "No", note or "—"]
            for name, src, pop, note in A.rule_vars]
    tbl = dk.table(slide, X, y + 0.50, W, [4.2, 5.2, 2.0, 7.7], len(rows) + 1,
                   row_h=min(0.46, max(0.30, (T.CONTENT_BOTTOM - y - 1.0) / max(1, len(rows)))))
    T.fill_table(tbl, headers, rows, size=14,
                 align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.LEFT])
    for i, (_, _, pop, _) in enumerate(A.rule_vars, 1):
        for p in tbl.cell(i, 2).text_frame.paragraphs:
            for run in p.runs:
                run.font.color.rgb = T.GREEN if pop else T.RED
                run.font.bold = True
    return slide


def _alignment(dk, A, b, *, section):
    slide = dk.content(f"Score alignment — {b.name}",
                       f"Score mix and mean score across bands of {b.name.lower()}  ·  "
                       f"source: {b.source_desc}",
                       section=section)
    y = T.CONTENT_TOP + 0.05
    h = T.CONTENT_BOTTOM - y
    if b.chart:
        T.image(slide, b.chart, X, y, 13.0, h)
    T.band_label(slide, X + 13.3, y, 5.85, "  READ")
    T.bullets(slide, X + 13.35, y + 0.62, 5.75, h - 0.70, _alignment_read(b), 15)
    if b.note:
        T.footnote(slide, b.note)
    return slide


def _alignment_read(b):
    labels = [l for l in b.band_labels if l in b.mean_score]
    means = [b.mean_score[l] for l in labels]
    valid = [(l, m) for l, m in zip(labels, means) if m == m]     # drop NaN
    if len(valid) < 2:
        return [f"Too few populated bands of {b.name.lower()} to read a trend."]
    first_l, first_m = valid[0]
    last_l, last_m = valid[-1]
    delta = last_m - first_m
    out = [f"Mean score moves from {first_m:.2f} at '{first_l}' to {last_m:.2f} at "
           f"'{last_l}' — a {abs(delta):.2f}-point "
           f"{'increase' if delta > 0 else 'decrease'}."]
    if abs(delta) < 0.15:
        out.append(f"That is effectively flat, so {b.name.lower()} is not differentiating "
                   f"the score much in this portfolio — worth checking whether the rule "
                   f"thresholds match where the accounts actually sit.")
    else:
        direction = "higher" if delta > 0 else "lower"
        out.append(f"The score moves {direction} as {b.name.lower()} rises, which is the "
                   f"direction the matrix intends.")
    biggest = max(zip(labels, [sum(b.comp[l].get(k, 0) for k in (1, 2, 3, 4, 5, 0))
                               for l in labels]), key=lambda t: t[1])
    out.append(f"'{biggest[0]}' is the largest band at {count(biggest[1])} accounts.")
    return out


def _outcomes(dk, A, *, section):
    slide = dk.content("Closure & charge-off by Deposit Score",
                       "Validating that adverse outcomes concentrate in the low scores",
                       section=section)
    y = T.CONTENT_TOP + 0.05
    h = T.CONTENT_BOTTOM - y
    if A.charts.get("chargeoff_by_score"):
        T.image(slide, A.charts["chargeoff_by_score"], X, y, 8.4, h * 0.92)
    if A.charts.get("closure_by_score"):
        T.image(slide, A.charts["closure_by_score"], X + 8.7, y, 8.4, h * 0.92)
    T.footnote(slide,
               "Charge-off rate is the cleaner validation signal: closed and charged-off "
               "accounts are generally not re-scored, so the 'Not scored' bucket is "
               "dominated by accounts that were already closed.")
    return slide


def _rdi(dk, A, *, section):
    r = A.rdi
    slide = dk.content("Returned Deposit Items (RDI) — risk cohort",
                       "Accounts with returned-deposit activity, and how the score treats them",
                       section=section)
    cards = [
        (count(r["n"]), "Accounts with RDI", f"{pct(r['pct'])} of the portfolio"),
        (money(r["amt_sum"]), "RDI dollars", f"median {money(r['amt_med'])} per account"),
        (f"{r['mean_with']:.2f}", "Mean score, with RDI",
         f"vs {r['mean_without']:.2f} without"),
        (pct(r["co_with"], 2), "Charge-off rate, with RDI",
         f"vs {pct(r['co_without'], 2)} without"),
    ]
    T.kpi_cards(slide, T.MARGIN_L, T.CONTENT_TOP + 0.05, T.CONTENT_W, 2.25, cards)
    y = T.CONTENT_TOP + 2.55
    h = T.CONTENT_BOTTOM - y
    if A.charts.get("rdi_scoremix"):
        T.image(slide, A.charts["rdi_scoremix"], X, y, 9.2, h)
    T.band_label(slide, X + 9.6, y, W - 9.6, "  READ")
    items = [f"The highest score awarded to any account with RDI activity is "
             f"{r['max_score']} — the matrix caps the score once returned deposits appear."]
    if r["by_type"]:
        parts = ", ".join(f"{k}: {count(v)}" for k, v in
                          sorted(r["by_type"].items(), key=lambda kv: -kv[1]))
        items.append(f"Cohort by account type — {parts}.")
    items.append(f"{count(r['items_sum'])} returned deposit items across the cohort.")
    T.bullets(slide, X + 9.65, y + 0.62, W - 9.7, h - 0.70, items, 15)
    return slide
