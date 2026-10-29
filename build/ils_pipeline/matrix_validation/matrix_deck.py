# Copied from Tim Barrett's ILS Matrix Validation Deck Builder (M:\TimBarrett\ILS Matrix Validation Deck Builder\matrix_deck.py, 2026-07-20), unchanged; reused with James Gilmore's go-ahead (2026-10-28).
"""
Generic ILS Matrix Validation deck builder.

Point it at any client's `Matrixvalidation_*.txt` export and it renders the
house-style PowerPoint (navy/white, 10 x 5.625").  Everything that used to be
hard-coded for a single client — account types, matrix codes, limits, tier
counts, trending thresholds and the narrative notes — is now discovered from
the file, so the same code works for every client review.

Public entry point:
    build_deck(txt_path, client_name, out_path=None, report_date=None) -> out_path
"""
import os
import re
from datetime import datetime
from collections import defaultdict, OrderedDict

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from .matrix_report import parse

# ── palette ─────────────────────────────────────────────────────────────────
NAVY = RGBColor(0x1E, 0x27, 0x61); WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x33, 0x33, 0x33); MED = RGBColor(0x66, 0x66, 0x66)
ALT  = RGBColor(0xE8, 0xED, 0xF7); GREEN = RGBColor(0x17, 0x63, 0x42)
RED  = RGBColor(0xC0, 0x39, 0x2B); GRAY = RGBColor(0x99, 0x99, 0x99)
LIGHT_BLUE = RGBColor(0xCA, 0xDC, 0xFC)
HEADER_BLUE = RGBColor(0x44, 0x72, 0xC4)

# Familiar colours for the common account types; anything else draws from EXTRA.
KNOWN_TYPE_COLORS = {
    "Business":      RGBColor(0x1C, 0x72, 0x93),   # teal
    "Personal":      RGBColor(0x21, 0x45, 0x8B),   # mid-blue
    "Second Chance": RGBColor(0x7A, 0x4E, 0x9E),   # purple
}
EXTRA_COLORS = [
    RGBColor(0x2E, 0x7D, 0x32),   # green
    RGBColor(0xC0, 0x66, 0x2B),   # orange
    RGBColor(0x8B, 0x2E, 0x5B),   # magenta
    RGBColor(0x4E, 0x6E, 0x9E),   # steel
    RGBColor(0x6B, 0x6B, 0x2E),   # olive
    RGBColor(0x30, 0x6B, 0x6B),   # deep teal
]


# ═════════════════════════════ low-level helpers ═════════════════════════════
def cell_fmt(cell, text, fs=8, bold=False, align=PP_ALIGN.CENTER,
             fg=DARK, bg=None, wrap=True):
    tf = cell.text_frame; tf.word_wrap = wrap
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = str(text)
    r.font.size = Pt(fs); r.font.bold = bold; r.font.color.rgb = fg; r.font.name = "Calibri"
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    if bg:
        cell.fill.solid(); cell.fill.fore_color.rgb = bg


def hdr(cell, text, fs=8, bg=NAVY, fg=WHITE):
    cell_fmt(cell, text, fs=fs, bold=True, fg=fg, bg=bg)


def is_true(v):
    """Format-agnostic truthiness: handles 1/0, True/False, Y/N, Yes/No, T/F."""
    return str(v).strip().lower() in ("1", "true", "t", "y", "yes")


def yesno(v):
    return "Yes" if is_true(v) else "No"


def factor_color(v):
    try:
        f = float(str(v).replace(",", "").replace("%", "").replace("$", ""))
    except ValueError:
        return DARK
    if f < 0: return RED
    if f == 0: return GRAY
    return GREEN


def fmt_factor(v):
    s = str(v).strip()
    pct = s.endswith("%")
    core = s[:-1] if pct else s
    try:
        f = float(core.replace(",", ""))
    except ValueError:
        return s
    if f == 0:
        return "0%" if pct else "0"      # avoid "-0" / "-0%"
    return f"{f:,.0f}%" if pct else f"{f:,.0f}"


def fmt_num(x):
    """Format a numeric threshold: 10 -> '10', 1.50 -> '1.5', 2.25 -> '2.25'."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    s = f"{f:.4f}".rstrip("0").rstrip(".")
    return s


def clean_range(rng):
    s = re.sub(r"^\[\d+\]\s*-\s*", "", rng)      # drop leading "[00] - "
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)         # drop trailing "(0.00, 0.00)"
    return s.strip()


def ridx(rng):
    m = re.match(r"\[(\d+)\]", rng)
    return int(m.group(1)) if m else 999


# ═════════════════════════════ slide furniture ═══════════════════════════════
class Deck:
    """Holds per-client metadata so slide builders stay data-driven."""
    def __init__(self, prs, client, date_str, types, codes, colors, footer_types,
                 relabel_mrpc=False):
        self.prs = prs
        self.client = client
        self.date_str = date_str
        self.types = types            # ordered list of account-type names
        self.codes = codes            # {type: matrix code}
        self.colors = colors          # {type: RGBColor}
        self.footer_types = footer_types
        self.relabel_mrpc = relabel_mrpc

    def term(self, s):
        """Optionally relabel 'MRPC' as 'CashPlease' in display text."""
        if not self.relabel_mrpc or "MRPC" not in s:
            return s
        out = s.replace("MRPC", "CashPlease")
        return re.sub(r"CashPlease(?:\s+CashPlease)+", "CashPlease", out)  # collapse dupes

    def title_bar(self, slide, title, subtitle=None):
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb = WHITE
        # Navy bar holds both the title and the subtitle, so the subtitle can never
        # be overlapped by the section-label boxes / tables that follow below it.
        bar_h = 0.56 if subtitle else 0.52
        bar = slide.shapes.add_shape(1, Inches(0), Inches(0), self.prs.slide_width, Inches(bar_h))
        bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
        tb = slide.shapes.add_textbox(Inches(0.18), Inches(0.03), Inches(9.6), Inches(0.30))
        tb.text_frame.word_wrap = False
        r = tb.text_frame.paragraphs[0].add_run(); r.text = title
        r.font.bold = True; r.font.size = Pt(14); r.font.color.rgb = WHITE; r.font.name = "Calibri"
        if subtitle:
            tb2 = slide.shapes.add_textbox(Inches(0.18), Inches(0.31), Inches(9.6), Inches(0.22))
            tb2.text_frame.word_wrap = False
            r2 = tb2.text_frame.paragraphs[0].add_run(); r2.text = subtitle
            r2.font.size = Pt(8.5); r2.font.color.rgb = LIGHT_BLUE; r2.font.name = "Calibri"

    def footer(self, slide):
        fb = slide.shapes.add_textbox(Inches(0.2), Inches(5.37), Inches(9.6), Inches(0.2))
        r = fb.text_frame.paragraphs[0].add_run()
        r.text = (f"{self.client}  |  ILS Matrix Validation  |  {self.date_str}  |  "
                  f"{self.footer_types}  |  Confidential & Proprietary")
        r.font.size = Pt(6.5); r.font.color.rgb = MED; r.font.name = "Calibri"

    def new_slide(self):
        return self.prs.slides.add_slide(self.prs.slide_layouts[6])


def section_label(slide, x, y, w, h, text, bg=HEADER_BLUE):
    box = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = bg; box.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(x + 0.05), Inches(y), Inches(w - 0.1), Inches(h))
    r = tb.text_frame.paragraphs[0].add_run(); r.text = text
    r.font.bold = True; r.font.size = Pt(9); r.font.color.rgb = WHITE; r.font.name = "Calibri"


# ═════════════════════════════ data extraction ═══════════════════════════════
def _section(S, *names):
    """Return the first matching section's rows (case-insensitive), else []."""
    for name in names:
        for k in S:
            if k.strip().lower() == name.strip().lower():
                return S[k]["rows"]
    return []


def detect_types(S):
    """Ordered account types + their matrix codes and settings rows."""
    rows = _section(S, "ACCOUNT TYPES AND MIN/MAX LIMITS")
    types, codes, settings = [], {}, {}
    for r in rows:
        t = r.get("Account Type", "").strip()
        if not t:
            continue
        types.append(t)
        codes[t] = r.get("Matrix Code", "").strip()
        settings[t] = r
    return types, codes, settings


def assign_colors(types):
    colors, pool = {}, list(EXTRA_COLORS)
    for t in types:
        if t in KNOWN_TYPE_COLORS:
            colors[t] = KNOWN_TYPE_COLORS[t]
        else:
            colors[t] = pool.pop(0) if pool else NAVY
    return colors


def overrides_by_type(S, types):
    d = {t: [] for t in types}
    for r in _section(S, "OVERRIDES"):
        t = r.get("Account Type", "")
        if t in d:
            d[t].append(r)
    for t in d:
        d[t].sort(key=lambda r: int(r["Order Index"]) if str(r.get("Order Index", "")).isdigit() else 99)
    return d


