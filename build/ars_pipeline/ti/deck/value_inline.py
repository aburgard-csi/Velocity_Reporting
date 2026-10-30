# Ported from ARS v5 02-Scripts/ars/deck/build.py at a491b5c (James Gilmore); logic unchanged.
"""
value_inline.py — the six value slides v5 draws inline in `ars/deck/build.py`: What a card and an
opt-in earn, The value ladder, Value per account by branch, What a responder is worth, Where cards do
not follow volume, and Where branches diverge.

Each is lifted out of the build function as a builder with the house signature `(h, m)`, returning
None when drawn or the reason when declined (v5's `skip(...)` reason), so the Value chapter calls it
like any ported builder. The bodies are v5's line for line; only the closures they called (`slide`,
`chart`, `_rail`, `_chart_left`, `_picture`, `_kpi`, `_table`, `_text`, `_kicker`, `n`) are reached
through the helper bundle `h` or restated here.

Sheila's 1798 slide review (2026-10-30) changed three things v5 did not have:
  * footnotes are FOOTNOTE_PT (10.5pt), never v5's 9.5pt;
  * the card slide and the value ladder carry at most about 60 words; what was cut (the cardless and
    not-opted-in counts, the per-card and per-opt-in tiles) goes in the speaker notes, after the
    Source line, so the presenter still has it;
  * group Q: "Where cards do not follow volume" also carries the branch value spread and the branch
    with the widest card / Reg E divergence on its rail, so "Value per account by branch" and "Where
    branches diverge" can be tossed in `ti/slides.json` without losing their findings.
"""
from __future__ import annotations

from . import charts, headlines, labels
from .helpers import HEAD_FONT
from .labels import money as _money

FOOTNOTE_PT = 10.5


def _note_more(slide, *lines):
    """Add detail lines to a slide's speaker notes, after the Source line the frame wrote."""
    tf = slide.notes_slide.notes_text_frame
    extra = [ln for ln in lines if ln]
    if extra:
        tf.text = "\n".join([tf.text, *extra])


def _n(m, key, default=0):
    """v5's `n`: a figure, or the default when it is missing or empty."""
    return m.get(key, default) or default


