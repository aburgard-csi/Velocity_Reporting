#!/usr/bin/env python3
"""
build_ars_gen.py — client-agnostic ARS Executive Review renderer.

Clones the reference-derived ARS template (46 slides), swaps in the client's
computed values, charts, Lift Matrix, Product Mix slide, business take-rate,
and per-slide data-source notes.

Usage:
  build_ars_gen.py <base.pptx> <metrics.json> <base.json> <lift.json> \
                   <oddd_metrics.json> <charts_dir> <out.pptx> [odd_zip_or_csv]

Value-computation formulas reuse the arg-driven logic of build_gen.py /
build_gen_b.py / build_lift.py; find-strings/slide-indices/chart-partnames are
mapped to *this* template by semantics (see swap_map).
"""
import json, shutil, zipfile, os, sys, subprocess, datetime, re, tempfile, glob, csv, statistics
from collections import defaultdict
from pptx import Presentation
from pptx.util import Inches, Pt, Emu

BASE, METRICS, BASEJ, LIFTJ, ODDDJ, CHARTS, OUT = sys.argv[1:8]
ODD = sys.argv[8] if len(sys.argv) > 8 else None
HERE = os.path.dirname(os.path.abspath(__file__))
# Self-locating (2026-07-24 reorg): this file lives in build/ars_pipeline/, and the ARS
# helper scripts (render_lift/ticket_calc/ticket_chart/charts_gen/extract_*/metrics_gen/
# product_mix_slide) were consolidated into this same dir -> REF = HERE. BUILDDIR = build/
# (parent) for the shared post-processors restyle_fonts.py and
# strip_dead.py (build/ root). Override with RPE_BUILDDIR / RPE_REF.
BUILDDIR = os.environ.get("RPE_BUILDDIR") or os.path.abspath(os.path.join(HERE, os.pardir))
REF = os.environ.get("RPE_REF") or HERE
sys.path.insert(0, BUILDDIR)
sys.path.insert(0, HERE)
from rpe_env import use_font

# Slides whose own module wrote a source note. The blanket note pass below would
# otherwise overwrite them with a title-keyword guess, losing the population,
# column and scope the module actually knows (Aaron, 2026-08-29). Not "skip any
# slide that already has a note" — the template shell carries stale dummy-client
# notes that MUST be replaced.
_MODULE_NOTED = []
# Figure provenance. The swap gate below catches a swap that matched NOTHING;
# this catches two swaps that both landed and disagree — the Wellworth 1,077 vs
# 1,026 defect, where four slides filtered a historical mailing's responders
# through the current eligibility snapshot. Naming a measure is opt-in and only
# worth doing where the same measure reaches more than one slide.
import figures as _figs
from brand import NAVY as _BNAVY, ORANGE as _BORANGE, MUTED as _BMUTED

M = json.load(open(METRICS)); B = json.load(open(BASEJ)); L = json.load(open(LIFTJ)); O = json.load(open(ODDDJ))
# MM path = the lift matrix actually carries VALUES; else SM = monthly summary.
# Testing the list alone was wrong: an unpopulated Lift Matrix MM tab still yields
# row labels with all-None cells (1549 Wellworth), which read as truthy and routed
# a client with no lift matrix down the MM path — it then died on rev['26 Plus'].
MM = any(isinstance(v, (int, float)) for row in (L.get('matrix_rows') or [])
         for v in row[1:])
import datetime as _dt0
def _sm_mmyyyy(_v):
    try:
        _p=_v.strip().split(); return _dt0.datetime.strptime(_p[0][:3]+' '+_p[-1],'%b %Y').strftime('%m-%Y')
    except Exception: return _v
NAME = B['client']; ID = str(O.get('client', '')).strip()   # no client-name default; id comes from the data pack
ASSETS = tempfile.mkdtemp(prefix="ars_assets_")

# ------------------------------------------------------------------ derived values (from build_gen / build_gen_b)
def m2(x): return f"${x/1e6:.2f}M"
# Every number shown in a callout carries thousands separators (Aaron, 2026-08-27).
months = f"{B['months']:,}"; mailings = f"{B['mailings']:,}"
_nm_int = int(B['mailings'] or 0)
# "1 mailings" reads as a bug to the client. Use with {mailings} wherever the count is
# spoken rather than tabulated.
MAILING_W = "mailing" if _nm_int == 1 else "mailings"
MONTH_W = "month" if int(B['months'] or 0) == 1 else "months"
# start year: derived from the workbook's own data label, months inclusive. This was
# pinned to June 2026, which silently shifted START by a month on any other pull.
try:
    _last = datetime.datetime.strptime(B['data_label'].replace(" Data", "").strip(), "%B %Y").date()
except Exception:
    _last = datetime.date(2026, 6, 1)