def categories(S):
    """Distinct factor categories in first-seen order."""
    seen = OrderedDict()
    for r in _section(S, "RANGES AND FACTORS"):
        c = r.get("Category", "").strip()
        if c:
            seen[c] = True
    return list(seen)


def range_grid(S, category, types):
    """range-index -> {'label': ..., <type>: factor, ...} sorted by range index."""
    g = {}
    for r in _section(S, "RANGES AND FACTORS"):
        if r.get("Category") != category:
            continue
        key = ridx(r["Range"])
        g.setdefault(key, {"label": clean_range(r["Range"])})[r["Account Type"]] = r["Factor"]
    return [g[k] for k in sorted(g)]


def all_zero(rows, types):
    """True if every factor across all supplied types is 0/blank."""
    for row in rows:
        for t in types:
            v = str(row.get(t, "0")).replace(",", "").strip()
            if v and v not in ("0", "0.0", "0.00", "NULL"):
                return False
    return True


def zero_types(rows, types):
    """Types whose factors are all zero for this category."""
    out = []
    for t in types:
        vals = [str(row.get(t, "0")).replace(",", "").strip() for row in rows]
        if all(v in ("", "0", "0.0", "0.00", "NULL") for v in vals):
            out.append(t)
    return out


# ── trending: generic structure inferred from the Calculation text ────────────
# Trend repositories differ by client (Deposit Regularity, Windfall Deposit,
# Overdraft Repayment, …).  Rather than hard-code each one, we discover every
# repository and infer its factor grid straight from the SQL-ish Calculation:
# each row is a conjunction of range conditions on one or two variables; the
# variables that vary across rows become the grid dimensions.

_BETWEEN_RE = re.compile(
    r"(\[[^\]]+\](?:\s*/\s*\[[^\]]+\])?)\s+BETWEEN\s+([-\d.]+)\s+AND\s+([-\d.]+)", re.I)
_CMP_RE = re.compile(
    r"(\(?\s*\[[^\]]+\]\s*(?:/\s*\[[^\]]+\]\s*)?\)?)\s*(<=|>=|<|>)\s*([-\d.]+)")


def _key_norm(lhs):
    """Stable key for a left-hand expression (ignore spaces/parens)."""
    return re.sub(r"[\s()]", "", lhs)


def _key_caption(lhs):
    """Readable caption for an expression: drop brackets/extra spaces."""
    s = lhs.replace("[", "").replace("]", "").replace("(", "").replace(")", "")
    s = re.sub(r"\s*/\s*", " / ", s)
    return re.sub(r"\s+", " ", s).strip()


def _range_label(tokens):
    """tokens: list of ('cmp',op,num) / ('rng',a,b) -> a single range label."""
    lo = hi = lo_op = hi_op = None
    for tok in tokens:
        if tok[0] == "rng":
            return f"{fmt_num(tok[1])} – {fmt_num(tok[2])}"
        _, op, num = tok
        if op in (">", ">="):
            lo, lo_op = num, op
        else:
            hi, hi_op = num, op
    lo_sym = "≥" if lo_op == ">=" else ">"
    hi_sym = "≤" if hi_op == "<=" else "<"
    if lo is not None and hi is not None:
        return f"{lo_sym} {fmt_num(lo)} – {hi_sym} {fmt_num(hi)}"
    if hi is not None:
        return f"{hi_sym} {fmt_num(hi)}"
    if lo is not None:
        return f"{lo_sym} {fmt_num(lo)}"
    return "—"


def _parse_calc(calc):
    """Parse one Calculation into {key: (caption, [tokens])} for that row."""
    out = {}
    work = calc
    for m in _BETWEEN_RE.finditer(calc):
        lhs, a, b = m.group(1), m.group(2), m.group(3)
        k = _key_norm(lhs)
        out.setdefault(k, [_key_caption(lhs), []])[1].append(("rng", a, b))
    work = _BETWEEN_RE.sub(" ", calc)
    for m in _CMP_RE.finditer(work):
        lhs, op, num = m.group(1), m.group(2), m.group(3)
        k = _key_norm(lhs)
        out.setdefault(k, [_key_caption(lhs), []])[1].append(("cmp", op, num))
    return out


def trend_repositories(S):
    """Repository names in first-seen order."""
    seen = OrderedDict()
    for r in _section(S, "TRENDS"):
        rn = r.get("Repository Name", "").strip()
        if rn:
            seen[rn] = True
    return list(seen)


def _repo_rows(S, repo, account_type=None):
    rows = [r for r in _section(S, "TRENDS") if r.get("Repository Name") == repo]
    if account_type is None:
        account_type = rows[0].get("Account Type") if rows else None
    return [r for r in rows if r.get("Account Type") == account_type]


def trend_structure(S, repo):
    """Infer a repository's grid.

    Returns {'dims': [(caption, [labels]), ...], 'factors': {label-tuple: factor},
             'shared': bool} using the first account type's rows (grids are shared
             across account types in every export seen; 'shared' flags whether that
             held for this repo).
    """
    rows = _repo_rows(S, repo)
    parsed = [_parse_calc(r.get("Calculation", "")) for r in rows]
    facs = [r.get("Factor", "") for r in rows]

    # first-seen key order + captions + how often each key is present
    key_order, caps = [], {}
    for p in parsed:
        for k, (cap, _) in p.items():
            if k not in key_order:
                key_order.append(k); caps[k] = cap

    def lab(p, k):
        return _range_label(p[k][1]) if k in p else None

    # primary dimension: first key present in ALL rows whose label varies.
    # (This one sits at the start of the Calculation text, so it survives the
    # export's column-width truncation intact.)
    dimA = None
    for k in key_order:
        present = sum(1 for p in parsed if k in p)
        if present == len(rows) and len({lab(p, k) for p in parsed}) > 1:
            dimA = k
            break
    if dimA is None:                               # fall back to most-present key
        dimA = max(key_order, key=lambda k: sum(1 for p in parsed if k in p)) if key_order else None

    shared = _repo_shared(S, repo)

    if dimA is None:                               # no parseable structure
        return {"dims": [], "factors": {}, "shared": shared, "truncated": False}

    a_labels_row = [lab(p, dimA) for p in parsed]
    others = [k for k in key_order if k != dimA]

    # group rows by the primary label, preserving order
    groups = OrderedDict()
    for i, al in enumerate(a_labels_row):
        groups.setdefault(al, []).append(i)
    sizes = {len(v) for v in groups.values()}

    # 2-D grid: uniform group size > 1 and a secondary variable exists
    if others and len(sizes) == 1 and next(iter(sizes)) > 1:
        G = next(iter(sizes)); bkey = others[0]
        col_labels = [None] * G
        truncated = False
        for idxs in groups.values():
            for j, ri in enumerate(idxs):
                cand = lab(parsed[ri], bkey)
                if cand and _richer(cand, col_labels[j]):
                    col_labels[j] = cand
        for j in range(G):
            if col_labels[j] is None:
                col_labels[j] = f"Band {j + 1}"; truncated = True
        factors = {}
        for al, idxs in groups.items():
            for j, ri in enumerate(idxs):
                factors[(al, col_labels[j])] = facs[ri]
        return {"dims": [(caps[dimA], list(groups.keys())), (caps[bkey], col_labels)],
                "factors": factors, "shared": shared, "truncated": truncated}

    # 1-D
    labels, factors = [], {}
    for i, al in enumerate(a_labels_row):
        if al not in labels:
            labels.append(al)
        factors[(al,)] = facs[i]
    return {"dims": [(caps[dimA], labels)], "factors": factors,
            "shared": shared, "truncated": False}


def _richer(new, old):
    """Prefer the more complete label: a full range beats a partial/None."""
    if old is None:
        return True
    if ("–" in new) != ("–" in old):
        return "–" in new
    return len(new) > len(old)


def _repo_shared(S, repo):
    seqs = set()
    for t in {r.get("Account Type") for r in _section(S, "TRENDS")
              if r.get("Repository Name") == repo}:
        seqs.add(tuple(rr.get("Factor") for rr in _repo_rows(S, repo, t)))
    return len(seqs) <= 1


def trend_trigger_rows(S, types):
    """One row per (account type, repository) with its non-null trigger minimums."""
    out = []
    for t in types:
        for repo in trend_repositories(S):
            rows = _repo_rows(S, repo, t)
            if not rows:
                continue
            s = rows[0]
            def g(k):
                v = str(s.get(k, "")).strip()
                return v if v and v.upper() != "NULL" else "—"
            out.append({
                "type": t, "repo": repo,
                "dep_cnt": g("Min. Deposit Count"),
                "dep_amt": g("Min. Deposit Amount"),
                "od_cnt": g("Min. Overdraft Count"),
            })
    return out


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except (ValueError, TypeError):
        return None


