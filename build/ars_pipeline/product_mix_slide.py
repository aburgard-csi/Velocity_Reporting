#!/usr/bin/env python3
"""
product_mix_slide.py — reusable builder for the ARS "Product Mix & ARS Eligibility"
slide, inserted immediately before the Program Overview slide of an Executive
Review deck.

ARS workflow only. This slide belongs exclusively to the ARS Executive Review
workflow. It is gated two ways: (1) it is only wired into the ARS builds
(build.py, build_txb.py), and (2) extract_product_mix refuses to build if the
ODD has no "<Mon><yy> Elig" column — non-ARS dumps (e.g. ICS) lack it, so the
slide is skipped rather than emitting a meaningless 0-eligible slide.

Public entry point
------------------
    add_product_mix_slide(prs, odd, assets_dir, before_title="Program Overview")

    prs         : an open python-pptx Presentation (a cloned Executive Review deck)
    odd         : the client's ODD, given as any of:
                    * a "<ClientID>_ODDD.zip" path (preferred — how ODDs are stored)
                    * a raw ODD .csv path
                  Use odd_zip_path(oddd_dir, client_id) to build the zip path.
    assets_dir  : directory to write the two chart PNGs into (usually the build "A" dir)
    before_title: slide title to insert in front of (default "Program Overview")

The slide is fully data-driven: per-product OPEN account counts, ARS eligibility
(latest "<Mon><yy> Elig" snapshot == Yes), and business/personal split are all
computed from the ODD. Nothing is hard-coded per client.

Visual style matches the established Executive Review format:
  * navy title, orange data pill, grey subtitle, navy KPI tiles
  * table uses the same navy-header / orange-highlight / alternating-row format
    as build.py's add_table()
Design notes reused from oddd_optimize.py: real header row is the one whose first
cell == 'Acct ID'; file is latin-1 with NUL bytes; month columns look like
'Jun26 Elig'. Closed accounts are excluded from the "open" book.
"""
import csv, re, os, glob, zipfile, tempfile
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml

# standard callout / pill drop shadow (STYLE.md)
_SHADOW_XML = ('<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
               '<a:outerShdw blurRad="63500" dist="38100" dir="5400000" rotWithShape="0">'
               '<a:srgbClr val="000000"><a:alpha val="28000"/></a:srgbClr>'
               '</a:outerShdw></a:effectLst>')
def _shadow(shape):
    spPr = shape._element.spPr
    for e in spPr.findall(qn('a:effectLst')):
        spPr.remove(e)
    spPr.append(parse_xml(_SHADOW_XML))

# ----------------------------------------------------------------------------- palette / fonts
NAVY   = RGBColor(0x00, 0x27, 0x4C)
ORANGE = RGBColor(0xF4, 0x7A, 0x29)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
GREYB  = RGBColor(0xCF, 0xDB, 0xE8)   # light label grey (on navy)
GREYT  = RGBColor(0x5A, 0x66, 0x70)   # body text grey
ROWALT = RGBColor(0xEE, 0xF2, 0xF7)   # alternating table row
HEAD, BODY = "Montserrat", "Calibri"
_NAVY_HX, _ORANGE_HX, _GREY_HX, _TICK_HX = "#00274C", "#F47A29", "#CFDBE8", "#5A6670"

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
_MIDX  = {m: i for i, m in enumerate(MONTHS)}
_MONFULL = ["January","February","March","April","May","June","July","August",
            "September","October","November","December"]
_MONTH_RE = re.compile(r"^([A-Z][a-z]{2})(\d{2})\s+(.*)$")
_CLOSED = {"Closed"}

# ----------------------------------------------------------------------------- ODD resolution
def odd_zip_path(oddd_dir, client_id):
    """ODDs are stored as '<ClientID>_ODDD.zip' in the ODDD folder."""
    return os.path.join(oddd_dir, f"{client_id}_ODDD.zip")


