#!/usr/bin/env python3
"""status_slides.py — "MRPC Program to Date" and "MRPC Current Program Status", from the weekly.

Aaron, 2026-10-02: "what's the gap between Active Enrollments and Total Cards billed? Create
one slide with Program to Date Totals and another with current program status." Then: "go
ahead with the two new MRPC slides using the weekly."

They replace Card Portfolio and Key Metrics, whose figures did not reconcile: Key Metrics'
"Active Enrollments" (VIP `key_metrics.active_enrollments`, 4,396 for Marine FCU 1539) had no
date or source and had been carried forward; Card Portfolio's "Total Cards Billed" (VIP "Total
Fees by Fee Charged", 6,729) counts accounts per fee amount over an unknown window, and is more
than double every current active count; and its "Tier Mix (Program to Date)" was that same
billing breakdown, not a program-to-date figure. The MRPC Enrollment Summary weekly carries
both sides of the program in figures that agree with each other — see mrpc_weekly.py.

  Program to Date        cardholders and accounts ever enrolled, the take rate over open
                         accounts with a debit card, the Platinum / Gold / Business mix, and
                         who enrolled (primary / joint, new / existing account, employees)
  Current Program Status active accounts and cardholders now, enrollments over the last 12
                         COMPLETE months, every enrolled cardholder by status (active by days
                         since enrollment, or inactive), and the share still active

The VIP figures these slides no longer show are not dropped silently: the Current Program
Status notes carry them with the reason. A client with no tab in the weekly gets both slides
with a sentence saying so, never zeros.

Public entry points
-------------------
    figures(w)                                -> dict   (pure)
    fill_program_to_date(slide, f, w, assets, client)
    fill_current_status(slide, f, w, assets, client, vip)
"""
import datetime
import os

from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from shapes import textbox, shadow, fit_picture
from brand import HEAD, BODY, NAVY_RGB as NAVY, ORANGE_RGB as ORANGE, WHITE_RGB as WHITE, TICK_RGB

import month_complete
import mrpc_charts_gen as CH

GREY = TICK_RGB          # was a second text grey one step from TICK (2026-11-02)
WINDOW = 12           # complete months behind "enrolled in the last 12 months"
TILE_T, TILE_H = 1.62, 1.45
TILE_X = (0.7, 4.83, 8.96)
TILE_W = 3.97
LOWER_T, LOWER_H = 3.4, 3.2
CHART_BOX = (0.5, LOWER_T, 6.3, LOWER_H)
CARD_BOX = (7.2, LOWER_T, 5.6, LOWER_H)
_MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _pct(n, d):
    return n / d * 100 if d else None


def _mon_yy(ym):
    y, m = ym.split("-")
    return f"{_MON[int(m) - 1]}'{y[2:]}"


def _mon_year(ym):
    y, m = ym.split("-")
    return f"{_MON[int(m) - 1]} {y}"


def generated_date(w):
    return month_complete.report_date(w.get("report_generated") or "")


def _as_of(f):
    """'Sep 27, 2026' — or the weekly's own stamp text when it cannot be read as a date."""
    d = f.get("generated")
    return f"{d:%b} {d.day}, {d.year}" if d else "the latest weekly"


def _last_complete(as_of):
    """'YYYY-MM' of the month before `as_of`'s month — the last one that had ended."""
    if as_of is None:
        return None
    y, m = (as_of.year, as_of.month - 1) if as_of.month > 1 else (as_of.year - 1, 12)
    return f"{y}-{m:02d}"