def tier_summary(S):
    """Per-account-type tier stats for whichever types have their own tier table.

    Handles both uniform score bands (German American, $25) and variable-width
    bands (Space Coast).  band_w is set only when every band has the same width.
    """
    byt = defaultdict(list)
    for r in _section(S, "TIERS AND ROUNDING"):
        byt[r.get("Account Type", "")].append(r)
    out = {}
    for at, rows in byt.items():
        if not at:
            continue
        lims = [_num(r.get("Limit Value")) for r in rows]
        lims = [x for x in lims if x is not None]
        mins = [_num(r.get("Min Value")) for r in rows]
        maxs = [_num(r.get("Max Value")) for r in rows]
        # The top/catch-all band uses a huge Max (e.g. 999,999,999.99) and its
        # Limit Value is the real maximum granted limit — that is the max tier.
        SENTINEL = 1e6
        top_row = max(rows, key=lambda r: (_num(r.get("Max Value")) or -1))
        max_limit = _num(top_row.get("Limit Value"))
        if max_limit is None:
            max_limit = max(lims) if lims else 0.0
        widths = set()
        for mn, mx in zip(mins, maxs):
            if mn is not None and mx is not None and mx < SENTINEL:
                widths.add(round(mx - mn + 0.01, 2))
        finite_mins = [x for x in mins if x is not None]
        out[at] = {
            "n": len(rows),
            "band_w": next(iter(widths)) if len(widths) == 1 else None,
            "score_min": min(finite_mins) if finite_mins else 0.0,
            # the top band is open-ended, so its ceiling for display is the max
            # granted limit (score and limit share the same $ scale here)
            "score_max": max_limit,
            "max_limit": max_limit,
            "code": rows[0].get("Matrix Code", ""),
        }
    return out


# ═════════════════════════════ slides ════════════════════════════════════════
def slide_title(dk, settings):
    slide = dk.new_slide()
    slide.background.fill.solid(); slide.background.fill.fore_color.rgb = NAVY
    accent = dk.colors[dk.types[0]] if dk.types else HEADER_BLUE
    stripe = slide.shapes.add_shape(1, Inches(0), Inches(3.05), dk.prs.slide_width, Inches(0.06))
    stripe.fill.solid(); stripe.fill.fore_color.rgb = accent; stripe.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(1.4), Inches(8.8), Inches(1.6))
    tf = tb.text_frame; tf.word_wrap = True
    r = tf.paragraphs[0].add_run(); r.text = dk.client
    r.font.size = Pt(32); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Calibri"
    p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = "ILS Overdraft Matrix Validation"
    r2.font.size = Pt(19); r2.font.color.rgb = LIGHT_BLUE; r2.font.name = "Calibri"

    parts = []
    for t in dk.types:
        s = settings.get(t, {})
        code = dk.codes.get(t, "")
        mx = s.get("Max", "")
        try:
            mx = f"max ${int(float(mx)):,}"
        except (ValueError, TypeError):
            mx = ""
        label = f"{t} ({code}"
        label += f", {mx})" if mx else ")"
        parts.append(label)

    sub = slide.shapes.add_textbox(Inches(0.62), Inches(3.25), Inches(8.8), Inches(1.6))
    tf2 = sub.text_frame; tf2.word_wrap = True
    n = len(dk.types)
    r3 = tf2.paragraphs[0].add_run()
    r3.text = f"{n} account-type matri{'x' if n == 1 else 'ces'}:  " + "  •  ".join(parts)
    r3.font.size = Pt(12); r3.font.color.rgb = WHITE; r3.font.name = "Calibri"
    p4 = tf2.add_paragraph(); r4 = p4.add_run()
    r4.text = f"Configuration snapshot as of {dk.date_str}"
    r4.font.size = Pt(9); r4.font.italic = True
    r4.font.color.rgb = RGBColor(0x9A, 0xA6, 0xC2); r4.font.name = "Calibri"


def slide_settings(dk, S, settings):
    slide = dk.new_slide()
    dk.title_bar(slide, "Account-Type Settings & OD Status Codes",
                 "Matrix limits, tiering and eligibility for the configured account types")
    section_label(slide, 0.12, 0.60, 9.76, 0.22, "  ACCOUNT-TYPE MATRIX CONFIGURATION")
    cols = ["Account Type", "Matrix\nCode", "Calc?", "Min", "Max", "Enabled?",
            "Tiered\nLimits", "Matrix Modified", "Custom Inclusion Criteria"]
    w = [1.35, 0.55, 0.5, 0.55, 0.62, 0.66, 0.6, 1.6, 3.3]
    tbl = slide.shapes.add_table(len(dk.types) + 1, len(cols), Inches(0.12), Inches(0.84),
                                 Inches(sum(w)), Inches(min(1.6, 0.30 * (len(dk.types) + 1)))).table
    for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
    for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=7.5)
    for ri, t in enumerate(dk.types, 1):
        r = settings.get(t, {}); tc = dk.colors[t]
        cell_fmt(tbl.cell(ri, 0), t, fs=8, bold=True, fg=WHITE, bg=tc, align=PP_ALIGN.LEFT)
        cell_fmt(tbl.cell(ri, 1), dk.codes.get(t, ""), fs=8, bold=True, fg=WHITE, bg=tc)
        cell_fmt(tbl.cell(ri, 2), r.get("Calc?", ""), fs=8)
        cell_fmt(tbl.cell(ri, 3), f'${r.get("Min","")}', fs=8)
        try:
            mx = f'${int(float(r.get("Max",0))):,}'
        except (ValueError, TypeError):
            mx = r.get("Max", "")
        cell_fmt(tbl.cell(ri, 4), mx, fs=8, bold=True, fg=GREEN)
        cell_fmt(tbl.cell(ri, 5), r.get("Enabled?", ""), fs=8, fg=GREEN)
        cell_fmt(tbl.cell(ri, 6), r.get("Tiered Limits", ""), fs=8, fg=GREEN)
        cell_fmt(tbl.cell(ri, 7), str(r.get("Matrix Modified Date", ""))[:10], fs=7.5)
        crit = str(r.get("Custom Inclusion Criteria", "")).strip()
        cell_fmt(tbl.cell(ri, 8), crit if crit and crit != "NULL" else "—", fs=7, align=PP_ALIGN.LEFT)

    od = _section(S, "OD STATUS CODE MAPPING")
    if od:
        top = 0.86 + min(1.6, 0.30 * (len(dk.types) + 1)) + 0.35
        section_label(slide, 0.12, top - 0.24, 9.76, 0.22, "  OD STATUS CODE MAPPING")
        cols2 = ["Status Code", "Description", "ILS Calc", "Can Overdraft", "MRPC Elig.", "MRPC Loan Elig."]
        w2 = [1.7, 3.36, 1.1, 1.3, 1.1, 1.2]
        h2 = min(2.9, 0.245 * (len(od) + 1))
        tbl2 = slide.shapes.add_table(len(od) + 1, len(cols2), Inches(0.12), Inches(top),
                                      Inches(sum(w2)), Inches(h2)).table
        for i, wd in enumerate(w2): tbl2.columns[i].width = Inches(wd)
        for c, h in enumerate(cols2): hdr(tbl2.cell(0, c), dk.term(h), fs=7.5)
        for ri, r in enumerate(od, 1):
            bg = ALT if ri % 2 == 0 else None
            can_od = is_true(r.get("CAN_OVERDRAFT", ""))
            cell_fmt(tbl2.cell(ri, 0), r.get("STATUS_CODE", ""), fs=7.5, bg=bg, align=PP_ALIGN.LEFT)
            cell_fmt(tbl2.cell(ri, 1), r.get("DESCRIPTION", ""), fs=7.5, bg=bg, align=PP_ALIGN.LEFT)
            cell_fmt(tbl2.cell(ri, 2), yesno(r.get("ILS_CALC")), fs=7.5, bg=bg,
                     fg=GREEN if is_true(r.get("ILS_CALC")) else GRAY)
            cell_fmt(tbl2.cell(ri, 3), yesno(can_od), fs=7.5, bg=bg,
                     fg=GREEN if can_od else RED, bold=True)
            cell_fmt(tbl2.cell(ri, 4), yesno(r.get("MRPC_Eligible")), fs=7.5, bg=bg,
                     fg=GREEN if is_true(r.get("MRPC_Eligible")) else GRAY)
            cell_fmt(tbl2.cell(ri, 5), yesno(r.get("MRPC_Loan_Eligible")), fs=7.5, bg=bg,
                     fg=GREEN if is_true(r.get("MRPC_Loan_Eligible")) else GRAY)
    dk.footer(slide)


