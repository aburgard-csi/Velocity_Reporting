#!/usr/bin/env python3
"""
excluded_accounts_slide.py — the ARS "Excluded Accounts" slide, inserted directly
after "Product Mix & ARS Eligibility".

Product Mix shows what IS eligible. This slide answers the next question: of the
OPEN accounts on file, which ones ARS never sees, and why.

Scope — open accounts only (Aaron, 2026-08-29). A closed or charged-off account
is outside ARS by definition and explains nothing; a dormant or inactive one is a
different question from "why is this OPEN account not eligible". Both are still
counted and named in the slide's source note, so the scope is stated rather than
implied, but neither is drawn as a reason.

ARS workflow only. Like product_mix_slide it refuses to build when the ODD has no
"<Mon><yy> Elig" column, so a non-ARS dump cannot produce a meaningless slide.

What the ODD actually supports
------------------------------
The `Elig` flag is set by the client's core, not by us, so this slide ATTRIBUTES
exclusions rather than restating a rule we own. Each candidate reason was tested
against the flag on real client data (1509 Texas Bay, 72,059 accounts, May26):

  * Status        — closed / charged off never carries Elig=Yes. Clean exclusion.
  * Product code  — 14 of 21 open-book product codes had ZERO eligible accounts.
                    Clean exclusion, and the largest driver inside the open book.
  * Debit card    — explains most of the remainder inside otherwise-eligible
                    products (ARS is a debit program).
  * $0 balance    — NOT an exclusion. 1,221 accounts with a $0 average balance
                    were eligible. Reported as an observation, never as a reason.
  * Not mailable  — NOT an eligibility exclusion (9 accounts client-wide, 3 of
                    them eligible). It suppresses the MAILING, a separate funnel.
  * Mail codes    — `<Mon> Mail` holds the offer strategy (NU / TH-10..TH-25), not
                    a suppression code. "Not mailed" is the absence of a value.

So the slide carries two funnels, kept apart on purpose: an ELIGIBILITY waterfall
(every OPEN account, counted once, in the first reason that applies) and a MAILING
line for eligible accounts that were not sent an offer.

A reason that is genuinely near-zero for a client is STATED in words, not drawn as
a 0% bar (CLAUDE.md: missing source data is stated, never zeroed).

Public entry point
------------------
    add_excluded_accounts_slide(prs, odd, assets_dir, after_title="Product Mix")
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# Reuse the Product Mix visual contract rather than restating it — STYLE.md is the
# single source of truth and these two slides sit side by side in the deck.
from product_mix_slide import (
    _resolve_csv, _find_header_row, _latest_elig_col, _fixacr,
    _tb, _pill, _tile, _add_table, _blank_slide, _slide_title,
    _move_before, _renumber, _sldid_of,
    NAVY, ORANGE, WHITE, GREYT, HEAD, BODY,
    _NAVY_HX, _ORANGE_HX, _GREY_HX, _TICK_HX, _MONFULL, _MIDX,
)
from rpe_env import use_font
from periods import Period
from textfit import text_width_in


def _text_w(t, pt):
    """Rendered width at the size the run will ACTUALLY render at. restyle_fonts floors
    every run at 16pt, so measuring the nominal 10.5 understates every line."""
    return text_width_in(t, pt, "Calibri", False)

# Status wording is the shared vocabulary from CLAUDE.md / oddd_optimize.classify_status.
_CLOSED_PREFIX = ("closed", "charge", "purge", "pending close")
_OPEN_PREFIX = ("open", "active")

# Clients do not agree on which status field they populate. 1509 Texas Bay fills
# `Stat Desc` and leaves `Stat Code` redundant; 1549 Wellworth fills `Stat Code`
# (O / C / X) and leaves `Stat Desc` BLANK on every non-open account. Reading
# Stat Desc alone put 11,438 closed Wellworth accounts into the dormant bucket.
# So: use Stat Desc when it carries text, else fall back to the code.
# One vocabulary, defined once. oddd_optimize.STAT_CODE_MAP is the shared classifier
# CLAUDE.md names as the single source of truth for status values.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, os.pardir, "scripts"))
from oddd_optimize import STAT_CODE_MAP

_CODE_OPEN = {k for k, v in STAT_CODE_MAP.items() if v == "Open"}
_CODE_CLOSED = {k for k, v in STAT_CODE_MAP.items()
                if v in ("Closed", "Charged Off")}


def _status_class(desc, code):
    """-> 'open' | 'closed' | 'other'. `other` is deliberately NOT assumed to mean
    dormant: an unmapped code is surfaced as a flag, never guessed (CLAUDE.md)."""
    d = (desc or "").strip().lower()
    if d:
        if d.startswith(_CLOSED_PREFIX):
            return "closed"
        if d.startswith(_OPEN_PREFIX):
            return "open"
        return "other"
    c = (code or "").strip().upper()
    if c in _CODE_CLOSED:
        return "closed"
    if c in _CODE_OPEN:
        return "open"
    return "other"


def _num(s):
    v = (s or "").replace(",", "").replace("$", "").strip()
    if v in ("", "-"):
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


def extract_exclusions(odd_source):
    """Stream the ODD and return the exclusion picture. Never hardcodes a client:
    the excluded product codes are DERIVED per client as those with no eligible
    open account."""
    try:
        import pandas as pd
    except ImportError:
        raise SystemExit("excluded_accounts_slide requires pandas")

    odd_csv = _resolve_csv(odd_source)
    hdr, header = _find_header_row(odd_csv)
    keep = [c for c in header if c and not c.startswith("Unnamed")]
    elig_col, emon, eyy = _latest_elig_col(keep)
    if elig_col is None:
        raise ValueError("ODD has no ARS eligibility column — Excluded Accounts is "
                         "ARS-only (skipping).")
    # One derivation for the snapshot label (was hand-built here, in
    # excluded_accounts_slide and in tier_movement_slides identically).
    month_label = Period(f"{emon}{eyy}").label()
    mail_col = f"{emon}{eyy} Mail"
    has_mail = mail_col in keep

    want = {"Prod Code", "Prod Desc", "Business?", "Stat Desc", "Stat Code", "Avg Bal",
            "Curr Bal", "Debit?", "Mailable?", elig_col}
    if has_mail:
        want.add(mail_col)

    def norm(s):
        return s.fillna("").astype(str).str.replace("\x00", "", regex=False).str.strip()

    # pass 1 — counts, and per product code: does ANY live account carry Elig=Yes?
    #
    # Eligibility keys on the FLAG, never on status. 324 Dormant accounts on 1509
    # carry Elig=Yes; deriving eligibility from open-status instead would have put
    # those 324 on the slide as "outside ARS" while the core calls them eligible.
    prod = defaultdict(lambda: dict(desc="", live=0, elig=0))
    status = defaultdict(int)
    tot = closed = elig_all = 0
    reader = pd.read_csv(odd_csv, skiprows=hdr, dtype=str, chunksize=100_000,
                         encoding="latin-1", on_bad_lines="skip",
                         usecols=lambda c: c.strip() in want)
    chunks = []
    for ch in reader:
        ch = ch.rename(columns=lambda c: c.strip())
        for col in want:
            if col not in ch:
                ch[col] = ""
        d = pd.DataFrame({k: norm(ch[k]) for k in want})
        cls = [_status_class(a, b) for a, b in zip(d["Stat Desc"], d["Stat Code"])]
        d["cls"] = cls
        d["isclosed"] = d["cls"].eq("closed")
        d["isopen"] = d["cls"].eq("open")
        d["label"] = [(a.strip() or (f"status code {b.strip()}" if b.strip() else "(blank)"))
                      for a, b in zip(d["Stat Desc"], d["Stat Code"])]
        d["elig"] = d[elig_col].eq("Yes")
        tot += len(d)
        closed += int(d["isclosed"].sum())
        elig_all += int(d["elig"].sum())
        live = d[~d["isclosed"]]                     # the book ARS can act on
        for s_, n in live.loc[~live["isopen"] & ~live["elig"], "label"].value_counts().items():
            status[s_] += int(n)
        for (code, desc), g in live.groupby(["Prod Code", "Prod Desc"]):
            a = prod[code]
            a["desc"] = a["desc"] or _fixacr(desc.strip())
            a["live"] += len(g)
            a["elig"] += int(g["elig"].sum())
        chunks.append(live)

    excl_codes = {c for c, a in prod.items() if a["live"] and a["elig"] == 0}

    # pass 2 — waterfall over every account the core does NOT flag eligible,
    # each counted once, in the first reason that applies.
    o = pd.concat(chunks) if chunks else pd.DataFrame(columns=list(want) + ["elig", "isopen"])
    open_n = int(o["isopen"].sum()) if len(o) else 0
    # The slide explains excluded OPEN accounts only (Aaron, 2026-08-29). A closed
    # or charged-off account is outside ARS by definition and explains nothing; a
    # dormant or inactive one is a different question from "why is this open
    # account not eligible". Both are still counted, and named in the source note
    # so the scope is stated rather than implied — they are just not reasons.
    n_status = int((~o["isopen"] & ~o["elig"]).sum()) if len(o) else 0
    # Eligible among OPEN accounts, so the tiles reconcile:
    #   open accounts = open-and-excluded + open-and-eligible.
    # The whole-book eligible count (elig_all) includes dormant accounts the core
    # still flags eligible — 147 on 1204 — and using it here left the three tiles
    # 147 apart with no way for a reader to see why.
    elig_open = int((o["isopen"] & o["elig"]).sum()) if len(o) else 0
    r0 = o[o["isopen"] & ~o["elig"]] if len(o) else o   # open and not eligible
    ie = r0
    in_excl = r0["Prod Code"].isin(excl_codes) if len(r0) else r0
    n_prod = int(in_excl.sum()) if len(r0) else 0
    rest = r0[~in_excl] if len(r0) else r0
    no_debit = rest["Debit?"].ne("Yes") if len(rest) else rest
    n_nodebit = int(no_debit.sum()) if len(rest) else 0
    rem = rest[~no_debit] if len(rest) else rest
    n_rem = len(rem)

    # observations — reported in words, never as a reason bar
    avg = o["Avg Bal"].map(_num) if len(o) else []
    zero_elig = int(((avg == 0) & o["elig"]).sum()) if len(o) else 0
    zero_inel = int(((avg == 0) & ~o["elig"]).sum()) if len(o) else 0
    nm_all = int(o["Mailable?"].eq("No").sum()) if len(o) else 0
    nm_elig = int((o["Mailable?"].eq("No") & o["elig"]).sum()) if len(o) else 0

    mailed = codes = None
    if has_mail and len(o):
        e = o[o["elig"]]
        got = e[mail_col].ne("")
        mailed = int(got.sum())
        codes = sorted(c for c in e[mail_col].unique() if c)

    # Unmapped status values are FLAGGED, never folded into a named bucket.
    # 1549 Wellworth carries 6,836 accounts under Stat Code "X" with no Stat Desc;
    # calling that "dormant" would put a guess on a client-facing slide.
    flags = [lbl for lbl, _ in status.items() if lbl.startswith("status code ")
             or lbl == "(blank)"]
    if flags:
        print("!! excluded_accounts: unmapped status value(s) %s — ask Aaron how to "
              "map these before the deck ships (CLAUDE.md: do not guess)." % ", ".join(flags))

    excl_products = sorted(
        ({"code": c, "desc": prod[c]["desc"] or "(unlabeled)", "live": prod[c]["live"]}
         for c in excl_codes), key=lambda p: -p["live"])

    return dict(
        month_label=month_label, elig_col=elig_col, mail_col=mail_col if has_mail else None,
        total=tot, closed=closed, open_total=open_n,
        elig_total=elig_all, elig_open=elig_open, excluded_total=len(ie),
        n_status_excluded=n_status,
        status_other=sorted(status.items(), key=lambda kv: -kv[1]),
        excl_products=excl_products, n_excl_codes=len(excl_codes),
        n_prod_excluded=n_prod, n_no_debit=n_nodebit, n_unexplained=n_rem,
        zero_bal_elig=zero_elig, zero_bal_inelig=zero_inel,
        not_mailable=nm_all, not_mailable_elig=nm_elig,
        mailed=mailed, mail_codes=codes, flags=flags,
    )


# ----------------------------------------------------------------------------- chart
def render_chart(data, assets_dir):
    """Horizontal reason bars for the whole book. Orange = the largest reason."""
    os.makedirs(assets_dir, exist_ok=True)
    use_font("Carlito")

    # Reasons an OPEN account is not eligible. Closed / charged-off and
    # dormant / inactive accounts are excluded from the slide's population
    # entirely (Aaron, 2026-08-29) — they are not reasons, they are a different
    # book. Their counts are stated in the source note.
    rows = []
    if data["n_prod_excluded"]:
        rows.append((f"Product not in ARS ({data['n_excl_codes']} codes)",
                     data["n_prod_excluded"]))
    if data["n_no_debit"]:
        rows.append(("No debit card", data["n_no_debit"]))
    if data["n_unexplained"]:
        rows.append(("Other account-level reason", data["n_unexplained"]))
    rows = [r for r in rows if r[1] > 0]
    rows.reverse()                      # largest ends up on top in barh

    top = max((v for _, v in rows), default=0)
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [(_ORANGE_HX if v == top else _NAVY_HX) for v in vals]

    # Height follows the bar count. A fixed 3.05in figure with two bars drew a huge
    # pair of bars over half a panel of white, and pushed the slide's footnote into
    # the table beside it (Aaron, 2026-08-28).
    fig = plt.figure(figsize=(6.0, max(1.5, 0.62 * len(rows) + 0.55)))
    ax = fig.add_axes([0.42, 0.08, 0.56, 0.86])
    y = range(len(vals))
    ax.barh(list(y), vals, color=colors, height=0.62)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=10.5, color=_TICK_HX)
    ax.set_xlim(0, (top or 1) * 1.18)
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(_GREY_HX)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    denom = data["total"] or 1
    for i, v in enumerate(vals):
        ax.text(v + top * 0.02, i, f"{v:,}  ({v/denom*100:.1f}%)", va="center",
                ha="left", fontsize=10.5, color=_NAVY_HX, fontweight="bold")
    out = os.path.join(assets_dir, "excl_reasons.png")
    fig.savefig(out, dpi=300, facecolor="white", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return out


# ----------------------------------------------------------------------------- table
def _product_rows(data, max_rows=5):
    rows = [["Excluded product", "Code", "Accounts"]]
    shown = data["excl_products"][:max_rows]
    for p in shown:
        rows.append([p["desc"], p["code"], f"{p['live']:,}"])
    rest = data["excl_products"][max_rows:]
    if rest:
        rows.append([f"All other excluded products ({len(rest)})", "—",
                     f"{sum(p['live'] for p in rest):,}"])
    rows.append(["Total — excluded products", "", f"{data['n_prod_excluded']:,}"])
    return rows, (len(rows) - 1,)


# ----------------------------------------------------------------------------- public entry
def add_excluded_accounts_slide(prs, odd_source, assets_dir,
                                after_title="Product Mix",
                                before_title="Program Overview", renumber=True):
    """Build the Excluded Accounts slide and place it directly after the Product
    Mix slide. Returns (slide, data)."""
    data = extract_exclusions(odd_source)
    chart = render_chart(data, assets_dir)

    anchor = next((s for s in prs.slides if _slide_title(s).startswith(after_title)), None)
    template = anchor or next((s for s in prs.slides
                               if _slide_title(s).startswith(before_title)), prs.slides[0])
    s = _blank_slide(prs, template)

    _tb(s, 0.5, 0.28, 9.6, 0.9, "Excluded Accounts", 26, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    _pill(s, f"{data['month_label']} Data")
    _tb(s, 0.5, 1.12, 12.3, 0.5,
        "Why OPEN accounts are outside ARS. Each account is counted once, under "
        "the first reason that applies.",
        14, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    excl_all = data["excluded_total"]
    open_n = data["open_total"]
    share = round(excl_all / open_n * 100) if open_n else 0
    tiles = [(f"{open_n:,}", "Open accounts", NAVY),
             (f"{excl_all:,}", "Open, outside ARS", ORANGE),
             (f"{share}%", "Share of open accounts", NAVY),
             (f"{data['elig_open']:,}", "ARS-eligible open accounts", NAVY)]
    for i, (v, l, f) in enumerate(tiles):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 1.28, v, l, fill=f)

    _tb(s, 0.5, 3.10, 6.1, 0.35, "Reason for Exclusion", 13.5, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    s.shapes.add_picture(chart, Inches(0.2), Inches(3.42), Inches(6.25))

    _tb(s, 6.75, 3.10, 6.1, 0.35, "Products Not Carried by ARS", 13.5, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    rows, highlight = _product_rows(data)
    _add_table(s, 6.75, 3.45, 6.05, min(0.30 * len(rows), 2.30), rows,
               [2.0, 0.6, 0.8], highlight=highlight, fs=11)

    # Observations that are NOT exclusions. Stated in words rather than drawn as a
    # 0% bar, because a bar would read as a reason the data does not support.
    notes = []
    if data["zero_bal_elig"]:
        # "carry one" left the reader to resolve what "one" referred to across a
        # dash (Aaron, 2026-09-01). Named outright, matching the sibling sentence
        # below, which already says "carry a $0 average balance".
        notes.append(f"$0 average balance is not an exclusion — {data['zero_bal_elig']:,} "
                     f"eligible accounts carry a $0 balance.")
    elif data["zero_bal_inelig"]:
        notes.append(f"{data['zero_bal_inelig']:,} excluded accounts carry a $0 average balance.")
    if data["not_mailable"]:
        notes.append(f"Address quality removes {data['not_mailable']:,} accounts from the "
                     f"mailing, not from eligibility"
                     + (f" ({data['not_mailable_elig']:,} of them are eligible)."
                        if data["not_mailable_elig"] else "."))
    else:
        notes.append("No account on file is flagged as a bad or foreign address.")
    if data["mailed"] is not None:
        notes.append(f"{data['mailed']:,} of {data['elig_total']:,} eligible accounts were "
                     f"mailed — the mail field holds the offer strategy, not a suppression code.")

    # The footnote band is 2 lines: it sits at 6.05in and the logo/page-number band
    # starts at 6.78in, so a third line overflows into it. Which notes exist varies by
    # client — 1549 has no mail column at all, 1537 has all three — so the block is
    # MEASURED and truncated to what fits rather than assumed to be short enough
    # (1537 estimated 5 lines and failed the gate). Everything lands in the speaker
    # notes regardless, so nothing is lost, only moved.
    _USABLE, _MAXLINES = 12.30 - 0.2, 2
    shown, used = [], 0
    for n in notes:
        lines = max(1, int(_text_w(n, 16) // _USABLE) + (1 if _text_w(n, 16) % _USABLE else 0))
        if used + lines > _MAXLINES:
            continue
        shown.append(n); used += lines
    _tb(s, 0.5, 6.05, 12.3, 0.62, shown, 10.5, GREYT, False,
        PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    src = (f"Source: client ODD, {data['month_label']} snapshot ({data['elig_col']}). "
           f"Population: the {data['open_total']:,} OPEN accounts on file. Outside this "
           f"slide: {data['closed']:,} closed or charged-off accounts, and "
           f"{data['n_status_excluded']:,} dormant/inactive accounts that are not "
           f"eligible — both are a different book, not a reason an open account is "
           f"excluded. "
           f"Excluded product codes derived per client as those with no eligible open "
           f"account. Reason order: status, product code, debit card. "
           + " ".join(notes))
    s.notes_slide.notes_text_frame.text = src

    logo = os.path.join(assets_dir, "logo.png")
    if os.path.exists(logo):
        s.shapes.add_picture(logo, Inches(11.28), Inches(6.78), Inches(1.70), Inches(0.54))

    # place directly AFTER the Product Mix slide
    if anchor is not None:
        src_id, tgt_id = _sldid_of(prs, s), _sldid_of(prs, anchor)
        if src_id is not None and tgt_id is not None:
            prs.slides._sldIdLst.remove(src_id)
            tgt_id.addnext(src_id)
    else:
        _move_before(prs, s, before_title)
    if renumber:
        _renumber(prs)
    return s, data
