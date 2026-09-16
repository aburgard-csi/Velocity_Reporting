#!/usr/bin/env python3
"""Data-driven, client-agnostic ICS deck builder.

    python3 build_ics_gen.py <client_ics.json> <marine_ref.pptx> <out.pptx>

Builds the ICS data slides from the JSON in the brand style, appends the six
monthly-detail slides, and clones the static education/reference + Q&A slides
from the Marine reference deck. Mystery-shop slide included only when
mystery_shop.include is true.
"""
import sys, os, json, copy
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
import ics_charts_gen as CH


def peak_month(values):
    """-> (index of the high, indices of earlier months level with it).

    LATEST month on a tie, and the tie is reported rather than hidden. Plain
    max() takes the FIRST maximum, and the two referral captions each called it
    independently: the first time a month landed level with an earlier one the
    Power of Referrals slide said "August was the highest of the last 14 months
    at 52" while the Referral Trend slide facing it said "peak 52 in Jul'26"
    (True Sky 1676, Aug 26 = Jul 26 = 52; Aaron, 2026-09-09). Same data, two
    answers. Both captions read this function now.
    """
    if not values:
        return None, []
    i = max(range(len(values)), key=lambda k: (values[k], k))
    return i, [k for k in range(len(values)) if k != i and values[k] == values[i]]


def _goal_months_elapsed(rf):
    """How many months of the goal year this program has actually run -> (n, caption).

    Branch goals in the VIP export are ANNUAL. Comparing a YTD referral count to a
    full-year goal reports how far into the year it is, not how the branch is doing:
    Wellworth 1549 started in May and its Main branch showed 24 against 204 (12%).

    Two cases:
      * program started inside this goal year — program-to-date equals year-to-date,
        so count from the first month carrying referrals.
      * program predates the year — count January through the latest data month.

    Falls back to 12 (i.e. no pro-rating, the old behaviour) whenever the data does
    not let this be derived, so a client whose file lacks a trend can never get a
    silently wrong denominator.
    """
    months = ((rf.get("trend") or {}).get("months")) or []
    latest = rf.get("latest_data_month") or ""      # 'YYYY-MM'
    try:
        latest_m = int(latest.split("-")[1])
    except Exception:
        latest_m = None
    started_this_year = (rf.get("program_to_date") == rf.get("year_to_date")
                         and rf.get("program_to_date") is not None)
    n = None
    if started_this_year and months:
        # trend covers the whole program in this case, so its length IS the run
        n = len(months)
    elif latest_m:
        n = latest_m                                 # January .. latest, inclusive
    if not n or n <= 0:
        return 12, ""
    n = min(n, 12)
    if n >= 12:
        return 12, ""
    partial = " The current month is partial." if (rf.get("month_to_date") or {}).get("value") else ""
    return n, (f"Goal pro-rated to the {n} month{'s' if n != 1 else ''} the program has run "
               f"(annual goal \u00f7 12 \u00d7 {n}).{partial}")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import summit_slide
from textfit import fits_one_line   # measured against the bundled TTFs, not estimated
import periods as P

from brand import (NAVY_RGB as NAVY, ORANGE_RGB as ORANGE,
                   STEEL_SOFT_RGB as STEEL, usd_compact as _usd)
LIGHT=RGBColor(0xEC,0xF0,0xF4); WHITE=RGBColor(0xFF,0xFF,0xFF); GREYT=RGBColor(0x5A,0x66,0x70)
NAVYX="00274C"
# The standard callout drop shadow is defined ONCE, in build/shapes.py. This file
# carried its own copy at alpha 26% while ARS, MRPC and shapes.py drew 28% — a drift
# STYLE.md described as "matching" for six weeks (one definition since 2026-09-02).
from shapes import shadow

def _needs_two_lines(*labels, usable_in, pt=None):
    """True when any label is too wide for one line at the size it will RENDER at.

    Measured at MIN_PT, not at the size the drawing call passes in:
    enforce_min_font bumps every run up to that floor afterwards, so shrinking
    the font is not an available fix on an ICS slide. Measured with textfit
    rather than a character count — Montserrat is much wider than Calibri.
    """
    from textfit import text_width_in
    size = pt or MIN_PT
    return any(text_width_in(t, size, "Montserrat", True) > usable_in for t in labels)


def tb(s,l,t,w,h,txt,size,color,bold=False,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP,font="Montserrat"):
    b=s.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h)); tf=b.text_frame; tf.word_wrap=True; tf.vertical_anchor=anchor
    for i,ln in enumerate(txt if isinstance(txt,list) else [txt]):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph(); p.alignment=align
        r=p.add_run(); r.text=ln; r.font.size=Pt(size); r.font.bold=bold; r.font.name=font; r.font.color.rgb=color
    return b

def callout(s,l,t,w,h,big,lab,sub=None,fill=NAVY,big_size=40):
    shp=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(l),Inches(t),Inches(w),Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb=fill; shp.line.fill.background()
    try: shp.adjustments[0]=0.06
    except Exception: pass
    tf=shp.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    tf.margin_left=Inches(0.15); tf.margin_right=Inches(0.15)
    def line(t,sz,b,c,al=PP_ALIGN.CENTER,first=False):
        p=tf.paragraphs[0] if first else tf.add_paragraph(); p.alignment=al
        r=p.add_run(); r.text=t; r.font.size=Pt(sz); r.font.bold=b; r.font.color.rgb=c
        r.font.name="Montserrat"
    line(big,big_size,True,WHITE,first=True); line(lab,16,False,WHITE)
    if sub: line(sub,15,False,WHITE)
    shadow(shp); return shp

def pill(s,txt):
    shp=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(9.9),Inches(0.34),Inches(2.95),Inches(0.62))
    shp.fill.solid(); shp.fill.fore_color.rgb=ORANGE; shp.line.fill.background()
    tf=shp.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE; p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
    r=p.add_run(); r.text=txt; r.font.size=Pt(15); r.font.bold=True; r.font.name="Montserrat"; r.font.color.rgb=WHITE
    shadow(shp)   # period pill carries the standard callout drop shadow (STYLE.md)

def pagenum(s,n): tb(s,0.45,7.0,0.7,0.34,str(n),16,NAVY,True)

def cap_pill(s,l,t,w,h,txt,fill,size=22):
    shp=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(l),Inches(t),Inches(w),Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb=fill; shp.line.fill.background()
    try: shp.adjustments[0]=0.5
    except Exception: pass
    tf=shp.text_frame; tf.vertical_anchor=MSO_ANCHOR.MIDDLE; p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
    r=p.add_run(); r.text=txt; r.font.size=Pt(size); r.font.bold=True; r.font.name="Montserrat"; r.font.color.rgb=WHITE
    shadow(shp); return shp

LOGO=[None]
def logo(s):
    if LOGO[0] and os.path.exists(LOGO[0]):
        s.shapes.add_picture(LOGO[0],Inches(11.28),Inches(6.78),Inches(1.7))

def blank(prs):
    lay=prs.slide_layouts[6] if len(prs.slide_layouts)>6 else prs.slide_layouts[-1]
    s=prs.slides.add_slide(lay)
    for ph in list(s.placeholders):      # drop layout placeholders (no "Click to add title" prompts)
        ph._element.getparent().remove(ph._element)
    return s
def title(s,txt): tb(s,0.5,0.28,11.5,0.9,txt,26,NAVY,True,font="Montserrat",anchor=MSO_ANCHOR.MIDDLE)
def sub(s,txt,top=1.12): tb(s,0.5,top,12.3,0.6,txt,16,GREYT,False)
def notes(s,txt): s.notes_slide.notes_text_frame.text=txt

def _white_borders(cell,w=12700):
    tcPr=cell._tc.get_or_add_tcPr()
    for edge in ('a:lnB','a:lnT','a:lnR','a:lnL'):
        for e in tcPr.findall(qn(edge)): tcPr.remove(e)
        ln=parse_xml(f'<a:ln xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" w="{w}" cap="flat"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:ln>')
        ln.tag=qn(edge); tcPr.insert(0,ln)

def std_table(s,rows,l,t,w,colw,highlight_last=True,fs=16,rowh=0.4):
    nr=len(rows); nc=len(rows[0])
    gf=s.shapes.add_table(nr,nc,Inches(l),Inches(t),Inches(w),Inches(rowh*nr)); tbl=gf.table
    tw=sum(colw)
    for i,cw in enumerate(colw): tbl.columns[i].width=Inches(w*cw/tw)
    for row in tbl.rows: row.height=Inches(rowh)
    tblPr=tbl._tbl.tblPr
    for a in list(tblPr):
        if a.tag==qn('a:tableStyleId'): tblPr.remove(a)
    tbl.first_row=False; tbl.horz_banding=False
    for ri,row in enumerate(rows):
        for ci,val in enumerate(row):
            c=tbl.cell(ri,ci); _white_borders(c)
            c.margin_left=Inches(0.1); c.margin_right=Inches(0.08); c.margin_top=Inches(0.01); c.margin_bottom=Inches(0.01)
            c.vertical_anchor=MSO_ANCHOR.MIDDLE; p=c.text_frame.paragraphs[0]; p.alignment=PP_ALIGN.LEFT if ci==0 else PP_ALIGN.CENTER
            r=p.add_run(); r.text=str(val); r.font.name="Montserrat"
            if ri==0:
                c.fill.solid(); c.fill.fore_color.rgb=NAVY; r.font.color.rgb=WHITE; r.font.bold=True; r.font.size=Pt(fs)
            elif highlight_last and ri==nr-1:
                c.fill.solid(); c.fill.fore_color.rgb=ORANGE; r.font.color.rgb=WHITE; r.font.bold=True; r.font.size=Pt(fs)
            else:
                c.fill.solid(); c.fill.fore_color.rgb=RGBColor(0xF2,0xF5,0xF8) if ri%2 else WHITE
                r.font.color.rgb=NAVY; r.font.size=Pt(fs); r.font.bold=(ci==0)