def card_and_optin(h, m) -> str | None:
    """What a debit card and a Reg E opt-in earn, and the conversion math (v5 build.py)."""
    if m.get("value_debit_delta") is None:
        return "value_debit_delta"
    MARGIN_L, CONTENT_W, ORANGE, GREY = h["MARGIN_L"], h["CONTENT_W"], h["ORANGE"], h["GREY"]
    _text = h["text"]
    s, top = h["slide"](headlines.value(m), "What a card and an opt-in earn")
    # 1798's slide ran 101 words (Sheila's slide review, 2026-10-30): the KPI notes repeated the
    # conversion math's pool, so the cards carry label and value and the counts go to the notes
    h["kpi"](s, MARGIN_L + 0.1, top + 0.1, 5.9, "Debit card",
             _money(m.get("value_debit_delta")))
    h["kpi"](s, 6.95, top + 0.1, 5.9, "Reg E opt-in",
             _money(m.get("value_rege_delta")), accent=ORANGE)
    _note_more(s,
               f"Value of a debit card: {_money(m.get('value_debit_delta'))} per account per year; "
               f"{_n(m, 'value_debit_n_without'):,} eligible accounts without one.",
               f"Value of a Reg E opt-in: {_money(m.get('value_rege_delta'))} per account per year; "
               f"{_n(m, 'value_rege_n_without'):,} not opted in."
               if m.get("value_rege_delta") is not None else None,
               f"Converting the cardless at the current new-account rate is worth "
               f"{_money(m['value_debit_pot_l12m'])} a year."
               if m.get("value_debit_pot_l12m") else None)
    # James (issue #41): the conversion math, spelled out as an
    # equation -- pool x conversion = new cards, priced at the value
    # per card; the opt-in follow-on underneath
    without = _n(m, "value_debit_n_without")
    conv = _n(m, "take_new_pct")
    if without and conv and m.get("value_debit_delta") is not None:
        new_cards = int(round(without * conv / 100))
        annual = int(round(new_cards * m["value_debit_delta"]))
        cm_top = top + 2.15
        _text(s, MARGIN_L + 0.1, cm_top, 4.0, 0.26, "CONVERSION MATH", size=11,
              bold=True, color=ORANGE, font=HEAD_FONT)
        cells = [(f"{without:,}", "accounts with no card"),
                 (f"{conv:.0f}%", "new-account take rate"),
                 (f"{_money(annual)}", f"a year from {new_cards:,} new cards")]
        cw = 3.5
        xs = [0.92, 5.09, 9.26]
        for (value, label), x in zip(cells, xs):
            _text(s, x, cm_top + 0.55, cw, 0.55, value, size=30,
                  bold=True, font=HEAD_FONT)
            _text(s, x, cm_top + 1.15, cw, 0.5, label, size=11,
                  color=GREY)
        _text(s, 4.42, cm_top + 0.58, 0.5, 0.5, "×", size=26,
              bold=True, color=ORANGE, font=HEAD_FONT)
        _text(s, 8.59, cm_top + 0.58, 0.5, 0.5, "=", size=26,
              bold=True, color=ORANGE, font=HEAD_FONT)
        if m.get("value_rege_delta") is not None and _n(m, "rege_pct"):
            add = int(round(new_cards * _n(m, "rege_pct") / 100
                            * m["value_rege_delta"]))
            _text(s, MARGIN_L + 0.3, cm_top + 1.95, CONTENT_W - 0.3, 0.3,
                  f"{_money(add)} more a year if {_n(m, 'rege_pct')}% also opt in.",
                  size=12, bold=True)
    h["kicker"](s)
    return None


def value_ladder(h, m) -> str | None:
    """The value ladder: tenure on the way up, potential at the top (v5 build.py)."""
    va = m.get("value_by_account_age") or []
    if len(va) < 2:
        return "value_by_account_age"
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h["CONTENT_W"]
    s, top = h["slide"](headlines.value_ladder(m), "The value ladder")
    # 1798's ladder ran 94 words (Sheila's slide review, 2026-10-30). The biggest step is the
    # headline and the per-card / per-opt-in values are the card slide's, so the rail keeps the two
    # potentials only; the dropped tiles' figures go to the notes.
    items, cut = [], []
    step = m.get("value_age_biggest_step")
    if step:
        cut.append(f"Biggest step: {_money(step['step'])}, {step['from']} to {step['to']}.")
    per = []
    if m.get("value_per_card") is not None:
        per.append(("Per card", _money(m["value_per_card"]), "per account/yr"))
    if m.get("value_per_optin") is not None:
        per.append(("Per opt-in", _money(m["value_per_optin"]), "per account/yr"))
    if m.get("value_debit_pot_hist") is not None and m.get("value_debit_pot_full") is not None:
        items.append(("Cards potential", _money(m["value_debit_pot_hist"]),
                      f"{_money(m['value_debit_pot_full'])} at full"))
    if m.get("value_rege_pot_elected") is not None and m.get("value_rege_pot_full") is not None:
        items.append(("Reg E potential",
                      _money(m["value_rege_pot_elected"]),
                      f"{_money(m['value_rege_pot_full'])} at full"))
    if items:
        cut += [f"{label}: {value} {note}." for label, value, note in per]
    else:
        items = per          # no potentials: the per-card values are what the rail has
    _note_more(s, *cut)
    right = h["rail"](s, items, top=top) if items else h["RIGHT_EDGE"]
    path = h["chart"]("value_ladder", charts.grouped_bars,
                      [str(r["group"]) for r in va],
                      [r["rev_with"] for r in va],
                      [r["rev_without"] for r in va],
                      "with card", "without card", fmt="${:,.0f}")
    if path:
        h["chart_left"](s, path, top, right)
    h["text"](s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Base: eligible accounts in each tenure band; the tiles price "
              "closing the card and opt-in gaps.", size=FOOTNOTE_PT, color=h["GREY"])
    h["kicker"](s)
    return None