_startkey = (_last.year*12 + (_last.month-1)) - (B['months']-1)
START = str(_startkey // 12)
prof = f"{B['profitability']:.1f} : 1"
ltd_rev = m2(B['ltd_revenue']); ltd_profit = m2(B['ltd_profit'])
cur_rev = f"${B['cur_revenue']:,.0f}"; cur_profit = f"${B['cur_profit']:,.0f}"
rev_sum12 = f"${B['monthly_rev_sum12']/1000:.0f}K"; rev_avg12 = f"${B['monthly_rev_avg12']/1000:.0f}K"
take = f"{M['take_hist_pct']:.1f}%"; take_new = f"{M['take_new_pct']:.1f}%"
n_elig = f"{O['funnel']['eligible']:,}"  # canonical ODD flag count (personal+business); metrics n_eligible is personal-only
rege = f"{M['rege_pct']:.1f}%"; rege_in = f"{M['rege_in']:,}"; rege_pool = f"{M['rege_pool']:,}"
rege_new = f"{M['rege_new_pct']:.1f}%"; rege_new_in = f"{M['rege_new_in']:,}"; rege_new_pool = f"{M['rege_new_pool']:,}"
# Mailing response now comes from the ODD (metrics_gen.mail_summary), not the workbook.
# The workbook's denominator isn't the mailed population, so the summary slide and the
# latest-mailer slide disagreed on the same drop — 16.3% vs 10.7% on 1549 (Aaron,
# 2026-08-20). Newest mailing first; totals are weighted on offers sent.
def _branch_label(b):
    """The branch label as-is — a name once the Charts 2026 file has supplied one, otherwise
    the ODD number. No "Br"/"Branch" prefix on either (Aaron, 2026-08-27)."""
    return str(b)


MS = M['mail_summary']; MST = M['mail_summary_total']
mail_resp = f"{MST[4]:.1f}%"
cf = B['swipespend_36'][0][2]; cl = B['swipespend_36'][-1][2]
cardg = 100*(cl-cf)/cf; card_growth = f"{cardg:+.1f}%"
cardverb = "grown" if cardg > 2 else ("held steady" if cardg > -2 else "declined")
card_range = f"({cf/1000:.1f}K → {cl/1000:.1f}K)"
jun_spend = B['swipespend_36'][-1][1]
# Year-on-year spend: compare the latest month against the SAME month a year
# earlier, derived from the series (was pinned to the literal 'Jun 2025', which
# IndexErrors on any client whose history doesn't reach it — e.g. 1549 Wellworth,
# whose series starts May 2026).
_ss = {x[0]: x[1] for x in B['swipespend_36']}
_last_lbl = B['swipespend_36'][-1][0]
_ld = datetime.datetime.strptime(_last_lbl, '%b %Y')
_yago = _ld.replace(year=_ld.year - 1).strftime('%b %Y')
jun25 = _ss.get(_yago)
if jun25:
    spend_yoy = f"{100*(jun_spend-jun25)/jun25:+.0f}%"
else:
    # not enough history for a YoY read — state it rather than render a number
    spend_yoy = "n/a"
    print(f"NOTE: no {_yago} in the spend series ({len(_ss)} months) — YoY spend reported as n/a")
monthly_spend = f"${jun_spend:.1f}M"

# lift matrix values (MM only)
nu_dda = top_dda = dist26 = lift_top = 0; dist_str = ""
if MM:
    rev = {n: (d, v) for n, d, v in L['revseg']}
    nu_dda = rev['NU'][1]; top_dda = rev['26 Plus'][1]
    dist26 = round(100*rev['26 Plus'][0]); lift_top = L['matrix_rows'][0][-1]
    dist_str = ', '.join(f"{n} {round(100*d)}%" for n, d, v in L['revseg'])

# latest mailer / movement / dot
lm = M['latest_mailing']; lmailed = f"{M['latest_mailed']:,}"; lresp = f"{M['latest_responders']:,}"; lrr = f"{M['latest_resprate']:.1f}%"
mv = {k: v for k, v in M['movement']}
fr = mv.get('First Response', M['movement'][0][1]); imp = mv.get('Improved', M['movement'][1][1])
tog = fr+imp; togpct = round(100*tog/M['latest_responders'])
# before/after
ba0 = M['before_after'][0]['m']; ba1 = M['before_after'][-1]['m']
sgain = round(100*(M['ba_spend_after']-M['ba_spend_before'])/M['ba_spend_before'])
mgain = round(100*(M['ba_spend_med_after']-M['ba_spend_med_before'])/max(1, M['ba_spend_med_before']))

def updown(a, b, words): return words[2] if abs(a-b) < 0.05*max(abs(b), 1) else (words[0] if a > b else words[1])

# ------------------------------------------------------------------ business take rate (from ODD, metrics_gen methodology)
def resolve_csv(src):
    """Extract and return the ODD .csv from an ODDD zip.

    Several ODDD zips also carry the raw monthly transaction file as a .csv, so
    select the ODD by name and only fall back to the largest file.
    """
    if src.lower().endswith('.csv'): return src
    tmp = tempfile.mkdtemp(prefix="oddcsv_")
    with zipfile.ZipFile(src) as z: z.extractall(tmp)
    cands = glob.glob(os.path.join(tmp, '**', '*.csv'), recursive=True)
    if not cands: raise SystemExit(f'ERROR: no .csv inside {src}')
    odd = [c for c in cands
           if '-odd' in os.path.basename(c).lower() or '_v2_' in os.path.basename(c).lower()]
    return odd[0] if odd else max(cands, key=os.path.getsize)


def odd_snapshot(hdr):
    """(latest Elig column, latest monthly token) for THIS extract.

    The snapshot month moves with every ODD pull — hardcoding it (this was
    'Jun26 Elig') makes the build KeyError the moment a new pull lands.
    """
    hdr = [str(c).strip() for c in hdr]
    key = lambda t: datetime.datetime.strptime(t, '%b%y')
    eligs = [c for c in hdr if re.match(r'^[A-Z][a-z]{2}\d{2} Elig$', c)]
    mons = [m.group(1) for m in
            (re.match(r'^([A-Z][a-z]{2}\d{2}) Sig #$', c) for c in hdr) if m]
    if not eligs or not mons:
        raise SystemExit('ERROR: ODD carries no "<Mon><yy> Elig"/"Sig #" columns')
    return (sorted(eligs, key=lambda c: key(c.split()[0]))[-1],
            sorted(mons, key=key)[-1])

# Both branch charts share take_branch_chart's geometry, so both need the same bar cap.
# charts_gen.c_take_branch reads take_branch[:BRANCH_CAP].
import chart_lib as _cl_cap
BRANCH_CAP = _cl_cap.BRANCH_CAP
BIZ = None
# Labels for the new-account (take-rate) window. Defaults match the template
# literals; overwritten below from the ODD snapshot so the label always states
# the window actually used.
NEWWIN_PILL = "07-2025 · 06-2026"
NEWWIN_TEXT = "Jul 2025 – Jun 2026"
AS_OF_LONG = "June 2026"
AS_OF_SHORT = "Jun 2026"
NEWWIN_LONG = "July 2025 – June 2026"
if ODD:
    import pandas as pd
    csvp = resolve_csv(ODD)
    ELIG_COL, LATEST_MON = odd_snapshot(
        pd.read_csv(csvp, skiprows=4, nrows=0, encoding='latin-1').columns)
    # new-account window = the trailing 12 months of THIS extract
    _lm = datetime.datetime.strptime(LATEST_MON, '%b%y')
    _end = (_lm.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) \
        - datetime.timedelta(days=1)
    _y, _m = _lm.year, _lm.month - 11
    while _m <= 0: _m += 12; _y -= 1
    _start = datetime.datetime(_y, _m, 1)
    NEWWIN_PILL = f"{_start:%m-%Y} · {_end:%m-%Y}"
    NEWWIN_TEXT = f"{_start:%b %Y} – {_end:%b %Y}"
    # Point-in-time label for every "as of" caption. The template carries the
    # REFERENCE client's month (June 2026) in a dozen captions the builder never
    # swapped, so Wellworth shipped "Monthly debit spend (June 2026)" and
    # "opt-in status as of June 2026" on a Jul 2026 extract (Aaron, 2026-08-28).
    AS_OF_LONG = f"{_lm:%B %Y}"      # July 2026
    AS_OF_SHORT = f"{_lm:%b %Y}"     # Jul 2026
    NEWWIN_LONG = f"{_start:%B %Y} – {_end:%B %Y}"
    print(f"ODD snapshot: {LATEST_MON} (elig col '{ELIG_COL}'); "
          f"new-account window {_start:%Y-%m-%d}..{_end:%Y-%m-%d}")
    frames = []
    for ch in pd.read_csv(csvp, skiprows=4, dtype=str, encoding='latin-1', on_bad_lines='skip', chunksize=100000):
        ch = ch.rename(columns=lambda c: c.strip())
        frames.append(ch[['Business?', ELIG_COL, 'Debit?', 'Date Opened', 'Branch']])
    d = pd.concat(frames, ignore_index=True)
    for c in d.columns: d[c] = d[c].fillna('').str.replace('\x00', '', regex=False).str.strip()
    d['do'] = pd.to_datetime(d['Date Opened'], format='%m/%d/%Y', errors='coerce')
    d['card'] = d['Debit?'].eq('Yes'); d['biz'] = d['Business?'].eq('Yes')
    d['new'] = (d['do'] >= pd.Timestamp(_start)) & (d['do'] <= pd.Timestamp(_end))
    be = d[d['biz'] & (d[ELIG_COL] == 'Yes')]
    bn = d[d['biz'] & d['new']]
    bh_take = round(100*be['card'].sum()/len(be), 1) if len(be) else 0
    bn_take = round(100*bn['card'].sum()/len(bn), 1) if len(bn) else 0
    g = bn.groupby('Branch').agg(cards=('card', 'sum'), tot=('card', 'size'))
    g['take'] = (100*g['cards']/g['tot']).round(0)
    # Cap at the eight largest, matching the personal chart (charts_gen.c_take_branch
    # takes take_branch[:8]). Business had no cap while sharing the same chart geometry,
    # so the x labels ran together — 19 bars on 1549, 37 on 1075 (Aaron, 2026-08-20).
    # Already sorted by size, and the caption says "largest branches".
    g = g[g['tot'] >= 5].sort_values('tot', ascending=False).head(BRANCH_CAP)
    BIZ = dict(hist=bh_take, new=bn_take, elig=int(len(bn)), nocard=int((~bn['card']).sum()),
               hist_elig=int(len(be)),
               branches=[(str(i), int(r['cards']), int(r['tot']), int(r['take'])) for i, r in g.iterrows()])
    print("BIZ:", BIZ)

# ------------------------------------------------------------------ render Lift Matrix + Ticket + Business chart
LIFT_PNG = os.path.join(ASSETS, 'lift.png'); SM_PNG = None
if MM:
    subprocess.run([sys.executable, os.path.join(REF, 'render_lift.py'), LIFTJ, LIFT_PNG], check=True)
else:
    import matplotlib as _mpl; _mpl.use('Agg'); import matplotlib.pyplot as _plt
    use_font("Carlito")
    from brand import NAVY as _NV, ORANGE as _OR, TICK as _TK
    _mr = B.get('monthly_rev_last12', []); _lab=[m for m,_ in _mr]; _val=[float(v or 0) for _,v in _mr]
    _avg=(sum(_val)/len(_val)) if _val else 0
    _fig=_plt.figure(figsize=(13.0,3.9)); _ax=_fig.add_subplot(111); _x=range(len(_val))
    _ax.bar(_x,_val,color=_NV,width=0.66)
    if _val: _ax.axhline(_avg,ls='--',color=_OR,lw=2,zorder=2)
    # Bar labels sit above their bar, so a bar near the average has its label
    # crossing the dashed avg line — the dash struck straight through "$284K",
    # "$282K" and "$298K" on Austin (Aaron, 2026-08-29). A white halo lets the
    # line pass BEHIND the number instead of through it; zorder keeps it there.
    _halo=dict(boxstyle='square,pad=0.12', facecolor='white', edgecolor='none')
    for _i,_v in enumerate(_val):
        _ax.text(_i,_v+ (max(_val)*0.02 if _val else 0), f"${_v/1000:.0f}K", ha='center',
                 va='bottom', color=_NV, fontsize=10, fontweight='bold',
                 bbox=_halo, zorder=5)
    _ax.set_xticks(list(_x)); _ax.set_xticklabels([(l.split()[0][:3]+" '"+l.split()[-1][2:]) if ' ' in l else l for l in _lab], fontsize=10)
    _ax.set_ylim(0, (max(_val)*1.20 if _val else 1)); _ax.get_yaxis().set_visible(False)
    for _sp in ['top','right','left']: _ax.spines[_sp].set_visible(False)
    _ax.spines['bottom'].set_color(_BMUTED); _ax.tick_params(colors=_TK,length=0)
    [_t.set_color(_NV) for _t in _ax.get_xticklabels()]
    # The avg label sits just ABOVE the dashed line, not centred on it. va='center'
    # drew the orange text straight through the dash (Aaron, 2026-08-29). The offset
    # is a share of the axis so it holds at any revenue scale.
    if _val:
        _ax.text(len(_val)-0.5, _avg + max(_val)*0.025, f"  avg ${_avg/1000:.0f}K",
                 color=_OR, fontsize=11, va='bottom', fontweight='bold')
    SM_PNG=os.path.join(ASSETS,'sm_monthly.png'); _fig.savefig(SM_PNG,dpi=170,facecolor='white',bbox_inches='tight',pad_inches=0.12); _plt.close(_fig)

TICKET_PNG = None
if ODD:
    tjson = os.path.join(ASSETS, 'ticket.json'); TICKET_PNG = os.path.join(ASSETS, 'ticket.png')
    subprocess.run([sys.executable, os.path.join(REF, 'ticket_calc.py'), csvp, tjson], check=True)
    subprocess.run([sys.executable, os.path.join(REF, 'ticket_chart.py'), tjson, TICKET_PNG], check=True)
    R = json.load(open(tjson))

BIZ_PNG = None
if BIZ and BIZ['branches']:
    import chart_lib   # SAME renderer as the personal take-rate chart (charts_gen image11)
    br = chart_lib.branch_order(BIZ['branches'])   # largest branches, ordered by number
    BIZ_PNG = os.path.join(ASSETS, 'biz_branch.png')
    # business = navy bars / orange dashed avg; identical geometry to personal (orange/navy)
    chart_lib.take_branch_chart(BIZ_PNG, [str(b[0]) for b in br], [b[3] for b in br],
                                BIZ['new'], _BNAVY, _BORANGE, 1383, 540)
    print("wrote", BIZ_PNG)

# ------------------------------------------------------------------ open deck
WORK = os.path.join(tempfile.gettempdir(), f'_{ID}_ars_work.pptx')
shutil.copy(BASE, WORK); prs = Presentation(WORK); S = list(prs.slides)

# --- Slide resolution by TITLE (project rule: titles, not indices) -------------
# Index-based access silently no-ops when the template gains/loses a slide: that is
# exactly how the Appendix swaps went stale (fixed 2026-07-25). SB() raises instead.
def SB(title):
    key = title.strip().lower()
    for sl in prs.slides:
        for sh in sl.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                if sh.text_frame.text.strip().lower().startswith(key): return sl
                break
    raise RuntimeError(f"slide not found by title: {title!r} — template changed?")

# --- Swap-miss tracking -------------------------------------------------------
# Every find-string that matches nothing is recorded; the build FAILS at the end.
# A miss means the template literal drifted from the builder — the deck would ship
# with the reference client's numbers, which is worse than a hard failure.
MISSES = []
def _miss(kind, needle):
    MISSES.append(f"{kind}: {needle[:90]}")

def frames(shapes):
    for sh in shapes:
        if sh.has_text_frame and sh.text_frame.text.strip(): yield sh
        if sh.shape_type == 6: yield from frames(sh.shapes)

def _slide_has(slide, title):
    for sh in frames(slide.shapes):
        if sh.text_frame.text.strip().startswith(title):
            return True
    return False


def repl(slide, mapping, optional=False):
    hit = {a: False for a in mapping}
    for sh in frames(slide.shapes):
        for para in sh.text_frame.paragraphs:
            full = "".join(r.text for r in para.runs); new = full
            for a, b in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
                if a in new: new = new.replace(a, b); hit[a] = True
            if new != full and para.runs:
                para.runs[0].text = new
                for r in para.runs[1:]: r.text = ""
    if not optional:
        for a, ok in hit.items():
            if not ok: _miss("repl", a)

def set_exact(slide, oldtext, newtext, left_lo=None, left_hi=None, measure=None):
    _figs.record(measure, newtext, slide)
    for sh in frames(slide.shapes):
        if sh.text_frame.text.strip() == oldtext:
            if left_lo is not None:
                lp = Emu(sh.left).inches if sh.left is not None else -1
                if not (left_lo <= lp <= left_hi): continue
            p = sh.text_frame.paragraphs[0]
            if p.runs:
                p.runs[0].text = newtext
                for r in p.runs[1:]: r.text = ""
            else: p.add_run().text = newtext
            return True
    _miss("set_exact", oldtext)
    return False

def set_shape_text(slide, needle, newtext, optional=False, measure=None):
    _figs.record(measure, newtext, slide)
    for sh in frames(slide.shapes):
        if needle in sh.text_frame.text:
            tf = sh.text_frame; lines = newtext.split("\n"); paras = tf.paragraphs
            for i, line in enumerate(lines):
                if i < len(paras):
                    p = paras[i]
                    if p.runs:
                        p.runs[0].text = line
                        for r in p.runs[1:]: r.text = ""
                    else: p.add_run().text = line
                else: tf.add_paragraph().add_run().text = line
            for j in range(len(lines), len(paras)):
                for r in paras[j].runs: r.text = ""
            return True
    if not optional: _miss("set_shape_text", needle)
    return False

def tables(slide): return [sh.table for sh in slide.shapes if sh.has_table]
def set_table(slide, rows, trim=False):
    """Write `rows` into the slide's first table.

    trim=True drops any template rows the client's data doesn't reach. Without it a
    client with fewer rows than the template ships the reference client's numbers in
    the remainder — 1549 Wellworth has one mailing and its Mailing Response Summary
    carried eleven of Union Financial's mailings below it (found 2026-08-20).
    """
    t = tables(slide)[0]
    for ri, row in enumerate(rows):
        if ri >= len(t.rows): break
        for ci, val in enumerate(row):
            if ci >= len(t.columns): break
            cell = t.cell(ri, ci); p = cell.text_frame.paragraphs[0]
            if p.runs: p.runs[0].text = str(val)
            else: p.add_run().text = str(val)
            for r in p.runs[1:]: r.text = ""
    if trim and len(rows) < len(t.rows):
        for tr in list(t._tbl.tr_lst)[len(rows):]:
            t._tbl.remove(tr)
    # Surplus COLUMNS are the same defect as surplus rows and had no guard: the loop
    # above writes only as many columns as the data has, so any extra template column
    # keeps the REFERENCE client's value. 1549 Wellworth has 5 activity months against
    # the template's 11, and its take-rate-by-branch table shipped Apr/May/Jun and a
    # second Cards/Elig/Take% block from Union Financial — the months appeared twice
    # and looked like a rendering artefact (Aaron, 2026-08-28). A partial column write
    # is never intentional, so this trims unconditionally.
    ncols = len(rows[0]) if rows else 0
    if ncols and ncols < len(t.columns):
        total_w = sum(c.width for c in t.columns)
        tbl = t._tbl
        for gc in list(tbl.tblGrid)[ncols:]:
            tbl.tblGrid.remove(gc)
        for tr in tbl.tr_lst:
            for tc in list(tr.tc_lst)[ncols:]:
                tr.remove(tc)
        # re-spread the original width so the table still fills its slot
        first = t.columns[0].width
        rest = max(1, ncols - 1)
        each = int((total_w - first) / rest)
        for ci, col in enumerate(t.columns):
            if ci: col.width = each
        for sh in slide.shapes:
            if sh.has_table and sh.table._tbl is tbl:
                sh.width = total_w
        print(f"set_table: trimmed {len(list(tbl.tblGrid)) and ''}"
              f"surplus template columns -> {ncols} cols")


def add_table_rows(slide, n):
    """Lengthen the slide's first table by n rows.

    New rows are cloned from a BODY row and inserted BEFORE the last row, because the
    last row is the orange Total: cloning it appended four more orange rows to the
    take-rate-by-branch table and the bottom half of the slide read as five totals
    (Aaron, 2026-08-28). Keeping the Total last also means set_table still writes it
    last. Banding is re-applied afterwards so the added rows alternate like the rest.
    """
    from copy import deepcopy
    t = tables(slide)[0]; tbl = t._tbl
    rows = tbl.tr_lst
    if len(rows) < 3:
        src, anchor = rows[-1], None
    else:
        src, anchor = rows[-2], rows[-1]        # a body row, inserted above the Total
    for _ in range(n):
        clone = deepcopy(src)
        if anchor is None:
            tbl.append(clone)
        else:
            anchor.addprevious(clone)
    _reband(t)
    return t


def _reband(t):
    """Restore alternating body fills after rows are cloned. Header (row 0) and the
    Total (last row) keep whatever the template gave them."""
    from copy import deepcopy
    from pptx.oxml.ns import qn          # bound as _qn further down; import locally
    rows = t._tbl.tr_lst
    if len(rows) < 4:
        return
    body = rows[1:-1]
    # the template's first two body rows carry the two banded fills
    fills = []
    for r in body[:2]:
        tc = r.tc_lst[1] if len(r.tc_lst) > 1 else r.tc_lst[0]
        pr = tc.find(qn('a:tcPr'))
        fills.append(deepcopy(pr) if pr is not None else None)
    if len(fills) < 2 or fills[0] is None or fills[1] is None:
        return
    for i, r in enumerate(body):
        want = fills[i % 2]
        for tc in r.tc_lst:
            old_pr = tc.find(qn('a:tcPr'))
            new_pr = deepcopy(want)
            if old_pr is not None:
                tc.remove(old_pr)
            tc.append(new_pr)

def add_table_columns(slide, n, widths=None):
    """Widen the slide's first table by n columns, cloning the last column's formatting.

    python-pptx has no add-column API, so the gridCol and each row's last cell are
    deep-copied — that keeps each row's own fill and font (header row stays a header).
    `widths` is the full list of column widths in inches, applied after the clone.
    """
    from copy import deepcopy
    t = tables(slide)[0]
    tbl = t._tbl
    for _ in range(n):
        tbl.tblGrid.append(deepcopy(tbl.tblGrid[-1]))
        for tr in tbl.tr_lst:
            tr.append(deepcopy(tr.tc_lst[-1]))
    if widths:
        for col, w in zip(t.columns, widths):
            col.width = Inches(w)
        # `sh.table` builds a fresh wrapper each access, so compare the XML element —
        # an `is` test on the wrapper never matches and silently leaves the frame narrow.
        for sh in slide.shapes:
            if sh.has_table and sh.table._tbl is tbl:
                sh.width = Inches(sum(widths))

def remove_shapes_with_text(slide, texts, left_min=None):
    for sh in list(frames(slide.shapes)):
        t = sh.text_frame.text.strip()
        if t in texts:
            if left_min is not None:
                lp = Emu(sh.left).inches if sh.left is not None else -1
                if lp < left_min: continue
            sh._element.getparent().remove(sh._element)

def fk(x): return f"${x/1000:,.0f}K"
def pc(v, t): return f"{round(100*v/t)}%" if t else "0%"

# ------------------------------------------------------------------ the two month labels
# Two different months, and the builder swapped neither — every 2026.08 ARS deck shipped
# the template's "Executive Review • July 2026" and "PTD · June 2026" (found 2026-08-20).
#   PRESENT_MONTH — the month the deck is presented, i.e. the period tag on the filename
#                   (Aaron, 2026-08-20: "title slide is the month we're presenting").
#   DATA_MONTH    — the workbook's own data label, which is what PTD figures run through.
# ICS and MRPC already label the title correctly; this is an ARS-only gap.
_per = os.environ.get("ARS_PERIOD") or ""
if not _per:
    _mper = re.search(r"(\d{4})\.(\d{2})", os.path.basename(OUT))
    _per = f"{_mper.group(1)}.{_mper.group(2)}" if _mper else ""
# No fallback. The reporting month comes from ARS_PERIOD or the output filename,
# or the build refuses.
#
# It is NOT the Executive Summit's month: a Summit runs a couple of times a year
# and only for attendees, while these are the MONTHLY client reviews — two
# different deliveries, and deriving one from the other would be wrong ten months
# out of twelve (Aaron, 2026-08-29). It is not the wall clock either: that is
# right only while a deck is built in the month it ships, and a rebuild later
# silently moved it.
try:
    PRESENT_MONTH = datetime.date(int(_per[:4]), int(_per[5:7]), 1).strftime("%B %Y")
except Exception:
    raise SystemExit("cannot resolve the presentation month — pass ARS_PERIOD=YYYY.MM or "
                     "name the output <id>-<yyyy.mm>-ARS-… (got %r)" % os.path.basename(OUT))
DATA_MONTH = B['data_label'].replace(" Data", "").strip()
print(f"months: presenting {PRESENT_MONTH} | data through {DATA_MONTH}")

# ============================ SLIDE 1 — title
set_shape_text(S[0], "Program Performance", "Program Performance", optional=True)  # no-op guard; may be absent
repl(S[0], {"Union Financial": NAME})
repl(S[0], {"Executive Review  •  July 2026": f"Executive Review  •  {PRESENT_MONTH}"})

# PTD pill — the same literal appears on several slides (Program Overview, Financial
# Performance, and both latest-mailer slides), so swap it deck-wide.
_ptd_hits = 0
for _sl in prs.slides:
    for _sh in _sl.shapes:
        if not _sh.has_text_frame: continue
        for _pp in _sh.text_frame.paragraphs:
            for _r in _pp.runs:
                if "PTD · June 2026" in _r.text:
                    _r.text = _r.text.replace("PTD · June 2026", f"PTD · {DATA_MONTH}")
                    _ptd_hits += 1
if not _ptd_hits:
    raise SystemExit("MISS: 'PTD · June 2026' pill not found — the template changed, "
                     "and a silent no-op would ship the template's month")
print(f"PTD pill -> PTD · {DATA_MONTH} ({_ptd_hits} shapes)")

# ============================ SLIDE 3 — agenda (ARS-only sections)
set_exact(S[2], "Mailing Insights", "Mailing Insights")
set_exact(S[2], "Response summary, movement, sustained activity, before vs. after", "Response summary, movement, sustained activity, before vs. after")
set_exact(S[2], "Debit Card & Reg E Review", "Debit Card & Reg E Review")
set_exact(S[2], "Take rate, swipes & spend, overdraft opt-in", "Take rate, swipes & spend, overdraft opt-in")
set_exact(S[2], "Program Performance", "Program Performance")
set_exact(S[2], "Overview, financial results, Monthly Summary, debit segmentation", "Overview, financial results, " + ("Monthly Summary — Last 12 Months" if MM else "Monthly Summary") + ", debit segmentation")

# ============================ SLIDE 6 — Program Overview
set_shape_text(S[5], "Union Financial has run Account Revenue Solution® for 226 months across 81 mailings since 2007.",
    f"{NAME} has run Account Revenue Solution® for {months} {MONTH_W} across {mailings} {MAILING_W} since {START}.")
set_exact(S[5], "8,920", n_elig)
set_exact(S[5], "71.0%", take)
set_exact(S[5], "36.3%", rege)
set_exact(S[5], "18.8%", mail_resp)
set_exact(S[5], "81", mailings)
set_shape_text(S[5], "•  Account Revenue Solution® has returned $5.69M in incremental profit program-to-date — a 5.7 : 1 profitability ratio.\n•  Card-holding accounts have grown over the last 36 months — 6,805 → 7,101 (+4.3%).\n•  Responders show durable behavior change: every recent mailing produced a positive monthly debit-spend increase per responder.",
    f"•  Account Revenue Solution® has returned {ltd_profit} in incremental profit program-to-date — a {prof} profitability ratio.\n"
    f"•  Card-holding accounts have {cardverb} over the last 36 months — {cf:,} → {cl:,} ({card_growth}).\n"
    f"•  Responders show durable behavior change: every recent mailing produced a positive monthly debit-spend increase per responder.")

# ============================ SLIDE 7 — Financial Performance
set_exact(S[6], "5.7 : 1", prof)
set_exact(S[6], "$6.89M", ltd_rev)
set_exact(S[6], "$5.69M", ltd_profit)
set_exact(S[6], "$57,270", cur_rev, left_lo=4.0, left_hi=6.5)
set_exact(S[6], "$51,569", cur_profit, left_lo=8.0, left_hi=10.0)   # "Profit This Month" tile (was chasing the revenue literal -> never matched; fixed 2026-07-25)
# The 2 : 1 sentence was a template literal the builder only swapped the ratio into, so a
# client below the threshold shipped "0.2 : 1 is well above the 2 : 1 threshold" (1549,
# 2026-08-20). Wording now follows the actual ratio.
_ratio = B['profitability']
if _ratio >= 2:
    _prof_line = f"•  Profitability of {prof} is well above the 2 : 1 threshold — there is no deferred billing on this program.\n"
else:
    _prof_line = (f"•  Profitability of {prof} is below the 2 : 1 threshold — the program is {months} months in, "
                  f"with revenue still building against program-to-date costs.\n")
set_shape_text(S[6], "•  Account Revenue Solution® has generated $6.89M in incremental revenue and $5.69M in incremental profit program-to-date.\n•  Profitability of 5.7 : 1 is well above the 2 : 1 threshold — there is no deferred billing on this program.\n•  The program has run 226 months across 81 mailings, with $57,270 in incremental revenue this month.",
    f"•  Account Revenue Solution® has generated {ltd_rev} in incremental revenue and {ltd_profit} in incremental profit program-to-date.\n"
    + _prof_line
    + f"•  The program has run {months} {MONTH_W} across {mailings} {MAILING_W}, with {cur_rev} in incremental revenue this month.")

# ============================ SLIDE 8 — Lift Matrix (MM) or Monthly Summary (SM)
if MM:
    repl(S[7], {"07-2025 · 06-2026": f"12-month lift window: {L['window']}"})
    # Title stays "Monthly Summary — Last 12 Months" on both paths (Aaron, 2026-08-20:
    # the revenue model doesn't change the title; clients aren't aware of other models).
    # The subtitle did leak the internal model name and claimed a trailing window the MM
    # slide doesn't draw, so it's replaced with what the matrix actually shows.
    set_shape_text(S[7], "Selection: monthly incremental revenue, most recent 12 months (SM revenue model).",
        "Selection: monthly incremental revenue per account by swipe segment.")
    set_shape_text(S[7], "Monthly incremental revenue averaged $53K over the last 12 months, totaling $632K in program contribution.",
        f"Per-account monthly value climbs from ${nu_dda:,.2f} (Non-User) to ${top_dda:,.2f} at 26+ swipes; "
        f"heavy users (26+) are {dist26}% of card accounts. The ARS Lift Matrix is the difference between segments — "
        f"e.g., Non-User → 26+ = ${top_dda:,.2f} – ${nu_dda:,.2f} = ${lift_top:,.2f} per account per month.")
else:
    _lab8=[m for m,_ in B.get('monthly_rev_last12',[])]
    _win8=(_sm_mmyyyy(_lab8[0])+" \u00b7 "+_sm_mmyyyy(_lab8[-1])) if _lab8 else ""
    set_exact(S[7], "Monthly Summary — Last 12 Months", "Monthly Summary — Last 12 Months")
    repl(S[7], {"07-2025 · 06-2026": _win8})
    set_shape_text(S[7], "Selection: monthly incremental revenue, most recent 12 months (SM revenue model).", "Selection: monthly incremental revenue, most recent 12 months (SM revenue model).")
    _fmtk=lambda _v: (f"${_v/1e6:.2f}M" if abs(_v)>=1e6 else f"${_v/1000:.0f}K")
    set_shape_text(S[7], "Monthly incremental revenue averaged $53K over the last 12 months, totaling $632K in program contribution.",
        f"Monthly incremental revenue averaged {_fmtk(B['monthly_rev_avg12'])} over the last 12 months, "
        f"totaling {_fmtk(B['monthly_rev_sum12'])} in program contribution.")

# ============================ SLIDE 9 — Debit Usage Segmentation table (with % cols)
st = M['swipe_tier']; tt = M['swipe_tier_total']
rows = [["Segment", "Accounts", "% of\nAccts", "Swipes", "% of\nSwipes", "Spend", "% of\nSpend", "MTD NSFs", "% of\nNSFs"]]
for seg, a, sw, sp, ns in st:
    rows.append([seg, f"{a:,}", pc(a, tt[0]), f"{sw:,}", pc(sw, tt[1]), fk(sp), pc(sp, tt[2]), f"{ns:,}", pc(ns, tt[3])])
rows.append(["Total", f"{tt[0]:,}", "100%", f"{tt[1]:,}", "100%", fk(tt[2]), "100%", f"{tt[3]:,}", "100%"])
set_table(S[8], rows)

# ============================ SLIDE 10 — Average Ticket
if TICKET_PNG:
    remove_shapes_with_text(S[9], {"529", "71.6%", "28.0%"}, left_min=9.0)
    w0 = R['win'][0]; w1 = R['win'][-1]; win_pretty = f"{w0[:3]}–{w1[:3]} 20{w1[3:]}"
    set_shape_text(S[9], "Selection: ARS-eligible personal accounts with debit activity. Left: average spend per swipe by monthly-swipe tier (3-mo avg, Apr–Jun 2026). Right: mailing responders, ticket before vs. after response.",
        f"Selection: ARS-eligible personal accounts with debit activity. Left: average spend per swipe by monthly-swipe tier "
        f"(3-mo avg, {win_pretty}). Right: mailing responders, ticket before vs. after response.")
    segs = R['segments']; light = segs[0]; heavy = segs[-1]
    set_shape_text(S[9], "Spend per swipe declines as usage rises — light users (1-5/mo) average $89 per swipe versus $44 for heavy users (26+/mo), around the $47 blend. For responders, ticket holds through response (mean $50→$50, median $45→$45) while monthly swipes rise 11.7→17.1: the gain is more transactions, not larger ones.",
        f"Spend per swipe declines as usage rises — light users ({light[0]}/mo) average ${light[1]:.0f} per swipe "
        f"versus ${heavy[1]:.0f} for heavy users ({heavy[0]}/mo), around the ${R['blended']:.0f} blend. "
        f"For responders, ticket holds through response (mean ${R['base_mean']:.0f}→${R['resp_mean']:.0f}, "
        f"median ${R['base_med']:.0f}→${R['resp_med']:.0f}) while monthly swipes rise {R['base_swpm']}→{R['resp_swpm']}: "
        f"the gain is more transactions, not larger ones.")

# ============================ SLIDE 12 — Mailing Response Summary
# Subtitle used to hardcode "Most recent 12 …" and name the revenue model. It now follows
# the mailing count, and drops the model name (Aaron 2026-08-20: clients aren't aware of
# other revenue models).
_nmail = len(MS)
# The "counted from the ODD" sentence is dropped from the slide face (Aaron,
# 2026-08-28) — the data source belongs in the speaker notes, which already name the
# ODD extract, its pull stamp and the workbook. It stays there; only the on-slide
# line loses it.
if _nmail <= 1:
    _sub12 = "The program's first mailing."
elif _nmail < int(mailings or 0):
    _sub12 = f"Most recent {_nmail} of the program's {mailings} mailings."
else:
    _sub12 = f"All {_nmail} mailings to date."
repl(S[11], {"Most recent 12 of the program's 81 mailings (MM revenue model).": _sub12})
# First column carries "Trailing 12-Mailing Total", which wraps to two lines under ~2.7in.
# Right edge stays left of the corner logo at 11.28in.
add_table_columns(S[11], 2, widths=[2.80, 1.55, 1.55, 1.40, 1.70, 1.45])
rows = [["Mailing", "Offers Sent", "Responders", "NU 5+", "Threshold Met", "Response %"]]
for _lab, _sent, _rsp, _nu, _th, _tot in MS:
    rows.append([_lab, f"{_sent:,}", f"{_rsp:,}", f"{_nu:.1f}%", f"{_th:.1f}%", f"{_tot:.1f}%"])
# A total over a single mailing just restates that mailing — skip the row.
if _nmail > 1:
    rows.append([f"Trailing {_nmail}-Mailing Total", f"{MST[0]:,}", f"{MST[1]:,}",
                 f"{MST[2]:.1f}%", f"{MST[3]:.1f}%", f"{MST[4]:.1f}%"])
set_table(S[11], rows, trim=True)

# ============================ SLIDE 14 — Latest Mailer
repl(S[13], {"ARS Response — Apr 2026 Mailer": f"ARS Response — {lm} Mailer"})
# The Wellworth defect lived exactly here: these three figures also appear in
# the captions below and on slide 15, and the Reach/Depth/Ranking/Sustained
# slides counted the SAME mailing's responders through a different cohort. Named
# so the sidecar can assert one value per measure across every slide.
set_exact(S[13], "3,154", lmailed, measure="mailed_latest_mailing")
set_exact(S[13], "258", lresp, measure="responders_latest_mailing")
set_exact(S[13], "8.2%", lrr, measure="resprate_latest_mailing")
repl(S[13], {"The Apr 2026 mailing drew 258 responders (8.2% of those mailed), led by the higher threshold tiers.":
             f"The {lm} mailing drew {lresp} responders ({lrr} of those mailed), led by the higher threshold tiers.",
             "Selection: the 3,154 accounts mailed in the Apr 2026 drop.":
             f"Selection: the {lmailed} accounts mailed in the {lm} drop."})
_figs.record("mailed_latest_mailing", lmailed, S[13], note="caption")
_figs.record("responders_latest_mailing", lresp, S[13], note="caption")

# ============================ SLIDE 15 — Movement
repl(S[14], {"ARS Response — Apr 2026 Movement": f"ARS Response — {lm} Movement",
             "Selection: the 258 responders to the Apr 2026 mailing, compared with their prior mailing (first-time, improved, held steady, or declined).":
             f"Selection: the {lresp} responders to the {lm} mailing, compared with their prior mailing (first-time, improved, held steady, or declined).",
             "70 were first-time responders (no prior response) and 72 improved their tier — together 55% of the 258 responders moved up or in for the first time.":
             f"{fr:,} were first-time responders (no prior response) and {imp:,} improved their tier — together {togpct}% of the {lresp} responders moved up or in for the first time."})
_figs.record("responders_latest_mailing", lresp, S[14], note="caption")

# ============================ SLIDE 16 — Transaction Increase (dot)
repl(S[15], {"Selection: ARS responders (3,030).": f"Selection: ARS responders ({M['dot_n']:,})."})
_figs.record("dot_n", f"{M['dot_n']:,}", S[15], note="selection line")
set_exact(S[15], "+10.2", f"+{M['dot_mean']}")
set_exact(S[15], "14.7", f"{M['dot_std']}")
set_exact(S[15], "+5", f"+{M['dot_median']:.0f}")
repl(S[15], {"Half clear their goal by 5+ transactions in the month after the offer and the average by 10, with a long tail of heavy over-performers (156 at +40 or more).":
             f"Half clear their goal by {M['dot_median']:.0f}+ transactions in the month after the offer and the average by {M['dot_mean']:.0f}, with a long tail of heavy over-performers ({M['dot_tail40']} at +40 or more)."})

# ============================ SLIDE 17 — Sustained Respondent Activity
# The window and the benchmark were both template text that no swap touched, so every client
# shipped the reference client's "(Apr–Jun 2026)" and the wrong benchmark. Sustained is
# measured against the ask the responder ANSWERED, over the months AFTER their mailing —
# the response month itself is 100% by definition (Aaron, 2026-08-28).
_sw = M.get('sustained_window', 0)
_swtxt = ("the months after each mailing" if _sw > 1 else
          "the month after each mailing" if _sw == 1 else
          "the months after each mailing (no post-mailing month yet)")
repl(S[16], {"their first-offer activity goal over the latest 3 months (Apr–Jun 2026)":
             f"the activity goal they responded to, over {_swtxt}"})
repl(S[16], {"last bar not yet mature.":
             "a mailing with no month after it yet reads 100% by definition — "
             "attrition can only appear from the following month."}, optional=True)

# ============================ SLIDE 18 — Before/After Mean
_baw = M.get('ba_window_months', 3)
_bawm = f"{_baw} month" + ("s" if _baw != 1 else "")   # a young program can fall back to 1
repl(S[17], {"$644/mo before vs $1,027 after (+59%)": f"${M['ba_spend_before']:,}/mo before vs ${M['ba_spend_after']:,} after (+{sgain}%)",
             "Mailings Oct 2023 – Apr 2026.": f"Mailings {ba0} – {ba1}.",
             # Windows are symmetric now (3 before vs 3 after); the old caption claimed the
             # gain held across every later month, which the chart no longer measures.
             "held across all later months":
             f"held through the {_bawm} after",
             "3-month pre-mailing baseline vs. every month after the mailing (through June 2026)":
             f"{_baw}-month pre-mailing baseline vs. the {_bawm} after the mailing"})
# ============================ SLIDE 19 — Before/After by Offer Group
# Was the median twin of slide 18. The deck now reports ONE statistic — the mean —
# and splits it by the offer that was mailed instead (Aaron, 2026-08-28): NU asks a
# non-user to start using the card, TH asks an existing user to reach a threshold,
# and pooling them hid which offer moved.
_nu = M['ba_split_headline']['nu']; _th = M['ba_split_headline']['th']
def _grpline(g, label):
    """A Non-User's baseline is near zero by definition, so a percentage off it is
    meaningless — Wellworth's NU cohort computes to +9,018% off a $13 baseline. Below a
    $25 baseline the line states the dollar movement instead (Aaron, 2026-08-28)."""
    if not g['n']:
        return f"{label}: no mailing in this window had enough respondents to report."
    base = f"{label}: ${g['before']:,}/mo before vs ${g['after']:,} after"
    if g['before'] < 25:
        return (f"{base} — a non-user starts from effectively no card spend, so the "
                f"movement is read in dollars, not as a percentage "
                f"({g['n']:,} respondent-observations).")
    return f"{base} ({'+' if g['gain'] >= 0 else ''}{g['gain']}%), {g['n']:,} respondent-observations."
set_shape_text(S[18], "On a median basis",
               _grpline(_nu, "Non-User respondents") + " " + _grpline(_th, "Threshold respondents"),
               optional=True)
repl(S[18], {"Responder Activity: Before vs After (Median)":
             "Responder Activity: Before vs After by Offer"}, optional=True)
repl(S[18], {"Mailings Oct 2023 – Apr 2026.": f"Mailings {ba0} – {ba1}."})
repl(S[18], {"median monthly debit spend (all responders) and median NSF/OD items among overdraft participants":
             "average monthly debit spend per responder, split by the offer mailed "
             "(Non-User vs Threshold)"}, optional=True)

# ============================ SLIDE 21 — Personal Take Rate
set_exact(S[20], "73.7%", take_new)
set_exact(S[20], "71.0%", take)
set_exact(S[20], "707", f"{M['take_new_total']:,}")
set_exact(S[20], "186", f"{M['take_new_nocard']:,}")
repl(S[20], {"Dashed line = 73.7% program average.": f"Dashed line = {take_new} program average."})

# ============================ SLIDE 22 — Business Take Rate
if BIZ:
    set_exact(S[21], "51.7%", f"{BIZ['new']:.1f}%")
    set_exact(S[21], "0.0%", f"{BIZ['hist']:.1f}%")
    set_exact(S[21], "178", f"{BIZ['elig']:,}")
    set_exact(S[21], "86", f"{BIZ['nocard']:,}")
    repl(S[21], {"Selection: business accounts opened Jul 2025 – Jun 2026 (new take rate) and all ARS-eligible business accounts (historical). 0 business accounts are ARS-eligible in the current book.":
                 f"Selection: business accounts opened {NEWWIN_TEXT} (new take rate) and all ARS-eligible business accounts (historical). {BIZ['hist_elig']} business accounts are ARS-eligible in the current book.",
                 "Take rate by branch (new business accounts, largest branches). Dashed line = 52% program average.":
                 f"Take rate by branch (new business accounts, largest branches). Dashed line = {BIZ['new']:.0f}% program average."})

# ---- take-rate window labels: the pill and the personal selection were template
# literals the builder never swapped, so every deck shipped the TEMPLATE's window
# (07-2025 · 06-2026) no matter which months the charts actually covered. Resolve
# by title and swap them to the window this extract used.
for _t in ("12-Month Eligible Take Rate — Personal",
           "12-Month Eligible Take Rate — Business",
           "12-Month Take Rate by Branch"):
    repl(SB(_t), {"07-2025 · 06-2026": NEWWIN_PILL}, optional=(NEWWIN_PILL == "07-2025 · 06-2026"))
repl(SB("12-Month Eligible Take Rate — Personal"),
     {"Selection: ARS-eligible personal accounts, trailing 12 months (Jul 2025 – Jun 2026).":
      f"Selection: ARS-eligible personal accounts, trailing 12 months ({NEWWIN_TEXT})."})

# ============================ SLIDE 23 — Take by branch table
tm = M['take_months']
# Branch rows are sized to the space on the slide, not to a fixed 6. The table sat at
# 2.35in with six branches and stopped at 5.07in, leaving roughly a third of the slide
# empty (Aaron, 2026-08-28). Rows are 0.34in and the footer/logo band starts at 6.78in,
# so fill down to 6.60in and add table rows for whatever the template doesn't have.
import chart_lib as _cl_ord
_TBL_TOP, _ROW_H, _TBL_BOTTOM = 2.35, 0.34, 6.60
_max_body = int((_TBL_BOTTOM - _TBL_TOP) / _ROW_H) - 2      # minus header and Total
_nbranch = min(len(M['take_branch_monthly']), max(6, _max_body))
tbm = _cl_ord.branch_order(M['take_branch_monthly'][:_nbranch])
rows = [["Branch"]+tm+["Cards", "Elig", "Take%"]]
for row in tbm:
    b = row[0]; monthly = row[1:1+len(tm)]
    rows.append([str(b)]+[str(x) for x in monthly]+[str(row[-3]), str(row[-2]), f"{row[-1]}%"])
tct = M['take_new_cards']; tet = M['take_new_total']
rows.append(["Total (all branches)"]+[str(x) for x in M['take_col_totals']]+[str(tct), str(tet), f"{round(100*tct/tet)}%"])
_have = len(tables(S[22])[0].rows)
if len(rows) > _have:
    add_table_rows(S[22], len(rows) - _have)
    print(f"take-by-branch: grew table {_have} -> {len(rows)} rows ({len(tbm)} branches)")
set_table(S[22], rows, trim=True)
repl(S[22], {"six largest branches shown": f"{len(tbm)} largest branches shown"}, optional=True)
# The monthly COLUMNS span the activity months this extract carries, which is not the
# same as the 12-month new-account window. Wellworth's caption read "monthly Aug 2025 –
# Jul 2026" above five columns of Mar–Jul (Aaron, 2026-08-28).
if tm:
    # NB this runs BEFORE the as-of caption pass, so the needle is still the TEMPLATE's
    # literal, not NEWWIN_TEXT. Replacing it here also stops the later pass touching it.
    _cspan = f"{tm[0]} – {tm[-1]} 20{LATEST_MON[3:]}"
    _plural = "s" if len(tm) != 1 else ""
    repl(S[22], {"monthly Aug 2025 – Jun 2026;":
                 f"monthly {_cspan} ({len(tm)} month{_plural} of activity in this extract);"},
         optional=True)

# ============================ SLIDE 24 — Swipes & Spend
set_exact(S[23], "+4.3%", card_growth)
repl(S[23], {"(6.8K → 7.1K)": card_range})
set_exact(S[23], "$9.3M", monthly_spend)
set_exact(S[23], "+11%", spend_yoy)

# ============================ SLIDE 25 — NSF/OD
set_exact(S[24], "2,360", f"{M['nsf_last_items']:,}")
set_exact(S[24], "725", f"{M['nsf_last_accts']:,}")
# The two dated tile captions here are NOT reached by the as-of pass: "(June)" has
# no year and "(Jun 25 \u2192 Jun 26)" uses two-digit years, so both slipped past the
# stale-caption gate and shipped the reference client's months. They are swapped
# from the snapshot and from the window the YoY figure actually compared.
repl(S[24], {"NSF/OD (June)": f"NSF/OD ({AS_OF_LONG})"})
_nsf_yoy = M.get('nsf_yoy')
_nsf_win = M.get('nsf_yoy_window')
if _nsf_yoy is None:
    # Stated, never zeroed: this extract carries no same-month row a year back.
    print("!! NSF/OD: no same-month-a-year-earlier row in this extract "
          "(%d months) — the Items YoY tile reads n/a" % len(M['nsf_series']))
    set_exact(S[24], "-1%", "n/a")
    repl(S[24], {"(Jun 25 \u2192 Jun 26)": "(no prior year in extract)"})
else:
    set_exact(S[24], "-1%", f"{'+' if _nsf_yoy>=0 else ''}{_nsf_yoy}%")
    repl(S[24], {"(Jun 25 \u2192 Jun 26)": f"({_nsf_win[0]} \u2192 {_nsf_win[1]})"})

# ============================ SLIDE 27 — Reg E all
repl(S[26], {"all open personal accounts holding a debit card (6,192)": f"all open personal accounts holding a debit card ({rege_pool})",
             "36.3% of open personal debit-card holders are opted in to overdraft — 2,247 of 6,192.":
             f"{rege} of open personal debit-card holders are opted in to overdraft — {rege_in} of {rege_pool}.",
             "branches with 40+ eligible accounts). Dashed line = 36.3% overall.":
             f"branches with 40+ eligible accounts). Dashed line = {rege} overall."})

# ============================ SLIDE 28 — Reg E new
reldir = updown(M['rege_new_pct'], M['rege_pct'], ("above the book", "below the book", "in line with the book"))
repl(S[27], {"opened July 2025 – June 2026 and still open (519)": f"opened July 2025 – June 2026 and still open ({rege_new_pool})",
             "New-account opt-in runs below the book: 20.0% of accounts opened in the last 12 months — 104 of 519.":
             f"New-account opt-in runs {reldir}: {rege_new} of accounts opened in the last 12 months — {rege_new_in} of {rege_new_pool}.",
             # the branch-chart caption states what the chart plots and nothing else
             "Dashed line = 20.0% overall.": f"Dashed line = {rege_new} overall."})
# The template used to editorialise here — "Lower-staffed branches lag; higher-touch
# branches lead on new-account opt-in." The ODD carries no staffing or contact data, so
# neither half of that could be shown; it shipped on every ARS deck (Aaron, 2026-08-28,
# FNB&T 1537). Both templates are fixed, and this sweep catches a re-seeded reference deck
# that brings the sentence back — the needle above misses first, which is the warning that
# it did.
repl(S[27], {"Lower-staffed branches lag; higher-touch branches lead on new-account opt-in.":
             f"Dashed line = {rege_new} overall."}, optional=True)

# ============================ SLIDE 29 — Reg E vintage
vpool = f"{M['rege_vintage_pool']:,}"; v = M['rege_vintage']; first = v[0]; last = v[-1]
trend = "rises with each newer vintage" if last[2] > first[2]+3 else ("falls with each newer vintage" if last[2] < first[2]-3 else "is fairly even across vintages")
repl(S[28], {"open consumer debit-card holders (6,192)": f"open consumer debit-card holders ({vpool})",
             "Opt-in falls with each newer vintage — 44% (pre-2018) to 18% (2026); overdraft participants opt in at similar or higher rates.":
             f"Opt-in {trend} — {first[2]}% ({first[0].lower()}) to {last[2]}% ({last[0]}); overdraft participants opt in at similar or higher rates."})

# ============================ SLIDE 30 — Key Takeaways
bb = M['rege_branch'][0]
set_shape_text(S[29], "• 226 months, 81 mailings; 5.7 : 1 profitability\n• $5.69M incremental profit program-to-date\n• 18.8% recent mailing response\n• Consistent response across 81 mailings since 2007",
    # "Consistent response across 1 mailings" — a consistency claim needs more than one
    # mailing to stand on. One-mailing programs state the mailing instead (2026-08-20).
    f"• {months} {MONTH_W}, {mailings} {MAILING_W}; {prof} profitability\n• {ltd_profit} incremental profit program-to-date\n• {mail_resp} recent mailing response\n"
    + (f"• First mailing dropped {MS[-1][0]}" if _nm_int <= 1
       else f"• Consistent response across {mailings} {MAILING_W} since {START}"))
set_shape_text(S[29], "• 71.0% overall take rate\n• New-account take rate 73.7%\n• Card base +4.3% over 36 months\n• Monthly spend $9.3M",
    f"• {take} overall take rate\n• New-account take rate {take_new}\n• Card base {card_growth} over 36 months\n• Monthly spend {monthly_spend}")
set_shape_text(S[29], "• 36.3% opt-in (personal accounts)\n• Best branches ~49% (Branch 4 49%)\n• Opportunity at low-opt-in branches\n• New-account opt-in 20.0%",
    f"• {rege} opt-in (personal accounts)\n• Best branches ~{bb[3]}% ({_branch_label(bb[0])} {bb[3]}%)\n• Opportunity at low-opt-in branches\n• New-account opt-in {rege_new}")

# ============================ SLIDE 31 — Q&A
repl(S[30], {"Union Financial": NAME})

# ============================ SLIDE 33 — Reach
set_exact(SB("Program Reach"), "3,030", f"{M['reach_total']:,}", measure="reach_total")
set_exact(SB("Program Reach"), "~178", f"~{M['reach_perml']}")
# ============================ SLIDE 34 — Depth
repl(SB("Depth of Engagement"), {"50.7% of responders (1,536 customers) have responded to two or more mailings":
             f"{M['depth_repeat_pct']:.1f}% of responders ({M['depth_repeat']:,} customers) have responded to two or more mailings"})
# ============================ SLIDE 35 — Age
u25 = M['age_u25_rate']; o65 = M['age_o65_rate']
if M.get('age_missing'):
    # DOB absent from this client's extract — state that plainly. NEVER a phantom 0%
    # (CLAUDE.md: no slide is dropped and no zero is invented; this is a sourcing task).
    agetxt = ("Date of birth is not carried in this client's data extract, so the age profile "
              "cannot be produced for this period. Response-rate analysis by age resumes once "
              "age is available in the extract.")
elif u25 > o65+5: agetxt = f"Response rates are highest among younger accounts — {u25}% of under-25 eligibles respond versus {o65}% of those 65+ — even though the eligible base skews older (55+ = {M['age_55plus_pct']}%)."
elif o65 > u25+5: agetxt = f"Response rates run higher among older accounts — {o65}% of those 65+ respond versus {u25}% of under-25 eligibles; the eligible base skews older (55+ = {M['age_55plus_pct']}%)."
else: agetxt = f"Response is fairly even across ages — {u25}% of under-25 eligibles respond versus {o65}% of those 65+; the eligible base skews older (55+ = {M['age_55plus_pct']}%)."
repl(SB("Responder Age Profile"), {"(8,768 with age on file)": ("(age not available in this extract)" if M.get('age_missing')
                                          else f"({M['age_base']:,} with age on file)"),
             "Response rates are highest among younger accounts — 58% of under-25 eligibles respond versus 27% of those 65+ — even though the eligible base skews older (55+ = 56%).": agetxt})

if M.get('age_missing'):
    # The sentence above was already correct, but the CHART was still drawn — an empty
    # axis with a row of twelve zeros under it (1537 FNB&T, whose DOB column is present
    # but blank on all 29,852 rows). CLAUDE.md is explicit: state the absence, do NOT
    # render a 0% or an empty chart. Remove the plot and let the sentence carry the
    # slide. The PNG is still generated and swapped in elsewhere — leaving the template
    # image in place would show the REFERENCE client's age chart, which is worse than
    # an empty one (Aaron, 2026-08-28).
    _age_sl = SB("Responder Age Profile")
    # the Selection line promised "Age mix — full eligible base vs. responders" for a
    # chart that is no longer on the slide; say what is actually shown instead
    # replace the WHOLE clause, including its trailing as-of date — leaving that behind
    # produced "No age mix is shown, as of July 2026". This runs before the as-of caption
    # pass, so the needle is still the template's June literal.
    repl(_age_sl, {"Age mix — full eligible base vs. responders, as of June 2026.":
                   "No age mix is shown."}, optional=True)
    _dropped = 0
    for _sh in list(_age_sl.shapes):
        if _sh.shape_type == 13 and Emu(_sh.top).inches < 6.0 and Emu(_sh.width).inches > 5.0:
            _sh._element.getparent().remove(_sh._element); _dropped += 1
    # lift the explanatory sentence into the space the chart occupied
    for _sh in frames(_age_sl.shapes):
        if _sh.text_frame.text.strip().startswith("Date of birth is not carried"):
            _sh.top = Inches(2.60); _sh.left = Inches(1.45); _sh.width = Inches(10.4)
    print(f"age profile: DOB absent — removed {_dropped} empty chart image(s), kept the statement")

# ============================ SLIDE 36 — Balance
rm_, nm_ = M['bal_resp_med'], M['bal_non_med']
if rm_ < nm_*0.9: baltxt = f"Responders carry lower balances than non-responders (median ${rm_:,} vs ${nm_:,}) — ARS engages transaction-reliant customers, not the highest-balance ones. (Eligibility = any account scored across the recent 12 mailings.)"
elif rm_ > nm_*1.1: baltxt = f"Responders carry modestly higher balances than non-responders (median ${rm_:,} vs ${nm_:,}); ARS engages transaction-active customers across the balance range. (Eligibility = any account scored across the recent 12 mailings.)"
else: baltxt = f"Responders and non-responders carry similar balances (median ${rm_:,} vs ${nm_:,}) — ARS engages transaction-reliant customers across the balance range. (Eligibility = any account scored across the recent 12 mailings.)"
repl(SB("Who Responds"), {"Responders carry lower balances than non-responders (median $887 vs $2,409) — ARS engages transaction-reliant customers, not the highest-balance ones. (Eligibility = any account scored across the recent 12 mailings.)": baltxt})

# ============================ SLIDE 38 — New by product
topp = M['new_products'][0]; toppct = round(100*topp[1]/M['new_total'])
set_exact(SB("New Accounts by Product"), "772", f"{M['new_total']:,}")
set_exact(SB("New Accounts by Product"), "94%", f"{M['new_stillopen_pct']}%")
set_exact(SB("New Accounts by Product"), "96%", f"{M['new_checking_pct']}%")
repl(SB("New Accounts by Product"), {"FREE CHECKING makes up 93% of new personal accounts; checking products lead new growth.":
             f"{topp[0]} makes up {toppct}% of new personal accounts; checking products lead new growth."})
# ============================ SLIDE 39 — New balances
nb, ob = M['new_chk_avgbal'], M['open_chk_avgbal']
if nb < ob*0.95: baltxt2 = f"New checking accounts open with smaller balances than the existing book (${nb:,} vs ${ob:,}); {M['new_chk_funded_pct']}% are funded above zero."
elif nb > ob*1.05: baltxt2 = f"New checking accounts open with balances above the existing book (${nb:,} vs ${ob:,}); {M['new_chk_funded_pct']}% are funded above zero."
else: baltxt2 = f"New checking accounts open near the existing book on balance (${nb:,} vs ${ob:,}); {M['new_chk_funded_pct']}% are funded above zero."
set_exact(SB("New Checking Balances"), "$9,456", f"${nb:,}")
set_exact(SB("New Checking Balances"), "$9,560", f"${ob:,}")
set_exact(SB("New Checking Balances"), "93%", f"{M['new_chk_funded_pct']}%")
repl(SB("New Checking Balances"), {"New checking accounts open near the existing book on balance ($9,456 vs $9,560); 93% are funded above zero.": baltxt2})
# ============================ SLIDE 40 — Penetration
ncd = f"{M['new_chk_debit_pct']:.1f}%"; ocd = f"{M['open_chk_debit_pct']:.1f}%"; gap = M['debit_pen_gap']
pendir = updown(M['new_chk_debit_pct'], M['open_chk_debit_pct'], ("well above", "modestly below", "in line with"))
if abs(gap) > 7 and gap > 0: pendir = "well above"
set_exact(SB("Debit Card Penetration"), "69.6%", ncd)
set_exact(SB("Debit Card Penetration"), "+3.6pt", f"{gap:+.1f}pt")
repl(SB("Debit Card Penetration"), {"vs. open book (66.0%)": f"vs. open book ({ocd})",
             "New personal checking accounts carry a debit card 69.6% of the time — well above the 66.0% rate on the existing book.":
             f"New personal checking accounts carry a debit card {ncd} of the time — {pendir} the {ocd} rate on the existing book."})
# ============================ SLIDE 41 — Usage
nap = f"{M['new_active_pct']:.1f}%"; bap = f"{M['book_active_pct']:.1f}%"
set_exact(SB("Debit Card Usage"), "71.6%", nap)
set_exact(SB("Debit Card Usage"), "$1,233", f"${M['new_spend_active']:,}")
set_exact(SB("Debit Card Usage"), "82%", f"{M['new_ever_swiped_pct']}%")
repl(SB("Debit Card Usage"), {"By their first year new personal cards are approaching the established book — 71.6% active in June versus 77.1%, at $1,233 spend per active card versus $1,623.":
             f"By their first year new personal cards are approaching the established book — {nap} active in June versus {bap}, at ${M['new_spend_active']:,} spend per active card versus ${M['book_spend_active']:,}."})
# ============================ SLIDE 42 — New swipe seg
seg0 = M['new_swipe_seg'][0]
# Population counts are written as a bare parenthetical everywhere else in the deck —
# "(64,230)", "(6,926)" — so these two were the only slides carrying "n=" notation.
# Dropping it removes the last of it from the client-facing pages and makes the two
# Selection lines match the other four (Aaron, 2026-08-28).
repl(SB("New-Account Debit Adoption"), {"(n=529)": f"({M['new_card_n']:,})"})
set_exact(SB("New-Account Debit Adoption"), "529", f"{M['new_card_n']:,}")
set_exact(SB("New-Account Debit Adoption"), "71.6%", f"{M['new_swipe_monthly_pct']:.1f}%")
set_exact(SB("New-Account Debit Adoption"), "28.0%", f"{M['new_swipe_heavy_pct']:.1f}%")
repl(SB("New-Account Debit Adoption"), {"New-account debit use is split: 28% are already heavy users (26+ swipes/mo) while 28% are non-users, with the rest across the light tiers.":
             f"New-account debit use is split: {M['new_swipe_heavy_pct']:.0f}% are already heavy users (26+ swipes/mo) while {seg0[2]:.0f}% are non-users, with the rest across the light tiers."})
# ============================ SLIDE 43 — New Account Summary
repl(SB("New Account Profile — Summary"), {"772 new personal accounts opened. FREE CHECKING makes up 93% of openings.":
             f"{M['new_total']:,} new personal accounts opened. {topp[0]} makes up {toppct}% of openings.",
             "69.6% of new checking accounts carry a debit card, well above the 66.0% rate on the existing book.":
             f"{ncd} of new checking accounts carry a debit card, {pendir} the {ocd} rate on the existing book.",
             "New checking accounts average $9,456 versus $9,560 on the book; 93% carry a balance above zero.":
             f"New checking accounts average ${nb:,} versus ${ob:,} on the book; {M['new_chk_funded_pct']}% carry a balance above zero.",
             "71.6% of new cards are active monthly versus 77.1% on the book, at $1,233 spend per active card.":
             f"{nap} of new cards are active monthly versus {bap} on the book, at ${M['new_spend_active']:,} spend per active card."})
if nb >= ob*0.95:
    repl(SB("New Account Profile — Summary"), {"Opening balances are near the book.": ("Opening balances exceed the book." if nb > ob*1.05 else "Opening balances are near the book.")})
# ============================ SLIDE 44 — Openings vs Closures
net = M['net_24']; permo = round(net/24)
if net >= 0:
    optxt = f"The personal book grew a net +{net} over the trailing 24 months — roughly +{permo} accounts per month, with openings outpacing closures across the period."
    netstr = f"+{net}"
else:
    optxt = f"The personal book declined a net {net} over the trailing 24 months — roughly {permo} accounts per month, with closures outpacing openings across the period."
    netstr = str(net)
set_exact(SB("Account Growth"), "+258", netstr)
set_exact(SB("Account Growth"), "1,548", f"{M['open_24']:,}")
set_exact(SB("Account Growth"), "1,290", f"{M['close_24']:,}")
repl(SB("Account Growth"), {"The personal book grew a net +258 over the trailing 24 months — roughly +11 accounts per month, with openings outpacing closures across the period.": optxt})
# ============================ SLIDE 45 — Retention
set_exact(SB("Account Retention"), "89%", f"{M['ret_1yr']:.0f}%")
set_exact(SB("Account Retention"), "72%", f"{M['ret_3yr']:.0f}%")   # "Retained at 3 years" tile (literal is 72%, not 82%; fixed 2026-07-25)
set_exact(SB("Account Retention"), "4.5 yr", f"{M['median_closed_life']:.1f} yr")
repl(SB("Account Retention"), {"First-year retention is 89%, easing to about 72% by year three. Half of closed accounts stayed open about 4.5 years — attrition is steady, not early.":
             f"First-year retention is {M['ret_1yr']:.0f}%, easing to about {M['ret_3yr']:.0f}% by year three. Half of closed accounts stayed open about {M['median_closed_life']:.1f} years — attrition is steady, not early."})
# ============================ SLIDE 46 — Bayes
if M['bayes_close_used'] < M['bayes_close_notused']:
    btxt = f"Early debit use tracks with better first-year retention — {M['bayes_close_used']:.1f}% close vs {M['bayes_close_notused']:.1f}% for non-users."
else:
    btxt = f"In this book, early debit use shows no protective link with first-year retention — early-active accounts close slightly more ({M['bayes_close_used']:.1f}% vs {M['bayes_close_notused']:.1f}%)."
repl(SB("First-Year Closure"), {"(n=1,466)": f"({M['bayes_n']:,})", "13.4% base rate": f"{M['bayes_prior']}% base rate",
             "Early debit use tracks with better first-year retention — 10.3% close vs 17.4% for non-users.": btxt})

# --- swap gate: every find-string must have matched something -----------------
if MISSES:
    import sys as _sys
    _sys.stderr.write("BUILD FAILED — %d text swap(s) matched nothing. The deck would carry the\n"
                      "reference client's numbers on those slides. Fix the builder/template pair:\n" % len(MISSES))
    for _m in MISSES: _sys.stderr.write("  MISS " + _m + "\n")
    raise SystemExit(2)

# ---- series-span captions ------------------------------------------------------
# These name a HISTORICAL RANGE and a month count, both template literals. Wellworth
# has three months of activity and its deck claimed "Jul 2023 – Jun 2026 (36 months)"
# (Aaron, 2026-08-28). Each is derived from the series it describes, so a short
# extract states its real span instead of the reference client's.
def _span(rows, i=0):
    """(first, last, n) as 'Mon YYYY' from a series whose element i is a 'Mon yy' label."""
    if not rows: return None
    def _pretty(lbl):
        t = str(lbl).strip()
        for fmt in ("%b %y", "%b %Y", "%b%y"):
            try: return datetime.datetime.strptime(t, fmt).strftime("%b %Y")
            except ValueError: pass
        return t
    return _pretty(rows[0][i]), _pretty(rows[-1][i]), len(rows)

_ss = _span(B.get('swipespend_36') or [])
if _ss:
    repl(SB("Debit Card Swipes & Spend") if any(_slide_has(x, "Debit Card Swipes & Spend") for x in prs.slides) else S[23],
         {"Monthly totals, Jul 2023 – Jun 2026 (36 months).":
          f"Monthly totals, {_ss[0]} – {_ss[1]} ({_ss[2]} month{'s' if _ss[2] != 1 else ''})."},
         optional=True)
    # the same 36 that appears in the narrative bullets
    for _sl in prs.slides:
        repl(_sl, {"over the last 36 months": f"over the last {_ss[2]} months",
                   "over 36 months": f"over {_ss[2]} months"}, optional=True)

_ns = _span(M.get('nsf_series') or [])
if _ns:
    repl(S[24], {"accounts with activity (line), Sep 2023 – Jun 2026.":
                 f"accounts with activity (line), {_ns[0]} – {_ns[1]}."}, optional=True)

_op = _span(M.get('openings') or [])
if _op:
    _n = _op[2]
    repl(SB("Account Openings & Closures") if any(_slide_has(x, "Account Openings & Closures") for x in prs.slides) else S[44],
         {"over the trailing 24 months (Jul 2024 – Jun 2026)":
          f"over the trailing {_n} months ({_op[0]} – {_op[1]})",
          "over the trailing 24 months —": f"over the trailing {_n} months —"}, optional=True)
    for _sl in prs.slides:
        repl(_sl, {"trailing 24 months": f"trailing {_n} months"}, optional=True)

# The Kaplan-Meier cohort window is a real constant (the span over which closings are
# reliably captured), not a stale literal — but it was retyped in the caption, so the
# two could drift apart silently. Swapped from the metric so they cannot.
if M.get('km_cut'):
    for _sl in prs.slides:
        repl(_sl, {"accounts opened since Jul 2021": f"accounts opened since {M['km_cut']}"},
             optional=True)

# ---- client logo on the Agenda slide -------------------------------------------
# Placed in the right-hand third, which is empty: the agenda's own text reaches at
# most 8.80in (measured against the bundled TTFs at the 16pt floor, longest
# sub-line in Montserrat), so a logo from 9.30in clears it. Sized to FIT rather than
# to a fixed width — client logos run from 1.50 to 4.47 in aspect, so a fixed width
# would stretch one client and overflow another. A missing logo is not an error.
try:
    import rpe_env as _rpe          # phase 2 imports it later; the agenda runs in phase 1
    _logo_p = _rpe.client_logo(ID)
    if _logo_p is None:
        print(f"agenda logo: none on file for client {ID} "
              f"(Inputs/Logos/{ID}.png) — slide built without it")
    else:
        _ag = SB("Agenda")
        _LZ_L, _LZ_W, _LZ_CY, _LZ_H = 9.30, 3.60, 3.75, 1.60   # zone: left, width, centre-y, height
        # crop to the ink first — the raw files carry white or transparent padding,
        # and fitting the canvas renders a right-sized box holding a tiny logo
        _logo_p = _rpe.trim_logo(_logo_p, ASSETS)
        _fit = _rpe.fit_box(_logo_p, _LZ_W, _LZ_H)
        if _fit:
            _lw, _lh = _fit
            _ag.shapes.add_picture(str(_logo_p),
                                   Inches(_LZ_L + (_LZ_W - _lw) / 2.0),
                                   Inches(_LZ_CY - _lh / 2.0),
                                   Inches(_lw), Inches(_lh))
            print(f"agenda logo: {os.path.basename(str(_logo_p))} placed {_lw:.2f}x{_lh:.2f}in")
except Exception as _e:
    print("!! agenda logo skipped:", repr(_e))

# ---- point-in-time caption pass -------------------------------------------------
# The template's captions carry the REFERENCE client's month. Slide-specific swaps
# above cover the numbers but not these date phrases, so a Jul 2026 extract shipped
# "Monthly debit spend (June 2026)" and "opt-in status as of June 2026" (Aaron,
# 2026-08-28). These phrases are point-in-time captions ONLY — a mailing month is
# never written this way, so rewriting them cannot corrupt a "Jun 2026 Mailer" label.
_ASOF_SWAPS = {
    "(June 2026)": f"({AS_OF_LONG})",
    "as of June 2026": f"as of {AS_OF_LONG}",
    "through June 2026": f"through {AS_OF_LONG}",
    "in June 2026": f"in {AS_OF_LONG}",
    "for June 2026": f"for {AS_OF_LONG}",
    "July 2025 – June 2026": NEWWIN_LONG,
    "July 2025 through June 2026": NEWWIN_LONG.replace(" – ", " through "),
    "Jul 2025 – Jun 2026": NEWWIN_TEXT,
    "Aug 2025 – Jun 2026": NEWWIN_TEXT,
    "Apr – Jun 2026": M["w3_label"].replace("\u2013", " – "),
    "Apr–Jun 2026": M["w3_label"],
}
_asof_hits = {k: 0 for k in _ASOF_SWAPS}
for _s in prs.slides:
    for _sh in frames(_s.shapes):
        for _para in _sh.text_frame.paragraphs:
            _full = "".join(r.text for r in _para.runs)
            _new = _full
            for _a, _b in sorted(_ASOF_SWAPS.items(), key=lambda kv: -len(kv[0])):
                if _a != _b and _a in _new:
                    _new = _new.replace(_a, _b); _asof_hits[_a] += 1
            if _new != _full and _para.runs:
                _para.runs[0].text = _new
                for _r in _para.runs[1:]: _r.text = ""
print("as-of caption pass: %s" % ({k: v for k, v in _asof_hits.items() if v} or "nothing to rewrite"))

prs.save(WORK)
print("phase1 text done")

# ================================================================= PHASE 2
import product_mix_slide
import excluded_accounts_slide
import rege_branch_slide
from PIL import Image as _PImg
import zipfile as _zf
STRIP = os.path.join(BUILDDIR, "strip_dead.py")   # shared post-processor, next to restyle_fonts.py

# ---- 2a. Regenerate Product Mix slide via a clean strip-then-add (avoids partname reuse) ----
# Phase decks go to a TEMP directory, not next to OUT.
#
# Two reasons. They were landing in the delivery folder, which holds finished
# decks only; and a build that died partway left them there, because cleanup ran
# only on the happy path. Worse on the CSI machine, where the mount allows
# creating and copying but NOT deleting — `rm` returns "Operation not
# permitted" — so no amount of cleanup would have removed them there.
# A temp dir is local, always deletable, and never inside Outputs.
_PHASE_DIR = tempfile.mkdtemp(prefix="ars_phase_")
_ob = os.path.basename(OUT)
_A = os.path.join(_PHASE_DIR, _ob + ".A.pptx")
_B = os.path.join(_PHASE_DIR, _ob + ".B.pptx")
_C = os.path.join(_PHASE_DIR, _ob + ".C.pptx")


def _clean_phase_files():
    """Drop the phase directory however the build ends."""
    import shutil as _shutil
    _shutil.rmtree(_PHASE_DIR, ignore_errors=True)


import atexit as _atexit
_atexit.register(_clean_phase_files)
prs.save(_A)                                   # phase-1 text deck (reference product mix at idx4)
p2 = Presentation(_A); _xml = p2.slides._sldIdLst
_xml.remove(list(_xml)[4])                     # orphan reference product-mix slide
p2.save(_B)
subprocess.run([sys.executable, STRIP, _B, _C], check=True)   # GC the orphan -> 45 clean slides
prs = Presentation(_C)
if ODD:
    try:
        _MODULE_NOTED.append(product_mix_slide.add_product_mix_slide(
            prs, ODD, ASSETS, before_title="Program Overview")[0])
        print("product mix slide regenerated from ODD")
    except Exception as e:
        print("!! product-mix regen failed:", repr(e))
    # Excluded Accounts sits directly after Product Mix: Product Mix shows what IS
    # eligible, this shows what ARS never sees and why.
    try:
        _s, _x = excluded_accounts_slide.add_excluded_accounts_slide(
            prs, ODD, ASSETS, after_title="Product Mix")
        _MODULE_NOTED.append(_s)
        print("excluded accounts slide built from ODD (%s eligible / %s excluded of %s)"
              % (f"{_x['elig_total']:,}", f"{_x['excluded_total']:,}", f"{_x['total']:,}"))
        if _x["flags"]:
            print("!! excluded accounts: unmapped status value(s) %s — resolve before "
                  "delivery" % ", ".join(_x["flags"]))
    except Exception as e:
        print("!! excluded-accounts slide failed:", repr(e))
# Reg E opt-in by branch — the table companion to the two Reg E branch charts.
try:
    _rs, _rn = rege_branch_slide.add_rege_branch_slide(
        prs, M, ASSETS, AS_OF_LONG, after_title="Reg E Opt-In — Opened")
    if _rs is not None:
        print(f"reg-e-by-branch slide built ({_rn} branches)")
except Exception as e:
    print("!! reg-e-by-branch slide failed:", repr(e))

# ---- 2b. Source note on every slide ----
# Per-client source strings — DERIVED from the data pack; never hardcode a client.
# Regression guard: this block previously defaulted to CoastLife 1705, which leaked
# CoastLife source notes into every client\'s deck. Each deck must name ITS OWN client.
import re as _re_src, datetime as _dt_src, os as _os_src
_odd_csv = str(O.get("source_file") or (os.path.basename(ODD) if ODD else "")).strip()
_m_src = _re_src.search(r"\((\d{6}_\d{6})\)", _odd_csv)
_pull = _m_src.group(1) if _m_src else ""
_lm = str(O.get("latest_month") or "").strip()
try: _snap = _dt_src.datetime.strptime(_lm, "%b%y").strftime("%b %Y")
except Exception: _snap = _lm or "latest"
# The note on slide 1 states the reporting month, and the COVER already renders
# that as PRESENT_MONTH (from ARS_PERIOD or the filename's <yyyy.mm>). Taking
# today's clock here made the two agree only while the deck was rebuilt in the
# month it was published — rebuild an August deck in October and the cover says
# August while its own note says October.
# Reformatted to the note's existing "Aug 2026" abbreviation so this fix changes
# the deck ONLY where the month was actually wrong, not everywhere.
_gen_month = _dt_src.datetime.strptime(PRESENT_MONTH, "%B %Y").strftime("%b %Y")
_hist = "Jul23-forward"
_mm = " MM" if MM else ""
_pull_txt = (", pull " + _pull) if _pull else ""
_elig_col = (_lm + " Elig") if _lm else "latest Elig"
ODD_SRC = _os_src.environ.get("ARS_ODD_SRC") or ("ODD extract %s %s (%s%s), %s snapshot" % (ID, NAME, _hist, _pull_txt, _snap))
_wb_file = _os_src.environ.get("ARS_WB_FILE", "").strip()
WB_SRC = _os_src.environ.get("ARS_WB_SRC") or (("ARS Workbook %s (%s)" % (ID, _wb_file)) if _wb_file else ("ARS Workbook %s — %s" % (ID, NAME)))
def _title_of(sl):
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""
def _note_for(t, idx):
    tl = t.lower()
    if idx == 0: return "Source: program metadata. Reporting month = generation month (%s)." % _gen_month
    if idx in (1,2): return "Source: standard ARS Executive Review front matter (static)."
    if "product mix" in tl: return "Source: %s — open personal/business accounts by product; ARS eligibility = latest '%s' = Yes." % (ODD_SRC, _elig_col)
    if "program overview" in tl or "financial performance" in tl: return "Source: %s — Executive Financials%s / All Months Rollup%s (PTD incremental revenue/profit, profitability, monthly incremental revenue). Data thru %s." % (WB_SRC, _mm, _mm, _snap)
    if "monthly summary" in tl: return "Source: %s — All Months Rollup / Executive Financials (monthly incremental revenue, most recent 12 months)." % WB_SRC
    if "lift matrix" in tl: return "Source: %s — Lift Matrix MM tab (12-month lift window; segments on 3-month average swipes); Revenue Segmentation block." % WB_SRC
    if "average ticket" in tl or "debit usage" in tl: return "Source: %s — debit swipes/spend by tier." % ODD_SRC
    if "mailing" in tl or "response" in tl or "movement" in tl or "transaction increase" in tl or "sustained" in tl or "responder activity" in tl: return "Source: %s — Mail Response Summary%s + %s mailing/response fields." % (WB_SRC, _mm, ODD_SRC)
    if "take rate" in tl or "debit card review" in tl or "swipes & spend" in tl or "nsf" in tl: return "Source: %s — debit take rate (personal/business/by branch), swipes & spend, NSF/OD." % ODD_SRC
    if "reg e" in tl: return "Source: %s — Reg E opt-in (standardized Opt In/Opt Out/Default); all personal / opened last 12 mo / by vintage." % ODD_SRC
    if "key takeaways" in tl: return "Source: summary of %s financials + %s metrics shown in this deck." % (WB_SRC, ODD_SRC)
    if "questions" in tl or "agenda" in tl or tl.strip()=="appendix": return "Source: section slide (static)."
    return "Source: %s — responder / new-account analytics; associational, not causal where noted." % ODD_SRC
_S2 = list(prs.slides)
_keep = {id(x) for x in _MODULE_NOTED}
_written = 0
for _i, _sl in enumerate(_S2):
    if id(_sl) in _keep:
        continue
    _sl.notes_slide.notes_text_frame.text = _note_for(_title_of(_sl), _i)
    _written += 1
print(f"source notes written: {_written} ({len(_keep)} kept from their own module)")

# Per-mailing respondent counts for the by-Offer slide. They used to sit under each
# x-axis label as "(n=...)", which was unreadable the moment a client had more than a
# handful of mailings (Sugar River 1038 has fifteen). The chart drops them; the notes
# keep them, so the figure behind every bar is still auditable (Aaron, 2026-08-28).
_bas = M.get('before_after_split') or []
if _bas:
    for _sl in _S2:
        if _title_of(_sl).startswith("Responder Activity: Before vs After by Offer"):
            _counts = "; ".join(f"{r['m']}: NU {r['nu']['n']:,} / TH {r['th']['n']:,}"
                                for r in _bas)
            _sl.notes_slide.notes_text_frame.text += (
                f" Respondents per mailing (Non-User / Threshold) — {_counts}.")
            print("by-offer slide: %d per-mailing respondent counts written to notes" % len(_bas))
            break

# ensure separation between bottom text and the page number (skip title+summit front matter)
_nudged = 0
for _si, _sl in enumerate(prs.slides):
    if _si <= 1:   # title (0) and Executive Summit (1) are exempt / not repositioned
        continue
    _num = None
    for _sh in _sl.shapes:
        if _sh.has_text_frame and _sh.left is not None and _sh.top is not None and _sh.width is not None:
            _t = _sh.text_frame.text.strip()
            if _t.isdigit() and Emu(_sh.top).inches > 6.6 and Emu(_sh.left).inches < 1.6 and Emu(_sh.width).inches < 1.3:
                _num = _sh; break
    if _num is None:
        continue
    _nl = Emu(_num.left).inches; _nr = _nl + Emu(_num.width).inches
    _nt = Emu(_num.top).inches;  _nb = _nt + Emu(_num.height).inches
    for _sh in _sl.shapes:
        if _sh._element is _num._element or not _sh.has_text_frame: continue   # element identity (pptx yields fresh wrappers)
        if None in (_sh.left, _sh.top, _sh.width, _sh.height): continue
        if not _sh.text_frame.text.strip(): continue
        _l = Emu(_sh.left).inches; _r = _l + Emu(_sh.width).inches
        _t2 = Emu(_sh.top).inches; _b = _t2 + Emu(_sh.height).inches
        if _l < _nr + 0.1 and _r > _nl - 0.05 and _t2 < _nb + 0.05 and _b > _nt - 0.15:
            _newl = _nr + 0.3
            # right-rail callouts (AUTO_SHAPE / tiles on the right half); keep the caption clear of them
            _rail = [Emu(_c.left).inches for _c in _sl.shapes
                     if _c.left is not None and _c.width is not None
                     and Emu(_c.left).inches > 8.5 and Emu(_c.width).inches < 4.2
                     and _c.top is not None and Emu(_c.top).inches > 1.2]
            _rightcap = (min(_rail) - 0.2) if _rail else 13.15
            _w = Emu(_sh.width).inches
            if _newl + _w > _rightcap:
                _sh.width = Inches(max(2.0, _rightcap - _newl))
            _sh.left = Inches(_newl)
            _nudged += 1
print("page-number separation nudges:", _nudged)

# STYLE.md: make the Swipes&Spend (24) and NSF (25) charts taller to use the space (charts re-rendered at ar 1.81)
for _idx in (23, 24):
    _sl = list(prs.slides)[_idx]
    for _sh in _sl.shapes:
        if _sh.shape_type == 13 and _sh.width is not None and Emu(_sh.width).inches > 5:
            _sh.left = Inches(0.6); _sh.top = Inches(1.5); _sh.width = Inches(8.9); _sh.height = Inches(4.9)
    print(f"slide {_idx+1} chart enlarged")


# reformat the two long date pills that overflow (Aaron 2026-07-15): Lift Matrix + Debit Usage
import datetime as _dt2
def _mmyyyy(_v):
    try:
        _p=_v.strip().split(); _d=_dt2.datetime.strptime(_p[0][:3]+" "+_p[-1], "%b %Y"); return _d.strftime("%m-%Y")
    except Exception: return _v
_ls=_mmyyyy(L.get("window_start","")); _le=_mmyyyy(L.get("window_end",""))
_lift_pill = (_ls+" \u00b7 "+_le) if (_ls and _le and "-" in _ls and "-" in _le) else L.get("window","")
_du_pill = "Avg"
try:
    _p=L.get("data_date","").strip().split(); _de=_dt2.datetime.strptime(_p[0][:3]+" "+_p[-1], "%b %Y")
    _m=_de.month-2; _y=_de.year
    while _m<1: _m+=12; _y-=1
    _du_pill = "Avg: %02d-%d \u00b7 %s" % (_m, _y, _de.strftime("%m-%Y"))
except Exception: pass
def _set_pill(_sh, _txt):
    _tf=_sh.text_frame; _p0=_tf.paragraphs[0]
    if _p0.runs:
        _p0.runs[0].text=_txt
        for _r in _p0.runs[1:]: _r.text=""
    else:
        _p0.add_run().text=_txt
    for _pp in _tf.paragraphs[1:]:
        for _r in _pp.runs: _r.text=""
for _sl in prs.slides:
    for _sh in _sl.shapes:
        if not _sh.has_text_frame: continue
        if _sh.left is None or _sh.top is None: continue
        if Emu(_sh.left).inches < 8 or Emu(_sh.top).inches > 1.3: continue   # only the top-right pill, never the selection subtitle
        _low=_sh.text_frame.text.lower()
        if "lift window" in _low:
            _set_pill(_sh, _lift_pill); print("lift pill ->", _lift_pill)
        elif "3-mo avg" in _low:
            _set_pill(_sh, _du_pill); print("debit-usage pill ->", _du_pill)

# QA finalize (part 0): agenda badge shadow, slide-14 selection->top, slide-12 table, eligible footnote
from pptx.oxml.ns import qn as _qn
from pptx.oxml import parse_xml as _pxml
from pptx.dml.color import RGBColor as _RGBc
_SH=('<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
     '<a:outerShdw blurRad="63500" dist="38100" dir="5400000" rotWithShape="0">'
     '<a:srgbClr val="000000"><a:alpha val="28000"/></a:srgbClr></a:outerShdw></a:effectLst>')
def _qin(v): return Emu(v).inches if v is not None else None
def _shadowsh(_sh):
    _spPr=_sh._element.spPr
    for _e in _spPr.findall(_qn('a:effectLst')): _spPr.remove(_e)
    _spPr.append(_pxml(_SH))
# universal callout drop shadow: every solid-filled callout/tile/pill/badge on every slide (STYLE.md)
for _sl in prs.slides:
    for _x in _sl.shapes:
        if _x.shape_type==1:
            try:
                if _x.fill.type is not None and _x.fill.fore_color is not None and _x.fill.fore_color.type is not None:
                    _shadowsh(_x)
            except Exception: pass
# Contact slide at the very end (Aaron 2026-07-16; mirrors the ICS Contact Us design)
try:
    _has_contact = any(
        any(sh.has_text_frame and sh.text_frame.text.strip()=="Contact Us" for sh in _s0.shapes)
        for _s0 in prs.slides)
    if _has_contact:
        raise RuntimeError("skip: template already carries the Contact slide")
    from pptx.enum.shapes import MSO_SHAPE as _MSH
    from pptx.enum.text import PP_ALIGN as _PA
    from pptx.dml.color import RGBColor as _RGBk
    _NAVYk=_RGBk(0x00,0x27,0x4C); _ORk=_RGBk(0xF4,0x7A,0x29); _WHk=_RGBk(0xFF,0xFF,0xFF)
    _blank=next((_ly for _ly in prs.slide_layouts if len(_ly.placeholders)==0), prs.slide_layouts[-1])
    _cs=prs.slides.add_slide(_blank)
    _b=_cs.shapes.add_textbox(Inches(0.5),Inches(0.28),Inches(12.33),Inches(0.9)); _p=_b.text_frame.paragraphs[0]; _r=_p.add_run(); _r.text="Contact Us"; _r.font.name="Montserrat"; _r.font.size=Pt(30); _r.font.bold=True; _r.font.color.rgb=_NAVYk
    _contacts=[{"name":"Aaron Burgard","role":"Client Service Manager","phone":"910-617-1984","email":"aaron.burgard@csiweb.com"}]
    _ncc=len(_contacts); _cw=5.6; _gap=0.5; _x0=(13.333-(_ncc*_cw+(_ncc-1)*_gap))/2
    def _ctb(_x,_y,_w,_h,_txt,_sz,_col,_bold):
        _t=_cs.shapes.add_textbox(Inches(_x),Inches(_y),Inches(_w),Inches(_h)); _pp=_t.text_frame.paragraphs[0]; _pp.alignment=_PA.CENTER; _rr=_pp.add_run(); _rr.text=_txt; _rr.font.name="Montserrat"; _rr.font.size=Pt(_sz); _rr.font.bold=_bold; _rr.font.color.rgb=_col
    for _i,_cc in enumerate(_contacts):
        _l=_x0+_i*(_cw+_gap)
        _card=_cs.shapes.add_shape(_MSH.ROUNDED_RECTANGLE,Inches(_l),Inches(1.95),Inches(_cw),Inches(3.55))
        _card.fill.solid(); _card.fill.fore_color.rgb=_NAVYk; _card.line.fill.background()
        try: _card.adjustments[0]=0.05
        except Exception: pass
        _shadowsh(_card)
        _ctb(_l+0.35,2.45,_cw-0.7,0.7,_cc["name"],26,_WHk,True)
        _ctb(_l+0.35,3.25,_cw-0.7,1.0,_cc["role"],15,_ORk,False)
        _ctb(_l+0.35,4.5,_cw-0.7,0.5,_cc["phone"],17,_WHk,False)
        _ctb(_l+0.35,5.02,_cw-0.7,0.5,_cc["email"],15,_WHk,False)
    _logo=os.path.join(BUILDDIR,"assets","logo.png")
    if os.path.exists(_logo): _cs.shapes.add_picture(_logo,Inches(11.28),Inches(6.78),Inches(1.7))
    _pn=_cs.shapes.add_textbox(Inches(0.45),Inches(7.04),Inches(0.7),Inches(0.32)); _pp=_pn.text_frame.paragraphs[0]; _rr=_pp.add_run(); _rr.text=str(len(prs.slides._sldIdLst)); _rr.font.name="Calibri"; _rr.font.size=Pt(11); _rr.font.bold=True; _rr.font.color.rgb=_NAVYk
    _cs.notes_slide.notes_text_frame.text="Source: CSI / Velocity Solutions contact information (static)."
    print("contact slide added")
except Exception as _e:
    print("contact slide skip:", repr(_e))

# ---------- Appendix: Branch Reference (Aaron, 2026-08-27) ----------------------------
# Charts and tables label branches by NUMBER because the names collide on an eight-bar
# chart. So the deck carries the mapping once, as the first slide of the Appendix, and the
# reader looks a number up there. Built only when the client's "<Client> Charts 2026" file
# actually supplied names (metrics_gen puts them in M['branch_names'] keyed by the SAME
# label the charts print, so the two can never disagree).
def add_branch_reference_slide(prs, pairs):
    if not pairs:
        return False
    from pptx.enum.text import PP_ALIGN as _PA, MSO_ANCHOR as _MA
    from pptx.dml.color import RGBColor as _RC
    _navy=_RC(0x00,0x27,0x4C); _grey=_RC(0x5A,0x66,0x70); _white=_RC(0xFF,0xFF,0xFF)
    _band=_RC(0xEE,0xF2,0xF7)

    def _t0(sl):
        for sh in sl.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                return sh.text_frame.text.strip().split("\n")[0]
        return ""
    app = next((sl for sl in prs.slides if _t0(sl).strip().lower()=="appendix"), None)
    if app is None:
        return False
    s = prs.slides.add_slide(app.slide_layout)
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)

    def _tb(x,y,w,h,text,size,color,bold,align=_PA.LEFT,font="Montserrat"):
        b=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
        tf=b.text_frame; tf.word_wrap=True; p0=tf.paragraphs[0]; p0.alignment=align
        r=p0.add_run(); r.text=text
        r.font.size=Pt(size); r.font.bold=bold; r.font.color.rgb=color; r.font.name=font
        return b
    _tb(0.5,0.28,12.3,0.9,"Branch Reference",26,_navy,True)
    _tb(0.5,1.12,12.3,0.5,
        "Branch numbers are used on the charts and tables in this deck. This slide maps them "
        "to branch names.",14,_grey,False,font="Calibri")

    # Balanced columns. BOTTOM keeps the block clear of the corner logo (top 6.78) and the
    # slide number — a single full-width table of 14 branches ran to 6.85 and collided.
    top=1.75; BOTTOM=6.70
    ncol=max(1,min(3,-(-len(pairs)//12)))
    per=-(-len(pairs)//ncol)
    cols=[pairs[i*per:(i+1)*per] for i in range(ncol)]
    cols=[c for c in cols if c]
    gap=0.35; total_w=12.3; cw=(total_w-gap*(len(cols)-1))/len(cols)
    rowh=min(0.32,(BOTTOM-top)/(per+1))
    fsz=11 if rowh>=0.28 else 9
    for ci,col in enumerate(cols):
        left=0.5+ci*(cw+gap)
        tbl=s.shapes.add_table(len(col)+1,2,Inches(left),Inches(top),
                               Inches(cw),Inches(rowh*(len(col)+1))).table
        tbl.columns[0].width=Inches(cw*0.28); tbl.columns[1].width=Inches(cw*0.72)
        for j,(hdr,val) in enumerate([("Branch","Name")]+list(col)):
            for k,txt in enumerate((hdr,val)):
                cell=tbl.cell(j,k); cell.text=str(txt)
                cell.margin_left=Inches(0.06); cell.margin_right=Inches(0.04)
                cell.margin_top=0; cell.margin_bottom=0
                cell.vertical_anchor=_MA.MIDDLE
                para=cell.text_frame.paragraphs[0]
                run=para.runs[0] if para.runs else para.add_run()
                run.font.size=Pt(fsz); run.font.name="Calibri"
                if j==0:
                    cell.fill.solid(); cell.fill.fore_color.rgb=_navy
                    run.font.color.rgb=_white; run.font.bold=True
                else:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb=_band if j%2==0 else _white
                    run.font.color.rgb=_navy
    try:
        s.notes_slide.notes_text_frame.text=(
            "Source: the client's \"Charts 2026\" workbook, Branch Results tab (Branch # / "
            "Branch Name). Charts and tables in this deck label branches by number; this "
            "slide is the lookup. Branches with no name in that file are not listed.")
    except Exception:
        pass

    # Place it immediately after the Appendix divider.
    from pptx.oxml.ns import qn as _q
    lst=prs.slides._sldIdLst
    def _el(sl):
        for e in lst:
            if prs.part.related_part(e.get(_q("r:id"))) is sl.part: return e
        return None
    src,tgt=_el(s),_el(app)
    if src is not None and tgt is not None:
        lst.remove(src); lst.insert(list(lst).index(tgt)+1, src)
    return True

try:
    if add_branch_reference_slide(prs, M.get("branch_names") or []):
        print(f"branch reference slide added ({len(M['branch_names'])} branches)")
except Exception as _e:
    print("branch reference slide skip:", repr(_e))

# Appendix after Contact (Aaron 2026-07-24): move the Contact slide just before the Appendix
# divider so the Appendix section follows the Contact slide in every deck that includes it.
try:
    _sids = prs.slides._sldIdLst; _els = list(_sids)
    def _t0(sl):
        for sh in sl.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                return sh.text_frame.text.strip().split("\n")[0]
        return ""
    _ap_i = next((i for i, sl in enumerate(prs.slides) if _t0(sl).strip().lower() == "appendix"), None)
    _ct_i = next((i for i, sl in enumerate(prs.slides)
                  if any(sh.has_text_frame and sh.text_frame.text.strip() == "Contact Us" for sh in sl.shapes)), None)
    if _ap_i is not None and _ct_i is not None and _ct_i > _ap_i:
        _cel = _els[_ct_i]; _sids.remove(_cel); _sids.insert(_ap_i, _cel)
        print("reordered: Contact now precedes the Appendix section")
except Exception as _e:
    print("appendix-after-contact skip:", repr(_e))

for _sl in prs.slides:
    _shp=list(_sl.shapes)
    _titles=[x.text_frame.text.strip() for x in _shp if x.has_text_frame and x.text_frame.text.strip()]
    if any(("Mailer" in t and "Response" in t) for t in _titles):
        for _x in _shp:
            if _x.has_text_frame and _x.text_frame.text.strip().lower().startswith("selection: the") and _x.top is not None and _qin(_x.top)>5:
                _x.left=Inches(0.5); _x.top=Inches(1.12); _x.width=Inches(12.3); _x.height=Inches(0.5)
            if _x.has_text_frame and "mailing drew" in _x.text_frame.text and _x.left is not None:
                _x.width=Inches(max(3.0, 11.1-_qin(_x.left)))
        # rebalance: align left tiles to the chart's vertical span; give the chart title room
        for _x in _shp:
            if _x.has_text_frame and _x.text_frame.text.strip()=="Responders by tier":
                _x.left=Inches(4.7); _x.top=Inches(1.68); _x.width=Inches(7.8); _x.height=Inches(0.35)
            if _x.shape_type==13 and _x.width is not None and _qin(_x.width)>5:
                _x.left=Inches(4.7); _x.top=Inches(2.15); _x.width=Inches(7.8); _x.height=Inches(4.15)
        _tiles=sorted([_x for _x in _shp if _x.shape_type==1 and _x.left is not None and _qin(_x.left)<1.5 and _x.width is not None and _qin(_x.width)>2.5], key=lambda z:z.top)
        for _tile,_nt in zip(_tiles,[1.9,3.38,4.86]):
            _oldt=_qin(_tile.top); _d=_nt-_oldt
            for _x in _shp:
                if _x is _tile: continue
                if _x.has_text_frame and _x.left is not None and _qin(_x.left)<1.6 and _x.top is not None and _oldt-0.05<=_qin(_x.top)<=_oldt+1.35:
                    _x.top=Inches(_qin(_x.top)+_d)
            _tile.top=Inches(_nt)
    if any((t.startswith("Account Growth") or t.startswith("Account Retention")) for t in _titles):
        for _x in _shp:
            if _x.shape_type==13 and _x.width is not None and _qin(_x.width)>5:  # taller, aligned to the tile column
                _x.left=Inches(1.0); _x.top=Inches(1.75); _x.width=Inches(8.4); _x.height=Inches(4.38)
    if any(("Reg E Opt-In" in t and "Vintage" not in t) for t in _titles):  # 27/28 only, not the full-width vintage chart (29)
        for _x in _shp:
            if _x.shape_type==13 and _x.width is not None and _qin(_x.width)>5:  # branch chart -> shorter
                _x.left=Inches(4.4); _x.top=Inches(1.95); _x.width=Inches(7.6); _x.height=Inches(3.4)
    if any(t=="Mailing Response Summary" for t in _titles):
        for _x in _shp:
            if _x.has_table: _x.left=Inches(0.6); _x.top=Inches(1.5); _x.width=Inches(9.2); _x.height=Inches(5.3)
            elif _x.has_text_frame and _x.text_frame.text.strip().startswith("Most recent"): _x.left=Inches(0.6); _x.width=Inches(9.2)
_pers=M.get('n_eligible'); _tot=O.get('funnel',{}).get('eligible')
if _pers and _tot and _pers!=_tot:
    for _sl in prs.slides:
        if any(x.has_text_frame and x.text_frame.text.strip()=="Debit Usage Segmentation by Swipe Tier" for x in _sl.shapes):
            _fn=_sl.shapes.add_textbox(Inches(1.5),Inches(6.66),Inches(10.0),Inches(0.3)); _tf=_fn.text_frame; _tf.word_wrap=True
            _r=_tf.paragraphs[0].add_run(); _r.text=f"Personal ARS-eligible = {_pers:,}; total incl. business = {_tot:,} (Product Mix)."
            _r.font.name="Calibri"; _r.font.size=Pt(11); _r.font.color.rgb=_RGBc(0x5A,0x66,0x70)
            break

# QA finalize pass (mirrors the reviewed CoastLife fixes so the batch inherits them)
def _in(v): return Emu(v).inches if v is not None else None
for _sl in prs.slides:
    for _sh in _sl.shapes:
        if not _sh.has_text_frame or _sh.left is None: continue
        _low=_sh.text_frame.text.lower()
        if _in(_sh.left)>8 and _sh.top is not None and _in(_sh.top)<1.3:
            if "avg:" in _low:               # widen the Debit-Usage avg pill so it fits one line
                _sh.left=Inches(9.9); _sh.width=Inches(2.95)
            elif "through" in _low and "data" in _low:  # compact clipped take-rate window pills
                _r=_sh.text_frame.paragraphs[0]
                if _r.runs:
                    _r.runs[0].text=NEWWIN_PILL
                    for _x in _r.runs[1:]: _x.text=""
                for _pp in _sh.text_frame.paragraphs[1:]:
                    for _x in _pp.runs: _x.text=""
# cap bottom captions clear of right-rail tiles AND the bottom-right logo
for _sl in prs.slides:
    _obst=[]
    for _sh in _sl.shapes:
        if _sh.left is None or _sh.width is None or _sh.top is None: continue
        _l=_in(_sh.left); _t=_in(_sh.top)
        if _sh.shape_type==13 and _l>10.5 and _t>6.3: _obst.append(_l)
        elif _l>8.4 and _in(_sh.width)<4.3 and 1.2<_t<7.0 and _sh.shape_type in (1,17): _obst.append(_l)
    for _sh in _sl.shapes:
        if not _sh.has_text_frame or _sh.left is None or _sh.width is None or _sh.top is None: continue
        if not _sh.text_frame.text.strip(): continue
        _l=_in(_sh.left); _t=_in(_sh.top); _w=_in(_sh.width)
        if _t>5.7 and _l<3.2 and _w>3.5:
            _cap=(min(_obst)-0.2) if _obst else 11.15
            if _l+_w>_cap and _cap-_l>2.0: _sh.width=Inches(_cap-_l)

# QA finalize: standardize selection subtitles + insight captions to Calibri 16pt grey (skip summit/white)
from pptx.dml.color import RGBColor as _RGB
_GREY=_RGB(0x5A,0x66,0x70)
def _std(_sh):
    for _pa in _sh.text_frame.paragraphs:
        for _r in _pa.runs:
            try:
                if _r.font.color and _r.font.color.type is not None and str(_r.font.color.rgb)=="FFFFFF": return
            except Exception: pass
    for _pa in _sh.text_frame.paragraphs:
        for _r in _pa.runs:
            _r.font.name="Calibri"; _r.font.size=Pt(16); _r.font.color.rgb=_GREY
for _si,_sl in enumerate(prs.slides):
    if _si==1: continue
    for _sh in _sl.shapes:
        if not _sh.has_text_frame or _sh.left is None or _sh.top is None or not _sh.text_frame.text.strip(): continue
        _t=_in(_sh.top); _l=_in(_sh.left); _w=_in(_sh.width or 0); _tx=_sh.text_frame.text.strip().lower()
        if _tx.startswith("source"): continue   # source lines keep their own (small) size
        _sel=(1.0<_t<1.45 and _l<1.0 and _w>5 and _tx.startswith(("selection","distinct","personal accounts opened","open deposit","most recent")))
        _ins=(_t>5.7 and _l<6.5 and _w>3.2)
        if _sel or _ins: _std(_sh)

# user-corrected slide layouts (Aaron 2026-07-16, matched to the reviewed Sugar River deck)
for _sl in prs.slides:
    _tl=[x.text_frame.text.strip() for x in _sl.shapes if x.has_text_frame and x.text_frame.text.strip()]
    _t0=_tl[0] if _tl else ""
    if ("Reg E Opt-In" in _t0) and ("All Personal" in _t0 or "Opened in Last 12" in _t0):
        for _x in _sl.shapes:
            if _x.shape_type==13 and _x.width is not None and _x.height is not None and abs(_in(_x.width)-_in(_x.height))<0.5 and 2.4<_in(_x.width)<3.7:
                _x.left=Inches(0.5); _x.top=Inches(1.6); _x.width=Inches(3.2); _x.height=Inches(3.2)
        _bul=sorted([x for x in _sl.shapes if x.shape_type==1 and x.width is not None and _in(x.width)<0.35 and x.top is not None and 4.0<_in(x.top)<6.2], key=lambda z:z.top)
        for _b,_y in zip(_bul,[4.65,5.0,5.35]): _b.left=Inches(1.0); _b.top=Inches(_y)
        for _x in _sl.shapes:
            if not _x.has_text_frame or _x.top is None: continue
            _tt=_x.text_frame.text.strip().lower()
            if _tt.startswith(("opted in","opted out","no election")):
                _yy={"opted in":4.6,"opted out":4.95,"no election":5.3}[[k for k in ("opted in","opted out","no election") if _tt.startswith(k)][0]]
                _x.left=Inches(1.32); _x.top=Inches(_yy)
            elif _tt.startswith("opt-in rate by branch"):
                _x.left=Inches(4.68); _x.top=Inches(5.45); _x.width=Inches(7.2)
            elif _in(_x.top)>5.5 and _x.width is not None and _in(_x.width)>3:
                _x.left=Inches(0.5); _x.top=Inches(5.83); _x.width=Inches(3.75)
    elif _t0.startswith("Reg E Opt-In by Account Vintage"):
        for _x in _sl.shapes:
            if _x.shape_type==13 and _x.width is not None and _in(_x.width)>5: _x.top=Inches(2.0)
    elif _t0.startswith("Responder Age Profile"):
        for _x in _sl.shapes:
            if _x.shape_type==13 and _x.width is not None and _in(_x.width)>5: _x.left=Inches(1.95); _x.top=Inches(1.85); _x.width=Inches(9.3); _x.height=Inches(4.38)
    elif _t0.startswith("Who Responds"):
        for _x in _sl.shapes:
            if _x.shape_type==13 and _x.width is not None and _in(_x.width)>5: _x.left=Inches(2.42); _x.top=Inches(1.33); _x.width=Inches(8.5); _x.height=Inches(4.85)
    elif _t0.startswith("Account Retention"):
        for _x in _sl.shapes:
            if _x.shape_type==13 and _x.width is not None and _in(_x.width)>5: _x.left=Inches(1.03); _x.top=Inches(1.81); _x.width=Inches(8.4); _x.height=Inches(4.38)

# ---- 2c. Save -> chart swap -> letterbox -> fonts ----
# --- figure gate: one measure, ONE value -------------------------------------
# The swap gate above fails a build whose swap string matched nothing. This fails
# a build where two swaps BOTH landed and disagree — Wellworth's Jun 2026 drop
# reading 1,077 on the mailing slides and 1,026 on Reach/Depth/Ranking/Sustained.
# Unlike validate_deck's figure_identity rule, this needs no inference: the
# builder named the measure, so a difference is arithmetic, not a guess.
#
# Placed BEFORE the phase that materializes OUT. At the final save it still
# exited 2, but a partly-built deck was already sitting at the delivery path
# by then. Any future _figs.record() must go ABOVE this line.
_fx = _figs.log.conflicts()
if _fx:
    import sys as _sys2
    _sys2.stderr.write("BUILD FAILED — %d measure(s) rendered more than one value:\n" % len(_fx))
    for _measure, _byval in _fx:
        _sys2.stderr.write("  %s\n" % _measure)
        for _v, _slides in sorted(_byval.items()):
            _sys2.stderr.write("     %-14s on %s\n" % (_v, ", ".join(sorted(set(_slides)))))
    raise SystemExit(2)

_D = os.path.join(_PHASE_DIR, _ob + ".D.pptx"); prs.save(_D)
def _letterbox(src, w, h, dst):
    im = _PImg.open(src).convert("RGB"); iw, ih = im.size
    s = min(w/iw, h/ih); nw, nh = max(1,int(iw*s)), max(1,int(ih*s))
    cv = _PImg.new("RGB", (w, h), "white")
    cv.paste(im.resize((nw, nh), _PImg.LANCZOS), ((w-nw)//2, (h-nh)//2)); cv.save(dst)
_lift_lb = None
if MM: _lift_lb = os.path.join(ASSETS, "lift_lb.png"); _letterbox(LIFT_PNG, 2554, 784, _lift_lb)
_sm_lb = None
if SM_PNG: _sm_lb = os.path.join(ASSETS, "sm_lb.png"); _letterbox(SM_PNG, 2554, 784, _sm_lb)
_tik_lb = os.path.join(ASSETS, "ticket_lb.png"); _letterbox(TICKET_PNG, 2200, 790, _tik_lb) if TICKET_PNG else None
_biz_lb = BIZ_PNG   # already 1383x540 via chart_lib -> matches personal image11 exactly
def _c(n): return os.path.join(CHARTS, n)
swaps = {
 "image51": (_lift_lb if MM else _sm_lb), "image52": (_tik_lb if TICKET_PNG else None), "image3": _biz_lb,
 "image53": _c("image6.png"),  "image54": _c("image7.png"),  "image55": _c("image8.png"),
 "image56": _c("image28.png"), "image57": _c("image9.png"),  "image58": _c("image10.png"),
 "image59": _c("image31.png"), "image60": _c("image11.png"), "image61": _c("image12.png"),
 "image62": _c("image29.png"), "image63": _c("image13.png"), "image64": _c("image14.png"),
 "image65": _c("image15.png"), "image66": _c("image16.png"), "image67": _c("image30.png"),
 "image68": _c("image17.png"), "image69": _c("image18.png"), "image70": _c("image19.png"),
 "image71": _c("image20.png"), "image72": _c("image21.png"), "image73": _c("image22.png"),
 "image74": _c("image23.png"), "image75": _c("image24.png"), "image76": _c("image25.png"),
 "image77": _c("image26.png"), "image78": _c("image27.png"), "image79": _c("image32.png"),
}
with _zf.ZipFile(_D) as zin, _zf.ZipFile(OUT, "w", _zf.ZIP_DEFLATED) as zout:
    for it in zin.infolist():
        base = os.path.basename(it.filename); key = base.rsplit(".", 1)[0]
        src = swaps.get(key)
        if it.filename.startswith("ppt/media/") and src and os.path.exists(src):
            zout.writestr(it, open(src, "rb").read())
        else:
            zout.writestr(it, zin.read(it.filename))
subprocess.run([sys.executable, os.path.join(BUILDDIR, "restyle_fonts.py"), OUT], check=True)

# ---------- FINAL branding pass: logos + slide numbers (runs AFTER restyle_fonts) ----------
# Canonical geometry is documented in templates/STYLE.md. Rules (Aaron 2026-07-24):
#  - Slide number: Calibri 10pt bold navy, bottom-left; NONE on title / Summit / section headings.
#  - Logo: every slide EXCEPT the Summit slide shows the CSI|Velocity lockup. Data slides
#    carry it bottom-right at one fixed pos/size; section headings top-left at one fixed
#    pos/size; the title keeps its own centered cover lockup.
import io as _io2
from pptx.enum.shapes import MSO_SHAPE_TYPE as _MST
from pptx.dml.color import RGBColor as _RGBn
_bp = Presentation(OUT)
_NAVYnum = _RGBn(0x00, 0x27, 0x4C)
LOGO_DATA = (11.28, 6.78, 1.70, 0.54)       # STYLE.md: data-slide logo (bottom-right)
LOGO_SECTION = (0.71, 0.66, 1.90, 0.60)     # STYLE.md: section-heading logo (top-left)
NUM_LTWH = (0.45, 7.05, 0.70, 0.30); NUM_PT = 10   # STYLE.md: slide number (bottom-left)
def _emi(v): return Emu(v).inches if v is not None else None
def _is_logo_pic(sh):
    if sh.shape_type != _MST.PICTURE: return False
    w = _emi(sh.width) or 9; h = _emi(sh.height) or 9
    return w < 3.15 and h < 1.2
def _in_corner(sh):
    l = _emi(sh.left) or 5; t = _emi(sh.top) or 5
    return (l > 9.5 and t > 6.0) or (l < 2.0 and t < 2.0)
def _is_numbox(sh):
    if not sh.has_text_frame or None in (sh.left, sh.top, sh.width): return False
    tx = sh.text_frame.text.strip()
    return tx.isdigit() and _emi(sh.top) > 6.5 and _emi(sh.left) < 1.7 and _emi(sh.width) < 1.4
def _drop(sh): sh._element.getparent().remove(sh._element)
def _bigfont(sl):
    return max([ (r.font.size.pt if r.font.size else 0)
                 for sh in sl.shapes if sh.has_text_frame
                 for p in sh.text_frame.paragraphs for r in p.runs ] + [0])
# canonical CSI|Velocity lockup: grab the small pic off a section-heading slide (>=44pt title)
_logo_blob = None
for _s in _bp.slides:
    if _bigfont(_s) >= 44:
        for _sh in _s.shapes:
            if _is_logo_pic(_sh):
                try: _logo_blob = _sh.image.blob; break
                except Exception: pass
    if _logo_blob: break
if _logo_blob is None:
    _logo_blob = open(os.path.join(BUILDDIR, "assets", "logo.png"), "rb").read()
def _add_logo(sl, g):
    l, t, w, h = g
    sl.shapes.add_picture(_io2.BytesIO(_logo_blob), Inches(l), Inches(t), Inches(w), Inches(h))
def _put_num(sl, n):
    for sh in list(sl.shapes):
        if _is_numbox(sh): _drop(sh)
    l, t, w, h = NUM_LTWH
    tb = sl.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    r = tb.text_frame.paragraphs[0].add_run(); r.text = str(n)
    r.font.name = "Calibri"; r.font.size = Pt(NUM_PT); r.font.bold = True; r.font.color.rgb = _NAVYnum
def _clear_num(sl):
    for sh in list(sl.shapes):
        if _is_numbox(sh): _drop(sh)
def _has_topleft_logo(sl):
    return any(_is_logo_pic(sh) and (_emi(sh.left) or 9) < 2.0 and (_emi(sh.top) or 9) < 2.0 for sh in sl.shapes)
for _i, _sl in enumerate(list(_bp.slides)):
    _big = _bigfont(_sl)
    if _i == 0: role = "cover"                               # title
    elif _i == 1: role = "summit"
    elif _big >= 44: role = "section" if _has_topleft_logo(_sl) else "cover"  # cover = centered-lockup closer (e.g. Questions)
    else: role = "data"
    if role == "cover":
        _clear_num(_sl)                                      # keep existing centered lockup; no number
    elif role == "summit":
        for sh in list(_sl.shapes):
            if _is_logo_pic(sh) and _in_corner(sh): _drop(sh)   # drop the CSI corner logo only
        _clear_num(_sl)
    elif role == "section":
        for sh in list(_sl.shapes):
            if _is_logo_pic(sh): _drop(sh)
        _add_logo(_sl, LOGO_SECTION); _clear_num(_sl)
    else:  # data
        for sh in list(_sl.shapes):
            if _is_logo_pic(sh) and _in_corner(sh): _drop(sh)
        _add_logo(_sl, LOGO_DATA); _put_num(_sl, _i + 1)
import slide_geometry as _sg; _sg.apply(_bp)   # per-title geometry contract (build/)
import fit_layout as _fl; _fl.fit(_bp)   # final layout-fit: clear number/logo, clamp off-slide (shared)
_bp.save(OUT)
_sidecar = _figs.log.dump(_figs.sidecar_path(OUT))
if _sidecar:
    print("figures ->", os.path.basename(_sidecar),
          f"({len(_figs.log)} recorded, {len(_figs.log.by_measure())} measures)")
print("branding normalized: logos + slide numbers (10pt; none on title/summit/section)")
_clean_phase_files()
print("phase2 done ->", OUT)