def restyle_newrel(prs):
    """Static education-slide fixes: standard grid + centering on '2026 New Releases',
    nudge the 'E-Learning Library Guide' image off the logo, enlarge the 'New in 2026'
    bullets."""
    _t=lambda s: next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()),"")
    for s in prs.slides:
        ttl=_t(s)
        if ttl.startswith("2026 New Releases"):
            delta=0.0
            for sh in s.shapes:
                if not sh.has_table: continue
                sh.top=Inches(1.5); t=sh.table
                aw=sum(Emu(c.width).inches for c in t.columns); newL=(13.333-aw)/2
                delta=newL-Emu(sh.left).inches; sh.left=Inches(newL)
                for ri,row in enumerate(t.rows):
                    row.height=Inches(0.29)
                    hdr=t.cell(ri,0).text.strip().lower().startswith("quarter")
                    for ci in range(len(t.columns)):
                        c=t.cell(ri,ci); _white_borders(c); c.vertical_anchor=MSO_ANCHOR.MIDDLE
                        c.margin_top=Inches(0.01); c.margin_bottom=Inches(0.01)
                        for p in c.text_frame.paragraphs:
                            p.alignment=PP_ALIGN.CENTER
                            for r in p.runs:
                                r.font.name="Montserrat"; r.font.size=Pt(12 if hdr else 10.5)
                                r.font.color.rgb=WHITE if hdr else NAVY; r.font.bold=hdr
                        c.fill.solid()
                        c.fill.fore_color.rgb=NAVY if hdr else (RGBColor(0xF2,0xF5,0xF8) if ri%2 else WHITE)
            # shift the two column-header labels to stay centered over the table
            for sh in s.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip() in ("Leadership Training","Front Line Referrals"):
                    sh.left=Inches(Emu(sh.left).inches+delta)
        elif ttl.startswith("E-Learning Library"):
            for sh in s.shapes:
                if sh.shape_type==13 and not (Emu(sh.left).inches>11 and Emu(sh.top).inches>6.5):  # content image, not logo
                    sh.left=Inches(Emu(sh.left).inches-0.5)
        elif ttl.startswith(("New in 2026","Reporting: VIP")):
            for sh in s.shapes:
                if sh.has_text_frame and sh.top is not None and 1.1<Emu(sh.top).inches<6.5 and sh.width and Emu(sh.width).inches>3:
                    for p in sh.text_frame.paragraphs:
                        for r in p.runs:
                            cur=r.font.size.pt if r.font.size else 14
                            r.font.size=Pt(cur+4)

# Every run in an ICS deck is floored at this size, so a width guard must measure against
# MIN_PT rather than the size the drawing call passes in.
MIN_PT = 16


def enforce_min_font(prs, minpt=MIN_PT):
    """Bump any explicit run font size below minpt up to minpt across all slides.
    Skips the dense '2026 New Releases' reference table (can't fit at 16pt)."""
    _t=lambda s: next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()),"")
    for s in prs.slides:
        skip=_t(s).startswith(("2026 New Releases","Program Results by Month Opened","Referred Accounts by Product"))
        for sh in s.shapes:
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        if r.font.size is not None and r.font.size.pt<minpt: r.font.size=Pt(minpt)
            if sh.has_table and not skip:
                for row in sh.table.rows:
                    for c in row.cells:
                        for p in c.text_frame.paragraphs:
                            for r in p.runs:
                                if r.font.size is not None and r.font.size.pt<minpt: r.font.size=Pt(minpt)

# ---- clone (for static education slides) ----
SHAPE_TAGS={qn('p:sp'),qn('p:pic'),qn('p:graphicFrame'),qn('p:grpSp'),qn('p:cxnSp')}
def clone_from(dst, src_slide):
    new=dst.slides.add_slide(dst.slide_layouts[6])
    for sh in list(new.shapes): sh._element.getparent().remove(sh._element)
    tree=new.shapes._spTree
    for el in src_slide.shapes._spTree:
        if el.tag in SHAPE_TAGS: tree.append(copy.deepcopy(el))
    for blip in tree.iter(qn('a:blip')):
        rId=blip.get(qn('r:embed'))
        if not rId: continue
        # copy the image BLOB into a fresh part in the destination package (avoids
        # cross-package partname collisions like duplicate image8.png)
        src_part=src_slide.part.rels[rId].target_part
        _, new_rId=new.part.get_or_add_image_part(BytesIO(src_part.blob))
        blip.set(qn('r:embed'), new_rId)
    return new

def extract_logo(ref, path):
    for s in ref.slides:
        for sh in s.shapes:
            if sh.shape_type==13:
                try:
                    part=s.part.rels[sh._element.blipFill.blip.rEmbed].target_part
                    if "image2" in str(part.partname):
                        open(path,"wb").write(part.blob); return path
                except Exception: pass
    return None

# ============================ direct mail ============================
def _dm_month_label(token):
    """'2026-08' or 'Aug 26' -> 'August 2026', through periods (never hand-parsed)."""
    d0 = P.parse_month(token)
    return f"{P.MONTH_FULL[d0.month-1]} {d0.year}" if d0 else str(token)


def direct_mail_slide(prs, d, client, m, rf, chart_png):
    """Direct Mail New Accounts: the monthly chart on the left, two callouts and the top
    branches on the right, a caption derived from the figures. Widths are MEASURED (textfit
    at the 16pt floor) and the wording steps down until it fits."""
    dm = d["direct_mail"]
    months, vals = dm["by_month"]["months"], dm["by_month"]["accounts"]
    ptd = dm["accounts_opened_ptd"]
    partial = CH.dm_partial_last(dm)
    # Complete months only for the peak and the latest-month callout: a month still running is
    # on the chart, hatched, but is not named as the latest result.
    n_c = len(vals) - 1 if partial else len(vals)
    c_m, c_v = months[:n_c], vals[:n_c]
    s = blank(prs); title(s, "Direct Mail New Accounts")
    pill(s, f"PTD · {_dm_month_label(dm['last_month'])}")
    sub(s, "Selection: checking accounts opened through the ICS direct-mail channel, by open date.")
    bw, bh = CH.DM_BOX_IN
    s.shapes.add_picture(chart_png, Inches(0.35), Inches(1.65), Inches(bw), Inches(bh))

    RX, RW = 8.7, 4.15
    callout(s, RX, 1.75, RW, 1.35, f"{ptd:,}", "Opened Program-to-Date", big_size=40)
    if c_v:
        callout(s, RX, 3.25, RW, 1.35, f"{c_v[-1]:,}", f"Opened in {_dm_month_label(c_m[-1])}", big_size=40)

    # Top branches. Names come from the referral branch list (the Charts Goals tab) where the
    # number matches; otherwise the branch is shown by number, never guessed.
    names = {str(b.get("number")): b.get("name")
             for b in (rf.get("by_branch") or {}).get("branches", [])
             if b.get("number") is not None and b.get("name")}
    branches = [b for b in (dm.get("by_branch") or []) if b.get("accounts")]
    col_w = [2.55, 1.6]
    name_in = RW * col_w[0] / sum(col_w) - 0.18          # cell width less its margins

    def _bname(k):
        nm = names.get(str(k))
        if nm and fits_one_line(nm, name_in, MIN_PT, family="Montserrat", bold=True, margins_in=0):
            return nm
        return f"Branch {k}" if str(k) else "No branch"
    if len(branches) > 1:
        rows = [["Top Branches", "Accounts"]]
        rows += [[_bname(b["branch"]), f"{b['accounts']:,}"] for b in branches[:3]]
        rows.append([f"All {len(branches)} Branches", f"{sum(b['accounts'] for b in branches):,}"])
        std_table(s, rows, RX, 4.8, RW, col_w, highlight_last=True, fs=16, rowh=0.36)
    elif branches:
        callout(s, RX, 4.75, RW, 1.35, _bname(branches[0]["branch"]), "Branch with DM Accounts", big_size=28)

    span = f"{P.mon_yy(months[0])} – {P.mon_yy(months[-1])}" + (" (partial)" if partial else "")
    pk, _ = peak_month(c_v)
    peak = f"peak {c_v[pk]:,} in {P.mon_yy(c_m[pk])}" if pk is not None else ""
    options = [f"Direct-mail new accounts by month opened, {span}; {peak}.",
               f"Direct-mail new accounts, {span}; {peak}.",
               f"Direct-mail new accounts, {span}."]
    options = [o.replace("; .", ".") for o in options]
    cap = next((o for o in options if fits_one_line(o, 9.8, 16, family="Montserrat", min_pt=MIN_PT)),
               options[-1])
    tb(s, 1.2, 6.72, 9.8, 0.5, cap, 16, GREYT, False)
    logo(s); pagenum(s, 5)

    src_file = dm.get("source_file") or "the ICS direct-mail new-accounts report"
    where = ", ".join(x for x in (dm.get("source_folder"),
                                 f"report date {dm['report_date']}" if dm.get("report_date") else None) if x)
    top_txt = ", ".join(f"{_bname(b['branch'])} (branch {b['branch']}) {b['accounts']:,}" for b in branches[:3])
    notes(s, f"Source — ICS direct-mail new-accounts file {src_file}"
             + (f" ({where})" if where else "")
             + f" for {client} ({m['client_id']}). Selection: checking accounts opened through the "
             f"direct-mail channel, counted by Open Date and Branch Number, "
             f"{P.mon_yy(months[0])}–{P.mon_yy(months[-1])}: {ptd:,} accounts program-to-date"
             + (f"; {P.mon_yy(c_m[-1])} {c_v[-1]:,}" if c_v else "")
             + (f"; {peak}" if peak else "")
             + (f"; {len(branches)} branches, top {top_txt}" if branches else "")
             + ". These are direct-mail accounts, NOT referral counts, and are not included in any "
             "referral figure in this deck. Bars navy, last complete month orange"
             + (", the running month hatched." if partial else "."))