def slide_overrides(dk, S):
    slide = dk.new_slide()
    dk.title_bar(slide, "Override Criteria — " + " · ".join(dk.types),
                 "Rules applied to the scored intermediate limit (in order); values may be points, %, or absolute caps")
    ov = overrides_by_type(S, dk.types)
    n = len(dk.types)
    total_w, gap, left = 9.76, 0.08, 0.12
    cw = (total_w - gap * (n - 1)) / n
    fs = 6 if n <= 3 else 5.3
    for k, t in enumerate(dk.types):
        x = left + k * (cw + gap); tc = dk.colors[t]
        section_label(slide, x, 0.60, cw, 0.24, f"  {t.upper()} ({dk.codes.get(t,'')})", bg=tc)
        rows = ov[t]
        tbl = slide.shapes.add_table(len(rows) + 1, 3, Inches(x), Inches(0.86),
                                     Inches(cw), Inches(min(4.3, 0.32 * (len(rows) + 1)))).table
        tbl.columns[0].width = Inches(cw * 0.72)
        tbl.columns[1].width = Inches(cw * 0.19)
        tbl.columns[2].width = Inches(cw * 0.09)
        for c, h in enumerate(["Override Criteria", "Value", "Stop"]):
            hdr(tbl.cell(0, c), h, fs=6.5, bg=tc)
        for ri, r in enumerate(rows, 1):
            bg = ALT if ri % 2 == 0 else None
            crit = str(r.get("Override Criteria", "")).replace("[", "").replace("]", "")
            val = str(r.get("Override Value", "")).replace("ACCOUNTS.", "")
            cell_fmt(tbl.cell(ri, 0), crit, fs=fs, bg=bg, align=PP_ALIGN.LEFT)
            cell_fmt(tbl.cell(ri, 1), val, fs=fs, bg=bg, bold=True, fg=factor_color(val))
            cell_fmt(tbl.cell(ri, 2), "Y" if is_true(r.get("Stop Process")) else "",
                     fs=fs, bg=bg, fg=RED, bold=True)
    dk.footer(slide)


def category_grid_table(dk, slide, S, category, y=0.84, height=None):
    """Render the N-type factor grid for one category. Returns the data used."""
    data = range_grid(S, category, dk.types)
    n = len(dk.types)
    type_col_w = min(2.0, (9.76 - 2.8) / n) if n else 2.0
    label_w = 9.76 - type_col_w * n
    w = [label_w] + [type_col_w] * n
    if height is None:
        height = min(4.35, 0.235 * (len(data) + 1))
    tbl = slide.shapes.add_table(len(data) + 1, n + 1, Inches(0.12), Inches(y),
                                 Inches(sum(w)), Inches(height)).table
    for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
    hdr(tbl.cell(0, 0), category, fs=8)
    for ci, t in enumerate(dk.types, 1):
        hdr(tbl.cell(0, ci), f"{t} ({dk.codes.get(t,'')})", fs=7.5, bg=dk.colors[t])
    for ri, row in enumerate(data, 1):
        bg = ALT if ri % 2 == 0 else None
        cell_fmt(tbl.cell(ri, 0), row["label"], fs=7.5, bg=bg, align=PP_ALIGN.LEFT)
        for ci, t in enumerate(dk.types, 1):
            v = row.get(t, "—")
            cell_fmt(tbl.cell(ri, ci), fmt_factor(v), fs=7.5, bg=bg, bold=True, fg=factor_color(v))
    return data


def slide_category(dk, S, category, title, subtitle, note=None):
    slide = dk.new_slide()
    dk.title_bar(slide, title, subtitle)
    data = range_grid(S, category, dk.types)
    section_label(slide, 0.12, 0.60, 9.76, 0.22,
                  f"  {category.upper()} — POINTS BY RANGE ({len(data)} ranges)")
    category_grid_table(dk, slide, S, category, y=0.84)
    # auto-note: which types are not scored on this category
    zt = zero_types(data, dk.types)
    auto = ""
    if zt and len(zt) < len(dk.types):
        auto = f"{', '.join(zt)} carr{'ies' if len(zt)==1 else 'y'} 0 points across all {category.lower()} ranges (not scored on this variable)."
    text = " ".join(x for x in (note, auto) if x)
    if text:
        nb = slide.shapes.add_textbox(Inches(0.12), Inches(5.06), Inches(9.7), Inches(0.3))
        r = nb.text_frame.paragraphs[0].add_run(); r.text = text
        r.font.size = Pt(7.5); r.font.italic = True; r.font.color.rgb = MED; r.font.name = "Calibri"
    dk.footer(slide)


def slide_age_declines(dk, S):
    slide = dk.new_slide()
    dk.title_bar(slide, "Matrix Variables — Age of Account & Monthly Debit Declines",
                 "Points added to / subtracted from the scored limit by account age")
    age = range_grid(S, "Age of Account", dk.types)
    section_label(slide, 0.12, 0.60, 9.76, 0.22,
                  f"  AGE OF ACCOUNT — POINTS BY AGE ({len(age)} ranges)")
    category_grid_table(dk, slide, S, "Age of Account", y=0.84,
                        height=min(3.35, 0.235 * (len(age) + 1)))

    dd = range_grid(S, "Monthly Debit Declines", dk.types)
    notes = []
    if dd:
        if all_zero(dd, dk.types):
            notes.append("Monthly Debit Declines: all range factors are 0 for every account type — "
                         "debit-decline scoring is configured but inactive.")
        else:
            nz = [t for t in dk.types if t not in zero_types(dd, dk.types)]
            notes.append(f"Monthly Debit Declines: active scoring for {', '.join(nz)}.")
    zt_age = zero_types(age, dk.types)
    if zt_age:
        notes.append(f"{', '.join(zt_age)} carr{'ies' if len(zt_age)==1 else 'y'} 0 points for Age of Account.")
    if notes:
        note = slide.shapes.add_textbox(Inches(0.12), Inches(4.30), Inches(9.7), Inches(0.9))
        tf = note.text_frame; tf.word_wrap = True
        r = tf.paragraphs[0].add_run(); r.text = "  ".join(notes)
        r.font.size = Pt(8.5); r.font.italic = True; r.font.color.rgb = MED; r.font.name = "Calibri"
    dk.footer(slide)


def slide_trend_triggers(dk, S, oned_repos):
    """Trigger-threshold table (per account type × repository) plus any 1-D
    trend repositories (e.g. OD Repayment) rendered as small factor tables."""
    slide = dk.new_slide()
    dk.title_bar(slide, "Trending Adjustments — Triggers & Repayment",
                 "Trigger minimums that arm each trend; negative factors reduce the scored limit")

    rows = trend_trigger_rows(S, dk.types)
    # only keep trigger columns that carry a real value somewhere
    fields = [("dep_cnt", "Min Dep\nCount"), ("dep_amt", "Min Dep\nAmount"),
              ("od_cnt", "Min OD\nCount")]
    fields = [(k, h) for k, h in fields if any(r[k] != "—" for r in rows)]
    cols = ["Account Type", "Repository"] + [h for _, h in fields]
    w = [1.4, 2.5] + [1.0] * len(fields)
    section_label(slide, 0.12, 0.60, min(9.76, sum(w)), 0.22, "  TRENDING TRIGGER THRESHOLDS")
    tbl = slide.shapes.add_table(len(rows) + 1, len(cols), Inches(0.12), Inches(0.84),
                                 Inches(sum(w)), Inches(min(2.4, 0.30 * (len(rows) + 1)))).table
    for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
    for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=7.5)
    for ri, r in enumerate(rows, 1):
        bg = ALT if ri % 2 == 0 else None
        cell_fmt(tbl.cell(ri, 0), r["type"], fs=7.5, bold=True, fg=WHITE,
                 bg=dk.colors.get(r["type"], NAVY), align=PP_ALIGN.LEFT)
        cell_fmt(tbl.cell(ri, 1), r["repo"], fs=7.5, bg=bg, align=PP_ALIGN.LEFT)
        for ci, (k, _) in enumerate(fields, 2):
            val = r[k]
            if k == "dep_amt" and val != "—":
                val = f"${val}"
            cell_fmt(tbl.cell(ri, ci), val, fs=7.5, bg=bg)

    # 1-D repositories (usually OD Repayment): small 2-column factor tables
    y = 0.84 + min(2.4, 0.30 * (len(rows) + 1)) + 0.45
    for repo in oned_repos:
        st = trend_structure(S, repo)
        if not st["dims"]:
            continue
        cap, labels = st["dims"][0]
        section_label(slide, 0.12, y - 0.24, 5.6, 0.22, f"  {repo.upper()} — FACTORS")
        t = slide.shapes.add_table(len(labels) + 1, 2, Inches(0.12), Inches(y),
                                   Inches(5.6), Inches(min(1.9, 0.30 * (len(labels) + 1)))).table
        t.columns[0].width = Inches(4.0); t.columns[1].width = Inches(1.6)
        hdr(t.cell(0, 0), cap, fs=7.5); hdr(t.cell(0, 1), "Factor", fs=7.5)
        for ri, lb in enumerate(labels, 1):
            bg = ALT if ri % 2 == 0 else None
            f = st["factors"].get((lb,), "—")
            cell_fmt(t.cell(ri, 0), lb, fs=7.5, bg=bg, align=PP_ALIGN.LEFT)
            cell_fmt(t.cell(ri, 1), fmt_factor(f), fs=7.5, bg=bg, bold=True, fg=factor_color(f))
        y += min(1.9, 0.30 * (len(labels) + 1)) + 0.45
    dk.footer(slide)