def branch_value(h, m) -> str | None:
    """Value per account, branch by branch (v5 build.py)."""
    vb = m.get("value_by_branch") or []
    if len(vb) < 2:
        return "value_by_branch"
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h["CONTENT_W"]
    s, top = h["slide"](headlines.branch_value(m), "Value per account by branch")
    items = []
    vbest, vworst = m.get("value_branch_best"), m.get("value_branch_worst")
    if vbest:
        items.append(("Top branch", _money(vbest["value_per_acct"]),
                      labels.clip(vbest["group"], 16)))
    if vworst:
        items.append(("Bottom branch", _money(vworst["value_per_acct"]),
                      labels.clip(vworst["group"], 16)))
    if m.get("value_branch_spread") is not None:
        items.append(("Spread", _money(m["value_branch_spread"]),
                      "per account/yr"))
    if m.get("value_branch_penetration_share") is not None:
        items.append(("From cards",
                      f"{_n(m, 'value_branch_penetration_share'):.0f}%",
                      "of the spread"))
    # James (issue #41): larger chart -- full width, no rail; the
    # revenue qualified and the head count under each column
    path = h["chart"]("value_branch", charts.branch_bars,
                      [[r["group"], None, r["n"], r["value_per_acct"]]
                       for r in vb],
                      m.get("value_portfolio_per_acct") or 0, fmt="${:,.0f}",
                      top=16, show_n=True)
    if path:
        h["picture"](s, path, top=top + 0.05, max_h=6.35 - top)
    # the spread and its card share are the headline and sub; at 10.5pt the footnote keeps to one
    # line by defining the measure only
    qual = ("Value: interchange plus NSF/OD fees per eligible account a year; "
            "counts under each column are the branch's eligible accounts.")
    h["text"](s, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28, qual,
              size=FOOTNOTE_PT, color=h["GREY"])
    h["kicker"](s)
    return None


def responder_value(h, m) -> str | None:
    """What a responder is worth, group by group (v5 build.py)."""
    vr = m.get("value_by_response") or []
    if not vr:
        return "value_by_response"
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h["CONTENT_W"]
    s, top = h["slide"](headlines.responder_value(m),
                        "What a responder is worth")
    items = []
    if m.get("value_responder_premium") is not None:
        items.append(("Responder premium",
                      _money(m["value_responder_premium"]),
                      "per account/yr, carded"))
    if m.get("value_responder_premium_ic") is not None:
        items.append(("From interchange",
                      _money(m["value_responder_premium_ic"]),
                      "of the premium"))
    if m.get("value_responder_premium_nsf") is not None:
        items.append(("From NSF/OD",
                      _money(m["value_responder_premium_nsf"]),
                      "of the premium"))
    if m.get("value_carded_portfolio_per_acct") is not None:
        items.append(("Carded book",
                      _money(m["value_carded_portfolio_per_acct"]),
                      "per account/yr"))
    right = h["rail"](s, items, top=top)
    carded_by = {r["group"]: r
                 for r in (m.get("value_by_response_carded") or [])}
    rows = [["Group", "Accounts", "Card take", "Value/acct",
             "Carded only"]]
    for r in vr:
        c = carded_by.get(r["group"])
        rows.append([str(r["group"]), f"{r['n']:,}",
                     f"{r['take_rate']:.0f}%",
                     _money(r["value_per_acct"]),
                     _money(c["value_per_acct"]) if c else "-"])
    h["table"](s, rows, MARGIN_L, top + 0.1, right - MARGIN_L - 0.25,
               col_widths=[2.3, 1.5, 1.45, 1.7, 2.0], size=10.5)
    h["text"](s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Base: eligible personal accounts. Carded only holds card "
              "take at 100%, so the gap left is behaviour.",
              size=FOOTNOTE_PT, color=h["GREY"])
    h["kicker"](s)
    return None