# ============================ build ============================
def _latest_ics_workbook_period(client_id):
    """Period of the newest ICS workbook on file for this client, e.g. '2026.08'.

    Returns None when none is found. Filenames are
    '<id>-<yyyy.mm>-<name>-Invitation Checking Workbook ...' in the shared inputs
    folder. Resolved from RPE_DATA_ROOT so it works on either machine.
    """
    import glob, re
    try:
        import rpe_env
        folders = rpe_env.report_dirs()      # a folder per kind + the legacy flat one
    except Exception:
        return None
    best = None
    for f in [g for d in folders for g in glob.glob(str(d / f"{client_id}-*"))]:
        b = os.path.basename(f)
        if "invitation checking" not in b.lower():
            continue
        m = re.match(rf"^{re.escape(str(client_id))}-(\d{{4}}\.\d{{2}})-", b)
        if m and (best is None or m.group(1) > best):
            best = m.group(1)
    return best


def _period_label(period):
    """'2026.07' -> 'July 2026'. Unparseable input is returned unchanged rather than
    mangled — a pill is better wrong-looking than silently plausible."""
    from datetime import datetime as _dtc   # `build()` imports it locally, not here
    try:
        y, mo = period.split(".")
        return _dtc(int(y), int(mo), 1).strftime("%B %Y")
    except Exception:
        return period