def slide_trend_grid(dk, S, repo, st):
    """Dedicated slide rendering a 2-D trend factor grid for one repository."""
    slide = dk.new_slide()
    shared = "shared across account types" if st["shared"] else "differs by account type — showing first type"
    dk.title_bar(slide, f"Trending — {repo}",
                 f"Factor grid ({shared}); negative factors reduce the scored limit")
    (capA, labsA), (capB, labsB) = st["dims"][0], st["dims"][1]
    # orient so the dimension with more buckets runs down the rows
    if len(labsA) >= len(labsB):
        row_cap, rows_l, col_cap, cols_l, swap = capA, labsA, capB, labsB, False
    else:
        row_cap, rows_l, col_cap, cols_l, swap = capB, labsB, capA, labsA, True

    def fac(rl, cl):
        return st["factors"].get((cl, rl) if swap else (rl, cl), "—")

    def short_cap(c, n):
        c = c.replace(" / ", " ÷ ")
        return c if len(c) <= n else c[:n - 1] + "…"

    section_label(slide, 0.12, 0.60, 9.76, 0.22,
                  f"  ROWS: {short_cap(row_cap, 52)}   ·   COLUMNS: {short_cap(col_cap, 40)}")
    ncol = len(cols_l) + 1
    label_w = 2.1
    cw = (9.76 - label_w) / len(cols_l)
    nrow = len(rows_l) + 1
    h = min(4.5, 0.30 * nrow)
    fs = 7 if ncol <= 9 else (6.2 if ncol <= 12 else 5.5)
    tbl = slide.shapes.add_table(nrow, ncol, Inches(0.12), Inches(0.86),
                                 Inches(9.76), Inches(h)).table
    tbl.columns[0].width = Inches(label_w)
    for i in range(len(cols_l)): tbl.columns[i + 1].width = Inches(cw)
    hdr(tbl.cell(0, 0), short_cap(row_cap, 34), fs=fs)
    for c, cl in enumerate(cols_l, 1): hdr(tbl.cell(0, c), cl, fs=fs)
    for r, rl in enumerate(rows_l, 1):
        bg = ALT if r % 2 == 0 else None
        cell_fmt(tbl.cell(r, 0), rl, fs=fs, bold=True, bg=bg, align=PP_ALIGN.LEFT)
        for c, cl in enumerate(cols_l, 1):
            v = fac(rl, cl)
            cell_fmt(tbl.cell(r, c), fmt_factor(v), fs=fs, bold=True, fg=factor_color(v), bg=bg)
    if st.get("truncated"):
        nb = slide.shapes.add_textbox(Inches(0.12), Inches(0.86 + h + 0.05), Inches(9.7), Inches(0.3))
        rr = nb.text_frame.paragraphs[0].add_run()
        rr.text = ("Note: some range labels were reconstructed positionally because the source "
                   "export truncated the long rule text; factor values are exact.")
        rr.font.size = Pt(7.5); rr.font.italic = True; rr.font.color.rgb = MED; rr.font.name = "Calibri"
    dk.footer(slide)


def slide_tiers(dk, S, settings):
    slide = dk.new_slide()
    dk.title_bar(slide, "Tiered Limits & Rounding",
                 "The scored limit is snapped to a tier ceiling before overrides are applied")
    ts = tier_summary(S)
    section_label(slide, 0.12, 0.60, 9.76, 0.22, "  TIER TABLE SUMMARY BY MATRIX CODE")
    # rows: account types that have their own tier table
    owners = [t for t in dk.types if t in ts]
    cols = ["Matrix", "Code", "# Tiers", "Score Bands", "Score Range", "Max Limit"]
    w = [1.6, 0.7, 1.1, 1.9, 1.7, 1.4]
    tbl = slide.shapes.add_table(len(owners) + 1, len(cols), Inches(0.12), Inches(0.84),
                                 Inches(sum(w)), Inches(min(1.6, 0.30 * (len(owners) + 1)))).table
    for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
    for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=8)
    for ri, t in enumerate(owners, 1):
        d = ts[t]; tc = dk.colors[t]
        band = f'${d["band_w"]:,.2f} uniform' if d["band_w"] is not None else "Variable"
        cell_fmt(tbl.cell(ri, 0), t, fs=8, bold=True, fg=WHITE, bg=tc, align=PP_ALIGN.LEFT)
        cell_fmt(tbl.cell(ri, 1), dk.codes.get(t, d["code"]), fs=8, bold=True, fg=WHITE, bg=tc)
        cell_fmt(tbl.cell(ri, 2), f'{d["n"]}', fs=8)
        cell_fmt(tbl.cell(ri, 3), band, fs=8)
        cell_fmt(tbl.cell(ri, 4), f'${d["score_min"]:,.0f} – ${d["score_max"]:,.0f}', fs=8)
        cell_fmt(tbl.cell(ri, 5), f'${d["max_limit"]:,.0f}', fs=9, bold=True, fg=GREEN)

    # narrative: how tiering works, computed per client
    lines = [("How tiering works", True),
             ("• Each account's scored intermediate limit is mapped up to the nearest tier "
              "ceiling; that tier's Limit Value becomes the granted limit before override "
              "rules run.", False)]
    for t in owners:
        d = ts[t]
        band = (f"uniform ${d['band_w']:,.2f} score bands" if d["band_w"] is not None
                else "variable-width score bands")
        lines.append((f"• {t} (Matrix {dk.codes.get(t, d['code'])}) uses {d['n']} tiers "
                      f"({band}), scores ${d['score_min']:,.0f}–${d['score_max']:,.0f}, "
                      f"max limit ${d['max_limit']:,.0f}.", False))
    # account types that share another code's tier table
    for t in dk.types:
        if t in ts:
            continue
        code = dk.codes.get(t, "")
        owner = next((o for o in owners if dk.codes.get(o, ts[o]["code"]) == code), None)
        try:
            cap = f"${int(float(settings.get(t, {}).get('Max', 0))):,}"
        except (ValueError, TypeError):
            cap = "its account-type maximum"
        if owner:
            lines.append((f"• {t} shares the {owner} (Matrix {code}) tier table; its granted "
                          f"limit is capped at {cap}.", False))
    box = slide.shapes.add_textbox(Inches(0.12), Inches(0.86 + min(1.6, 0.30 * (len(owners) + 1)) + 0.2),
                                   Inches(9.7), Inches(2.9))
    tf = box.text_frame; tf.word_wrap = True
    for txt, bold in lines:
        p = tf.paragraphs[0] if txt == "How tiering works" else tf.add_paragraph()
        r = p.add_run(); r.text = txt
        r.font.size = Pt(10 if bold else 9); r.font.bold = bold
        r.font.color.rgb = NAVY if bold else DARK; r.font.name = "Calibri"
        p.space_after = Pt(5)
    dk.footer(slide)


def find_col(row, *needles):
    """First column name containing all needles (case-insensitive), else None."""
    for k in row:
        kl = k.lower()
        if all(n.lower() in kl for n in needles):
            return k
    return None


def _live(v):
    """True when a settings value is present (not blank/NULL)."""
    return str(v).strip() not in ("", "NULL", "None")


LN_FIELDS = [
    ("Limit Notification",                  "Enabled",       "bool"),
    ("Limit Notification Cycle On",         "Cycle Day",     "raw"),
    ("Limit Notification Zero Setting",     "Zero Balance",  "bool"),
    ("Limit Notification Recovery Setting", "Recovery",      "bool"),
    ("Limit Notification Reinstatement",    "Reinstatement", "bool"),
]


def has_limit_notification(settings):
    return any(_live(r.get("Limit Notification")) for r in settings.values())