def branch_tiles(m) -> list:
    """Group Q (Sheila's 1798 slide review, 2026-10-30): the findings of "Value per account by
    branch" and "Where branches diverge", as rail tiles for the card-gap slide, so both of those
    slides can be tossed. Each tile is shown only when its figures are there."""
    items = []
    best, worst = m.get("value_branch_best"), m.get("value_branch_worst")
    if m.get("value_branch_spread") is not None:
        who = ("per account/yr" if not (best and worst) else
               f"{labels.clip(best['group'], 10)} {_money(best['value_per_acct'])} vs "
               f"{labels.clip(worst['group'], 10)} {_money(worst['value_per_acct'])}")
        items.append(("Branch value spread", _money(m["value_branch_spread"]), who))
    share = m.get("value_branch_penetration_share")
    if share is not None:
        items.append(("Spread from card take", f"{share:.0f}%", "a process lever"))
    div = m.get("branch_divergence") or []
    if div and len(div[0]) >= 6 and div[0][5] is not None:
        name, _size, _dctr, _rege, d_gap, r_gap = div[0][:6]
        items.append(("Reg E vs the book", f"{r_gap:+.1f} pts",
                      f"{labels.clip(name, 14)}; cards {d_gap:+.1f} pts"))
    return items


def leaks(h, m) -> str | None:
    """Where cards do not follow volume (v5 build.py), with the branch value and divergence
    findings on the rail (group Q)."""
    leak_rows = m.get("dctr_leaks") or []
    if not leak_rows:
        return "dctr_leaks"
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h["CONTENT_W"]
    s, top = h["slide"](headlines.leaks(m), "Where cards do not follow volume")
    items = branch_tiles(m)
    right = h["rail"](s, items, top=top) if items else None
    path = h["chart"]("leaks", charts.leak_bars, leak_rows, unit="cards")
    if path and right:
        h["chart_left"](s, path, top + 0.05, right, max_h=6.35 - top)
    elif path:
        h["picture"](s, path, top=top + 0.05, max_h=6.35 - top)
    note = "Bars: cards short of the book rate, eligible base."
    if items:
        note += " Tiles: value per account a year; points vs the book."
    h["text"](s, MARGIN_L + 0.02, 6.44, CONTENT_W if not right else right - MARGIN_L, 0.3,
              note, size=FOOTNOTE_PT, color=h["GREY"])
    h["kicker"](s)
    return None


def divergence(h, m) -> str | None:
    """Branches strong on cards, weak on Reg E (v5 build.py)."""
    div = m.get("branch_divergence") or []
    if not div:
        return "branch_divergence"
    MARGIN_L = h["MARGIN_L"]
    s, top = h["slide"](headlines.divergence(m), "Where branches diverge")
    items = []
    if m.get("dctr_overall") is not None:
        items.append(("Book take rate", f"{_n(m, 'dctr_overall')}%", "cards"))
    if m.get("rege_pct") is not None:
        items.append(("Book opt-in", f"{_n(m, 'rege_pct')}%", "Reg E"))
    right = h["rail"](s, items, top=top)
    # paired gap bars off one zero line (James, issue #43): each
    # branch's card gap and Reg E gap vs the book, side by side
    path = h["chart"]("diverge", charts.gap_pairs,
                      [[name, size, d_gap, r_gap]
                       for name, size, dctr, rege, d_gap, r_gap in div])
    if path:
        h["chart_left"](s, path, top, right)
    h["text"](s, MARGIN_L + 0.02, 6.5, 9.4, 0.28,
              "Points vs the book rate, on each branch's eligible base; selling "
              "the card but missing the opt-in is a process gap.",
              size=FOOTNOTE_PT, color=h["GREY"])
    h["kicker"](s)
    return None