def _months_back(end, n):
    """The n 'YYYY-MM' months ending at `end`, oldest first."""
    y, m = int(end[:4]), int(end[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def figures(w):
    """Everything the two slides state, from one client's weekly tab. Pure."""
    t = w["totals"]
    tiers = [(n, t.get(k) or 0) for n, k in (("Platinum", "platinum"), ("Gold", "gold"),
                                               ("Business", "business"))]
    tiers = [(n, v) for n, v in tiers if v]
    cardholders = w.get("all_cardholders")
    buckets = w.get("cardholders_active_buckets") or {}
    # Twelve CALENDAR months ending at the last complete one. The weekly lists only months
    # with an enrollment, so its last twelve rows can span more than a year (Capital Bank
    # 1502: Jul'25-Aug'26); a month it does not list enrolled no one.
    months = w.get("monthly") or []
    gen0 = generated_date(w)
    end = _last_complete(gen0) or (months[-1]["month"] if months else None)
    window = _months_back(end, WINDOW) if end else []
    last = [r for r in months if r["month"] in window]
    enrolled_12 = (sum((r["platinum"] + r["gold"] + r["business"]) for r in last)
                   if months else None)
    take = w.get("new_account_take") or {}
    cur = take.get("cur_label")
    cur_ym = None
    if isinstance(cur, datetime.datetime):
        cur_ym = f"{cur.year}-{cur.month:02d}"
    elif isinstance(take.get("cur_label"), str) and take["cur_label"][:3].title() in _MON:
        try:
            mon, yr = take["cur_label"].split()[:2]
            cur_ym = f"{yr}-{_MON.index(mon[:3].title()) + 1:02d}"
        except ValueError:
            cur_ym = None
    gen = generated_date(w)
    # The month's new-account take rate is a latest-month figure: shown only when that month
    # had ended when the weekly was generated (CLAUDE.md, complete months only).
    cur_ok = bool(cur_ym and gen and month_complete.month_ended(cur_ym, gen))
    active_ch = w.get("active_cardholders")
    return {
        "generated": gen,
        "cardholders": cardholders,
        "accounts": w.get("all_mrpc_accounts"),
        "open_with_debit": w.get("open_with_debit"),
        "take_rate_all": (w["take_rate_all"] * 100) if w.get("take_rate_all") is not None else None,
        "tiers": tiers,
        "primary": t.get("primary"), "joint": t.get("joint"),
        "new": t.get("new"), "existing": t.get("existing"),
        "employees": t.get("employees"),
        "ptd_opened": take.get("ptd_opened"), "ptd_enrolled": take.get("ptd_enrolled"),
        "active_accounts": w.get("active_mrpc_accounts"),
        "active_cardholders": active_ch,
        "take_rate_active": (w["take_rate_active"] * 100) if w.get("take_rate_active") is not None else None,
        "still_active_pct": _pct(active_ch, cardholders) if active_ch is not None else None,
        # Past the 90-day trial: the active cardholders enrolled more than 90 days ago. This
        # is the count VIP's Active Enrollments chart was settled on as (2026-07-25: "VIP
        # already applies the past-90-day-trial filter"), now read from the weekly's buckets.
        "past_trial": ((buckets.get("91-180") or 0) + (buckets.get("180+") or 0)
                       if buckets and buckets.get("180+") is not None else None),
        "buckets": [("Active, 1–90 days", buckets.get("1-90")),
                    ("Active, 91–180 days", buckets.get("91-180")),
                    ("Active, over 180 days", buckets.get("180+")),
                    ("Inactive", buckets.get("inactive"))] if buckets else [],
        "enrolled_12": enrolled_12,
        "window": (window[0], window[-1]) if window and months else None,
        "window_n": len(window),
        "cur_month": cur_ym if cur_ok else None,
        "cur_opened": take.get("cur_opened") if cur_ok else None,
        "cur_enrolled": take.get("cur_enrolled") if cur_ok else None,
    }


# ------------------------------------------------------------------ drawing
def clear(slide):
    """Remove every shape but the title, the date pill, the slide number and the logo."""
    keep = []
    for sh in slide.shapes:
        top = sh.top / 914400 if sh.top is not None else None
        left = sh.left / 914400 if sh.left is not None else None
        if top is None:
            continue
        if sh.has_text_frame and top < 0.5 and left < 1.0:
            keep.append(sh)                                   # title
        elif sh.shape_type == 1 and top < 0.6 and left > 10.0:
            keep.append(sh)                                   # date pill
        elif top > 6.9 and left < 1.0:
            keep.append(sh)                                   # slide number
        elif sh.shape_type == 13 and top > 6.6 and left > 11.0:
            keep.append(sh)                                   # CSI | Velocity logo
    for sh in list(slide.shapes):
        if sh not in keep:
            sh._element.getparent().remove(sh._element)


def set_title(slide, text):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.top is not None and sh.top / 914400 < 0.5 \
                and sh.left / 914400 < 1.0:
            runs = [r for p in sh.text_frame.paragraphs for r in p.runs]
            if runs:
                runs[0].text = text
                for r in runs[1:]:
                    r.text = ""
            return


def _selection(slide, text):
    textbox(slide, 0.5, 1.06, 12.3, 0.42, text, 14, GREY, False, PP_ALIGN.LEFT, BODY,
            MSO_ANCHOR.TOP)


def _tiles(slide, items):
    """Three navy tiles: a 36pt figure over a 16pt label (the shared tile's 12pt label is
    the size Aaron has been asking to grow)."""
    for x, (value, label) in zip(TILE_X, items):
        sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(TILE_T),
                                    Inches(TILE_W), Inches(TILE_H))
        sp.fill.solid(); sp.fill.fore_color.rgb = NAVY; sp.line.fill.background()
        shadow(sp)
        textbox(slide, x + 0.05, TILE_T + 0.16, TILE_W - 0.1, 0.72, value, 36, WHITE, True,
                PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
        textbox(slide, x + 0.05, TILE_T + 0.9, TILE_W - 0.1, 0.42, label, 16, WHITE, False,
                PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP)


def _card(slide, head, big, lines):
    """The navy callout at lower right: an orange heading, a big figure, then lines."""
    L, T, W, H = CARD_BOX
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(L), Inches(T),
                                Inches(W), Inches(H))
    sp.fill.solid(); sp.fill.fore_color.rgb = NAVY; sp.line.fill.background()
    try:
        sp.adjustments[0] = 0.06
    except Exception:
        pass
    shadow(sp)
    textbox(slide, L + 0.3, T + 0.18, W - 0.6, 0.42, head, 16, ORANGE, True, PP_ALIGN.LEFT,
            HEAD, MSO_ANCHOR.TOP)
    y = T + 0.62
    if big:
        textbox(slide, L + 0.3, y, W - 0.6, 0.75, big, 40, WHITE, True, PP_ALIGN.LEFT, HEAD,
                MSO_ANCHOR.TOP)
        y += 0.85
    box = slide.shapes.add_textbox(Inches(L + 0.3), Inches(y), Inches(W - 0.6),
                                   Inches(T + H - y - 0.15))
    tf = box.text_frame; tf.word_wrap = True
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        r = p.add_run(); r.text = ln
        r.font.size = Pt(16); r.font.name = BODY; r.font.color.rgb = WHITE


def _missing(slide, w_name, client):
    textbox(slide, 0.5, 2.2, 12.3, 1.2,
            f"{client} has no tab in the MRPC Enrollment Summary weekly"
            f"{f' ({w_name})' if w_name else ''}, so these figures are not shown. "
            "They return when the weekly carries the client.",
            18, NAVY, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)


def _source(w):
    return (f"Source: MRPC Enrollment Summary weekly {w['file']}, tab '{w['tab']}', "
            f"Report Generated {w['report_generated']}.")


def fill_program_to_date(slide, f, w, assets, client):
    """Returns the notes text."""
    clear(slide)
    set_title(slide, "MRPC Program to Date")
    if f is None:
        _missing(slide, None, client)
        return ("Source: MRPC Enrollment Summary weekly — no tab for this client, so the "
                "program-to-date figures are not shown.")
    _selection(slide, f"Every cardholder and account enrolled since the program began, from the "
                      f"MRPC Enrollment Summary of {_as_of(f)}.")
    _tiles(slide, [
        (f"{f['cardholders']:,}", "Cardholders enrolled"),
        (f"{f['accounts']:,}", "Accounts enrolled"),
        (f"{f['take_rate_all']:.1f}%" if f["take_rate_all"] is not None else "—",
         "Of open debit accounts"),
    ])
    names = [n for n, _v in f["tiers"]]
    vals = [v for _n, v in f["tiers"]]
    png = os.path.join(assets, "mrpc_tiers_ptd.png")
    CH.chart_tier_donut(names, vals, f"{sum(vals):,}", "cardholders", png, CH.DIMS["tiers"])
    fit_picture(slide, png, *CHART_BOX)
    ch = f["cardholders"] or 1
    lines = [f"Primary {f['primary']:,}  ·  Joint {f['joint']:,}",
             f"New accounts {f['new']:,}  ·  Existing {f['existing']:,}",
             f"Employees {f['employees']:,} ({f['employees'] / ch * 100:.1f}%)"]
    if f["ptd_opened"]:
        lines.append(f"{f['ptd_enrolled']:,} of {f['ptd_opened']:,} new accounts opened "
                     f"enrolled ({f['ptd_enrolled'] / f['ptd_opened'] * 100:.1f}%).")
    _card(slide, "Who enrolled", None, lines)
    return (_source(w) + " Selection: program to date. "
            f"All MRPC primary and joint cardholders {f['cardholders']:,}; all MRPC accounts "
            f"{f['accounts']:,}; take rate = accounts / open accounts with a debit card "
            f"({f['accounts']:,} / {f['open_with_debit']:,}) = {f['take_rate_all']:.1f}%. "
            "Tier mix (TOTAL row): " + ", ".join(f"{n} {v:,}" for n, v in f["tiers"]) + ". "
            f"Primary {f['primary']:,} / joint {f['joint']:,}; new {f['new']:,} / existing "
            f"{f['existing']:,}; employees {f['employees']:,} — each pair sums to the "
            "cardholders enrolled. New-account take rate program to date: "
            f"{f['ptd_enrolled']:,} enrolled of {f['ptd_opened']:,} opened. "
            "This slide replaced Card Portfolio on 2026-10-02: its tier mix was VIP's card "
            "billing breakdown, not a program-to-date figure.")


def fill_current_status(slide, f, w, assets, client, vip):
    """Returns the notes text. `vip` is the client's VIP sheet, for the figures no longer shown."""
    clear(slide)
    set_title(slide, "MRPC Current Program Status")
    kept = _vip_not_shown(vip)
    if f is None:
        _missing(slide, None, client)
        return ("Source: MRPC Enrollment Summary weekly — no tab for this client, so the "
                "current-status figures are not shown. " + kept)
    _selection(slide, f"Active accounts and cardholders as of the MRPC Enrollment Summary of "
                      f"{_as_of(f)}.")
    win = (f"{_mon_yy(f['window'][0])}–{_mon_yy(f['window'][1])}" if f["window"] else None)
    _tiles(slide, [
        (f"{f['active_accounts']:,}", "Active accounts"),
        (f"{f['active_cardholders']:,}", "Active cardholders"),
        (f"{f['enrolled_12']:,}" if f["enrolled_12"] is not None else "—",
         f"Enrolled, {win}" if win else "Enrolled, last 12 months"),
    ])
    labels = [n for n, v in f["buckets"] if v is not None]
    vals = [v for _n, v in f["buckets"] if v is not None]
    png = os.path.join(assets, "mrpc_status_now.png")
    if vals:
        CH.chart_status_bars(labels, vals, png, CH.DIMS["status"])
        fit_picture(slide, png, *CHART_BOX)
    lines = [f"{f['active_cardholders']:,} of the {f['cardholders']:,} cardholders enrolled to "
             f"date are active."]
    if f["past_trial"] is not None:
        lines.append(f"{f['past_trial']:,} of them are past the 90-day trial period.")
    if f["cur_month"]:
        lines.append(f"In {_mon_year(f['cur_month'])}, {f['cur_enrolled']:,} of "
                     f"{f['cur_opened']:,} new accounts enrolled "
                     f"({f['cur_enrolled'] / f['cur_opened'] * 100:.1f}%).")
    big = f"{f['still_active_pct']:.0f}%" if f["still_active_pct"] is not None else "—"
    _card(slide, "Still active", big, lines)
    note = (_source(w) + " Selection: status as of the report date. "
            f"Active/Signed MRPC accounts {f['active_accounts']:,}; active primary and joint "
            f"cardholders {f['active_cardholders']:,} of {f['cardholders']:,} enrolled "
            f"({f['still_active_pct']:.1f}%). Cardholders by status (TOTAL ACCOUNTHOLDERS row): "
            + "; ".join(f"{n} {v:,}" for n, v in f["buckets"] if v is not None) + ". "
            + (f"Past the 90-day trial = 91–180 days + over 180 days = {f['past_trial']:,} "
               "(the definition VIP's Active Enrollments was settled on, 2026-07-25). "
               if f["past_trial"] is not None else "")
            + f"Enrolled in the last {f['window_n']} complete months"
            + (f" ({_mon_year(f['window'][0])} – {_mon_year(f['window'][1])})" if f["window"] else "")
            + f": {f['enrolled_12']:,} cardholders (tiers summed by month; a month not ended "
              "at the report date is left out). ")
    bvals = [v for _n, v in f["buckets"] if v is not None]
    if bvals:
        act, alls = sum(bvals[:-1]), sum(bvals)
        if act != f["active_cardholders"] or alls != f["cardholders"]:
            note += (f"The status rows sum to {act:,} active and {alls:,} in all, against the "
                     f"weekly's own totals of {f['active_cardholders']:,} and {f['cardholders']:,}; "
                     "the chart's shares are of the rows' sum. ")
    if f["cur_month"]:
        note += (f"New-account take rate {_mon_year(f['cur_month'])}: {f['cur_enrolled']:,} "
                 f"enrolled of {f['cur_opened']:,} opened. ")
    return note + kept


def _vip_not_shown(vip):
    """The VIP figures Card Portfolio and Key Metrics showed, kept in the notes with the reason."""
    if not vip:
        return ""
    cb, km = vip.get("card_billing") or {}, vip.get("key_metrics") or {}
    parts = []
    if km.get("active_enrollments") is not None:
        parts.append(f"VIP key_metrics.active_enrollments {km['active_enrollments']:,}")
    if km.get("ptd_total") is not None:
        parts.append(f"VIP enrollments program to date {km['ptd_total']:,}")
    if km.get("enrollments_trailing_12") is not None:
        parts.append(f"VIP enrollments trailing 12 {km['enrollments_trailing_12']:,}")
    if cb.get("total_accounts") is not None:
        fees = ", ".join(f"{r.get('label') or r.get('fee')}: {r.get('accounts'):,}"
                         for r in cb.get("by_fee") or [])
        parts.append(f"VIP Total Fees by Fee Charged {cb['total_accounts']:,} accounts"
                     + (f" ({fees})" if fees else "")
                     + (f", monthly billing ${cb['monthly_billing']:,.0f}"
                        if cb.get("monthly_billing") else ""))
    if not parts:
        return ""
    return ("NOT SHOWN, and why (2026-10-02): " + "; ".join(parts) + ". These came from the VIP "
            "dashboards and do not reconcile with the weekly or with each other — the active "
            "figure carries no date or source, and the fee breakdown counts accounts per fee "
            "amount over a window VIP does not state. Card Portfolio and Key Metrics showed them "
            "until this slide replaced both.")