def has_cashplease(settings):
    for r in settings.values():
        for c in (find_col(r, "CashPlease", "Max $"),
                  find_col(r, "CashPlease", "Max %"),
                  find_col(r, "CashPlease", "Elig")):
            if c and _live(r.get(c)):
                return True
    return False


def slide_limit_notification(dk, settings):
    slide = dk.new_slide()
    dk.title_bar(slide, "Limit Notification Settings",
                 "Member notification of the assigned overdraft limit, by account type")
    section_label(slide, 0.12, 0.60, 9.76, 0.22, "  LIMIT NOTIFICATION CONFIGURATION")
    cols = ["Account Type"] + [h for _, h, _ in LN_FIELDS]
    w = [1.7, 1.3, 1.3, 1.5, 1.4, 1.6]
    tbl = slide.shapes.add_table(len(dk.types) + 1, len(cols), Inches(0.12), Inches(0.84),
                                 Inches(sum(w)), Inches(min(1.8, 0.32 * (len(dk.types) + 1)))).table
    for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
    for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=8)
    for ri, t in enumerate(dk.types, 1):
        r = settings.get(t, {})
        cell_fmt(tbl.cell(ri, 0), t, fs=8, bold=True, fg=WHITE, bg=dk.colors[t], align=PP_ALIGN.LEFT)
        for ci, (key, _, kind) in enumerate(LN_FIELDS, 1):
            v = r.get(key, "")
            if not _live(v):
                cell_fmt(tbl.cell(ri, ci), "—", fs=8, fg=GRAY)
            elif kind == "bool":
                cell_fmt(tbl.cell(ri, ci), yesno(v), fs=8, fg=GREEN if is_true(v) else GRAY)
            else:
                cell_fmt(tbl.cell(ri, ci), str(v), fs=8)
    note = slide.shapes.add_textbox(Inches(0.12), Inches(3.0), Inches(9.7), Inches(2.2))
    tf = note.text_frame; tf.word_wrap = True
    for txt, bold in [
        ("How limit notification works", True),
        ("• Enabled — whether the member is notified of their calculated overdraft limit.", False),
        ("• Cycle Day — day of the statement/notification cycle on which limits are published.", False),
        ("• Zero Balance — send a notification even when the calculated limit is $0.", False),
        ("• Recovery — notify when a suspended limit is restored after recovery.", False),
        ("• Reinstatement — notify when a removed limit is reinstated.", False),
    ]:
        p = tf.paragraphs[0] if bold and txt.startswith("How") else tf.add_paragraph()
        r = p.add_run(); r.text = txt
        r.font.size = Pt(10 if bold else 9); r.font.bold = bold
        r.font.color.rgb = NAVY if bold else DARK; r.font.name = "Calibri"
        p.space_after = Pt(4)
    dk.footer(slide)


def slide_cashplease(dk, settings):
    slide = dk.new_slide()
    dk.title_bar(slide, "CashPlease Settings",
                 "Small-dollar CashPlease loan configuration, by account type")
    section_label(slide, 0.12, 0.60, 9.76, 0.22, "  CASHPLEASE CONFIGURATION")
    cols = ["Account Type", "CashPlease Max $", "CashPlease Max %", "CashPlease Eligible"]
    w = [1.9, 2.1, 2.1, 2.2]
    tbl = slide.shapes.add_table(len(dk.types) + 1, len(cols), Inches(0.12), Inches(0.84),
                                 Inches(sum(w)), Inches(min(1.8, 0.32 * (len(dk.types) + 1)))).table
    for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
    for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=8)
    enabled = []
    for ri, t in enumerate(dk.types, 1):
        r = settings.get(t, {})
        mx = find_col(r, "CashPlease", "Max $"); pc = find_col(r, "CashPlease", "Max %")
        el = find_col(r, "CashPlease", "Elig")
        mx_v = r.get(mx) if mx else None; pc_v = r.get(pc) if pc else None
        el_v = r.get(el) if el else None
        elig = _live(el_v) and is_true(el_v)
        cell_fmt(tbl.cell(ri, 0), t, fs=8, bold=True, fg=WHITE, bg=dk.colors[t], align=PP_ALIGN.LEFT)
        try:
            mxt = f"${float(str(mx_v).replace(',', '')):,.2f}" if _live(mx_v) else "—"
        except ValueError:
            mxt = str(mx_v)
        try:
            pct = f"{float(str(pc_v).replace(',', '')):.0f}%" if _live(pc_v) else "—"
        except ValueError:
            pct = str(pc_v)
        cell_fmt(tbl.cell(ri, 1), mxt, fs=8, bold=_live(mx_v), fg=GREEN if _live(mx_v) else GRAY)
        cell_fmt(tbl.cell(ri, 2), pct, fs=8)
        cell_fmt(tbl.cell(ri, 3), yesno(el_v) if _live(el_v) else "—",
                 fs=8, bold=True, fg=GREEN if elig else GRAY)
        if elig:
            enabled.append(t)
    note = slide.shapes.add_textbox(Inches(0.12), Inches(2.7), Inches(9.7), Inches(2.4))
    tf = note.text_frame; tf.word_wrap = True
    summary = (f"CashPlease is enabled for: {', '.join(enabled)}."
               if enabled else "CashPlease is not currently enabled for any account type.")
    for txt, bold in [
        ("About CashPlease", True),
        (summary, False),
        ("• CashPlease Max $ — maximum small-dollar loan amount offered.", False),
        ("• CashPlease Max % — cap expressed as a percentage of the qualifying figure.", False),
        ("• CashPlease Eligible — whether accounts of this type may be offered CashPlease.", False),
    ]:
        p = tf.paragraphs[0] if bold and txt == "About CashPlease" else tf.add_paragraph()
        r = p.add_run(); r.text = txt
        r.font.size = Pt(10 if bold else 9); r.font.bold = bold
        r.font.color.rgb = NAVY if bold else DARK; r.font.name = "Calibri"
        p.space_after = Pt(4)
    dk.footer(slide)


# ── optional component slides (Communication Strategies / Strategic Refunds /
#    Deposit Score), each rendered only when that component is active ───────────
def has_comm_strategies(S):
    return any(is_true(r.get("ACTIVE")) for r in _section(S, "COMMUNICATION STRATEGIES"))


def has_strategic_refunds(S):
    return any(_section(S, n) for n in (
        "STRATEGIC REFUNDS RANGES AND FACTORS",
        "STRATEGIC REFUNDS TIERS",
        "STRATEGIC REFUNDS DAILY MAX"))


def has_deposit_score(S):
    return any(is_true(r.get("ACTIVE")) for r in _section(S, "DEPOSIT SCORE MATRIX"))


ROWS_PER_SLIDE = 15


def _paginate(items, per, show_all):
    """Split items into page-slices. When not show_all, only the first page is
    returned (the caller adds a 'showing N of M' note)."""
    pages = [items[i:i + per] for i in range(0, len(items), per)] or [[]]
    return pages if show_all else pages[:1]


def _overflow_note(slide, y, shown, total, what):
    nb = slide.shapes.add_textbox(Inches(0.12), Inches(y), Inches(9.7), Inches(0.3))
    rr = nb.text_frame.paragraphs[0].add_run()
    rr.text = (f"Showing {shown} of {total} {what}. "
               f"Enable “show all rows” to list them across multiple slides.")
    rr.font.size = Pt(7.5); rr.font.italic = True; rr.font.color.rgb = MED; rr.font.name = "Calibri"


def slide_comm_strategies(dk, S, show_all=False):
    all_rows = _section(S, "COMMUNICATION STRATEGIES")
    active = [r for r in all_rows if is_true(r.get("ACTIVE"))]

    def pri(r):
        v = str(r.get("STRATEGY_PRIORITY", "")).strip()
        return int(v) if v.isdigit() else 999
    active.sort(key=lambda r: (pri(r), r.get("STRATEGY_NAME", "")))

    pages = _paginate(active, ROWS_PER_SLIDE, show_all)
    cols = ["Strategy Name", "Priority", "Repeat (days)", "Remove (days)", "Remove on + Balance"]
    w = [4.3, 1.0, 1.5, 1.5, 1.46]
    for pi, page in enumerate(pages, 1):
        slide = dk.new_slide()
        suffix = f"  ({pi} of {len(pages)})" if len(pages) > 1 else ""
        dk.title_bar(slide, "Communication Strategies" + suffix,
                     f"{len(active)} of {len(all_rows)} strategies active — member outreach cadence")
        section_label(slide, 0.12, 0.60, 9.76, 0.22, "  ACTIVE COMMUNICATION STRATEGIES")
        tbl = slide.shapes.add_table(len(page) + 1, len(cols), Inches(0.12), Inches(0.84),
                                     Inches(sum(w)), Inches(min(4.3, 0.29 * (len(page) + 1)))).table
        for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
        for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=7.5)
        for ri, r in enumerate(page, 1):
            bg = ALT if ri % 2 == 0 else None
            rep = str(r.get("THRESHOLD_REPEAT", "")).strip()
            rep = "never" if rep in ("99999", "999999") else (rep or "—")
            rem = str(r.get("THRESHOLD_REMOVE", "")).strip()
            rem = rem if rem and rem.upper() != "NULL" else "—"
            cell_fmt(tbl.cell(ri, 0), r.get("STRATEGY_NAME", ""), fs=7, bg=bg, align=PP_ALIGN.LEFT)
            cell_fmt(tbl.cell(ri, 1), r.get("STRATEGY_PRIORITY", ""), fs=7, bg=bg)
            cell_fmt(tbl.cell(ri, 2), rep, fs=7, bg=bg)
            cell_fmt(tbl.cell(ri, 3), rem, fs=7, bg=bg)
            cell_fmt(tbl.cell(ri, 4), yesno(r.get("RemoveOnPositiveBalance")), fs=7, bg=bg,
                     fg=GREEN if is_true(r.get("RemoveOnPositiveBalance")) else GRAY)
        if not show_all and len(active) > len(page):
            _overflow_note(slide, 5.06, len(page), len(active), "active strategies (by priority)")
        dk.footer(slide)


