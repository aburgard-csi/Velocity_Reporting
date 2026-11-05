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
    _move_before, _renumber, _sldid_of, _fit_picture, POP_TILE_LABEL,
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

# Status classification is `odd_rows.status_class` — one vocabulary, defined once,
# alongside the OPEN/CLOSED status sets it belongs to. It used to live here, which
# is how `product_mix_slide` came to carry a different rule and count charged-off
# accounts as open.
from odd_rows import status_class as _status_class, client_of as _client_of

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

    _cid = _client_of(odd_source)   # the client's code sheet settles unknown statuses
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
    tot = closed = 0
    reader = pd.read_csv(odd_csv, skiprows=hdr, dtype=object, chunksize=100_000,
                         encoding="latin-1", on_bad_lines="skip",
                         usecols=lambda c: c.strip() in want)
    chunks = []
    for ch in reader:
        ch = ch.rename(columns=lambda c: c.strip())
        for col in want:
            if col not in ch:
                ch[col] = ""
        d = pd.DataFrame({k: norm(ch[k]) for k in want})
        cls = [_status_class(a, b, _cid) for a, b in zip(d["Stat Desc"], d["Stat Code"])]
        d["cls"] = cls
        d["isclosed"] = d["cls"].eq("closed")
        d["isopen"] = d["cls"].eq("open")
        d["label"] = [(a.strip() or (f"status code {b.strip()}" if b.strip() else "(blank)"))
                      for a, b in zip(d["Stat Desc"], d["Stat Code"])]
        d["elig"] = d[elig_col].eq("Yes")
        tot += len(d)
        closed += int(d["isclosed"].sum())
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
    # ONE population across both slides (Aaron, 2026-10-02): every account the core
    # does not call closed. Product Mix counts its "Total Accounts - Excl. Closed"
    # the same way, through the same classifier, so the two slides state the same
    # book and this slide's pieces sum to it:
    #     accounts excl. closed = outside ARS + ARS-eligible.
    # This slide used to count the strictly-OPEN subset instead (Aaron, 2026-08-29),
    # which is defensible on its own and does not survive being read next to the
    # slide before it: 1549 showed 66,462 open here under 71,466 excl. closed there,
    # and two eligible counts two apart, bridged only by a footnote. A reader cannot
    # add up a deck whose consecutive slides count different books.
    live_n = len(o)
    open_n = int(o["isopen"].sum()) if len(o) else 0
    elig_live = int(o["elig"].sum()) if len(o) else 0
    elig_open = int((o["isopen"] & o["elig"]).sum()) if len(o) else 0
    # Eligible but NOT open — dormant or inactive accounts the core still flags
    # eligible (2 on 1549, 147 on 1204). They are inside the eligible tile now,
    # because Product Mix counts them too; the note still names them.
    elig_other = int((~o["isopen"] & o["elig"]).sum()) if len(o) else 0

    # The waterfall: every account excl. closed that the core does NOT flag
    # eligible, counted once, in the first reason that applies. Status goes FIRST —
    # an account that is not open is outside ARS whatever its product — which is
    # also what leaves the product / debit card / other bars reading exactly as they
    # did when this slide counted open accounts only.
    r0 = o[~o["elig"]] if len(o) else o                 # excl. closed, not eligible
    ie = r0
    n_status = int((~r0["isopen"]).sum()) if len(r0) else 0
    r_open = r0[r0["isopen"]] if len(r0) else r0
    in_excl = r_open["Prod Code"].isin(excl_codes) if len(r_open) else r_open
    n_prod = int(in_excl.sum()) if len(r_open) else 0
    rest = r_open[~in_excl] if len(r_open) else r_open
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
        total=tot, closed=closed, open_total=live_n, open_only=open_n,
        elig_total=elig_live, elig_open=elig_open, elig_other=elig_other,
        excluded_total=len(ie),
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

    # Reasons an account excl. closed is not eligible, including "not open" — which
    # IS a reason, and is the one the slide used to leave out by scoping it away.
    # Closed and charged-off accounts are outside the population entirely; their
    # count is stated in the source note.
    rows = []
    if data["n_status_excluded"]:
        # "Account not open" names what the bucket holds without naming a status the
        # data did not give: dormant, inactive, frozen, and any value the shared
        # classifier could not map (flagged separately, never guessed at).
        rows.append(("Account not open", data["n_status_excluded"]))
    if data["n_prod_excluded"]:
        rows.append((f"Product not in ARS ({data['n_excl_codes']} codes)",
                     data["n_prod_excluded"]))
    if data["n_no_debit"]:
        rows.append(("No debit card", data["n_no_debit"]))
    if data["n_unexplained"]:
        rows.append(("Other account-level reason", data["n_unexplained"]))
    rows = [r for r in rows if r[1] > 0]
    # Sorted, THEN reversed: "largest on top" used to rely on the reasons happening
    # to be listed in descending order, which a fourth bar need not respect.
    rows.sort(key=lambda r: -r[1])
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
    # Percentages are of the book the tiles state, not of every row in the extract.
    # Against `total` a bar read 17.5% under a tile saying 43% of the same accounts.
    denom = data["open_total"] or 1
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
    if len(rest) == 1:
        # Same rule as the Reg E branch table: a rollup of one names it.
        rows.append([rest[0]["desc"], rest[0]["code"], f"{rest[0]['live']:,}"])
    elif rest:
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
    # No "plus N eligible dormant accounts" clause any more: those accounts are
    # inside the eligible tile, which is why it now matches Product Mix's.
    # One line at 16pt in 12.10in: the first wording of this said which statuses are
    # in the population and measured 13.66in, which the gate caught. The statuses are
    # in the notes; the slide only has to say the population is the same one.
    _sub = ("Why accounts are outside ARS. Same accounts as Product Mix. Each "
            "counted once, first reason that applies.")
    _tb(s, 0.5, 1.12, 12.3, 0.5, _sub,
        14, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    excl_all = data["excluded_total"]
    book = data["open_total"]
    share = round(excl_all / book * 100) if book else 0
    # Tile 1 and tile 4 carry Product Mix's wording as well as its figures: a reader
    # comparing the two slides is comparing like with like, and the middle two tiles
    # say how the book splits — excl_all + elig_total == book, by construction.
    tiles = [(f"{book:,}", POP_TILE_LABEL, NAVY),
             (f"{excl_all:,}", "Outside ARS", ORANGE),
             (f"{share}%", "Share of accounts", NAVY),
             (f"{data['elig_total']:,}", "ARS-eligible accounts", NAVY)]
    for i, (v, l, f) in enumerate(tiles):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 1.28, v, l, fill=f, small_label=True)

    _tb(s, 0.5, 3.10, 6.1, 0.35, "Reason for Exclusion", 13.5, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    # Placed in a BOX, not by width. The chart grows with the number of reasons, and
    # the fourth one took it from 3.42in to 6.39in — through the footnote band that
    # starts at 6.05in. Bounded here, a fifth reason shrinks the bars instead of
    # walking over the sentences underneath.
    _fit_picture(s, chart, 0.2, 3.42, 6.25, 5.98 - 3.42)

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
           f"Population: the {data['open_total']:,} accounts on file excluding closed — "
           f"the same population Product Mix counts, so the two slides agree. "
           f"{data['open_only']:,} of them are open; the other "
           f"{data['open_total'] - data['open_only']:,} are dormant, inactive or a "
           f"status this extract does not map, and are outside ARS for that reason "
           f"({data['elig_other']:,} of them are flagged eligible by the core even so, "
           f"and are counted as eligible here and on Product Mix). Outside this slide: "
           f"{data['closed']:,} closed or charged-off accounts. "
           f"Excluded product codes derived per client as those with no eligible "
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