def build(d, static_path, out, referrals_only=False):
    _stale_workbook = False
    # ICS financial detail ships ONLY when the workbook is for the deck's own period
    # (Aaron, 2026-08-28). It used to carry the prior quarter's figures forward, which
    # kept the numbers auditable in the source notes but dated them as current on the
    # slide face: 1537 FNB&T and 1676 True Sky both stamped "PTD · August 2026" on an
    # ICS Financial Summary built from a 2026.06 and 2026.07 workbook respectively.
    # A stale workbook now drops the workbook-driven sections instead, exactly as a
    # client with no workbook at all does.
    _meta = d.get("meta") or {}
    _cid, _period = _meta.get("client_id"), _meta.get("period")
    # The Contact Us card is the client's managing CSM (Aaron, 2026-09-16), resolved before
    # anything is rendered so a client with no CSM on file stops with a sentence. Any
    # `contacts` list in the sheet is ignored: it named one CSM for every client.
    import rpe_env as _rpe_c
    contact = _rpe_c.csm_contact(_cid)
    # Standalone ICS decks also carry the ICS program contact beside the CSM (Aaron, 2026-09-16).
    # A combined deck keeps its base program's Contact slide, so this card appears only here.
    _program_contact = (None if contact["name"].casefold() == _rpe_c.ICS_PROGRAM_CONTACT.casefold()
                        else _rpe_c.contact_by_name(_rpe_c.ICS_PROGRAM_CONTACT, _cid))
    _stale_wb_month = None
    # OPT-IN override (Aaron, 2026-09-09): include the workbook sections even when the
    # workbook is older than the deck, for a client who needs the financial slides
    # before the next workbook lands. Off by default, so the rule below still governs
    # every other build, and it does NOT re-date anything: the workbook-driven slides
    # are stamped with the WORKBOOK's own month, so a July figure reads "PTD · July
    # 2026" on a September deck rather than passing as current. Re-dating them is the
    # defect the rule exists to prevent; showing them, labelled, is not.
    _allow_stale = os.environ.get("ICS_ALLOW_STALE_WORKBOOK", "").strip() not in ("", "0")
    if not referrals_only and _cid and _period:
        _wbp = _latest_ics_workbook_period(_cid)
        if _wbp != _period and _allow_stale and _wbp:
            _stale_wb_month = _period_label(_wbp)
            print(f"ICS financial detail INCLUDED FROM A {_wbp} WORKBOOK on a {_period} "
                  f"deck, by ICS_ALLOW_STALE_WORKBOOK. Every workbook-driven slide is "
                  f"stamped 'PTD · {_stale_wb_month}', not the deck period, so no figure "
                  f"is presented as current. Referrals remain {_period}.")
        elif _wbp != _period:
            print(f"ICS financial detail OMITTED: newest ICS workbook for {_cid} is "
                  f"{_wbp or 'none on file'}, deck period is {_period}. Carried-forward "
                  f"figures would be dated as current on the slide face, so the "
                  f"workbook-driven sections are ABSENT rather than re-dated. Supply a "
                  f"{_period} workbook to include them.")
            referrals_only = True
            _stale_workbook = True
    # Missing-input guard (Aaron 2026-07-24/25): ICS financials are QUARTERLY (workbook-
    # driven); referrals are monthly (VIP). A monthly refresh CARRIES FORWARD the latest
    # workbook's financial sections in the client JSON (source notes keep the workbook
    # period, so the carry-forward is auditable). A null section therefore means the data
    # sheet was never populated / mis-assembled — STOP; never render empty slides or 0%.
    _required=("referrals",) if referrals_only else (
        "referrals","performance","revenue","financial_summary","monthly_detail","benchmark")
    _missing=[k for k in _required if not d.get(k)]
    if referrals_only:
        _skipped=[k for k in ("performance","revenue","financial_summary","monthly_detail",
                              "benchmark") if not d.get(k)]
        if _stale_workbook:
            print(f"REFERRALS-ONLY build: the workbook-driven sections are present in the "
                  f"client JSON but are NOT rendered, because they come from an older "
                  f"workbook than this deck's period. Referrals, trend, branch results and "
                  f"the education slides are unaffected.")
        else:
            print(f"REFERRALS-ONLY build: omitting workbook-driven sections {_skipped} — no "
                  f"ICS workbook has landed for this client yet. The financial slides are "
                  f"ABSENT, not zeroed.")
    if _missing:
        _cid=(d.get("meta") or {}).get("client_id","?")
        raise SystemExit(
            f"ICS build STOPPED for client {_cid} — missing input section(s): {', '.join(_missing)}.\n"
            f"referrals = monthly from VIP; the financial sections come from the latest ICS workbook\n"
            f"(quarterly). For a monthly refresh, carry the prior quarter's financial sections\n"
            f"forward in the client JSON — the slide source notes name the workbook + period.\n"
            f"If no workbook has EVER landed for this client, wait for it — do NOT build a\n"
            f"partial deck (CLAUDE.md: never render a slide from null).")
    # static_path = ics_static.pptx (5 education slides + Q&A, native from Marine). Data
    # slides are built into this package and reordered to the front.
    m=d["meta"]; client=m["client_name"]; rm=m["report_month"]
    from datetime import datetime
    # A sheet built from LOCAL files (ics_local_sheet.py, 1776 CoastHills CU) carries the
    # last referral date as `data_through`. Its pull date is only the day the file was
    # copied, so the pill names the date the referrals actually run to. VIP sheets carry no
    # data_through and keep their pull date.
    _local = m.get("source_kind") == "local"
    try:
        _dd=datetime.strptime(m.get("data_through") or m.get("data_pull",""),"%Y-%m-%d"); data_date=f"{_dd.strftime('%B')} {_dd.day}, {_dd.year}"
    except Exception:
        data_date=rm
    wbm=m.get("workbook_month",rm)   # last completed month in the workbook (PTD as-of)
    # A workbook older than the deck stamps its OWN month on every slide it feeds.
    if _stale_wb_month:
        wbm=_stale_wb_month
    A=os.path.join(os.path.dirname(out) or ".","_ics_assets"); os.makedirs(A,exist_ok=True)
    CH.render_all(d, A, referrals_only=referrals_only); a=lambda n: os.path.join(A,n)
    prs=Presentation(static_path)
    prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
    # the template may be a FULL populated demo deck (Union Financial) — keep only the
    # static education/reference + Q&A slides; everything else is rebuilt from data.
    STATIC_TITLES=("New in 2026","E-Learning Library Guide","2026 New Releases",
                   "Reporting: VIP","VIP Best Practices","Questions & Discussion")
    # Mark which template slides to keep, but DO NOT remove them yet.
    #
    # Dropping them here frees their slide partnames, and python-pptx then hands
    # those freed numbers to the data slides we are about to add. The retained
    # static slides sit at slide22-slide27, so the last six data slides landed on
    # partnames the statics still held: six parts each ended up referenced TWICE
    # in sldIdLst. The deck reported 28 slides but contained 22 — LibreOffice
    # refused to open it at all and PowerPoint recovered by reordering, which is
    # how the title slide vanished and Contact Us surfaced near the front.
    #
    # Deferring the removal until after the data slides exist keeps every
    # template partname in use, so the new slides allocate above them.
    _lst=prs.slides._sldIdLst
    _tpl_els=list(_lst)
    _static_els, _drop_els, _static_slides = [], [], []
    for _el,_sl in zip(_tpl_els, list(prs.slides)):
        _ft=next((sh.text_frame.text.strip().split("\n")[0] for sh in _sl.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()),"")
        if _ft.startswith(STATIC_TITLES):
            _static_els.append(_el); _static_slides.append(_sl)
        else:
            _drop_els.append(_el)
    n_static=len(_static_els)
    # logo comes from the slides we are keeping (the deck still holds the demo
    # slides at this point, so scanning everything could grab a chart image)
    LOGO[0]=extract_logo(type("_Ref",(),{"slides":_static_slides})(), a("logo.png"))
    restyle_newrel(prs)   # standard grid + logo-clearance on the static '2026 New Releases' table
    # Replace the static Q&A slide's client reference. Resolve the slide by TITLE and the
    # line by its "<client>  •  <month>" shape — never by the template's dummy client name.
    # Matching a literal ("Marine") silently no-ops the moment the template is re-baked with
    # a different dummy, and the deck then ships THAT name on the Q&A slide: exactly what
    # the 2026-07-24 genericization to "Union Financial" caused.
    _qa_swapped=False
    for sl in prs.slides:
        _txt=[sh.text_frame.text.strip() for sh in sl.shapes
              if sh.has_text_frame and sh.text_frame.text.strip()]
        if not any(t.startswith("Questions & Discussion") for t in _txt):
            continue
        for sh in sl.shapes:
            if not sh.has_text_frame: continue
            _t=sh.text_frame.text.strip()
            if _t.startswith("Questions & Discussion") or "•" not in _t: continue
            for p in sh.text_frame.paragraphs:
                if p.runs and "•" in "".join(r.text for r in p.runs):
                    p.runs[0].text=f"{client}  •  {rm}"
                    for r in p.runs[1:]: r.text=""
                    _qa_swapped=True
    if not _qa_swapped:
        raise SystemExit(
            "MISS: Questions & Discussion client line not found in the ICS template.\n"
            "  Unswapped, the deck ships the TEMPLATE client's name on the Q&A slide.\n"
            "  Fix the builder/template pair — do not ship.")

    # 1 cover
    # CANONICAL title layout (matches ARS/MRPC): centered lockup card, centered 40pt title,
    # orange centered client + review lines (STYLE.md, Aaron 2026-07-24)
    s=blank(prs)
    r=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,prs.slide_width,prs.slide_height); r.fill.solid(); r.fill.fore_color.rgb=NAVY; r.line.fill.background()
    _tcard=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(5.01),Inches(0.7),Inches(3.32),Inches(1.27))
    _tcard.fill.solid(); _tcard.fill.fore_color.rgb=WHITE; _tcard.line.fill.background()
    try: _tcard.adjustments[0]=0.25
    except Exception: pass
    if LOGO[0] and os.path.exists(LOGO[0]):
        s.shapes.add_picture(LOGO[0],Inches(5.17),Inches(0.86),Inches(3.0),Inches(0.95))
    tb(s,0.8,2.7,11.7,2.0,"Invitation Checking® System",40,WHITE,True,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE,font="Montserrat")
    tb(s,0.8,5.0,11.7,1.2,[client,f"Executive Review  •  {rm}"],20,ORANGE,True,align=PP_ALIGN.CENTER,font="Montserrat")
    notes(s,"Title slide. No data.")

    # 2 divider — CANONICAL product-divider layout (STYLE.md, Aaron 2026-07-24):
    # white logo card top-left, centered 52pt title, orange centered benefits line
    s=blank(prs)
    r=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,prs.slide_width,prs.slide_height); r.fill.solid(); r.fill.fore_color.rgb=NAVY; r.line.fill.background()
    _card=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(0.55),Inches(0.5),Inches(2.22),Inches(0.92))
    _card.fill.solid(); _card.fill.fore_color.rgb=WHITE; _card.line.fill.background()
    try: _card.adjustments[0]=0.25
    except Exception: pass
    if LOGO[0] and os.path.exists(LOGO[0]):
        s.shapes.add_picture(LOGO[0],Inches(0.71),Inches(0.66),Inches(1.9),Inches(0.6))
    tb(s,0.7,2.25,11.9,2.4,"Invitation Checking® System",52,WHITE,True,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE,font="Montserrat")
    tb(s,0.7,5.05,11.9,0.9,
       "Referrals" if referrals_only else "Referrals · Account Performance · Revenue",
       22,ORANGE,True,align=PP_ALIGN.CENTER,font="Montserrat")
    notes(s,"Section divider. No data.")

    # Agenda (after the ICS section header)
    #
    # A referrals-only deck must not advertise sections it does not contain. The
    # section divider already dropped to "Referrals", but the agenda still listed
    # Performance / Revenue / Financial Summary / Comparisons — four sections that are
    # deliberately ABSENT from the build. Wellworth 1549 shipped that way (Aaron,
    # 2026-08-28). Rows are REMOVED, not blanked, for the same reason the combined-deck
    # assembler removes them: an empty numbered row reads as a section that failed.
    s=blank(prs); title(s,"Agenda")
    _dm_slide=CH.has_direct_mail(d)
    items=["The Power of Referrals",
           "Referral Trend, Results by Branch & Direct Mail" if _dm_slide
           else "Referral Trend & Results by Branch"]
    if not referrals_only:
        items+=["Performance of ICS Accounts","ICS Revenue & Revenue Detail",
                "ICS Financial Summary","Comparisons"]
    items+=["E-Learning & VIP Resources","Questions & Discussion"]
    yy=1.55
    for i,it in enumerate(items,1):
        bd=s.shapes.add_shape(MSO_SHAPE.OVAL,Inches(1.6),Inches(yy),Inches(0.55),Inches(0.55))
        bd.fill.solid(); bd.fill.fore_color.rgb=ORANGE; bd.line.fill.background()   # all badges orange (Aaron)
        btf=bd.text_frame; btf.vertical_anchor=MSO_ANCHOR.MIDDLE; bp=btf.paragraphs[0]; bp.alignment=PP_ALIGN.CENTER
        br=bp.add_run(); br.text=str(i); br.font.size=Pt(16); br.font.bold=True; br.font.name="Montserrat"; br.font.color.rgb=WHITE
        tb(s,2.45,yy+0.02,9.5,0.5,it,20,NAVY,False,anchor=MSO_ANCHOR.MIDDLE)
        yy+=0.66
    # Client logo, right-hand third. The agenda's own text reaches at most 7.31in
    # (measured against the bundled TTFs), so a logo from 8.60in clears it. Centred on
    # the agenda block, which is shorter in a referrals-only build.
    try:
        import rpe_env as _rpe
        _lp=_rpe.client_logo(m.get("client_id"))
        if _lp is None:
            print(f"agenda logo: none on file for client {m.get('client_id')} "
                  f"(Inputs/Logos/<id>.png) — slide built without it")
        else:
            _lp=_rpe.trim_logo(_lp,A)
            _fit=_rpe.fit_box(_lp,3.90,1.70)
            if _fit:
                _lw,_lh=_fit
                _cy=(1.55+yy-0.66+0.5)/2.0     # centre of the agenda block
                s.shapes.add_picture(str(_lp),Inches(8.60+(3.90-_lw)/2.0),
                                     Inches(_cy-_lh/2.0),Inches(_lw),Inches(_lh))
                print(f"agenda logo: {os.path.basename(str(_lp))} placed {_lw:.2f}x{_lh:.2f}in")
    except Exception as _e:
        print("!! agenda logo skipped:",repr(_e))
    logo(s); pagenum(s,3); notes(s,"Agenda. No data.")

    rf=d["referrals"]; base=f"Source — {m.get('vip_source','VIP ICS Referral Data')} and {m.get('workbook','ICS workbook')} for {client} ({m['client_id']}), pulled {m['data_pull']}."
    if _local:
        # Local-file sheet: name the files it was built from, never the VIP dashboard, and
        # name a workbook only when the sheet carries one.
        base=(f"Source — {m['referral_source']}"
              + (f"; financial figures from {m['workbook']}" if m.get("workbook") else "")
              + f"; for {client} ({m['client_id']}).")
    # No goal on file (a local sheet without a Charts Goals tab): goal tiles, captions and
    # columns are left out rather than shown as 0% or a dash.
    _goal=rf.get("monthly_goal")

    # 3 Power of Referrals
    s=blank(prs); title(s,"The Power of Referrals"); pill(s,f"PTD · {data_date}")
    sub(s,"Selection: checking referrals logged by branch staff — program-to-date and 2026 YTD.")
    total_ref=rf["program_to_date"]   # single source: the current program-to-date total shown in the callout
    callout(s,0.55,1.7,3.5,2.0,f"{total_ref:,}","Referrals Program-to-Date",big_size=44)
    pm=rf["previous_month"]
    # The previous month used to be DECLARED "a program high" unconditionally.
    # It usually is not: Marine's July was 103 against a June of 129, Austin's
    # July 363 against 423, Texas Bay's July 40 against a March of 73 — every ICS
    # deck asserted a record that the client's own trend contradicts, which is
    # also the "no superlatives or unsupported claims" rule in CLAUDE.md.
    #
    # The claim is now earned or dropped, and it is scoped to what the data can
    # actually support: `trend` is a 14-month window, not the whole programme, so
    # nothing here can prove a PROGRAMME high. The last entry is the partial
    # current month, so complete months are trend[:-1] and the previous month is
    # the last of those.
    _tr = rf["trend"]
    _tm, _tv = _tr["months"], _tr["referrals"]
    # Drop the last entry ONLY when it is the partial current month. The chart
    # renderer reads `partial_last` for exactly this; the caption used to assume
    # it, so a pull taken after month close would have dropped a COMPLETE month
    # from the peak search — and if that month were the peak, named an older and
    # lower one instead.
    _n = -1 if _tr.get("partial_last") else len(_tv)
    _cm, _cv = _tm[:_n], _tv[:_n]
    if _cv:
        _pi, _tie_ix = peak_month(_cv)
        # The claim is tested on the value it PRINTS. `previous_month.value` and
        # `trend.referrals[-1]` are separate fields of the VIP pull and agree on
        # every client today; asserting a record from one while testing the other
        # would break silently the first time a restatement touched only one.
        _last = _cv[-1]
        _tied = [_cm[k] for k in _tie_ix] if _last >= _cv[_pi] else []
        if _last >= _cv[_pi] and _tied:
            if len(_tied) == 1:
                _lvl = f"level with {P.mon_yy(_tied[0])}"
            elif len(_tied) == 2:
                _lvl = f"level with {P.mon_yy(_tied[0])} and {P.mon_yy(_tied[1])}"
            else:
                _lvl = f"level with {len(_tied)} earlier months"
            _high = (f"{pm['label']} tied the {len(_cv)}-month high at {_last}, "
                     f"{_lvl}.")
        elif _last >= _cv[_pi]:
            _high = (f"{pm['label']} was the highest of the last {len(_cv)} months "
                     f"at {_last}.")
        else:
            _high = (f"{pm['label']} brought {_last}; the last {len(_cv)} months "
                     f"peaked at {_cv[_pi]} in {P.mon_yy(_cm[_pi])}.")
    else:
        _high = f"{pm['label']} brought {pm['value']}."
    tb(s,4.35,1.7,8.45,2.4,
       f"{client} team members have generated {total_ref:,} checking referrals since "
       f"program inception — {rf['year_to_date']:,} year-to-date in 2026. {_high}",
       28,NAVY,False,anchor=MSO_ANCHOR.MIDDLE,font="Calibri")   # 28pt fills the space (Aaron 2026-07-24)
    # Previous-month-vs-goal is keyed generically; the month-named key (june_/july_)
    # is a leftover that only exists while that month happens to be the previous
    # one, so reading it directly KeyErrors on every later pull.
    _vs_goal = rf.get('prev_month_vs_goal_pct',
                      rf.get(f"{pm['label'].lower()}_vs_goal_pct", 0))
    _tiles=[(f"{rf['year_to_date']:,}","2026 Year-to-Date"),
            (f"{pm['value']}",f"Previous Month ({pm['label']})")]
    if _goal is not None:
        _tiles.append((f"{_vs_goal}%",f"{pm['label']} vs Goal"))
    # Three tiles keep their original positions; two are centred as a pair.
    _tx0=0.55 if len(_tiles)==3 else (13.333-(len(_tiles)*3.8+(len(_tiles)-1)*0.3))/2
    for i,(big,lab) in enumerate(_tiles):
        callout(s,_tx0+i*4.1,4.15,3.8,1.5,big,lab)
    logo(s); pagenum(s,3)
    _goal_note=(f"monthly goal {_goal:,} ({pm['label']} vs goal {_vs_goal}%)" if _goal is not None
                else "no referral goal on file, so none is shown")
    _thru_note=(f"Referral detail file, counted by Issue Date, referrals through {m.get('data_through')}."
                if _local else f"VIP, current thru {rf['month_to_date']['label']} (partial).")
    notes(s,base+f" Referrals PTD {rf['program_to_date']:,}, YTD {rf['year_to_date']:,}, {pm['label']} {pm['value']}, "
                f"{_goal_note}. {_thru_note}")

    # 4 Referral Trend
    t=rf["trend"]; s=blank(prs); title(s,f"Referral Trend – Last {len(t['months'])} Months")
    pill(s,f"PTD · {data_date}")
    s.shapes.add_picture(a("ics_trend.png"),Inches(0.66),Inches(1.55),Inches(12.0))
    # Same correction as the Power of Referrals caption: the peak is FOUND, not
    # assumed to be the second-to-last month. [-2] is merely the last complete
    # month, and naming it the high was wrong on every client checked.
    _cn = -1 if t.get("partial_last") else len(t['referrals'])
    _ccv = t['referrals'][:_cn]; _ccm = t['months'][:_cn]
    # Same function as the Power of Referrals caption above, so the two cannot
    # name different peak months again.
    _pk, _ = peak_month(_ccv)
    _peak_txt = (f"peak {_ccv[_pk]} in {P.mon_yy(_ccm[_pk])}" if _pk is not None
                 else "no complete month yet")
    # Months in MMM'YY, matching the axis directly above, and the partial note
    # folded into the range rather than repeated at the end. That repetition is
    # what pushed this past one line: at 16pt MONTSERRAT the old wording measured
    # 9.96" in a 9.8" box, wrapped to two, and overflowed into the page-number
    # corner on Austin 1075. Measured, not eyeballed — this fits at 9.33" with
    # four-digit values in both slots.
    _span = (f"{P.mon_yy(t['months'][0])} – {P.mon_yy(t['months'][-1])}"
             + (" (partial)" if t.get("partial_last") else ""))
    tb(s,1.2,6.72,9.8,0.5,
       f"Monthly checking referrals, {_span}; {_peak_txt}."
       + (f" Goal {_goal:,}/mo." if _goal is not None else ""),
       16,GREYT,False)
    logo(s); pagenum(s,4)
    if _local:
        notes(s,base+(f" Monthly referrals vs the {_goal:,}/mo goal." if _goal is not None else " Monthly referrals.")
                    +" Bars navy, last complete month orange"
                    +(", partial month hatched." if t.get("partial_last") else ".")
                    +" Referral detail file, counted by Issue Date.")
    else:
        notes(s,base+f" Monthly referrals vs the {rf['monthly_goal']:,}/mo goal. Bars navy, last complete month orange, partial month hatched. VIP.")

    # 5 Results by Branch
    # Branch goals in the VIP data are ANNUAL, but a program that started partway
    # through the year has not had a year to hit them. Wellworth 1549 began in May and
    # its Main branch read 24 against a 204 annual goal — 12%, which reports the
    # calendar, not the branch. The goal is pro-rated to the months the program has
    # actually run (Aaron, 2026-08-28); Main then reads 24 of 68, or 35%.
    s=blank(prs); title(s,"Results by Branch – Year to Date"); pill(s,f"YTD · {data_date}")
    _elapsed, _elapsed_txt = _goal_months_elapsed(rf)
    bb=rf["by_branch"]
    _gh = "Goal to Date" if _elapsed < 12 else "Goal"
    _has_goals = any(b.get("goal") for b in bb["branches"])
    rows=[["Branch","Referrals YTD",_gh,"% of Goal"]]
    shown=bb["branches"][:8]
    def _prorate(annual):
        """Annual goal -> goal for the months run. Rounded per branch so the column
        adds up to what the reader would total by hand."""
        return int(round(annual / 12.0 * _elapsed))
    # A branch can carry a zero goal (non-retail units like 1734's "Operations").
    # Show a dash rather than dividing by zero — and never invent a percentage.
    for b in shown:
        g_=_prorate(b["goal"]) if b.get("goal") else 0
        pct=f"{round(b['referrals']/g_*100)}%" if g_ else "—"
        rows.append([b["name"],f"{b['referrals']}",f"{g_}" if g_ else "—",pct])
    tr=sum(b["referrals"] for b in shown)
    tg=sum(_prorate(b["goal"]) for b in shown if b.get("goal"))
    rows.append([f"Top {len(shown)} Total",f"{tr}",f"{tg}",
                 f"{round(tr/tg*100)}%" if tg else "—"])
    if not _has_goals:
        # No branch carries a goal: drop the goal columns rather than print a column of dashes.
        rows=[r[:2] for r in rows]
    # widened to fill the space the callouts left — at 6.95in the table stopped at
    # 10.3in and the right third of the slide sat empty
    std_table(s,rows,3.35,1.45,9.45,[2.4,1.1,0.9,0.9][:len(rows[0])],highlight_last=True,fs=16,rowh=0.5)

    # Callouts in the empty left column (Aaron, 2026-08-28). The table shows the top 8;
    # these read across EVERY branch, so participation and overall pace are visible
    # without the reader adding up a truncated table.
    _all = bb["branches"]
    _rep = sum(1 for b in _all if b.get("referrals", 0) > 0)
    _none = len(_all) - _rep
    _ar = sum(b.get("referrals", 0) for b in _all)
    _ag = sum(_prorate(b["goal"]) for b in _all if b.get("goal"))
    _apct = f"{round(_ar/_ag*100)}%" if _ag else "—"
    for _i, (_big, _lab) in enumerate([
            (f"{_rep}", "Branches Reporting Referrals"),
            (f"{_none}", "Branches Without Referrals")]
            + ([(_apct, "% of Goal — All Branches")] if _has_goals else [])):
        callout(s, 0.5, 1.55 + _i*1.62, 2.65, 1.42, _big, _lab,
                fill=(ORANGE if _i == 2 else NAVY), big_size=34)

    # No selection line on this slide (Aaron, 2026-08-28). With the callouts and the
    # pro-rating note it ran to ~20in of text in a 9.68in box: it wrapped, its box
    # overlapped the table above and it ran into the logo band below. The selection,
    # the branch counts and the pro-rating basis are all in the notes, which is where
    # STYLE.md puts the source anyway.
    logo(s); pagenum(s,5)
    if _local and not _has_goals:
        notes(s,base+f" Callouts: {_rep} of {len(_all)} branches logged a referral, {_none} none. "
                     f"Referrals by branch, YTD ({_ar:,} in total); no branch goals on file, so no "
                     f"goal or % of goal is shown. Top branches by referrals. Referral detail file, "
                     f"counted by Issue Date and Branch.")
    elif _local:
        notes(s,base+f" Callouts: {_rep} of {len(_all)} branches logged a referral, {_none} none; "
                     f"all-branch pace {_apct} ({_ar:,} referrals vs {_ag:,} pro-rated goal). "
                     f"Referrals by branch, YTD, vs each branch's goal pro-rated to "
                     f"{_elapsed} month{'s' if _elapsed != 1 else ''} of program activity "
                     f"(monthly goal x {_elapsed}); the Charts 'Goals' tab carries a MONTHLY goal per branch. "
                     f"Top branches by referrals. Referral detail file, counted by Issue Date and Branch; "
                     f"branch names from the Charts 'Goals' tab.")
    else:
        notes(s,base+f" Callouts: {_rep} of {len(_all)} branches logged a referral, {_none} none; "
                 f"all-branch pace {_apct} ({_ar:,} referrals vs {_ag:,} pro-rated goal). "
                 f"Referrals by branch, YTD, vs each branch's goal pro-rated to "
                 f"{_elapsed} month{'s' if _elapsed != 1 else ''} of program activity "
                 f"(annual goal / 12 x {_elapsed}); the VIP file carries the ANNUAL goal. "
                 f"Top branches by referrals. VIP; branch names reconciled to the Charts 'Goals' tab.")

    # 5a Direct Mail New Accounts (Aaron, 2026-09-16: "Direct mail should get its own slide").
    # Accounts opened through the ICS DIRECT-MAIL channel, from the sheet's `direct_mail` block
    # (ics_local_sheet reads the CSM's "Direct Mail New Accounts Opened PTD" file). A different
    # channel from referrals: these counts are never added to any referral figure. Built only
    # when the block carries accounts; a sheet without one gets no slide, not a slide of zeros.
    if _dm_slide:
        direct_mail_slide(prs, d, client, m, rf, a("ics_direct_mail.png"))

    # 5b Referred Accounts by Product (workbook 'Referred Accounts by Product' tab, participating products only)
    rbp=d.get("referred_by_product")
    if rbp:
        prods=rbp["products"]; tot_ref=sum(p["referred"] for p in prods); tot_acc=sum(p["total"] for p in prods)
        s=blank(prs); title(s,"Referred Accounts by Product"); pill(s,f"PTD · {wbm}")
        sub(s,"Checking products participating in the Invitation Checking® System — accounts referred vs. total book.")
        s.shapes.add_picture(a("ics_refprod.png"),Inches(0.35),Inches(1.75),Inches(7.35))
        rows=[["Product","Total Accts","Referred","% of Ref."]]
        for p in sorted(prods,key=lambda x:-x["referred"]):
            pct=f"{p['referred']/tot_ref*100:.0f}%" if (tot_ref and p["referred"]>0) else "—"
            rows.append([p["name"],f"{p['total']:,}",f"{p['referred']:,}",pct])
        rows.append(["Total — participating",f"{tot_acc:,}",f"{tot_ref:,}","100%"])
        std_table(s,rows,7.9,1.85,5.05,[2.5,0.95,0.85,0.85],highlight_last=True,fs=13,rowh=0.5)
        logo(s); pagenum(s,6)
        notes(s,base+" Referred Accounts by Product — workbook 'Referred Accounts by Product' tab, filtered to Participates in ICS = Yes. Chart shows products with referrals; table lists all participating products.")

    # ---- workbook-driven sections (ICS financials are QUARTERLY) ------------------
    # Skipped ONLY in explicit referrals-only mode, for a client whose first ICS
    # workbook has not landed yet (Wellworth 1549, Aaron 2026-08-27). These slides are
    # OMITTED, never rendered from null — an empty ROI/revenue slide is precisely what
    # the missing-section guard exists to prevent. A normal build still stops hard.
    if not referrals_only:
        # 5b Performance of Accounts — section intro (Cindy's layout, our style)
        s=blank(prs); title(s,"Performance of Accounts")
        intro_bullets=["Drilling into the data","Overall Profitability","Breakdown of Revenue",
                       "Breakdown by Month","Comparisons"]
        bx=s.shapes.add_textbox(Inches(0.75),Inches(2.05),Inches(6.0),Inches(4.5)); btf=bx.text_frame; btf.word_wrap=True
        for i,it in enumerate(intro_bullets):
            pp=btf.paragraphs[0] if i==0 else btf.add_paragraph(); pp.space_after=Pt(16)
            r1=pp.add_run(); r1.text="•  "; r1.font.size=Pt(22); r1.font.bold=True; r1.font.name="Calibri"; r1.font.color.rgb=ORANGE
            r2=pp.add_run(); r2.text=it; r2.font.size=Pt(22); r2.font.name="Calibri"; r2.font.color.rgb=NAVY
        s.shapes.add_picture(a("ics_perfintro.png"),Inches(6.55),Inches(1.75),Inches(5.85))
        logo(s); pagenum(s,6)
        notes(s,"Section intro to the ICS account-performance analysis (profitability, revenue breakdown, monthly detail, comparisons). Motif = monthly referrals (bars) + cumulative referrals (line), from the "
                +(f"referral trend in {m['referral_source'].split(' (')[0]}" if _local else "VIP referral trend")
                +". No figures on the slide face.")

        # --- ROI / Present Value recalculated per client (the workbook ROI is not used) ---
        # PV per account = annual profit × life; life = velocity avg 6.9 yrs for the program's
        # first 2 years, else the client's modeled life. PV total = PV/acct × accounts opened.
        # ROI = PV total ÷ (cost per acquired account × accounts opened).  (Aaron, 2026-07-13)
        import datetime as _dt
        VELOCITY_LIFE=6.9
        p=d["performance"]; _fs=d["financial_summary"]; n_acct=_fs["ics_accounts"]
        def _prog_years():
            ps=d["meta"].get("program_start")
            if not ps: return 99
            y,m=(int(x) for x in ps.split("-")[:2])
            yy,mm,dd=(int(x) for x in d["meta"]["data_pull"].split("-"))
            return (_dt.date(yy,mm,dd)-_dt.date(y,m,1)).days/365.25
        life_used=VELOCITY_LIFE if _prog_years()<2 else p.get("life_of_ics_account_years",VELOCITY_LIFE)
        pv_per_acct=p["annual_profit_per_account"]*life_used
        pv_total=pv_per_acct*n_acct
        total_cost=p["cost_per_account"]*n_acct
        roi_calc=pv_total/total_cost if total_cost else 0

        # 6 Performance of ICS Accounts (Cindy's ROI layout: 3 rectangular callouts + heading + bullets)
        AMBER=RGBColor(0xF5,0xA6,0x23)
        s=blank(prs); title(s,"Performance of ICS Accounts"); pill(s,f"PTD · {wbm}")
        tb(s,0.5,1.12,12.3,0.6,f"Return on Investment — {roi_calc:.2f} to 1",22,NAVY,True)
        modeled=p.get("life_of_ics_account_years",life_used)
        young=abs(life_used-VELOCITY_LIFE)<0.05   # first-2-years programs use the 6.9-yr velocity life
        if young:
            life_bullets=[f"Models indicate your average life of account is {modeled:g} years",
                          "National Average is 6.9 Years"]
            pv_bullets=["Using 6.9 Years to be conservative",
                        f"Acquisition Cost: ${p['cost_per_account']:,.0f}"]
        else:
            life_bullets=[f"{p.get('pct_added_life',0)*100:.0f}% longer than the {VELOCITY_LIFE:g}-year "
                          "average for all accounts","Modeled from ICS account survival"]
            pv_bullets=[f"Using the {life_used:g}-year modeled account life",
                        f"Acquisition Cost: ${p['cost_per_account']:,.0f}"]
        cols=[(AMBER, f"${p['annual_profit_per_account']:,.2f}",
               # "Annual Profit Contribution per Account" is 4.91in of Montserrat 18pt in a
               # 3.60in column — it wrapped onto the bullet beneath (Aaron, 2026-08-27).
               "Annual Profit per Account",
               [f"Accounts pay for themselves in ~{p['payback_months']} months"]),
              (ORANGE, f"{life_used:g} years",
               "Average Life of Accounts", life_bullets),
              (NAVY, f"${pv_per_acct:,.2f}",
               "Present Value per Account", pv_bullets)]
        BW,BT,BH,GAP=3.8,1.9,2.35,0.42
        x0=(13.333-(3*BW+2*GAP))/2                     # centered block, equal side margins
        for k,(fill,big,heading,bullets) in enumerate(cols):
            x=x0+k*(BW+GAP)
            box=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(x),Inches(BT),Inches(BW),Inches(BH))
            box.fill.solid(); box.fill.fore_color.rgb=fill; box.line.fill.background()
            try: box.adjustments[0]=0.06                # rounded corners, matches deck callouts
            except Exception: pass
            tf=box.text_frame; tf.vertical_anchor=MSO_ANCHOR.MIDDLE; pp=tf.paragraphs[0]; pp.alignment=PP_ALIGN.CENTER
            r=pp.add_run(); r.text=big; r.font.size=Pt(36); r.font.bold=True; r.font.name="Montserrat"; r.font.color.rgb=WHITE
            shadow(box)
            tb(s,x,BT+BH+0.12,BW,0.6,heading,18,NAVY,True)
            bt=s.shapes.add_textbox(Inches(x),Inches(BT+BH+0.8),Inches(BW),Inches(1.7)); btf=bt.text_frame; btf.word_wrap=True
            for j,bl in enumerate(bullets):
                q=btf.paragraphs[0] if j==0 else btf.add_paragraph(); q.space_after=Pt(4)
                rr=q.add_run(); rr.text="•  "+bl; rr.font.size=Pt(17); rr.font.name="Calibri"; rr.font.color.rgb=NAVY
        logo(s); pagenum(s,6)
        notes(s,base+f" ROI recalculated (workbook ROI not used): PV/acct = annual profit ${p['annual_profit_per_account']:.2f} × {life_used:g} yr "
                    f"(velocity life, program <2 yr) = ${pv_per_acct:,.2f}; PV total = ${pv_total:,.0f}; "
                    f"ROI = PV total ÷ (${p['cost_per_account']:.0f} × {n_acct:,}) = {roi_calc:.2f} : 1.")

        # 6b Program Results by Month Opened — monthly-detail data table (revenue + amortized expense)
        md0=d["monthly_detail"]; mos=md0["months"]; nrm=len(mos)
        mo_open=[nrm-i for i in range(nrm)]; amort=p["cost_per_account"]/60.0
        _rr=lambda label,vals,fmt:[label]+[fmt(v) for v in vals]
        trows=[["Month Opened"]+mos,
               _rr("Accounts Opened",md0["accounts_opened"],lambda v:f"{v:,}"),
               _rr("Avg Balance / Acct",md0["avg_balance"],lambda v:f"${v:,.0f}"),
               _rr("Spread on Deposits",md0["spread"],lambda v:f"${v:,.0f}"),
               _rr("Interchange Income",md0["interchange"],lambda v:f"${v:,.0f}"),
               _rr("NSF / OD Fees",md0["nsf_od"],lambda v:f"${v:,.0f}"),
               _rr("Other Fees",md0["other_fees"],lambda v:f"${v:,.0f}"),
               _rr("Account Profit Contribution",md0["profit_contribution"],lambda v:f"${v:,.0f}"),
               _rr("Amortized Expense / Acct / Mo",[amort]*nrm,lambda v:f"${v:,.2f}"),
               _rr("Months Open",mo_open,lambda v:f"{v}")]
        s=blank(prs); title(s,"Program Results by Month Opened"); pill(s,f"PTD · {wbm}")
        sub(s,"ICS-originated checking accounts by opening-month cohort — revenue and amortized acquisition expense.")
        std_table(s,trows,0.35,1.7,12.63,[2.9]+[1]*nrm,highlight_last=False,fs=13,rowh=0.46)
        tb(s,0.4,6.55,12.55,0.4,f"Amortized expense: ${p['cost_per_account']:.0f} ÷ 60 months = ${amort:.2f} per account per month × time open.",14,GREYT,False)
        logo(s); pagenum(s,7)
        notes(s,base+f" Monthly Detail tab: revenue components, account profit contribution, amortized expense (${p['cost_per_account']:.0f} ÷ 60 = ${amort:.2f}/acct/mo). Cohort by opening month.")

        # 7 ICS Revenue
        s=blank(prs); title(s,"ICS Revenue"); pill(s,f"PTD · {wbm}")
        sub(s,"Selection: ICS-originated checking accounts; revenue program-to-date.")
        s.shapes.add_picture(a("ics_revpie.png"),Inches(0.5),Inches(1.55),Inches(12.3))
        logo(s); pagenum(s,7)
        notes(s,base+" PTD revenue by source: "+", ".join(f"{c['name']} ${c['amount']:,.0f}" for c in d['revenue']['components'])+f"; total ${d['revenue']['total']:,.0f}. Workbook 'Monthly Detail'.")

        # 8-13 monthly detail
        md=d["monthly_detail"]; icPTD=sum(md["interchange"]); nsPTD=sum(md["nsf_od"]); acc=md["cumulative_accounts"][-1]
        am=CH.acct_months(d)
        nsoPTD=sum(md["nsf_od"])+sum(md["other_fees"]); spPTD=sum(md["spread"])
        nso_nov=(md["nsf_od"][0]+md["other_fees"][0])
        SPREAD_DEF="Spread = 2.75% × avg month-end balance/account, summed monthly, net of interest paid."
        def mdslide(pg,ttl,subt,img,tiles,note,foot=None):
            s=blank(prs); title(s,ttl); sub(s,subt); s.shapes.add_picture(img,Inches(0.4),Inches(1.7),Inches(8.6))
            ty=1.9
            for big,lab in tiles: callout(s,9.3,ty,3.5,1.4,big,lab,big_size=26); ty+=1.6
            if foot: tb(s,0.5,6.5,12.3,0.5,foot,16,GREYT,False)
            logo(s); pagenum(s,pg); notes(s,note)
        IC_DEF="Interchange Income: Blended Rate × Debit Card Spend"
        mdslide(8,"Total Interchange Revenue",
                "Interchange revenue by cohort (opening month), program-to-date.",
                a("ics_ic_tot.png"),[(f"${icPTD:,.0f}","Interchange PTD"),(f"{acc:,}","ICS accounts")],
                base+" Interchange revenue by cohort. Workbook 'Monthly Detail' (revenue only).",foot=IC_DEF)
        mdslide(9,"Interchange Revenue per Account per Month",
                "Interchange revenue ÷ accounts opened ÷ months open, by cohort (e.g. Nov 25: $398.47 / 19 / 8 = $2.62).",
                a("ics_ic_pam.png"),[(f"${icPTD/am:.2f}","Blended / account / month"),(f"${icPTD/acc:.2f}","Per account, life-to-date")],
                base+" Interchange per account per month, cohort-normalized. Workbook 'Monthly Detail'.",foot=IC_DEF)
        mdslide(10,"Total NSF/OD & Other Fee Revenue",
                # Trailing "Revenue only — not item counts." pushed this to 13.06in in a
                # 12.10in box, wrapping onto the callout value; it is already in the notes.
                "NSF/OD fees plus other service charges by cohort (opening month), program-to-date.",
                a("ics_nsf_tot.png"),[(f"${nsoPTD:,.0f}","NSF/OD & Other PTD"),(f"{acc:,}","ICS accounts")],
                base+" NSF/OD + other service charges by cohort. Workbook 'Monthly Detail' (revenue only).")
        mdslide(11,"NSF/OD & Other Fees per Account per Month",
                f"(NSF/OD + other charges) ÷ accounts opened ÷ months open, by cohort (e.g. Nov 25: ${nso_nov:,.2f} / 19 / 8 = ${nso_nov/19/8:.2f}).",
                a("ics_nsf_pam.png"),[(f"${nsoPTD/am:.2f}","Blended / account / month"),(f"${nsoPTD/acc:.2f}","Per account, life-to-date")],
                base+" NSF/OD + other charges per account per month, cohort-normalized. Workbook 'Monthly Detail'.")
        mdslide(12,"Total Spread Revenue",
                "Spread revenue by cohort (opening month), program-to-date.",
                a("ics_spread_tot.png"),[(f"${spPTD:,.0f}","Spread PTD"),(f"{acc:,}","ICS accounts")],
                base+" Spread revenue by cohort. Workbook 'Monthly Detail'.",foot=SPREAD_DEF)
        mdslide(13,"Spread Revenue per Account per Month",
                f"Spread revenue ÷ accounts opened ÷ months open, by cohort (e.g. Nov 25: ${md['spread'][0]:,.2f} / 19 / 8 = ${md['spread'][0]/19/8:.2f}).",
                a("ics_spread_pam.png"),[(f"${spPTD/am:.2f}","Blended / account / month"),(f"${spPTD/acc:.2f}","Per account, life-to-date")],
                base+" Spread per account per month, cohort-normalized. Workbook 'Monthly Detail'.",foot=SPREAD_DEF)
        mdslide(14,"Revenue Composition by Month",
                "Monthly revenue per referral by source: spread (net of interest), interchange, NSF/OD, other.",
                a("ics_comp.png"),[(f"${sum(md['profit_contribution']):,.0f}","Profit contribution PTD"),(f"{acc:,}","ICS accounts")],
                base+" Monthly revenue composition by cohort. Workbook 'Monthly Detail'.")
        tot_pam=(sum(md["spread"])+sum(md["interchange"])+sum(md["nsf_od"])+sum(md["other_fees"]))/am
        mdslide(15,"Revenue per Account per Month by Source",
                "Blended revenue per account per month by source, life-to-date (cohort revenue ÷ account-months).",
                a("ics_bucketcmp.png"),[(f"${tot_pam:,.2f}","All sources / acct / mo"),(f"{acc:,}","ICS accounts")],
                base+" Per-account-per-month revenue compared across sources (spread, interchange, NSF/OD, other), life-to-date. Workbook 'Monthly Detail'.")

        # 14 Financial Summary
        fs=d["financial_summary"]; s=blank(prs); title(s,"ICS Financial Summary"); pill(s,f"PTD · {wbm}")
        sub(s,"Selection: ICS-originated checking accounts; figures program-to-date.")
        BT0=1.85                                    # callout block sits lower to balance against the selection text (Aaron 2026-07-24)
        panel=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(0.5),Inches(BT0),Inches(4.3),Inches(4.6))
        panel.fill.solid(); panel.fill.fore_color.rgb=LIGHT; panel.line.fill.background()
        try: panel.adjustments[0]=0.04
        except Exception: pass
        cpa=d["performance"]["cost_per_account"]; billed=cpa*fs["ics_accounts"]
        tb(s,0.75,BT0+0.1,3.8,0.4,"Program to Date",16,NAVY,True)
        yy=BT0+0.6
        # Just "Billed Expense" — the account count is dropped unconditionally
        # (Aaron, 2026-09-01). It was conditional on fits_one_line, which passed
        # counts that then wrapped anyway: 6,785 measured as fitting and still
        # ran onto the value beneath it. The count is already on this slide in
        # the "ICS Accounts" callout, so the label never needed to carry it and
        # a width test is not worth keeping for a figure that is redundant.
        _billed_lab="Billed Expense"
        _labels=[("Account Profit Contribution",f"${fs['account_profit_contribution']:,.0f}"),
                 ("Amortized Program Expense",f"${fs['total_program_expense']:,.0f}"),
                 ("Net Profit",f"${fs['net_profit']:,.0f}"),
                 (_billed_lab,f"${billed:,.0f}")]
        for lab,val in _labels:
            # Surface any other label that would wrap rather than let it collide unnoticed.
            if not fits_one_line(lab,3.9,14,family="Montserrat",min_pt=MIN_PT):
                print(f"WARNING ICS Financial Summary: label {lab!r} may wrap in its 3.9in box",
                      file=sys.stderr)
            tb(s,0.75,yy,3.9,0.4,lab,14,GREYT,False); tb(s,0.75,yy+0.32,3.9,0.5,val,20,NAVY,True); yy+=0.98
        tb(s,0.5,6.5,12.6,0.5,f"Amortized expense: ${cpa:,.0f} ÷ 60 months = ${cpa/60:.2f} per account per month × time open.",16,GREYT,False)
        for i,(big,lab) in enumerate([(f"{fs['ics_accounts']:,}","ICS Accounts"),(f"${fs['average_balance']:,.0f}","Average Balance"),(f"{roi_calc:.2f} : 1","Return on Investment")]):
            callout(s,5.15,BT0+i*1.55,3.3,1.35,big,lab,big_size=24)
        callout(s,8.7,BT0,4.15,4.6,_usd(pv_total),"Present Value",
                "of New ICS Accounts",fill=ORANGE,big_size=44)
        logo(s); pagenum(s,14)
        notes(s,base+f" Contribution ${fs['account_profit_contribution']:,.0f} − expense ${fs['total_program_expense']:,.0f} = net ${fs['net_profit']:,.0f}; "
                    f"{fs['ics_accounts']:,} accounts, avg balance ${fs['average_balance']:,.0f}. Present Value = ${pv_total:,.0f} (annual profit × {life_used:g} yr × accounts); ROI {roi_calc:.2f}:1 (recalculated, workbook ROI not used).")

        # 15 Comparisons (modeled on the CSI/Velocity ICS Review template)
        bm=d["benchmark"]; s=blank(prs); title(s,"Comparisons")
        # Both column headers share one size so the pair reads as a pair, and that
        # size steps down until the LONGER of the two fits on one line. At a flat
        # 18pt "Altamaha Bank and Trust Company Data" measured 5.28in in a 3.9in
        # box, wrapped to two lines and collided with the 19% below it — a long
        # client name is not an exception, it is just the widest case.
        _hl, _hr = "Velocity Clients' Average", f"{client} Data"
        # A long client name does not fit one line here — "Altamaha Bank and
        # Trust Company Data" is 4.64in of Montserrat 16pt in a 3.7in box — and
        # shrinking is not an option because enforce_min_font floors every run at
        # MIN_PT. So the header band grows upward instead, bottom-anchored, and
        # the values below it never move. Both columns move together so the pair
        # stays aligned. A name that fits keeps the original geometry exactly.
        _two = _needs_two_lines(_hl, _hr, usable_in=3.9-0.2)
        _htop, _hh = (1.15, 0.95) if _two else (1.4, 0.5)
        _anc = MSO_ANCHOR.BOTTOM if _two else MSO_ANCHOR.TOP
        tb(s,1.3,_htop,3.9,_hh,_hl,18,NAVY,True,align=PP_ALIGN.CENTER,anchor=_anc)
        tb(s,8.15,_htop,3.9,_hh,_hr,18,NAVY,True,align=PP_ALIGN.CENTER,anchor=_anc)
        def cfmt(v,f):
            if f=="usd0": return f"${v:,.0f}"
            if f=="pct0": return f"{v:.0f}%"
            if f=="pct1": return f"{v:.1f}%"
            # One decimal on BOTH sides of the row. "%g" prints the shortest form,
            # so the Velocity average rendered "6.9 Years" against a client
            # "6.21 Years" — two precisions in a row whose whole purpose is
            # comparing the pair (Aaron, 2026-08-30).
            if f=="years": return f"{v:.1f} Years"
            return f"{v:g}"
        yy=2.15
        for mm in bm["metrics"]:
            cval=pv_per_acct if mm["label"].startswith("Lifetime Value") else mm["client"]   # recomputed PV
            cap_pill(s,1.3,yy,3.9,0.78,cfmt(mm["velocity_avg"],mm["fmt"]),ORANGE)
            tb(s,5.3,yy-0.05,2.75,0.9,mm["label"],17,NAVY,False,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
            cap_pill(s,8.15,yy,3.9,0.78,cfmt(cval,mm["fmt"]),NAVY)
            yy+=1.06
        if bm.get("non_ics_close_rate_pct"):
            tb(s,1.3,yy+0.06,10.8,0.4,f"Note: your Non-ICS accounts' 12-month close rate = {bm['non_ics_close_rate_pct']:.1f}%.",14,GREYT,False)
        logo(s); pagenum(s,15)
        notes(s,base+f" {client} vs the Velocity ICS client average — openings/branch, lifetime value, 12-mo close rate (ICS {[x['client'] for x in bm['metrics'] if 'Close' in x['label']][0]:.2f}% vs Non-ICS {bm.get('non_ics_close_rate_pct',0):.2f}%), account life. Velocity averages are program-wide constants.")

    # optional mystery shop
    if (d.get("mystery_shop") or {}).get("include"):   # key can be present-but-null
        ms=d["mystery_shop"]; s=blank(prs); title(s,"Mystery Shop & Insights")
        for i,(big,lab,fill) in enumerate([(f"{ms['mystery_shops_ytd']}","Mystery Shops (YTD)",NAVY),
                                            (f"{ms['pass_rate_pct']}%","Pass Rate",ORANGE),
                                            (f"{ms['offered_referral_pct']}%","Offered a Referral",NAVY)]):
            callout(s,0.55+i*4.1,1.5,3.8,1.5,big,lab,fill=fill)
        logo(s); pagenum(s,16); notes(s,base+" Mystery shops YTD, pass rate, referral-offered rate. ICS Charts.")

    # Contact slide (built last so it lands at the very end, after Q&A). Every ICS deck has
    # one, and its card is the client's managing CSM (rpe_env.csm_contact, resolved above).
    from shapes import (contact_card_lines, contact_card_note, CONTACT_CARD_TOP,
                        CONTACT_CARD_W as cw, CONTACT_CARD_H)
    s=blank(prs); title(s,"Contact Us")
    contacts=[contact] + ([_program_contact] if _program_contact else [])
    ncc=len(contacts); gap=0.5; x0=(13.333-(ncc*cw+(ncc-1)*gap))/2
    _cstyle={"name":(26,WHITE,True),"role":(15,ORANGE,False),"phone":(17,WHITE,False),"email":(15,WHITE,False)}
    for i,cc in enumerate(contacts):
        l=x0+i*(cw+gap)
        card=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(l),Inches(CONTACT_CARD_TOP),Inches(cw),Inches(CONTACT_CARD_H))
        card.fill.solid(); card.fill.fore_color.rgb=NAVY; card.line.fill.background()
        try: card.adjustments[0]=0.05
        except Exception: pass
        shadow(card)
        for _f,_txt,_top,_hh in contact_card_lines(cc):
            _sz,_col,_b=_cstyle[_f]
            tb(s,l+0.35,_top,cw-0.7,_hh,_txt,_sz,_col,_b,align=PP_ALIGN.CENTER)
    logo(s); pagenum(s,99)
    notes(s,contact_card_note(contact) + (f" ICS program contact: {_program_contact['name']}." if _program_contact else ""))

    # ---- reorder: data slides move to the front; static education + Q&A stay last;
    # the contact slide (last-built data slide) goes to the very end ----
    lst=prs.slides._sldIdLst
    # now that every data slide exists, discard the template's demo slides
    # (entry AND relationship, so no orphan parts are serialised)
    for _el in _drop_els:
        _rid=_el.get(qn('r:id'))
        if _el in list(lst):
            lst.remove(_el)
        if _rid:
            try: prs.part.drop_rel(_rid)
            except KeyError: pass
    ids=list(lst)
    static_ids=[e for e in ids if e in _static_els]
    data_ids=[e for e in ids if e not in _static_els]
    tail=[]
    if data_ids: tail=[data_ids.pop()]   # contact slide (always built) -> very end
    for sid in ids: lst.remove(sid)
    for sid in data_ids+static_ids+tail: lst.append(sid)
    # invariant: every slide referenced exactly once
    _seen=[e.get(qn('r:id')) for e in list(lst)]
    if len(_seen)!=len(set(_seen)):
        raise SystemExit("ERROR: duplicate slide references in sldIdLst")
    # Renumber every kept slide part 1..N in deck order BEFORE anything else adds a slide.
    # The retained static slides still hold the template's partnames (slide22-slide27), and
    # python-pptx names a new slide slide<count+1>.xml. The Summit slide inserted below
    # therefore landed on slide27.xml — already a static's name — whenever this deck held 20
    # data slides: a full build with no Contact slide (1776 CoastHills CU, 2026-09-16), which
    # wrote slide27.xml twice and failed the package check. Sequential names leave count+1 free.
    prs.part.rename_slide_parts([e.get(qn('r:id')) for e in list(lst)])

    enforce_min_font(prs, MIN_PT)   # minimum size across the deck
    summit_slide.insert_summit_after_title(prs)   # Executive Summit after the title (all decks)

    # renumber the content-slide page boxes sequentially (skip cover/divider/full-bleed)
    n=0
    for sl in prs.slides:
        n+=1
        for sh in sl.shapes:
            if sh.has_text_frame and sh.left is not None and sh.top is not None:
                if abs(Emu(sh.left).inches-0.45)<0.2 and abs(Emu(sh.top).inches-7.04)<0.2 and sh.text_frame.text.strip().isdigit():
                    sh.text_frame.paragraphs[0].runs[0].text=str(n)
    # Per-title geometry contract, before fit_layout — the same call ARS makes.
    # No title in this deck carries a rule yet, so today this is a no-op; it is
    # wired now so the next layout fix lands in the contract instead of in one
    # deck (CLAUDE.md rule 2).
    import slide_geometry; slide_geometry.apply(prs)
    import fit_layout; fit_layout.fit(prs)   # clear number/logo, clamp off-slide (shared)
    prs.save(out); print("built",out,"->",len(prs.slides._sldIdLst),"slides")

if __name__=="__main__":
    _argv=[a for a in sys.argv[1:] if a!="--referrals-only"]
    # The client sheet resolves through rpe_env: a literal path still works, and
    # a bare `1705` or `1705_ics.json` is looked up under
    # RPE_DATA_ROOT/Inputs/VIP Data/ then the repo's data/ folder. Those JSONs
    # are real client data and are gitignored, so a fresh checkout on the other
    # machine has the code and none of the inputs (PRD criterion 1).
    from rpe_env import resolve_client_json
    build(json.load(open(resolve_client_json(_argv[0], "ics"), encoding="utf-8")), _argv[1], _argv[2],
          referrals_only="--referrals-only" in sys.argv)