def _deposit_rules_table(slide, rows, y, cols2, w2):
    tbl2 = slide.shapes.add_table(len(rows) + 1, len(cols2), Inches(0.12), Inches(y),
                                  Inches(sum(w2)), Inches(min(4.2, 0.26 * (len(rows) + 1)))).table
    for i, wd in enumerate(w2): tbl2.columns[i].width = Inches(wd)
    for c, h in enumerate(cols2): hdr(tbl2.cell(0, c), h, fs=7.5)
    for ri, r in enumerate(rows, 1):
        bg = ALT if ri % 2 == 0 else None
        cell_fmt(tbl2.cell(ri, 0), r.get("NAME", ""), fs=7, bg=bg, align=PP_ALIGN.LEFT)
        cell_fmt(tbl2.cell(ri, 1), yesno(r.get("ENABLE")), fs=7, bg=bg,
                 fg=GREEN if is_true(r.get("ENABLE")) else GRAY)
        desc = str(r.get("DESCRIPTION", "")).strip()
        cell_fmt(tbl2.cell(ri, 2), desc if desc and desc != "NULL" else "—", fs=7, bg=bg, align=PP_ALIGN.LEFT)


def slide_deposit_score(dk, S, show_all=False):
    dm = _section(S, "DEPOSIT SCORE MATRIX")
    dr = _section(S, "DEPOSIT SCORE MATRIX RULES")
    rules_total = defaultdict(int); rules_on = defaultdict(int)
    for r in dr:
        mid = r.get("DEPOSIT_SCORE_ID")
        rules_total[mid] += 1
        if is_true(r.get("ENABLE")):
            rules_on[mid] += 1

    slide = dk.new_slide()
    dk.title_bar(slide, "Deposit Score Matrix",
                 "Regression-tree deposit-score models configured for the institution")
    section_label(slide, 0.12, 0.60, 9.76, 0.22, "  DEPOSIT SCORE MATRICES")
    cols = ["Matrix Name", "Active", "Assign Default", "Apply Tier", "Critical", "Rules (on / total)"]
    w = [2.6, 1.0, 1.5, 1.3, 1.1, 2.26]
    tbl = slide.shapes.add_table(len(dm) + 1, len(cols), Inches(0.12), Inches(0.84),
                                 Inches(sum(w)), Inches(min(1.8, 0.32 * (len(dm) + 1)))).table
    for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
    for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=8)
    for ri, r in enumerate(dm, 1):
        bg = ALT if ri % 2 == 0 else None
        mid = r.get("ID")
        act = is_true(r.get("ACTIVE"))
        cell_fmt(tbl.cell(ri, 0), r.get("NAME", ""), fs=8, bold=True, bg=bg, align=PP_ALIGN.LEFT)
        cell_fmt(tbl.cell(ri, 1), yesno(r.get("ACTIVE")), fs=8, bg=bg, bold=True,
                 fg=GREEN if act else GRAY)
        cell_fmt(tbl.cell(ri, 2), yesno(r.get("ASSIGN_DEFAULT")), fs=8, bg=bg)
        cell_fmt(tbl.cell(ri, 3), yesno(r.get("APPLY_TIER")), fs=8, bg=bg)
        cell_fmt(tbl.cell(ri, 4), yesno(r.get("CRITICAL")), fs=8, bg=bg)
        cell_fmt(tbl.cell(ri, 5), f"{rules_on.get(mid,0)} / {rules_total.get(mid,0)}", fs=8, bg=bg)

    active_ids = {r.get("ID") for r in dm if is_true(r.get("ACTIVE"))}
    act_rules = [r for r in dr if r.get("DEPOSIT_SCORE_ID") in active_ids] or dr
    cols2 = ["Rule Name", "Enabled", "Description"]; w2 = [2.6, 1.0, 6.16]
    y = 0.86 + min(1.8, 0.32 * (len(dm) + 1)) + 0.35
    FIRST = 10   # rules that fit below the matrices table on the first slide
    section_label(slide, 0.12, y - 0.24, 9.76, 0.22, "  RULES (ACTIVE MATRICES)")
    _deposit_rules_table(slide, act_rules[:FIRST], y, cols2, w2)
    if not show_all and len(act_rules) > FIRST:
        _overflow_note(slide, y + min(4.2, 0.26 * (FIRST + 1)) + 0.05, FIRST, len(act_rules), "rules")
    dk.footer(slide)
    # continuation slides for the remaining rules
    if show_all and len(act_rules) > FIRST:
        for page in _paginate(act_rules[FIRST:], ROWS_PER_SLIDE, True):
            s2 = dk.new_slide()
            dk.title_bar(s2, "Deposit Score Matrix — Rules (continued)",
                         "Regression-tree rules for the active deposit-score matrices")
            section_label(s2, 0.12, 0.60, 9.76, 0.22, "  RULES (CONTINUED)")
            _deposit_rules_table(s2, page, 0.84, cols2, w2)
            dk.footer(s2)