def _resolve_csv(odd_source):
    """Accept a '<id>_ODDD.zip' or a raw '.csv'. Return a path to the CSV.

    Zips are extracted to a temp dir. Several ODDD zips also carry the raw
    monthly transaction file as a .csv (and on some clients it is the LARGER
    file), so select the ODD extract by name and only fall back to size — taking
    the largest blindly picks the transaction dump and the build then dies with
    "could not find 'Acct ID' header row"."""
    if odd_source.lower().endswith(".csv"):
        if not os.path.exists(odd_source):
            raise FileNotFoundError(f"ODD csv not found: {odd_source}")
        return odd_source
    if odd_source.lower().endswith(".zip"):
        if not os.path.exists(odd_source):
            raise FileNotFoundError(f"ODD zip not found: {odd_source}")
        tmp = tempfile.mkdtemp(prefix="oddd_")
        with zipfile.ZipFile(odd_source) as z:
            z.extractall(tmp)
        csvs = glob.glob(os.path.join(tmp, "**", "*.csv"), recursive=True)
        if not csvs:
            raise FileNotFoundError(f"no .csv inside {odd_source}")
        odd = [c for c in csvs
               if "-odd" in os.path.basename(c).lower()
               or "_v2_" in os.path.basename(c).lower()]
        return odd[0] if odd else max(csvs, key=os.path.getsize)
    raise ValueError(f"unrecognized ODD source (want .zip or .csv): {odd_source}")


# ----------------------------------------------------------------------------- ODD extraction
def _find_header_row(path):
    with open(path, "r", encoding="latin-1", newline="") as fh:
        for i, row in enumerate(csv.reader(fh)):
            if i > 25:
                break
            if any(c.strip() == "Acct ID" for c in row):
                return i, [c.strip() for c in row]
    raise SystemExit("product_mix_slide: could not find 'Acct ID' header row")


def _latest_elig_col(cols):
    """Return (colname, 'Mon', 'yy') of the most recent '<Mon><yy> Elig' column."""
    best = None
    for c in cols:
        m = _MONTH_RE.match(c)
        if m and m.group(3).strip() == "Elig":
            key = (2000 + int(m.group(2))) * 12 + _MIDX[m.group(1)]
            if best is None or key > best[0]:
                best = (key, c, m.group(1), m.group(2))
    if best is None:
        return None, None, None
    return best[1], best[2], best[3]


def _fixacr(s):
    """Collapse spaced-out acronyms from the raw ODD Prod Desc, e.g.
    'Individual H S A' -> 'Individual HSA', 'Family H S A' -> 'Family HSA'."""
    import re
    return re.sub(r'(?:\b[A-Z]\s){1,}[A-Z]\b',
                  lambda m: m.group(0).replace(' ', ''), s)


def extract_product_mix(odd_source):
    """Stream the ODD (zip or csv) and return a dict describing the product book.

    Returns keys: month_label, open_total, elig_total, biz, per, other,
    n_products (open>0), products (list of dicts: name, open, total, elig,
    is_business, is_eligible).

    Raises ValueError if the ODD has no eligibility column — this slide is
    ARS-only, and non-ARS dumps (e.g. ICS) do not carry '<Mon><yy> Elig'.
    """
    try:
        import pandas as pd
    except ImportError:
        raise SystemExit("product_mix_slide requires pandas")

    odd_csv = _resolve_csv(odd_source)
    hdr, header = _find_header_row(odd_csv)
    keep = [c for c in header if c and not c.startswith("Unnamed")]
    elig_col, emon, eyy = _latest_elig_col(keep)
    if elig_col is None:
        raise ValueError("ODD has no ARS eligibility column — Product Mix & ARS "
                         "Eligibility slide is ARS-only (skipping).")
    month_label = f"{_MONFULL[_MIDX[emon]]} 20{eyy}"

    def norm(s):
        return s.fillna("").astype(str).str.replace("\x00", "", regex=False).str.strip()

    agg = defaultdict(lambda: dict(open=0, total=0, elig=0, biz=0, per=0, oth=0))
    reader = pd.read_csv(odd_csv, skiprows=hdr, dtype=str, chunksize=100_000,
                         encoding="latin-1", on_bad_lines="skip")
    for ch in reader:
        ch = ch.rename(columns=lambda c: c.strip())
        for col in ("Prod Desc", "Business?", "Stat Desc"):
            if col not in ch:
                ch[col] = ""
        if elig_col and elig_col not in ch:
            ch[elig_col] = ""
        d = pd.DataFrame({
            "prod": norm(ch["Prod Desc"]),
            "biz":  norm(ch["Business?"]),
            "stat": norm(ch["Stat Desc"]),
            "elig": norm(ch[elig_col]) if elig_col else "",
        })
        d["isopen"] = ~d["stat"].isin(_CLOSED)
        for name, g in d.groupby("prod"):
            a = agg[name]
            a["total"] += len(g)
            go = g[g["isopen"]]
            a["open"] += len(go)
            a["elig"] += int((go["elig"] == "Yes").sum())
            a["biz"]  += int((go["biz"] == "Yes").sum())
            a["per"]  += int((go["biz"] == "No").sum())
            a["oth"]  += int((~go["biz"].isin(["Yes", "No"])).sum())

    products = []
    for name, a in agg.items():
        if a["open"] == 0:
            continue
        products.append(dict(
            name=(_fixacr(name.strip()) or "(unlabeled)"),
            open=a["open"], total=a["total"], elig=a["elig"],
            is_business=(a["biz"] > a["per"]),
            is_eligible=(a["elig"] > 0),
        ))
    products.sort(key=lambda p: -p["open"])
    open_total = sum(p["open"] for p in products)
    biz = sum(a["biz"] for a in agg.values())
    per = sum(a["per"] for a in agg.values())
    oth = sum(a["oth"] for a in agg.values())
    return dict(
        month_label=month_label,
        open_total=open_total,
        elig_total=sum(p["elig"] for p in products),
        biz=biz, per=per, other=oth,
        n_products=len(products),
        products=products,
    )