def slide_strategic_refunds(dk, S, show_all=False):
    rf = _section(S, "STRATEGIC REFUNDS RANGES AND FACTORS")
    dmax = _section(S, "STRATEGIC REFUNDS DAILY MAX")
    tiers = _section(S, "STRATEGIC REFUNDS TIERS")

    slide = dk.new_slide()
    dk.title_bar(slide, "Strategic Refunds",
                 "Risk-scored fee-refund program: scoring categories and daily caps")

    # scoring categories (grouped) on the left
    bycat = OrderedDict()
    for r in rf:
        bycat.setdefault(r.get("Category", ""), []).append(r.get("Factor", ""))
    if bycat:
        section_label(slide, 0.12, 0.60, 5.5, 0.22, "  SCORING CATEGORIES")
        cols = ["Category", "# Ranges", "Factor Range"]
        w = [3.5, 0.9, 1.1]
        tbl = slide.shapes.add_table(len(bycat) + 1, 3, Inches(0.12), Inches(0.84),
                                     Inches(sum(w)), Inches(min(3.6, 0.30 * (len(bycat) + 1)))).table
        for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
        for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=7.5)
        for ri, (cat, facs) in enumerate(bycat.items(), 1):
            bg = ALT if ri % 2 == 0 else None
            nums = [_num(f) for f in facs if _num(f) is not None]
            frng = f"{min(nums):g}–{max(nums):g}" if nums else "—"
            cell_fmt(tbl.cell(ri, 0), cat, fs=6.5, bg=bg, align=PP_ALIGN.LEFT)
            cell_fmt(tbl.cell(ri, 1), str(len(facs)), fs=7, bg=bg)
            cell_fmt(tbl.cell(ri, 2), frng, fs=7, bg=bg)

    # daily strategic max on the right
    if dmax:
        section_label(slide, 5.9, 0.60, 3.98, 0.22, "  DAILY STRATEGIC MAX")
        qk = find_col(dmax[0], "QTY"); uk = find_col(dmax[0], "USD")
        rows = sorted(dmax, key=lambda r: _num(r.get(qk)) if qk and _num(r.get(qk)) is not None else 0)
        tbl2 = slide.shapes.add_table(len(rows) + 1, 2, Inches(5.9), Inches(0.84),
                                      Inches(3.98), Inches(min(3.0, 0.30 * (len(rows) + 1)))).table
        tbl2.columns[0].width = Inches(1.98); tbl2.columns[1].width = Inches(2.0)
        hdr(tbl2.cell(0, 0), "Refunds / Day (Qty)", fs=7.5)
        hdr(tbl2.cell(0, 1), "Max Refund $ / Day", fs=7.5)
        for ri, r in enumerate(rows, 1):
            bg = ALT if ri % 2 == 0 else None
            usd = _num(r.get(uk)) if uk else None
            cell_fmt(tbl2.cell(ri, 0), r.get(qk, "") if qk else "", fs=7.5, bg=bg)
            cell_fmt(tbl2.cell(ri, 1), f"${usd:,.2f}" if usd is not None else "—",
                     fs=7.5, bg=bg, bold=True, fg=GREEN)

    note = slide.shapes.add_textbox(Inches(0.12), Inches(4.55), Inches(9.7), Inches(0.7))
    tf = note.text_frame; tf.word_wrap = True
    rr = tf.paragraphs[0].add_run()
    ntiers = len({r.get("REFUND_ID") for r in tiers}) if tiers else 0
    rr.text = (f"Strategic Refunds scores accounts across {len(bycat)} categories; the resulting risk "
               f"score maps to a refund tier"
               + (f" ({len(tiers)} tier rows)" if tiers else "")
               + ", subject to the per-day dollar/quantity caps above."
               + ("" if show_all else "  Ranges & factors detailed on the next slide(s) when "
                  "“show all rows” is enabled."))
    rr.font.size = Pt(8); rr.font.italic = True; rr.font.color.rgb = MED; rr.font.name = "Calibri"
    dk.footer(slide)

    # detailed ranges & factors (paginated) — only when show_all
    if show_all and rf:
        cols = ["Category", "Range", "Factor"]; w = [4.0, 4.16, 1.6]
        PER = 16
        pages = _paginate(rf, PER, True)
        for pi, page in enumerate(pages, 1):
            s2 = dk.new_slide()
            suffix = f"  ({pi} of {len(pages)})" if len(pages) > 1 else ""
            dk.title_bar(s2, "Strategic Refunds — Ranges & Factors" + suffix,
                         "Risk-score factor by category and range")
            section_label(s2, 0.12, 0.60, 9.76, 0.22, "  RANGES & FACTORS")
            tbl = s2.shapes.add_table(len(page) + 1, 3, Inches(0.12), Inches(0.84),
                                      Inches(sum(w)), Inches(min(4.4, 0.27 * (len(page) + 1)))).table
            for i, wd in enumerate(w): tbl.columns[i].width = Inches(wd)
            for c, h in enumerate(cols): hdr(tbl.cell(0, c), h, fs=7.5)
            for ri, r in enumerate(page, 1):
                bg = ALT if ri % 2 == 0 else None
                cell_fmt(tbl.cell(ri, 0), r.get("Category", ""), fs=6.5, bg=bg, align=PP_ALIGN.LEFT)
                cell_fmt(tbl.cell(ri, 1), clean_range(r.get("Range", "")), fs=6.5, bg=bg, align=PP_ALIGN.LEFT)
                fv = r.get("Factor", "")
                cell_fmt(tbl.cell(ri, 2), fmt_factor(fv), fs=7, bg=bg, bold=True, fg=factor_color(fv))
            dk.footer(s2)


# ═════════════════════════════ orchestration ═════════════════════════════════
def _report_date(txt_path, override=None):
    if override:
        return override
    m = re.search(r"(\d{8})", os.path.basename(txt_path))
    if m:
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d")
            return f"{d.strftime('%B')} {d.day}, {d.year}"
        except ValueError:
            pass
    return datetime.today().strftime("%B ") + f"{datetime.today().day}, {datetime.today().year}"


CATEGORY_SLIDES = [
    ("Actual Monthly Deposit Count",
     "Matrix Variable — Actual Monthly Deposit Count",
     "Points by number of deposits in the month; negative factors reduce the scored limit"),
    ("Actual Monthly Deposits",
     "Matrix Variable — Actual Monthly Deposit Dollars",
     "Points by total monthly deposit dollars"),
]
HANDLED_CATEGORIES = {"Actual Monthly Deposit Count", "Actual Monthly Deposits",
                      "Age of Account", "Monthly Debit Declines"}


def build_deck(txt_path, client_name, out_path=None, report_date=None, out_dir=None,
               replace_mrpc=False, extra_components=False, show_all_rows=False):
    """Parse the client's matrix-validation file and write the deck. Returns out_path.

    Output location precedence: explicit out_path > out_dir + auto name >
    input file's folder + auto name.

    replace_mrpc: when True, 'MRPC' labels are relabeled 'CashPlease' in the deck.
    extra_components: when True, append a slide for each active supplementary
        component found in the file (Communication Strategies, Strategic Refunds,
        Deposit Score).
    show_all_rows: when True, component tables that exceed one slide are paginated
        across multiple slides instead of being capped at 15 rows.
    """
    S = parse(txt_path)
    types, codes, settings = detect_types(S)
    if not types:
        raise ValueError("No account types found — is this an ILS Matrix Validation export?")
    colors = assign_colors(types)
    date_str = _report_date(txt_path, report_date)
    footer_types = "  ·  ".join(f"{t} ({codes.get(t,'')})" for t in types)

    prs = Presentation(); prs.slide_width = Inches(10); prs.slide_height = Inches(5.625)
    dk = Deck(prs, client_name, date_str, types, codes, colors, footer_types,
              relabel_mrpc=replace_mrpc)

    slide_title(dk, settings)
    slide_settings(dk, S, settings)
    slide_overrides(dk, S)
    present = set(categories(S))
    for cat, title, sub in CATEGORY_SLIDES:
        if cat in present:
            slide_category(dk, S, cat, title, sub)
    if "Age of Account" in present:
        slide_age_declines(dk, S)
    # trends: classify each repository as 1-D or a 2-D grid, discovered from the file
    if _section(S, "TRENDS"):
        grids = []
        oned = []
        for repo in trend_repositories(S):
            st = trend_structure(S, repo)
            if len(st["dims"]) >= 2:
                grids.append((repo, st))
            elif len(st["dims"]) == 1:
                oned.append(repo)
        slide_trend_triggers(dk, S, oned)
        for repo, st in grids:
            slide_trend_grid(dk, S, repo, st)
    if _section(S, "TIERS AND ROUNDING"):
        slide_tiers(dk, S, settings)
    # any factor category we don't have a dedicated slide for
    for cat in categories(S):
        if cat not in HANDLED_CATEGORIES:
            slide_category(dk, S, cat, f"Matrix Variable — {cat}",
                           "Points by range; negative factors reduce the scored limit")
    if has_limit_notification(settings):
        slide_limit_notification(dk, settings)
    if has_cashplease(settings):
        slide_cashplease(dk, settings)
    # optional supplementary component slides, each only when active
    if extra_components:
        if has_comm_strategies(S):
            slide_comm_strategies(dk, S, show_all_rows)
        if has_strategic_refunds(S):
            slide_strategic_refunds(dk, S, show_all_rows)
        if has_deposit_score(S):
            slide_deposit_score(dk, S, show_all_rows)

    if not out_path:
        month = date_str.rsplit(",", 1)[0].rsplit(" ", 1)[0] if "," in date_str else date_str
        year = date_str.rsplit(" ", 1)[-1]
        fname = f"{client_name} - ILS Matrix Validation - {month} {year}.pptx"
        fname = re.sub(r'[<>:"/\\|?*]', "", fname)
        folder = out_dir if out_dir else os.path.dirname(os.path.abspath(txt_path))
        os.makedirs(folder, exist_ok=True)
        out_path = os.path.join(folder, fname)
    prs.save(out_path)
    return out_path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate an ILS Matrix Validation deck from a client export.")
    ap.add_argument("txt", help="path to Matrixvalidation_*.txt")
    ap.add_argument("--client", required=True, help="client name for titles/footers")
    ap.add_argument("--out", help="full output .pptx path (overrides --out-dir)")
    ap.add_argument("--out-dir", dest="out_dir",
                    help="output folder; file is auto-named (default: next to the input file)")
    ap.add_argument("--date", help='report date label, e.g. "July 3, 2026" (default: from filename)')
    ap.add_argument("--replace-mrpc", dest="replace_mrpc", action="store_true",
                    help="relabel 'MRPC' as 'CashPlease' throughout the deck")
    ap.add_argument("--extra-components", dest="extra_components", action="store_true",
                    help="append slides for active Communication Strategies / Strategic Refunds / Deposit Score")
    ap.add_argument("--all-rows", dest="show_all_rows", action="store_true",
                    help="show all component rows across multiple slides instead of capping at 15")
    a = ap.parse_args()
    out = build_deck(a.txt, a.client, a.out, a.date, a.out_dir, a.replace_mrpc,
                     a.extra_components, a.show_all_rows)
    print("Saved:", out)