# ----------------------------------------------------------------------------- charts
def render_charts(data, assets_dir):
    os.makedirs(assets_dir, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    prods = data["products"]

    # ---- personal product-mix donut (open accounts) ----
    # Center total ties to the business/personal bar's Personal count (data["per"],
    # i.e. Business? == "No"). Named slices exclude internal/unlabeled buckets;
    # whatever personal remainder is left (small tails + internal) rolls into "Other".
    personal = [p for p in prods if not p["is_business"]
                and p["name"] not in ("Internal Accounts", "(unlabeled)")]
    named = personal[:10]
    per_total = data["per"]
    other = max(0, per_total - sum(p["open"] for p in named))
    labels = [p["name"] for p in named] + (["Other personal"] if other > 0 else [])
    vals   = [p["open"] for p in named] + ([other] if other > 0 else [])
    elig   = [p["is_eligible"] for p in named] + ([False] if other > 0 else [])
    orange_sh = ["#F47A29", "#F79552", "#FBB27E"]
    cold = ["#00274C","#12406E","#245C8C","#3D74A0","#6E93B4","#9DB4C8",
            "#C0D0DD","#DDE6ED","#EAF0F4","#F2F5F8"]
    oi = ci = 0
    colors = []
    for e in elig:
        if e:
            colors.append(orange_sh[min(oi, 2)]); oi += 1
        else:
            colors.append(cold[min(ci, len(cold) - 1)]); ci += 1
    fig = plt.figure(figsize=(7.6, 4.9))
    ax = fig.add_axes([0.00, 0.02, 0.50, 0.94]); ax.set_aspect("equal")
    w, _ = ax.pie(vals, colors=colors, startangle=90, counterclock=False,
                  wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
    for _wedge in w:                          # flat donut, no shadow; no-clip keeps edges crisp (STYLE.md)
        _wedge.set_clip_on(False)
    ax.text(0, 0.13, f"{per_total:,}", ha="center", va="center",
            color=_NAVY_HX, fontsize=27, fontweight="bold")
    ax.text(0, -0.18, "personal\naccounts", ha="center", va="center",
            color=_TICK_HX, fontsize=12.5)
    tot = sum(vals) or 1
    leg = [f"{l}   {v:,}  ({v/tot*100:.0f}%)" for l, v in zip(labels, vals)]
    ax.legend(w, leg, loc="center left", bbox_to_anchor=(0.96, 0.5), frameon=False,
              fontsize=12, handlelength=1.0, handleheight=1.0, labelspacing=0.62)
    donut = os.path.join(assets_dir, "pm_donut.png")
    fig.savefig(donut, dpi=300, transparent=False, facecolor="white", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    # ---- business vs personal 100% stacked bar ----
    # Labels are drawn inside each segment. If a segment is too narrow to hold
    # its label, the label is omitted for that bar (no external legend).
    seg = [("Personal", data["per"], _NAVY_HX), ("Business", data["biz"], _ORANGE_HX)]
    if data["other"] > 0:
        seg.append(("Other", data["other"], _GREY_HX))
    stot = sum(s[1] for s in seg) or 1
    fig = plt.figure(figsize=(5.8, 0.95))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    x = 0
    for name, v, c in seg:
        frac = v / stot
        ax.barh(0, frac, left=x, height=0.5, color=c, edgecolor="white", linewidth=1.2)
        if frac > 0.12:   # only label when the text comfortably fits inside
            fs = 11 if frac >= 0.25 else 8.5   # shrink so narrow segments don't clip
            ax.text(x + frac / 2, 0, f"{name}\n{v:,} ({frac*100:.0f}%)", ha="center",
                    va="center", color="white", fontsize=fs, fontweight="bold")
        x += frac
    ax.set_xlim(0, 1); ax.set_ylim(-0.5, 0.5)
    segbar = os.path.join(assets_dir, "pm_segbar.png")
    fig.savefig(segbar, dpi=200, transparent=True, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return donut, segbar

# ----------------------------------------------------------------------------- shape helpers (match build.py)
def _tb(slide, L, T, W, H, lines, size, color, bold, align=PP_ALIGN.CENTER,
        font=HEAD, anchor=MSO_ANCHOR.MIDDLE):
    box = slide.shapes.add_textbox(Inches(L), Inches(T), Inches(W), Inches(H))
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    if isinstance(lines, str):
        lines = [lines]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        r.font.size = Pt(size); r.font.bold = bold; r.font.name = font
        r.font.color.rgb = color
    return box


def _pill(slide, t):
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(10.5), Inches(0.34), Inches(2.35), Inches(0.5))
    sp.fill.solid(); sp.fill.fore_color.rgb = ORANGE; sp.line.fill.background()
    tf = sp.text_frame; tf.word_wrap = True; p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = t
    r.font.size = Pt(12); r.font.bold = True; r.font.name = HEAD; r.font.color.rgb = WHITE
    _shadow(sp)   # period pill carries the standard callout drop shadow (STYLE.md)


def _tile(slide, L, T, W, H, value, label, fill=NAVY):
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(L), Inches(T), Inches(W), Inches(H))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill; sp.line.fill.background()
    sp.shadow.inherit = False
    _tb(slide, L + 0.05, T + 0.14, W - 0.1, H * 0.5, value, 28, WHITE, True,
        PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    _tb(slide, L + 0.05, T + H * 0.60, W - 0.1, H * 0.34, label, 12, GREYB, False,
        PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP)


def _add_table(slide, L, T, W, H, data, colw, highlight=(), header=True, fs=10):
    """Identical styling contract to build.py add_table()."""
    rows = len(data); cols = len(data[0])
    gf = slide.shapes.add_table(rows, cols, Inches(L), Inches(T), Inches(W), Inches(H))
    tb = gf.table; tb.first_row = False; tb.horz_banding = False
    tot = sum(colw)
    for j, wd in enumerate(colw):
        tb.columns[j].width = Inches(W * wd / tot)
    for i, row in enumerate(data):
        tb.rows[i].height = Inches(H / rows)
        for j, val in enumerate(row):
            c = tb.cell(i, j)
            c.margin_top = Pt(2); c.margin_bottom = Pt(2)
            c.margin_left = Pt(5); c.margin_right = Pt(4)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame; tf.word_wrap = True; p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r = p.add_run(); r.text = str(val); r.font.name = BODY; r.font.size = Pt(fs)
            if header and i == 0:
                c.fill.solid(); c.fill.fore_color.rgb = NAVY
                r.font.color.rgb = WHITE; r.font.bold = True
            elif i in highlight:
                c.fill.solid(); c.fill.fore_color.rgb = ORANGE
                r.font.color.rgb = WHITE; r.font.bold = True
            else:
                c.fill.solid(); c.fill.fore_color.rgb = (WHITE if i % 2 else ROWALT)
                r.font.color.rgb = NAVY
    return gf

# ----------------------------------------------------------------------------- slide plumbing
def _blank_slide(prs, template_slide):
    """Add a slide using template_slide's layout, stripped of all shapes."""
    s = prs.slides.add_slide(template_slide.slide_layout)
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)
    return s


def _slide_title(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip()
    return ""


def _sldid_of(prs, slide):
    from pptx.oxml.ns import qn
    for el in prs.slides._sldIdLst:
        rId = el.get(qn("r:id"))
        if prs.part.related_part(rId) is slide.part:
            return el
    return None


def _move_before(prs, slide, before_title):
    lst = prs.slides._sldIdLst
    target = None
    for s in prs.slides:
        if _slide_title(s).startswith(before_title) and s is not slide:
            target = s; break
    if target is None:
        return False
    src = _sldid_of(prs, slide)
    tgt = _sldid_of(prs, target)
    if src is None or tgt is None:
        return False
    lst.remove(src)
    tgt.addprevious(src)
    return True


def _renumber(prs):
    """Mirror build.py's final page-number pass."""
    for n, s in enumerate(prs.slides, 1):
        found = None
        for sh in s.shapes:
            if (sh.has_text_frame and sh.top is not None and sh.top > Inches(6.8)
                    and sh.left is not None and sh.left < Inches(1.2)):
                txt = sh.text_frame.text.strip()
                if txt.isdigit() or txt in ("‹#›", ""):
                    found = sh; break
        if found and found.text_frame.paragraphs[0].runs:
            found.text_frame.paragraphs[0].runs[0].text = str(n)
        elif n > 1 and found is None:
            _tb(s, 0.45, 7.04, 0.7, 0.32, str(n), 11, NAVY, True, PP_ALIGN.LEFT,
                BODY, MSO_ANCHOR.MIDDLE)

# ----------------------------------------------------------------------------- table content
def _build_table_rows(data, max_elig=5):
    # Sort eligible products by ARS-eligible volume (the ARS-Elig. column), show the
    # top N, and fold everything else (eligible tail + non-eligible) into a single
    # "All other products" line so the column still reconciles to the Total. No
    # eligible-subtotal row — display is capped at max_elig products for bottom
    # alignment with the slide footer.
    elig_prods = [p for p in data["products"] if p["is_eligible"]]
    elig_prods.sort(key=lambda p: -p["elig"])
    rows = [["Product", "Open", "ARS-Elig."]]
    shown = elig_prods[:max_elig]
    for p in shown:
        rows.append([p["name"], f"{p['open']:,}", f"{p['elig']:,}"])
    shown_open = sum(p["open"] for p in shown)
    shown_elig = sum(p["elig"] for p in shown)
    n_other = data["n_products"] - len(shown)
    other_elig = data["elig_total"] - shown_elig
    rows.append([f"All other products ({n_other})",
                 f"{data['open_total'] - shown_open:,}",
                 f"{other_elig:,}" if other_elig > 0 else "—"])
    rows.append(["Total — open accounts", f"{data['open_total']:,}",
                 f"{data['elig_total']:,}"])
    highlight = (len(rows) - 1,)   # orange Total row
    return rows, highlight

# ----------------------------------------------------------------------------- public entry point
def add_product_mix_slide(prs, odd_csv, assets_dir, before_title="Program Overview",
                          renumber=True):
    """Build the Product Mix & ARS Eligibility slide and insert it before
    the Program Overview slide. Returns (slide, data)."""
    data = extract_product_mix(odd_csv)
    donut, segbar = render_charts(data, assets_dir)

    # template slide = the one we insert before (keeps master/theme consistent)
    template = next((s for s in prs.slides
                     if _slide_title(s).startswith(before_title)), prs.slides[0])
    s = _blank_slide(prs, template)

    _tb(s, 0.5, 0.28, 9.6, 0.9, "Product Mix & ARS Eligibility", 26, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    _pill(s, f"{data['month_label']} Data")
    _tb(s, 0.5, 1.12, 12.3, 0.5,
        "Open deposit accounts by product. ARS eligibility reflects the current "
        "program eligibility flag.",
        14, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    # KPI tiles
    share = round(data["elig_total"] / data["open_total"] * 100) if data["open_total"] else 0
    n_elig = sum(1 for p in data["products"] if p["is_eligible"])
    tiles = [(f"{data['open_total']:,}", "Open accounts", NAVY),
             (f"{data['elig_total']:,}", "ARS-eligible accounts", ORANGE),
             (f"{share}%", "Eligible share of open", NAVY),
             (f"{n_elig}", f"Eligible products (of {data['n_products']})", NAVY)]
    for i, (v, l, f) in enumerate(tiles):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 1.28, v, l, fill=f)

    # left: personal product-mix donut
    s.shapes.add_picture(donut, Inches(0.2), Inches(3.15), Inches(6.15))

    # right: business/personal + eligibility table
    s.shapes.add_picture(segbar, Inches(6.75), Inches(3.15), Inches(5.95))
    _tb(s, 6.75, 4.48, 6.1, 0.35, "Products & ARS Eligibility",
        13.5, NAVY, True, PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    rows, highlight = _build_table_rows(data)   # top-5 products + all-other + total
    # Keep the table clear of the footer source line (~7.06"): top-5 fits the
    # 4.82 → ~6.6 band with margin below (Aaron, 2026-07-13).
    tbl_h = 6.60 - 4.82
    _add_table(s, 6.75, 4.82, 6.05, tbl_h, rows, [1.7, 0.8, 0.9],
               highlight=highlight, fs=11)

    # source in the notes, not on the slide face (STYLE.md, Aaron 2026-07-15)
    s.notes_slide.notes_text_frame.text = (f"Source: client ODD, {data['month_label']}. "
        "Open accounts exclude closed. ARS eligibility per current program flag.")
    logo = os.path.join(assets_dir, "logo.png")
    if os.path.exists(logo):
        s.shapes.add_picture(logo, Inches(11.28), Inches(6.78), Inches(1.70), Inches(0.54))

    _move_before(prs, s, before_title)
    if renumber:
        _renumber(prs)
    return s, data
