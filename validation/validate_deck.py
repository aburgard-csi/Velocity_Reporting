#!/usr/bin/env python3
"""
validate_deck.py — the pre-ship lint gate for a built deck (every program).

    python3 validate_deck.py <deck.pptx> [base_extract.json]

Exit 0 when there is no FAIL-level finding, 1 otherwise. A non-zero exit blocks
delivery: fix the BUILDER or the template shell and rebuild (CLAUDE.md). It is a
text + structure linter — it reads the package and the shapes, never a rendered
chart — so anything only a picture could settle is reported as REVIEW (look with
your eyes), not FAIL.

Every rule is a function returning [(level, slide_index, message)]; `RULES` lists
them in the order they run, and `run()` is what main() and the tests call. The
rules, and the shipped defect each one exists for:

    package_findings              duplicated / dangling / orphaned slide parts (2026.08 ICS decks)
    reference_leak_findings       another client's name in a slide body ("Union Financial" on Q&A)
    single_line_overflow_findings a one-line label wider than its box, spilling onto text
    stale_template_caption_findings a dated caption still byte-identical to the template's
    figure_identity_findings      one labelled measure, two values (REVIEW — inferred)
    period_findings               span arithmetic, and captions dated after the snapshot
    source_note_findings          a data slide with no Source line, or another client's source
    closing_month_findings        Questions & Discussion month/client differs from the cover (2026.09 ARS decks)
table_label_fit_findings      a wrapped table row label pushes the table off the slide (branch names, 2026-09-17)
    figure_sidecar_findings       one NAMED measure, two values (FAIL — the builder said so)
    claim_consistency_findings    "flat" / "rose" / "lower" against the figures beside them
    text_rule_findings            banned words, plurals, thresholds, impossible counts, superlatives
    geometry_findings             off-slide shapes, number/logo collisions, chart-over-tile
    text_collision_findings       one text run drawn over another (CashPlease footnote over pills)
    autofit_findings              PowerPoint fontScale hiding an overflow
    mailing_table_findings        more mailing rows than the program has run
    extract_findings              headline figures vs base_extract.json (only when given)
    labelled_metric_findings      a labelled metric with more than two values (REVIEW)

Standing rule (Aaron, 2026-08-17): when a defect gets through this gate, add the
rule that would have caught it here — do not just fix the instance.
"""
import json
import math
import os
import re
import sys

from pptx import Presentation
from pptx.util import Emu

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))
from brand import usd_compact as _usd                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(os.path.dirname(HERE), "build")
sys.path.insert(0, BUILD)

# Optional build-tree imports. The validator must still run on a checkout that
# has only validation/ — every rule that needs one of these degrades to "no
# finding" rather than crashing the gate.
try:
    from textfit import text_width_in
except Exception:                 # pragma: no cover
    text_width_in = None
try:
    from periods import Period, parse_month, month_diff
except Exception:                 # pragma: no cover
    Period = None
try:
    from figures import FigureLog, find_sidecar
except Exception:                 # pragma: no cover
    FigureLog = None

    def find_sidecar(_):
        return None

# ---------------------------------------------------------------- slide geometry
SLIDE_W, SLIDE_H = 13.333, 7.5
# Glyph estimates shared by every geometry rule: inches of width per character
# per point, and line height per point. Box geometry is not glyph geometry
# (CLAUDE.md rule 2) — these are what the rules measure with when the bundled
# TTFs are not consulted. cp_qa.py in the CashPlease project mirrors CHAR_W.
CHAR_W = 0.0066
LINE_H = 0.0163


def _in(v):
    return Emu(v).inches if v is not None else None


def _box(sh):
    l, t, w, h = _in(sh.left), _in(sh.top), _in(sh.width), _in(sh.height)
    return None if None in (l, t, w, h) else (l, t, l + w, t + h)


def _overlap(a, b, pad=0.05):
    return (min(a[2], b[2]) - max(a[0], b[0])) > pad and (min(a[3], b[3]) - max(a[1], b[1])) > pad


def _is_num(sh):
    """The bottom-left slide number (STYLE.md: 0.45", 7.05", 0.70 x 0.30)."""
    if not (sh.has_text_frame and sh.text_frame.text.strip().isdigit()):
        return False
    b = _box(sh)
    return b is not None and b[1] > 6.5 and b[0] < 1.7 and (b[2] - b[0]) < 1.4


def _is_logo(sh):
    """The CSI | Velocity lockup — a small picture (data slides: 1.70 x 0.54)."""
    if sh.shape_type != 13:
        return False
    b = _box(sh)
    return b is not None and (b[2] - b[0]) < 3.15 and (b[3] - b[1]) < 1.2


def _is_summit(s):
    t = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
    return "Executive Summit" in t or "About the Summit" in t


def _lbl(sh):
    return (sh.text_frame.text.strip()[:34]
            if sh.has_text_frame and sh.text_frame.text.strip() else "chart/table")


def _title(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def _max_pt(sh, default=16.0):
    pts = [r.font.size.pt for pa in sh.text_frame.paragraphs for r in pa.runs if r.font.size]
    return max(pts) if pts else default


def _is_centered(sh):
    try:
        return str(sh.text_frame.paragraphs[0].alignment) == "CENTER (2)"
    except Exception:
        return False


def _has_text(sh):
    return sh.has_text_frame and bool(sh.text_frame.text.strip())


# ---------------------------------------------------------------- vocabulary
BANNED = ["robust", "comprehensive", "leverage", "seamless", "delve", "lift",
          "lifted", "ramp", "ramping", "healthy", "predominantly", "companion",
          "seasoned book", "annuity"]
# banned words that legitimately appear as data labels / fixed template terms
BANNED_ALLOW_CONTEXT = ["lift matrix"]   # 'Lift Matrix' is a named slide/table, allowed
SUPERLATIVES = ["strongest", "weakest", "best", "worst", "highest", "lowest",
                "largest", "smallest", "top-performing", "#1", "record ", "all-time"]
# filler / AI-tell phrases to keep off client-facing slides (notes/narration only)
AI_PHRASES = ["onboarding opportunity", "clear opportunity", "unlock", "empower",
              "at the end of the day", "when it comes to", "in today's landscape",
              "game-changer", "seamless", "leverage"]

# Every program template is trimmed from a real client's deck, so the reference
# client's name is baked into any literal the builder forgets to swap. All seven
# 2026.08 ICS decks shipped at 0 FAIL carrying "Union Financial  •  July 2026" on
# the Questions & Discussion slide (found 2026-08-21). A deck naming someone
# else's client is the worst thing we can hand a client, so it FAILs.
REFERENCE_CLIENTS = ["Union Financial", "Marine FCU", "Marine Federal Credit Union",
                     "Sugar River", "CoastLife", "Wellworth", "Canandaigua",
                     "Bank Name"]

# One institution can reach a deck under more than one name, and the reference list has
# to know they are ONE client. Marine FCU (1539) is the old reference client, so both of
# its names are on the list above; the CashPlease workbook calls it "Marine Federal Credit
# Union" while the roster, filename and cover say "Marine FCU". The first four-program
# deck (ARS-ICS-MRPC-CP, 2026-09-14) therefore failed on its OWN CashPlease source notes
# as "a different client's provenance". A name counts as the deck's own when any name in
# its group is on the filename or cover; a genuinely different client still fails.
REFERENCE_ALIASES = [("Marine FCU", "Marine Federal Credit Union")]


def _is_own_name(name, own):
    group = next((g for g in REFERENCE_ALIASES if name in g), (name,))
    return any(n.lower() in own for n in group)

# The program tags a filename can carry (CLAUDE.md filename convention).
PROGRAM_TAGS = ("ARS", "ICS", "MRPC", "CP")


def _own_client(path, prs):
    """Everything that legitimately identifies THIS deck: filename + title slide."""
    own = os.path.basename(path).lower()
    try:
        for sh in prs.slides[0].shapes:
            if sh.has_text_frame:
                own += " " + sh.text_frame.text.lower()
    except Exception:
        pass
    return own


def slide_texts(prs):
    """[(slide_index, [every text block on the slide, tables as ' | ' rows])]."""
    out = []

    def rec(shapes):
        for sh in shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                yield sh.text_frame.text
            if sh.has_table:
                for row in sh.table.rows:
                    yield " | ".join(c.text for c in row.cells)
            if sh.shape_type == 6:
                yield from rec(sh.shapes)
    for i, s in enumerate(prs.slides, 1):
        out.append((i, list(rec(s.shapes))))
    return out


def _has_chart_image(slide):
    """A picture that is not the logo (image1 is the lockup in every shell)."""
    for sh in slide.shapes:
        if sh.shape_type == 13:  # picture
            try:
                rId = sh._element.blipFill.blip.rEmbed
                pn = str(slide.part.rels[rId].target_part.partname)
                if not pn.endswith("image1.png"):
                    return True
            except Exception:
                pass
    return False


def has_chart_image(prs, idx):
    return _has_chart_image(list(prs.slides)[idx - 1])


# ================================================================ package
def package_findings(path):
    """OOXML package integrity — the layer python-pptx will happily lie about.

    Added 2026-08-17 after all seven ICS decks shipped at 0 FAIL while being
    structurally broken: 50 slide parts, 28 sldId entries, and six parts each
    referenced TWICE. python-pptx enumerates a duplicated reference as two
    slides, so every text/geometry rule passed — but LibreOffice refused to open
    the file and PowerPoint silently reordered it (title slide gone, Contact Us
    near the front). Nothing else in this file can see that class of defect.

    Checks: the archive itself is readable, no part name is written twice, no
    duplicate slide references, no dangling references, no orphaned slide parts,
    and parts == entries == distinct targets.
    """
    import zipfile
    from collections import Counter
    out = []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        return [("FAIL", 0, f"package will not open as a zip: {e}")]
    try:
        # Two whole-archive checks that need no renderer. They carry more weight
        # since the LibreOffice render smoke test was removed (2026-09-11): it
        # could never run on this machine, so what it would have caught has to be
        # caught structurally or not at all.
        #
        # A part name written TWICE is a malformed package that python-pptx reads
        # back without complaint — it happened on 2026-09-11 cloning the Summit
        # slide, where relating the asset's image Part carried its partname along
        # and a deck that already had /ppt/media/image2.png got the entry twice.
        # Nothing above sees it: these are media parts, not slide parts.
        dup_names = {n: c for n, c in Counter(z.namelist()).items() if c > 1}
        if dup_names:
            out.append(("FAIL", 0,
                        f"{len(dup_names)} part name(s) written more than once in the "
                        f"package: "
                        + ", ".join(f"{n}x{c}" for n, c in list(dup_names.items())[:6])
                        + ("..." if len(dup_names) > 6 else "")))
        # CRC check: catches a truncated or corrupt member. testzip() RETURNS the
        # first bad name for a CRC mismatch but RAISES when the stream will not
        # decompress at all — and an unhandled zlib.error here is a traceback out
        # of the gate instead of a FAIL, which reads as a broken validator rather
        # than a broken deck.
        try:
            bad = z.testzip()
        except Exception as e:
            out.append(("FAIL", 0, f"corrupt part in the package: {e}"))
        else:
            if bad:
                out.append(("FAIL", 0, f"corrupt part in the package (bad CRC): {bad}"))

        parts = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        pres = z.read("ppt/presentation.xml").decode("utf-8", "replace")
        rids = re.findall(r"<p:sldId[^>]*r:id=\"(rId\d+)\"", pres)
        rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8", "replace")
        rmap = dict(re.findall(r"Id=\"(rId\d+)\"[^>]*Target=\"([^\"]+)\"", rels))
        tgts = [rmap.get(r) for r in rids]

        dangling = [r for r, t in zip(rids, tgts) if not t]
        if dangling:
            out.append(("FAIL", 0, f"{len(dangling)} slide reference(s) resolve to no "
                                   f"relationship: {dangling[:5]}"))
        resolved = [t for t in tgts if t]
        dup = {t: c for t, c in Counter(resolved).items() if c > 1}
        if dup:
            out.append(("FAIL", 0,
                        f"{len(dup)} slide part(s) referenced more than once in sldIdLst "
                        f"— the deck reports {len(rids)} slides but holds "
                        f"{len(set(resolved))}: "
                        + ", ".join(f"{t.split('/')[-1]}x{c}" for t, c in list(dup.items())[:6])))
        if len(set(rids)) != len(rids):
            out.append(("FAIL", 0, "duplicate rIds in sldIdLst"))
        used = {("ppt/" + t.replace("../", "")) for t in resolved}
        orphan = sorted(set(parts) - used)
        if orphan:
            out.append(("FAIL", 0,
                        f"{len(orphan)} orphaned slide part(s) in the package "
                        f"(present but unreferenced): "
                        + ", ".join(o.split('/')[-1] for o in orphan[:6])
                        + ("..." if len(orphan) > 6 else "")))
        missing = sorted(used - set(parts))
        if missing:
            out.append(("FAIL", 0, f"{len(missing)} referenced slide part(s) missing from "
                                   f"the package: {[m.split('/')[-1] for m in missing[:5]]}"))
    finally:
        z.close()
    return out


# ================================================================ reference leak
def reference_leak_findings(path, prs, texts=None):
    """FAIL when another client's name appears anywhere but the slide's own header.

    Identity lives in the header band (top ~1.3") — that is how the Executive Summit
    one sheets legitimately name a different client per slide. A reference client's
    name appearing in the BODY is leakage from the template.
    """
    own = _own_client(path, prs)
    out = []
    for idx, slide in enumerate(prs.slides, start=1):
        header, body = [], []

        def rec(shapes):
            for sh in shapes:
                if getattr(sh, "shape_type", None) == 6:
                    rec(sh.shapes)
                    continue
                if sh.has_text_frame and sh.text_frame.text.strip():
                    top = _in(sh.top) or 0
                    (header if top < 1.3 else body).append(sh.text_frame.text)
        rec(slide.shapes)
        head_low = "  ".join(header).lower()
        body_join = "  ".join(body)
        for name in REFERENCE_CLIENTS:
            if _is_own_name(name, own) or name.lower() in head_low:
                continue
            m = re.search(r"[^\n]*\b" + re.escape(name) + r"\b[^\n]*", body_join, re.I)
            if m:
                out.append(("FAIL", idx,
                            f"reference-client leakage: '{name}' appears on a deck for a "
                            f"different client — …{m.group(0).strip()[:70]}…"))
    return out


# ================================================================ one-line overflow
def single_line_overflow_findings(prs):
    """FAIL a one-line label whose glyphs are wider than its box AND land on other text.

    Added 2026-08-27. The ICS Financial Summary shipped "Billed Expense for 46,195
    Accounts" in a 3.9in box: 3.80in of Montserrat against 3.70in of usable width, so it
    wrapped onto the value beneath it. Everything else passed, because:

      * the deck asks for Calibri 14pt but enforce_min_font floors runs at 16 and the
        font-role pass rewrites them to Montserrat, which is far wider (3.10in -> 3.80in);
      * the LibreOffice render substitutes a narrower face, so it looked clean there.

    So measure the ACTUAL run font and size (textfit, against the bundled TTFs) against
    the box minus its own margins. Scoped to boxes only tall enough for one line — a
    deliberately wrapping paragraph is fine — and a spill is a defect only when it lands
    on ANOTHER TEXT shape: captions here are sized tight on purpose and the art below
    them sits with clearance.
    """
    if text_width_in is None:
        return []
    out = []
    for idx, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if not sh.has_text_frame or sh.width is None or sh.height is None:
                continue
            tf = sh.text_frame
            paras = [p for p in tf.paragraphs if p.runs]
            if len(paras) != 1:
                continue
            runs = paras[0].runs
            text = "".join(r.text for r in runs).strip()
            if not text or "\n" in text:
                continue
            pt = next((r.font.size.pt for r in runs if r.font.size), None)
            fam = next((r.font.name for r in runs if r.font.name), None)
            if not pt or not fam:
                continue                       # inherited from the layout — not ours to judge
            bold = bool(runs[0].font.bold)
            usable = _in(sh.width) - (_in(tf.margin_left) or 0) - (_in(tf.margin_right) or 0)
            if usable <= 0:
                continue
            w = text_width_in(text, pt, fam, bold)
            line_in = pt / 72.0 * 1.22
            need = math.ceil(w / usable - 0.02)
            box_h = _in(sh.height) - (_in(tf.margin_top) or 0) - (_in(tf.margin_bottom) or 0)
            holds = max(1, int(box_h / line_in + 0.15))
            if need <= holds:
                continue
            spill_top = _in(sh.top) + _in(sh.height)
            spill_bot = spill_top + (need - holds) * line_in
            l, r = _in(sh.left), _in(sh.left) + _in(sh.width)
            hit = None
            for other in slide.shapes:
                if other is sh or other.top is None or other.height is None:
                    continue
                if not _has_text(other):
                    continue
                ot, ob = _in(other.top), _in(other.top) + _in(other.height)
                ol, orr = _in(other.left), _in(other.left) + _in(other.width)
                if ob <= spill_top + 0.01 or ot >= spill_bot - 0.01:
                    continue
                if orr <= l + 0.01 or ol >= r - 0.01:
                    continue
                hit = other
                break
            if hit is not None:
                out.append(("FAIL", idx,
                            f"one-line label wraps and collides: needs {need} lines, box holds "
                            f"{holds} ({w:.2f}in of {fam} {pt:.0f}pt in {usable:.2f}in) — "
                            f"…{text[:44]}… spills onto "
                            f"…{(_lbl(hit) or '')[:28]}…"))
    return out


PILL_WRAP_RATIO = 0.955


def pill_wrap_findings(prs):
    """REVIEW a top-right date pill whose text needs a second line.

    Added 2026-09-14. The pill's box is tall enough for two lines and nothing sits
    under it, so `single_line_overflow_findings` — which fails only a spill onto other
    text — never sees a wrapped pill.

    PowerPoint wraps BEFORE textfit's width reaches the box. Twelve 12pt Montserrat
    pills rendered through PowerPoint (2026-09-14): every one at or below 0.940 of the
    usable width held one line, every one at or above 0.974 took two — including
    "As of September 14, 2026" at 0.993, which is how this rule came to exist. Hence
    PILL_WRAP_RATIO, between the two. REVIEW, not FAIL: most 2026.09 CashPlease and ICS
    pills wrap, and the fix (shorter date or wider pill) is a style decision across
    programs, not something the gate should impose mid-cycle.
    """
    if text_width_in is None:
        return []
    out = []
    for idx, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if (not sh.has_text_frame or sh.top is None or sh.left is None
                    or sh.shape_type != 1               # MSO_SHAPE_TYPE.AUTO_SHAPE
                    or _in(sh.top) > 0.9 or _in(sh.left) < 9.0):
                continue
            tf = sh.text_frame
            paras = [p for p in tf.paragraphs if p.runs]
            if len(paras) != 1:
                continue
            runs = paras[0].runs
            text = "".join(r.text for r in runs).strip()
            pt = next((r.font.size.pt for r in runs if r.font.size), None)
            fam = next((r.font.name for r in runs if r.font.name), None)
            if not text or not pt or not fam:
                continue
            usable = _in(sh.width) - (_in(tf.margin_left) or 0) - (_in(tf.margin_right) or 0)
            w = text_width_in(text, pt, fam, bool(runs[0].font.bold))
            if w > usable * PILL_WRAP_RATIO:
                out.append(("REVIEW", idx,
                            f"date pill wraps to two lines: '{text}' is {w:.2f}in of "
                            f"{fam} {pt:.0f}pt in {usable:.2f}in (PowerPoint wraps "
                            f"past {PILL_WRAP_RATIO:.0%})"))
    return out


# ================================================================ stale template caption
def stale_template_caption_findings(prs, deck_path=None, template_path=None):
    """FAIL a dated caption still byte-identical to the TEMPLATE's.

    The builder swaps numbers into captions but for a dozen date phrases it never
    swapped anything, so the reference client's month shipped verbatim: 1549
    Wellworth ran on a Jul 2026 extract and its deck read "Monthly debit spend
    (June 2026)", "opt-in status as of June 2026" and "Jul 2023 – Jun 2026 (36
    months)" — on a client with five months of data (Aaron, 2026-08-28).

    The tell is exact identity with the template: a swapped caption always differs
    somewhere (its own counts), so an untouched dated paragraph is a caption no swap
    reached. Only long paragraphs carrying the template's OWN reporting month are
    considered — a fixed historical window (the Kaplan-Meier cohort starts Jul 2021
    for every client) is correct precisely because it still matches, and a short
    date PILL is a derived value with its own guard (the ARS builder hard-fails if
    its pill swap matches nothing; an ICS section legitimately reports an older
    month than the ARS section beside it).
    """
    if template_path is None:
        template_path = os.path.join(HERE, os.pardir, "templates", "ars_template.pptx")
    if not os.path.exists(template_path):
        return []
    # A template compared against itself is identical everywhere, so this check is
    # meaningless there — qa_all lints every template and would report the whole deck.
    if deck_path:
        tdir = os.path.realpath(os.path.dirname(template_path))
        if os.path.realpath(os.path.dirname(deck_path)) == tdir:
            return []
    try:
        tpl = Presentation(template_path)
    except Exception:
        return []
    ref = None
    for s_ in tpl.slides:
        for sh in s_.shapes:
            if sh.has_text_frame:
                m = re.search(r"\b([A-Z][a-z]+)\s+(\d{4})\s+Data\b", sh.text_frame.text)
                if m:
                    ref = (m.group(1), m.group(2))
                    break
        if ref:
            break
    if not ref:
        return []
    long_m, yr = ref
    forms = (f"{long_m} {yr}", f"{long_m[:3]} {yr}")
    tpl_dated = set()
    for s_ in tpl.slides:
        for sh in s_.shapes:
            if sh.has_text_frame:
                for para in sh.text_frame.paragraphs:
                    t = "".join(r.text for r in para.runs).strip()
                    if len(t) > 40 and any(f in t for f in forms):
                        tpl_dated.add(t)
    if not tpl_dated:
        return []
    out = []
    for idx, s_ in enumerate(prs.slides, 1):
        for sh in s_.shapes:
            if not sh.has_text_frame:
                continue
            for para in sh.text_frame.paragraphs:
                t = "".join(r.text for r in para.runs).strip()
                if t in tpl_dated:
                    out.append(("FAIL", idx,
                                "dated caption identical to the template — no swap "
                                f"reached it, so it still names the reference client's "
                                f"month: '{t[:90]}'"))
    return out


# ================================================================ figure identity
# A figure worth tracking: a thousands-separated integer, or a percentage.
_FIGURE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d{1,3}(?:\.\d)?%)(?![\w])")
_WORD = re.compile(r"[a-z][a-z'\-]+")

# Labels that legitimately carry different values in different places. A
# per-mailing or per-branch or per-tier figure is SUPPOSED to vary by row.
# NOTE: "drop" is deliberately NOT here. A drop names one specific mailing, and
# the defect this rule exists to catch was two different counts for the SAME
# Jun 2026 drop — listing it as varying made the canonical example invisible.
_VARYING = re.compile(
    r"\b(mailing|mailer|branch|tier|segment|vintage|cohort|quarter|"
    r"product|band|group|channel|category|reason|each|per)\b", re.I)

# Words that, when they appear in a slide TITLE, mean the slide reports a
# DIFFERENT cut of the book. "12-Month Eligible Take Rate — Personal" and the
# same title ending "— Business" carry the same caption wording next to
# different numbers, correctly. Without this the two produced a false conflict.
_DISCRIMINATORS = ("personal", "business", "mean", "median", "new", "existing",
                   "book", "opt-in", "opt-out", "gold", "platinum", "before",
                   "after", "combined", "overall", "consumer")


def _label_of(text, start):
    """The 2-4 content words immediately before a figure, normalized.

    Month words are KEPT in the label, deliberately. Stripping them was worse:
    "responders in Jun 2026" and "responders in Jul 2026" then normalized to the
    same label and every period-over-period pair read as a conflict. Left in,
    the two periods simply carry different labels and are never compared.
    """
    words = _WORD.findall(text[:start].lower())
    if not words:
        return None
    label = " ".join(words[-4:])
    return label if len(label) >= 6 else None


def _title_key(slide):
    t = _title(slide).lower()
    return tuple(d for d in _DISCRIMINATORS if d in t) if t else ()


def figure_identity_findings(prs):
    """One labelled measure carrying two different values (REVIEW).

    The 2026-08-28 Wellworth defect: the Jun 2026 responder count rendered as
    1,077 on the mailing slides and 1,026 on Reach / Depth / Ranking /
    Sustained. The labelled-metric rule could not see it — "responder" was not
    among its four hardcoded label words and the values are not percentages.

    Labels are DISCOVERED from the deck (the 2-4 content words before the
    figure) rather than hardcoded, so a measure nobody listed is still covered.
    Three guards keep it quiet on a correct deck: table rows are skipped (a
    mailing table is MEANT to vary by row); a label carrying a per-thing word is
    skipped; slides whose titles differ on a discriminator are never compared.

    REVIEW, not FAIL: proving two renderings are the SAME measure needs the
    builder to say so — that is figure_sidecar_findings.
    """
    seen = {}      # (title_key, label) -> {value: {slides}}
    for idx, slide in enumerate(prs.slides, 1):
        tkey = _title_key(slide)
        for sh in slide.shapes:
            if sh.has_table or not sh.has_text_frame:
                continue
            text = sh.text_frame.text
            if not text.strip():
                continue
            for m in _FIGURE.finditer(text):
                label = _label_of(text, m.start())
                if not label or _VARYING.search(label):
                    continue
                seen.setdefault((tkey, label), {}).setdefault(m.group(1), set()).add(idx)

    out = []
    for (tkey, label), byval in sorted(seen.items(), key=lambda kv: kv[0][1]):
        # never compare a count against a percentage — different measures
        pcts = {v for v in byval if v.endswith("%")}
        for group in (pcts, set(byval) - pcts):
            if len(group) < 2:
                continue
            slides = set().union(*(byval[v] for v in group))
            if len(slides) < 2:
                continue      # two values on one slide is a layout, not a conflict
            detail = "; ".join(
                f"{v} on slide{'s' if len(byval[v])>1 else ''} "
                f"{', '.join(str(x) for x in sorted(byval[v]))}"
                for v in sorted(group))
            out.append(("REVIEW", 0,
                        f"'{label}' renders {len(group)} different values — {detail}"
                        f" — confirm these are distinct measures"))
    return out


# ================================================================ periods
_MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"

# Point-in-time captions: each names THE month the slide reports.
_PIT_PATTERNS = [
    ("as of",     re.compile(r"as of\s+(" + _MON + r")", re.I)),
    ("data pill", re.compile(r"(" + _MON + r")\s+Data\b", re.I)),
    ("PTD pill",  re.compile(r"PTD\s*[·|]\s*(" + _MON + r")", re.I)),
    ("snapshot",  re.compile(r"\((" + _MON + r")\s+snapshot\)", re.I)),
]
# "Aug 2023 – Jul 2026 (36 months)" — the count must match the span it claims.
_SPAN = re.compile(
    r"(" + _MON + r")\s*[–—-]\s*(" + _MON + r")\s*\(\s*(\d+)\s*months?\s*\)", re.I)


def find_period_pack(deck_path):
    """The ODD snapshot pack governing this deck's captions, or None.

    Only an ARS-ONLY deck. `oddd_metrics.json` is an ARS artifact: its
    `latest_month` is the ODD snapshot, which says nothing about when an ICS,
    MRPC or CashPlease deck's figures are current. Marine 1539's MRPC deck reads
    "as of August 2026" against a Jul 2026 ODD and is right to — those are
    different data with different cadences. Combined decks are excluded for the
    same reason: one pack cannot arbitrate captions belonging to several
    programs. The span-arithmetic half of period_findings needs no pack.
    """
    base = os.path.basename(deck_path)
    programs = [t for t in PROGRAM_TAGS if f"-{t}-" in base]
    if programs != ["ARS"]:
        return None
    d = os.path.dirname(os.path.abspath(deck_path))
    for cand in ("oddd_metrics.json", os.path.join("oddd", "oddd_metrics.json"),
                 os.path.join("..", "oddd", "oddd_metrics.json")):
        p = os.path.join(d, cand)
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8"))
            except Exception:
                return None
    return None


def period_findings(prs, pack=None):
    """Date phrases that contradict the deck's own data.

    A literal month is legitimate — an ICS section reporting a quarterly figure
    is RIGHT to name an older month than the ARS section beside it. What is
    checked is only whether a phrase contradicts something knowable:

      * FAIL   — a span whose stated month count does not match its own endpoints
                 ("Jul 2023 – Jun 2026 (30 months)"). Pure arithmetic, no pack needed.
      * FAIL   — a point-in-time caption naming a month AFTER the snapshot.
      * REVIEW — a point-in-time caption naming a month before the snapshot:
                 usually a stale literal, sometimes correct, so raised not blocked.
    """
    if Period is None:
        return []
    latest = None
    if pack:
        try:
            latest = Period.from_pack(pack).latest
        except Exception:
            latest = None

    out = []
    for idx, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            text = " ".join(sh.text_frame.text.split())
            if not text:
                continue
            for m in _SPAN.finditer(text):
                a, b, claimed = parse_month(m.group(1)), parse_month(m.group(2)), int(m.group(3))
                if not (a and b):
                    continue
                actual = month_diff(a, b)
                if actual != claimed:
                    out.append(("FAIL", idx,
                                f"span '{m.group(0)}' claims {claimed} months but "
                                f"{m.group(1)}–{m.group(2)} is {actual}"))
            if latest is None:
                continue
            for kind, rx in _PIT_PATTERNS:
                for m in rx.finditer(text):
                    got = parse_month(m.group(1))
                    if not got:
                        continue
                    if got > latest:
                        out.append(("FAIL", idx,
                                    f"{kind} names {m.group(1)}, after the "
                                    f"{latest:%b %Y} data snapshot — the data "
                                    f"cannot come from the future"))
                    elif got < latest:
                        out.append(("REVIEW", idx,
                                    f"{kind} names {m.group(1)} but the snapshot is "
                                    f"{latest:%b %Y} — confirm this is a carried-forward "
                                    f"figure and not a stale caption"))
    return out


# ================================================================ source notes
# Structural slides carry no data, so they are not required to cite one. Matched
# as a title PREFIX, so keep entries specific: "CashPlease®" is the divider, while
# the CashPlease content slides ("CashPlease Loan Volume by Month") carry no ®.
_NO_SOURCE_TITLES = (
    "Agenda", "Questions & Discussion", "Contact Us", "Appendix",
    "Account Revenue Solution", "Invitation Checking", "MyRewards Premium Cards",
    "CashPlease®",
    "Debit Card Review", "Reg E Review", "Program Overview",
    "Community financial institutions",
    # ICS resource / marketing slides — screenshots of Velocity material, not
    # client data, so there is nothing to cite.
    "New in 2026", "E-Learning", "2026 New Releases", "Reporting:",
    "VIP Best Practices", "Comparisons", "Performance of Accounts",
)
_TEMPLATE_SHELLS = ("_template.pptx", "multi-product_reference_deck.pptx")


def _is_template_shell(path):
    """A shell, not a deliverable. Source notes are written by the builder at
    build time, so requiring them of a template is a category error."""
    return os.path.basename(path).endswith(_TEMPLATE_SHELLS)


def _has_data(slide):
    """A slide REPORTING data — one that owes a source.

    A wide picture alone is not enough: the ICS resource slides are full-bleed
    screenshots with nothing derived on them. A data slide has a table, or a
    chart AND a figure in its text.
    """
    has_chart = has_table = False
    for sh in slide.shapes:
        if sh.has_table:
            has_table = True
        if str(getattr(sh, "shape_type", "")).startswith("PICTURE"):
            if (_in(sh.width) or 0) > 2.5:   # a logo is ~1.7"; a chart is wider
                has_chart = True
    if has_table:
        return True
    if not has_chart:
        return False
    text = " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)
    return bool(re.search(r"\d", text))


def source_note_findings(path, prs):
    """CLAUDE.md: source-in-notes is 'a hard requirement, not a nicety'.

      * a data slide with NO speaker note, or a note with no Source line — FAIL;
      * a note naming a reference client that is not this deck's own — FAIL.
        This is the CoastLife defaults defect: build_ars_gen defaulted its source
        strings to CoastLife 1705, so every other client inherited CoastLife's
        provenance, and reference_leak_findings only ever read slide TEXT.
    """
    if _is_template_shell(path):
        return []
    own = _own_client(path, prs)
    out = []
    for idx, slide in enumerate(prs.slides, 1):
        title = _title(slide)
        note = (slide.notes_slide.notes_text_frame.text.strip()
                if slide.has_notes_slide else "")
        structural = title.startswith(_NO_SOURCE_TITLES)
        owes = _has_data(slide) and not structural
        if not note:
            if owes:
                out.append(("FAIL", idx,
                            f"no speaker note — every data slide records its source "
                            f"(CLAUDE.md): '{title[:44]}'"))
            continue
        if "source" not in note.lower() and owes:
            out.append(("FAIL", idx,
                        f"speaker note carries no Source line: '{title[:44]}'"))
        for name in REFERENCE_CLIENTS:
            if _is_own_name(name, own):
                continue
            # Word-boundary match: a plain substring test flagged every "Credit
            # Union financials" note as naming "Union Financial".
            if re.search(r"\b" + re.escape(name) + r"\b", note, re.I):
                out.append(("FAIL", idx,
                            f"source note names '{name}', a different client — "
                            f"the deck inherited another client's provenance"))
    return out


# ================================================================ summit date
def summit_date_findings(prs):
    """The Summit slide must not advertise a Summit that has already happened.

    THE GAP THIS CLOSES: on 2026-09-11 all eighteen delivered 2026.09 decks carried
    "Boston, MA — August 31-September 1, 2026", eleven days after that Summit ended.
    Nothing failed. `summit_slide.summit_period()` warned on stderr when the date was
    past, but only when a build happened to CALL it for a reporting month, and a
    warning in a build log is not a gate. The slide is replaced by hand before each
    Summit, so "the asset went stale" is the expected failure mode, not an exotic one.

    REVIEW, not FAIL, and deliberately so: a deck legitimately built for an event that
    starts tomorrow is indistinguishable from one built a day after it ended, and
    blocking a rebuild of an older period would be wrong. It has to be visible, not
    fatal.
    """
    import datetime
    try:
        from summit_slide import _SUMMIT_DATE_RE, _MONTHS
    except Exception:
        return []
    today = datetime.date.today()
    for idx, slide in enumerate(prs.slides, 1):
        if not _is_summit(slide):
            continue
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            m = _SUMMIT_DATE_RE.search(" ".join(sh.text_frame.text.split()))
            if not m:
                continue
            mon = next((i for i, n in enumerate(_MONTHS)
                        if n.lower().startswith(m.group(1).lower()[:3])), None)
            if mon is None:
                continue
            d = datetime.date(int(m.group(3)), mon + 1, int(m.group(2)))
            if d < today:
                # Built by hand, not strftime: "%-d" is a GNU extension and raises
                # ValueError on Windows, which is where this gate runs.
                when = "%s %d, %d" % (_MONTHS[d.month - 1], d.day, d.year)
                return [("REVIEW", idx,
                         f"the Summit slide names {when}, which has passed "
                         f"({(today - d).days} days ago) — replace "
                         f"build/assets/summit_slide.pptx before shipping")]
            return []
    return []


# ================================================================ closing month
_MONTH_YEAR = re.compile(r"\b(January|February|March|April|May|June|July|August|September|"
                         r"October|November|December)\s+(\d{4})\b")


def _cover_client_and_month(prs):
    """(client, 'Month YYYY') from the cover's "<client> / Executive Review • <month>" lines.

    The cover is the one slide carrying "Executive Review" (the same test
    assemble_combined uses). The client is the non-empty paragraph just before the
    Executive Review line in the same text frame, or None when the builder drew it as
    a separate box.
    """
    for slide in prs.slides:
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            paras = [" ".join(p.text.split()) for p in sh.text_frame.paragraphs]
            for i, para in enumerate(paras):
                if "Executive Review" not in para or "•" not in para:
                    continue
                m = _MONTH_YEAR.search(para.split("•")[-1])
                if not m:
                    continue
                prior = [x for x in paras[:i] if x]
                head = para.split("Executive Review")[0].strip(" |•")
                client = head or (prior[-1] if prior else None)
                return client, m.group(0)
    return None, None


def table_label_fit_findings(prs):
    """FAIL when a table's row label cannot fit its column on one line and the table would
    then run past the bottom of the slide.

    THE GAP THIS CLOSES: branch names reached the take-rate-by-branch table (Aaron,
    2026-09-17) in a first column sized for branch NUMBERS. Great Lakes' "Member Contact
    Center" wrapped to three lines, every long name to two, and the table ran off the
    slide under the logo. Nothing failed: python-pptx reports the row heights as set, not
    as PowerPoint grows them to fit wrapped text.

    For each table, the first column's labels are measured in the bundled font
    (textfit); each label that is wider than its cell adds lines to its row. The table's
    rendered bottom is estimated from those lines, and a table ending past 7.40" FAILs.
    """
    try:
        from textfit import text_width_in
    except Exception:
        return []
    import math
    from pptx.util import Emu
    out = []
    for idx, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if not sh.has_table or sh.top is None:
                continue
            tbl = sh.table
            cols = list(tbl.columns)
            if not cols:
                continue
            col_in = Emu(cols[0].width).inches - 0.20          # cell margins
            bottom = Emu(sh.top).inches
            worst = None
            for row in tbl.rows:
                cell = row.cells[0]
                size, bold = 16.0, False
                for pa in cell.text_frame.paragraphs:
                    for r in pa.runs:
                        if r.font.size:
                            size = r.font.size.pt
                        bold = bool(r.font.bold) or bold
                text = " ".join(cell.text_frame.text.split())
                row_in = Emu(row.height).inches
                lines = 1
                if text and col_in > 0:
                    lines = max(1, math.ceil(text_width_in(text, size, "Carlito", bold) / col_in))
                if lines > 1:
                    row_in = max(row_in, lines * size * 1.2 / 72 + 0.08)
                    worst = worst or text
                bottom += row_in
            if worst and bottom > 7.40:
                out.append(("FAIL", idx,
                            f"table row label '{worst}' wraps in a {col_in + 0.20:.2f}\" first column "
                            f"and the table runs to ~{bottom:.2f}\" (slide ends 7.50\"): widen the "
                            f"label column in the builder"))
    return out


def closing_month_findings(prs):
    """FAIL when the Questions & Discussion slide names a different month or client
    than the cover.

    THE GAP THIS CLOSES: every 2026.09 ARS deck in Outputs — 33 of them, the combined
    decks built on an ARS shell included — carried "<Client>  •  July 2026" on the
    Questions & Discussion slide under a cover reading September 2026 (Aaron,
    2026-09-17). build_ars_gen swapped the cover's month and only the client NAME on
    the closing slide, so the template shell's month rode through. Nothing failed:
    the reference-leak rule looks for another client's name, and "July 2026" is a
    perfectly valid month.

    Both slides are built from one reporting month, so the rule is exact, not
    inferred: the closing line's month must equal the cover's. The template shells
    carry the same dummy month on both slides, so they pass as they should; the rule
    only fires when a builder swaps one slide and not the other.
    """
    client, month = _cover_client_and_month(prs)
    if not month:
        return []
    out = []
    for idx, slide in enumerate(prs.slides, 1):
        if not _title(slide).startswith("Questions & Discussion"):
            continue
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            for p in sh.text_frame.paragraphs:
                line = " ".join(p.text.split())
                if "•" not in line or line.startswith("Questions & Discussion"):
                    continue
                who, _, when = line.rpartition("•")
                who = who.strip()
                m = _MONTH_YEAR.search(when)
                if m and m.group(0) != month:
                    out.append(("FAIL", idx,
                                f"Questions & Discussion reads '{line}' but the cover says "
                                f"{month} — the closing slide carries the template's month; "
                                f"fix the builder so both use the reporting month"))
                if client and who and who != client:
                    out.append(("FAIL", idx,
                                f"Questions & Discussion names '{who}' but the cover names "
                                f"'{client}'"))
    return out


# ================================================================ figure sidecar
def figure_sidecar_findings(deck_path):
    """FAIL when one NAMED measure rendered more than one value.

    The FAIL-grade counterpart to figure_identity_findings: here the BUILDER
    recorded the measure as it wrote each figure (build/figures.py), so a
    difference is arithmetic, not inference. Absent sidecar = no finding; a deck
    built before the sidecar existed must still validate.
    """
    if FigureLog is None:
        return []
    path = find_sidecar(deck_path)
    if not path:
        return []
    try:
        log = FigureLog.load(path)
    except Exception as e:
        return [("REVIEW", 0, f"figure sidecar {os.path.basename(path)} could not be read ({e})")]
    out = []
    for measure, byval in log.conflicts():
        detail = "; ".join(
            f"{v!r} on {', '.join(sorted(set(sl)) or ['(untitled)'])}"
            for v, sl in sorted(byval.items()))
        out.append(("FAIL", 0,
                    f"measure '{measure}' rendered {len(byval)} different values — {detail}"))
    return out


# ================================================================ claims
# A claim about MOVEMENT is checkable arithmetic. Marine FCU's responder
# commentary read "NSF/OD activity stayed roughly flat" while NSF/OD had risen
# 27% in the very extract the slide was built from; every other rule passed it.
#
# Three things had to be right before this could FAIL rather than advise:
#
# 1. COMPARISON IS NOT MOVEMENT. "Responders carry lower balances than
#    non-responders ($924 vs $2,477)" orders two GROUPS at one moment, and is
#    right. Read as a change over time it is a 168% rise; the first draft failed
#    six correct slides that way. "than" is the discriminator.
# 2. A SENTENCE CAN CARRY MORE THAN ONE CLAIM. "ticket holds (mean $56->$53)
#    while monthly swipes rise 8.9->17.4" holds two claims and three pairs. Each
#    claim is matched to its NEAREST pair, within CLAIM_WINDOW characters.
# 3. "DROP" IS A MAILING HERE, not a decline.
#
# Deliberately NOT checked: a movement word with no figure near it. That version
# produced 156 findings across 20 files, almost all legitimate summary bullets
# whose evidence is the chart. Catching an unsupported claim needs the DATA —
# that is a cross-check against the metrics pack, not a lint rule.
_NUM = r"\$?\d[\d,]*(?:\.\d+)?"
_PAIR_RX = re.compile(
    r"(?P<a>" + _NUM + r")(?!\s*%)\s*(?:vs\.?|versus|->|→|\bto\b)\s*"
    r"(?P<b>" + _NUM + r")(?!\s*%)", re.I)
_PCT = re.compile(r"\(?\s*(?P<sign>[+-]?)\s*(?P<v>\d+(?:\.\d+)?)\s*%\s*\)?")
_FLAT = re.compile(r"\b(?:roughly |about |essentially |largely |broadly |relatively |"
                   r"more or less )?(?:flat|unchanged|steady|stable|holds|hold|held|"
                   r"little changed|no change)\b", re.I)
# Movement: one measure at two different times.
_UP_MOVE = re.compile(r"\b(?:rose|risen|rise|rises|increased|increase|grew|grown|"
                      r"climbed|improved|gained|jumped)\b", re.I)
_DOWN_MOVE = re.compile(r"\b(?:fell|fallen|declines|declined|decline|decreased|"
                        r"decrease|reduced|shrank)\b", re.I)
# Comparative: two things at the same time.
_MORE_CMP = re.compile(r"\b(?:higher|more|greater|larger|above)\b", re.I)
_LESS_CMP = re.compile(r"\b(?:lower|less|fewer|smaller|below)\b", re.I)
_THAN = re.compile(r"\bthan\b", re.I)
# A negated verb claims the opposite of what it says.
_NEGATED = re.compile(r"\b(?:not|no|never|without|n't)\b[^.;]*$", re.I)
# Metadata and definitions are not claims about a client's results.
_SKIP_LINE = re.compile(r"^\s*(?:selection|source|note|method|definition)\s*:", re.I)

FLAT_BAND_PCT = 2.0      # Aaron's band (2026-08-31): inside this, report as almost flat
PCT_TOLERANCE = 1.5      # "+94%" against a computed 93.6% is rounding, not a defect
CLAIM_WINDOW = 80        # how far a claim word may sit from the pair it describes


def _f(tok):
    try:
        return float(tok.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _sentences(text):
    for part in re.split(r"(?<=[.;!?])\s+|\n+|\s+—\s+", text):
        part = part.strip()
        if part:
            yield part


def _nearest(pos, items):
    """The (start, ...) item closest to `pos`, or None past CLAIM_WINDOW."""
    best, bestd = None, None
    for it in items:
        d = abs(it[0] - pos)
        if bestd is None or d < bestd:
            best, bestd = it, d
    if best is None or bestd > CLAIM_WINDOW:
        return None
    return best


def claim_consistency_findings(prs):
    """Movement and comparison claims must agree with the figures beside them."""
    out = []
    for idx, blocks in slide_texts(prs):
        for block in blocks:
            for s in _sentences(block):
                if _SKIP_LINE.match(s) or " = " in s:
                    continue
                pairs = [(m.start(), m.group("a"), m.group("b"),
                          _f(m.group("a")), _f(m.group("b")))
                         for m in _PAIR_RX.finditer(s)]
                if not pairs:
                    continue
                pcts = [(m.start(), m.group("sign"), float(m.group("v")))
                        for m in _PCT.finditer(s)]
                comparative = bool(_THAN.search(s))
                short = s if len(s) <= 90 else s[:87] + "..."

                claims = []
                for rx, kind in ((_FLAT, "flat"), (_UP_MOVE, "up"), (_DOWN_MOVE, "down"),
                                 (_MORE_CMP, "more"), (_LESS_CMP, "less")):
                    for m in rx.finditer(s):
                        if _NEGATED.search(s[max(0, m.start() - 24):m.start()]):
                            continue           # "did not increase" is not an increase
                        claims.append((m.start(), kind, m.group(0)))

                for pos, kind, word in claims:
                    p = _nearest(pos, pairs)
                    if not p:
                        continue
                    _, atok, btok, a, b = p
                    if a is None or b is None:
                        continue
                    if kind in ("more", "less"):
                        # Only a genuine comparison ("X than Y"); otherwise
                        # "higher"/"lower" describes a move, handled below.
                        if not comparative or a == b:
                            continue
                        if kind == "less" and a > b:
                            out.append(("FAIL", idx,
                                        "text says %r but %s is GREATER than %s - %r"
                                        % (word, atok, btok, short)))
                        elif kind == "more" and a < b:
                            out.append(("FAIL", idx,
                                        "text says %r but %s is LESS than %s - %r"
                                        % (word, atok, btok, short)))
                        continue
                    if comparative or a == 0:
                        continue
                    change = 100.0 * (b - a) / a
                    if kind == "flat" and abs(change) > FLAT_BAND_PCT:
                        out.append(("FAIL", idx,
                                    "text says %r but %s -> %s is %+.1f%%, outside the "
                                    "+/-%.0f%% band - %r"
                                    % (word, atok, btok, change, FLAT_BAND_PCT, short)))
                    elif kind == "up" and change < -FLAT_BAND_PCT:
                        out.append(("FAIL", idx,
                                    "text says %r but %s -> %s FELL %+.1f%% - %r"
                                    % (word, atok, btok, change, short)))
                    elif kind == "down" and change > FLAT_BAND_PCT:
                        out.append(("FAIL", idx,
                                    "text says %r but %s -> %s ROSE %+.1f%% - %r"
                                    % (word, atok, btok, change, short)))

                # ONE percentage only. Two or more in a sentence describe
                # different things, and attaching them to the single pair
                # nearby is guesswork ("net +26.2% against -17.2%, with swipes
                # 11.5 -> 16.0" failed a correct slide).
                for pos, sign, v in (pcts if len(pcts) == 1 else []):
                    p = _nearest(pos, pairs)
                    if not p or comparative:
                        continue
                    _, atok, btok, a, b = p
                    if a in (None, 0) or b is None:
                        continue
                    change = 100.0 * (b - a) / a
                    stated = -v if sign == "-" else v
                    if sign == "" and abs(abs(change) - v) <= PCT_TOLERANCE:
                        continue
                    if abs(stated - change) > PCT_TOLERANCE:
                        out.append(("FAIL", idx,
                                    "stated %g%% does not match %s -> %s, which is "
                                    "%+.1f%% - %r"
                                    % (stated, atok, btok, change, short)))
    return out


# ================================================================ text rules
def text_rule_findings(prs, texts=None):
    """Wording rules, per slide, over every text block and table row.

      FAIL   banned words (CLAUDE.md writing style; 'lift' passes on the Lift Matrix slide)
      FAIL   "1 mailings" — count/plural disagreement on an interpolated count (1549, 2026-08-20)
      FAIL   "0.2 : 1 is well above the 2 : 1 threshold" — a threshold claim contradicting its ratio
      FAIL   "N of M" with N > M
      REVIEW "X% of <group> (N)" whose N does not tie to a total on the slide
      REVIEW filler / AI-tell phrases; superlatives; "higher/lower rate" claims
      REVIEW a caption promising a comparison or an orange highlight on a chart slide
    """
    texts = texts if texts is not None else slide_texts(prs)
    slides = list(prs.slides)
    out = []
    for idx, blocks in texts:
        joined = "  ".join(blocks)
        low = joined.lower()

        lift_slide = "lift matrix" in low   # the ARS Lift Matrix slide is entirely about lift
        for w in BANNED:
            for m in re.finditer(r"\b" + re.escape(w) + r"\b", low):
                ctx = low[max(0, m.start() - 25):m.start() + 25]
                if any(a in ctx for a in BANNED_ALLOW_CONTEXT):
                    continue
                if w in ("lift", "lifted") and lift_slide:
                    continue
                out.append(("FAIL", idx, f"banned word '{w}' — …{ctx.strip()}…"))

        for m in re.finditer(r"\b1 (mailings|months|responders|accounts|branches|customers)\b", joined):
            out.append(("FAIL", idx, f"count/plural disagreement: '1 {m.group(1)}'"))

        for m in re.finditer(r"([\d.]+)\s*:\s*1\s+is\s+(well above|above|below|under)\s+the\s+([\d.]+)\s*:\s*1", joined):
            got, word, thr = float(m.group(1)), m.group(2), float(m.group(3))
            claims_above = word in ("well above", "above")
            if claims_above != (got >= thr):
                out.append(("FAIL", idx,
                            f"threshold claim contradicts the ratio: {got} : 1 described as "
                            f"'{word} the {thr} : 1 threshold'"))

        for m in re.finditer(r"([\d,]+)\s+of\s+([\d,]+)", joined):
            n, tot = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
            if n > tot:
                out.append(("FAIL", idx, f"impossible count: {n} of {tot} (sub-count exceeds total)"))

        for m in re.finditer(r"([\d.]+)%\s+of\s+(\w+)\s*\(([\d,]+)", joined):
            pct = float(m.group(1))
            cnt = int(m.group(3).replace(",", ""))
            tot = None
            for mm in re.finditer(r"([\d,]{3,})", joined):
                v = int(mm.group(1).replace(",", ""))
                if v >= cnt and abs(cnt / v * 100 - pct) < 1.5:
                    tot = v
                    break
            if tot and cnt > tot:
                out.append(("FAIL", idx, f"{cnt} exceeds total {tot} on same slide"))
            if tot is None:
                out.append(("REVIEW", idx,
                            f"'{pct}% of {m.group(2)} ({cnt})' — confirm {cnt}/{pct}% ties to the chart total"))

        for ph in AI_PHRASES:
            if ph in low:
                out.append(("REVIEW", idx, f"filler/AI-tell phrase '{ph}' — move to narration/notes"))

        for w in SUPERLATIVES:
            if w in low:
                s = next((b for b in blocks if w in b.lower()), "")
                out.append(("REVIEW", idx, f"superlative '{w.strip()}' — verify vs. the ranking: “{s[:90]}”"))

        for m in re.finditer(r"(higher|lower)\s+rate[^.]{0,60}?([\d.]+)%", low):
            out.append(("REVIEW", idx,
                        f"'{m.group(1)} rate: {m.group(2)}%' — confirm direction vs. the baseline it compares to"))

        if _has_chart_image(slides[idx - 1]):
            if re.search(r"\bvs\.?\b|versus|compared with|both .* and |mailed .* responded", low):
                out.append(("REVIEW", idx,
                            "caption implies a comparison — confirm the chart draws BOTH series (not one)"))
            if "in orange" in low or "shown in orange" in low:
                out.append(("REVIEW", idx,
                            "caption references an orange highlight — confirm the highlighted bars actually render orange"))
    return out


# ================================================================ geometry
def _glyph_run_x(sh, b, txt, pt):
    """Estimated horizontal glyph extent (left, right) of a text box's longest line."""
    width = b[2] - b[0]
    tw = min(len(txt) * CHAR_W * pt, width)
    if _is_centered(sh):
        cx = (b[0] + b[2]) / 2
        return cx - tw / 2, cx + tw / 2
    return b[0], b[0] + tw


def geometry_findings(prs):
    """Layout defects `fit_layout` is meant to prevent; a survivor FAILs.

      FAIL   a shape running off the slide
      FAIL   text/picture/table whose glyph run collides with the slide number or logo
      FAIL   a bottom caption whose estimated lines reach the number/logo corners
      FAIL   a chart picture overlapping a callout/tile by more than 0.15 sq in
      REVIEW a text box overlapping a chart image (letterboxed whitespace is often benign)

    The number/logo zones are glyph-aware: a centered line's glyphs may clear the
    corner even when its box does not. The Executive Summit slide is skipped.
    """
    out = []
    for idx, s in enumerate(prs.slides, 1):
        if _is_summit(s):
            continue
        zones = [(_box(sh), "slide number") for sh in s.shapes if _is_num(sh)]
        zones += [(_box(sh), "logo") for sh in s.shapes if _is_logo(sh)]
        shapes = [(sh, _box(sh)) for sh in s.shapes if not (_is_num(sh) or _is_logo(sh))]

        # off-slide, and collisions with the number/logo corners
        for sh, b in shapes:
            has = _has_text(sh) or sh.shape_type == 13 or sh.has_table
            if not has or b is None:
                continue
            if b[3] > 7.56 or b[2] > 13.42:
                out.append(("FAIL", idx, f"runs off the slide (right={b[2]:.2f}\", bottom={b[3]:.2f}\") — {_lbl(sh)!r}"))
                continue
            gb = b
            if _has_text(sh):
                gl, gr = _glyph_run_x(sh, b, sh.text_frame.text.strip(), _max_pt(sh))
                gb = (gl, b[1], gr, b[3])
            hit = next((zn for zb, zn in zones if zb and _overlap(gb, zb)), None)
            if hit:
                out.append(("FAIL", idx, f"collides with the {hit} — {_lbl(sh)!r}"))

        # estimated overflow of a bottom caption into the number/logo corners
        for sh, b in shapes:
            if not _has_text(sh) or b is None or b[1] < 5.8:
                continue
            txt = sh.text_frame.text.strip()
            width = max(0.5, b[2] - b[0])
            pt = _max_pt(sh)
            est_lines = max(1, math.ceil(len(txt) * CHAR_W * pt / width))
            est_bottom = b[1] + 0.08 + est_lines * LINE_H * pt
            gl, gr = _glyph_run_x(sh, b, txt, pt)
            if est_bottom > 7.10 and est_bottom > b[3] + 0.05 and (gl < 1.25 or gr > 11.15):
                out.append(("FAIL", idx, f"caption likely overflows its box into the bottom corners (est {est_lines} lines, est bottom {est_bottom:.2f}\") — {_lbl(sh)!r}"))

        # a chart picture must stop at the tile rail
        tiles = [b for sh, b in shapes
                 if sh.shape_type == 1 and b and (b[2] - b[0]) < 6.5 and (b[3] - b[1]) < 4.0]
        charts = [b for sh, b in shapes if sh.shape_type == 13 and b and (b[2] - b[0]) > 3.0]
        for pb in charts:
            for tb in tiles:
                ox = min(pb[2], tb[2]) - max(pb[0], tb[0])
                oy = min(pb[3], tb[3]) - max(pb[1], tb[1])
                if ox > 0.1 and oy > 0.1 and ox * oy > 0.15:
                    tile_area = (tb[2] - tb[0]) * (tb[3] - tb[1])
                    if tile_area and (ox * oy) / tile_area > 0.6:
                        continue    # tile sits mostly ON the picture = an annotation, by design
                    out.append(("FAIL", idx, f"chart overlaps a callout/tile by {ox*oy:.1f} sq in — cap the chart at the tile rail"))
                    break

        # text over a chart image — REVIEW, since letterboxing can make it benign
        for sh, b in shapes:
            if not _has_text(sh) or b is None:
                continue
            for cb in charts:
                ox = min(b[2], cb[2]) - max(b[0], cb[0])
                oy = min(b[3], cb[3]) - max(b[1], cb[1])
                if ox > 0.5 and oy > 0.12 and ox * oy > 0.25:
                    out.append(("REVIEW", idx, f"text overlaps a chart image ({ox*oy:.1f} sq in) — check for collision: {_lbl(sh)!r}"))
                    break
    return out


# ================================================================ text over text
# Tolerances for the glyph-box comparison. A hairline is rounding, not layout.
COLLISION_TOL = 0.05     # inches, both axes
CONTAINED = 0.98         # fraction of the smaller box inside the larger to call it nesting


def _glyph_box(sh):
    """The box a text shape's GLYPHS occupy, not the frame it sits in.

    Frames are not glyphs (CLAUDE.md rule 2). Every ARS title box ends 0.10" below
    the top of the selection line beneath it, and the ICS education titles sit in
    boxes two inches tall — the frames overlap, the letters never do. So the
    horizontal extent is the longest line's estimated run, placed by paragraph
    alignment, and the vertical extent is the estimated line count at the run's
    line height, placed by the frame's vertical anchor. Text that needs more
    height than its frame spills the way PowerPoint spills it: down from a TOP
    anchor, both ways from MIDDLE, up from BOTTOM.
    """
    b = _box(sh)
    if b is None:
        return None
    tf = sh.text_frame
    text = tf.text.strip()
    pt = _max_pt(sh)
    ml = _in(tf.margin_left) if tf.margin_left is not None else 0.1
    mr = _in(tf.margin_right) if tf.margin_right is not None else 0.1
    mt = _in(tf.margin_top) if tf.margin_top is not None else 0.05
    mb = _in(tf.margin_bottom) if tf.margin_bottom is not None else 0.05
    usable = max(0.3, (b[2] - b[0]) - ml - mr)
    # Per paragraph, at THAT paragraph's size: an ICS callout stacks a 40 pt
    # value over a 16 pt label, and pricing both lines at 40 pt made every
    # stacked tile look 40% taller than it is.
    need_h = 0.0
    longest = 0.0
    for para in tf.paragraphs:
        ptext = "".join(r.text for r in para.runs).strip()
        ppt = max((r.font.size.pt for r in para.runs if r.font.size), default=pt)
        w = len(ptext) * CHAR_W * ppt
        longest = max(longest, min(w, usable))
        lines = max(1, math.ceil(w / usable)) if ptext else 1
        need_h += lines * LINE_H * ppt
    # horizontal: by alignment of the first paragraph
    try:
        align = str(tf.paragraphs[0].alignment or "")
    except Exception:
        align = ""
    if "CENTER" in align:
        cx = (b[0] + b[2]) / 2
        gl, gr = cx - longest / 2, cx + longest / 2
    elif "RIGHT" in align:
        gr = b[2] - mr
        gl = gr - longest
    else:
        gl = b[0] + ml
        gr = gl + longest
    # vertical: by anchor
    anchor = str(tf.vertical_anchor or "")
    inner_top, inner_bot = b[1] + mt, b[3] - mb
    if "MIDDLE" in anchor:
        cy = (inner_top + inner_bot) / 2
        gt, gb_ = cy - need_h / 2, cy + need_h / 2
    elif "BOTTOM" in anchor:
        gb_ = inner_bot
        gt = gb_ - need_h
    else:
        gt = inner_top
        gb_ = gt + need_h
    return (gl, gt, gr, gb_)


def text_collision_findings(prs):
    """FAIL when one text shape's glyphs are drawn over another's.

    Ported from the CashPlease project's cp_qa.py (2026-09-01). The Peer
    Comparison footnote was authored at 6.62"; `fit_layout` pulled it up to
    6.14" to clear the number band, where it landed 0.56" on top of the last row
    of capsule pills — and validate_deck returned 0 FAIL, 0 REVIEW, because its
    overlap rules looked for text over a CHART, never text over text.

    Compared as glyph boxes (see _glyph_box), which is what keeps the house
    stacking pattern quiet: a title frame that touches the selection line's
    frame, a KPI value box that abuts its label, an oversized template title
    box. Two exclusions: the slide number (its collisions are reported by
    geometry_findings), and a label nested inside its own tile or capsule.
    """
    out = []
    for idx, s in enumerate(prs.slides, 1):
        if _is_summit(s):
            continue
        items = []
        for sh in s.shapes:
            if not _has_text(sh) or _is_num(sh):
                continue
            g = _glyph_box(sh)
            if g:
                items.append((sh, _box(sh), g))
        for i in range(len(items)):
            a, fa, ga = items[i]
            for j in range(i + 1, len(items)):
                b, fb, gb = items[j]
                ox = min(ga[2], gb[2]) - max(ga[0], gb[0])
                oy = min(ga[3], gb[3]) - max(ga[1], gb[1])
                if ox <= COLLISION_TOL or oy <= COLLISION_TOL:
                    continue
                # nesting: the smaller FRAME sits inside the larger one (a label on its tile)
                fox = min(fa[2], fb[2]) - max(fa[0], fb[0])
                foy = min(fa[3], fb[3]) - max(fa[1], fb[1])
                small = min((fa[2] - fa[0]) * (fa[3] - fa[1]), (fb[2] - fb[0]) * (fb[3] - fb[1]))
                if small > 0 and fox > 0 and foy > 0 and (fox * foy) / small >= CONTAINED:
                    continue
                out.append(("FAIL", idx,
                            f"text drawn over text ({ox:.2f}\" x {oy:.2f}\"): "
                            f"{_lbl(a)!r} over {_lbl(b)!r}"))
    return out



# ================================================================ tile labels
TILE_ESCAPE_TOL = 0.04          # inches of slack before a label counts as escaping
# PowerPoint's own defaults, applied when a frame leaves its margins unset (python-pptx
# reports those as None). single_line_overflow_findings still reads an unset margin as zero
# and so measures 0.2in more width than a label really has — worth fixing there too, with a
# run over the shipped decks to see what it starts catching.
DEFAULT_MARGIN_X, DEFAULT_MARGIN_Y = 0.1, 0.05


def tile_label_findings(prs):
    """FAIL a label whose wrapped text runs out of the bottom of the tile it sits on.

    Added 2026-09-22, after the Revenue Guarantee slide shipped three tile labels wrapping
    onto the slide behind them — grey text on white, below the navy box, on a deck the gate
    had passed at 0 FAIL.

    Nothing caught it. `single_line_overflow_findings` measures exactly this overflow but
    only FAILs when the spill lands on ANOTHER TEXT SHAPE, and here it landed on empty
    background; `text_collision_findings` deliberately excludes a label nested inside its own
    tile, which is what this is. So a label could leave its tile as long as it left it into
    white space.

    The trap underneath is the one from single_line_overflow_findings' own docstring: a label
    authored at 12pt is floored to 16pt by restyle_fonts and rewritten into a wider face, so
    what fit when it was written does not fit when it is drawn. Measured here at the run's
    ACTUAL font and size, against the TILE's bottom edge rather than the text box's.
    """
    if text_width_in is None:
        return []
    out = []
    for idx, slide in enumerate(prs.slides, 1):
        # shape_type 1 is MSO_SHAPE_TYPE.AUTO_SHAPE — compared as the int this file already
        # uses for it (see pill_wrap_findings), so no new import.
        tiles = [sh for sh in slide.shapes
                 if sh.shape_type == 1 and sh.width and sh.height
                 and _in(sh.height) <= 2.0 and not _has_text(sh)]
        if not tiles:
            continue
        for sh in slide.shapes:
            if not _has_text(sh) or sh.width is None or sh.height is None:
                continue
            box = _box(sh)
            host = None
            for t in tiles:
                tb = _box(t)
                ox = min(box[2], tb[2]) - max(box[0], tb[0])
                oy = min(box[3], tb[3]) - max(box[1], tb[1])
                if ox <= 0 or oy <= 0:
                    continue
                area = (box[2] - box[0]) * (box[3] - box[1])
                if area > 0 and (ox * oy) / area >= 0.9:
                    host = tb
                    break
            if host is None:
                continue
            tf = sh.text_frame
            # An UNSET margin is not a zero margin: python-pptx reports None and PowerPoint
            # then applies its own 0.1in left/right, 0.05in top/bottom. Treating None as 0
            # gave every label 0.2in of width it does not have, which is exactly the slack
            # that let "Incremental revenue, to date" wrap on the shipped slide and still
            # measure as fitting here.
            ml = _in(tf.margin_left) if tf.margin_left is not None else DEFAULT_MARGIN_X
            mr = _in(tf.margin_right) if tf.margin_right is not None else DEFAULT_MARGIN_X
            mt = _in(tf.margin_top) if tf.margin_top is not None else DEFAULT_MARGIN_Y
            usable = _in(sh.width) - ml - mr
            if usable <= 0:
                continue
            need_in = 0.0
            for p in tf.paragraphs:
                runs = [r for r in p.runs if r.text]
                text = "".join(r.text for r in runs).strip()
                if not text:
                    continue
                pt = next((r.font.size.pt for r in runs if r.font.size), None)
                fam = next((r.font.name for r in runs if r.font.name), None)
                if not pt or not fam:
                    continue
                bold = bool(runs[0].font.bold)
                w = text_width_in(text, pt, fam, bold)
                # No slack. PowerPoint lays these out a shade wider than the TTF estimate, so
                # the 2% forgiveness single_line_overflow_findings allows itself is the exact
                # width that let "Incremental revenue, to date" (2.56in in 2.55in of usable
                # box) wrap on the slide and measure as fitting here.
                lines = max(1, math.ceil(w / usable))
                need_in += lines * pt / 72.0 * 1.22
            if not need_in:
                continue
            bottom = box[1] + mt + need_in
            if bottom > host[3] + TILE_ESCAPE_TOL:
                out.append(("FAIL", idx,
                            f"tile label runs out of its tile by "
                            f"{bottom - host[3]:.2f}\" — {_lbl(sh)!r} needs {need_in:.2f}\" "
                            f"below {box[1]:.2f}\" and the tile ends at {host[3]:.2f}\""))
    return out

# ================================================================ cross-slide tiles
_TILE_NUM = re.compile(r"^\$?-?[\d,]+$")


def _tile_pairs(slide):
    """-> {label: (figure, text)} for the KPI tiles across the top of a slide.

    Paired by column rather than by geometry containment: every builder lays these
    out with `shapes._tile`, one value box directly over one label box in the same
    x band, so grouping the band is enough and needs no tile-shape detection.
    """
    band = []
    for sh in slide.shapes:
        if not getattr(sh, "has_text_frame", False) or sh.top is None or sh.left is None:
            continue
        top = _in(sh.top)
        if not (1.4 <= top <= 3.0):                 # the KPI row, below the subtitle
            continue
        t = " ".join(sh.text_frame.text.split())
        if t:
            band.append((round(_in(sh.left), 1), top, t))
    cols = {}
    for left, top, t in band:
        cols.setdefault(left, []).append((top, t))
    out = {}
    for parts in cols.values():
        parts.sort()
        nums = [t for _, t in parts if _TILE_NUM.match(t)]
        labels = [t for _, t in parts if not _TILE_NUM.match(t)]
        if len(nums) == 1 and len(labels) == 1:
            out[labels[0].lower()] = (int(nums[0].lstrip("$").replace(",", "")), nums[0])
    return out


# Lower-cased copies of the two slides' shared tile labels. Deliberately literals
# rather than an import of the builder: renaming a label must fail this check loudly
# (see the docstring) rather than follow it silently to a deck nobody compared.
_POP_LABEL = "accounts excl. closed"
_OUT_LABEL = "outside ars"
_ELIG_LABEL = "ars-eligible accounts"


def account_population_findings(prs):
    """FAIL when Product Mix and Excluded Accounts do not state one book that adds up.

    Added 2026-10-02, with the fix. These two slides are consecutive and about the same
    accounts, and they counted different populations: 71,466 accounts excluding closed on
    Product Mix against 66,462 open accounts on Excluded Accounts, with two eligible counts
    two apart. Both slides were internally consistent, which is why every rule in this file
    passed them — each reads one slide at a time. A general "one label, one figure" rule was
    written first and thrown away: 12-Month Eligible Take Rate — Personal and — Business
    carry the same tile labels over different populations by design, so it failed correct
    slides, and it could not see this defect anyway — these two slides disagreed about the
    wording as well as the number.

    So this check is deliberately specific to the pair, and it FAILS when it cannot find
    what it is checking rather than passing quietly. A check that goes silent when a label
    is renamed is worse than no check: it reports a clean deck it never looked at.
    """
    mix = exc = None
    for idx, slide in enumerate(prs.slides, 1):
        t = (_title(slide) or "").strip().lower()
        if t.startswith("product mix"):
            mix = (idx, slide)
        elif t.startswith("excluded accounts"):
            exc = (idx, slide)
    # Keyed off Excluded Accounts, which only a BUILT deck has: the ARS template shell
    # carries a dummy Product Mix slide on its own, and failing that is failing a slide
    # for not yet having been built. A build that produced Excluded Accounts and lost
    # Product Mix is a real defect and still fails below.
    if exc is None:
        return []
    out = []
    if mix is None:
        return [("FAIL", exc[0],
                 "Excluded Accounts is in this deck without Product Mix — the two "
                 "slides state one population between them and neither can be "
                 "reconciled alone")]
    tiles = {"Product Mix": (mix[0], _tile_pairs(mix[1])),
             "Excluded Accounts": (exc[0], _tile_pairs(exc[1]))}
    for name, (idx, t) in tiles.items():
        for lbl in ((_POP_LABEL, _ELIG_LABEL) if name == "Product Mix"
                    else (_POP_LABEL, _ELIG_LABEL, _OUT_LABEL)):
            if lbl not in t:
                out.append(("FAIL", idx,
                            f"{name}: no tile labelled {lbl!r}, so the two slides' "
                            f"account figures cannot be reconciled — fix the label or "
                            f"this check, do not leave it unable to look"))
    if out:
        return out
    mi, mt = tiles["Product Mix"]
    ei, et = tiles["Excluded Accounts"]
    if mt[_POP_LABEL][0] != et[_POP_LABEL][0]:
        out.append(("FAIL", ei,
                    f"Excluded Accounts counts {et[_POP_LABEL][1]} accounts where Product "
                    f"Mix (slide {mi}) counts {mt[_POP_LABEL][1]} — consecutive slides, "
                    f"two books"))
    if mt[_ELIG_LABEL][0] != et[_ELIG_LABEL][0]:
        out.append(("FAIL", ei,
                    f"Excluded Accounts reports {et[_ELIG_LABEL][1]} ARS-eligible accounts "
                    f"where Product Mix (slide {mi}) reports {mt[_ELIG_LABEL][1]}"))
    got = et[_OUT_LABEL][0] + et[_ELIG_LABEL][0]
    if got != et[_POP_LABEL][0]:
        out.append(("FAIL", ei,
                    f"{et[_OUT_LABEL][1]} outside ARS + {et[_ELIG_LABEL][1]} eligible = "
                    f"{got:,}, but the slide states {et[_POP_LABEL][1]} accounts"))
    return out


# ================================================================ one program-to-date ratio
_RATIO_RX = re.compile(r"\b(\d+\.\d) : 1\b")
_DIVIDER_RATIO_LABEL = "revenue to fees, program to date"


def _ptd_ratio_statements(prs):
    """[(slide index, where, '2.2 : 1')] for every place the deck states the program-to-date
    profitability ratio: the P&L's Profitability row (last column), the ARS divider's stat
    labelled 'revenue to fees, program to date', and any sentence '… N.N : 1 profitability'."""
    out = []
    for idx, slide in enumerate(prs.slides, 1):
        title = (_title(slide) or "").strip().lower()
        shapes = list(slide.shapes)
        if title.startswith("ars financial performance"):
            for sh in shapes:
                if not sh.has_table:
                    continue
                for row in sh.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if cells and cells[0].lower() == "profitability" and _RATIO_RX.fullmatch(cells[-1] or ""):
                        out.append((idx, "ARS Financial Performance, Profitability, program to date", cells[-1]))
        for sh in shapes:
            if not _has_text(sh) or sh.has_table:
                continue
            txt = sh.text_frame.text.strip()
            if txt.lower() == _DIVIDER_RATIO_LABEL and sh.top is not None:
                # The value is the ratio-shaped text box drawn above the label, same column.
                cands = [o for o in shapes if _has_text(o) and o is not sh and o.top is not None
                         and _RATIO_RX.fullmatch(o.text_frame.text.strip())
                         and abs(o.left - sh.left) < Emu(457200) and o.top < sh.top]   # half an inch
                if cands:
                    val = min(cands, key=lambda o: sh.top - o.top)
                    out.append((idx, f"section divider, '{_DIVIDER_RATIO_LABEL}'", val.text_frame.text.strip()))
            for m in re.finditer(r"\b(\d+\.\d) : 1 profitability\b", txt):
                out.append((idx, f"'{m.group(0)}' in the text", f"{m.group(1)} : 1"))
    return out


def ptd_ratio_findings(prs):
    """FAIL when the deck states the program-to-date profitability ratio two different ways.

    Added 2026-10-12, with the fix. True Sky's ARS divider read "2.1 : 1 revenue to fees,
    program to date" and its ARS Financial Performance P&L read "2.2 : 1" in the same
    column, from the same $2,026,429 over $941,929. The extractor had rounded the quotient
    to 2.15 before storing it, and f"{2.15:.1f}" is "2.1" because the float is 2.1499...;
    the P&L formatted the unrounded 2.1513 and said 2.2. Each slide was right by its own
    arithmetic, so every rule that reads one slide at a time passed both. Like
    `account_population_findings`, this reads the specific places the deck makes that
    statement and FAILs when they do not match. Fewer than two statements is nothing to
    compare, not a pass.
    """
    stated = _ptd_ratio_statements(prs)
    if len({v for _, _, v in stated}) <= 1:
        return []
    listing = "; ".join(f"slide {i} {where}: {v}" for i, where, v in stated)
    return [("FAIL", stated[0][0],
             f"the program-to-date profitability ratio is stated {len({v for _, _, v in stated})} "
             f"different ways — {listing}. One quotient, one formatter (revenue_guarantee_slide.ratio_text).")]


# ================================================================ autofit
def autofit_findings(prs):
    """FAIL a frame PowerPoint shrinks below 90%.

    `normAutofit fontScale` hides an overflow: the text renders smaller in
    PowerPoint than its nominal size, and LibreOffice renders ignore it entirely
    (CLAUDE.md rule 1). Size the text to fit instead.
    """
    from pptx.oxml.ns import qn
    out = []
    for idx, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if not sh.has_text_frame:
                continue
            na = sh.text_frame._txBody.bodyPr.find(qn('a:normAutofit'))
            if na is not None and na.get('fontScale') and int(na.get('fontScale')) < 90000:
                out.append(("FAIL", idx,
                            f"PowerPoint autofit shrinks this text to {int(na.get('fontScale'))//1000}% — remove autofit and size to fit: {_lbl(sh)!r}"))
    return out


# ================================================================ mailing table
_MAILING_MONTH = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}$")


def mailing_table_findings(prs, texts=None):
    """FAIL a mailing table listing more mailings than the program has run.

    set_table only overwrote the rows the client's data reached and left the
    rest of the template standing, so 1549 (one mailing) shipped eleven of the
    reference client's mailings underneath its own (2026-08-20). Any table whose
    first column is "Mailing" is checked against the count the deck states
    ("across N mailings").
    """
    texts = texts if texts is not None else slide_texts(prs)
    allj = " ".join(b for _, bl in texts for b in bl)
    mc = re.search(r"across (\d[\d,]*) mailings?\b", allj)
    if not mc:
        return []
    stated = int(mc.group(1).replace(",", ""))
    out = []
    for idx, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if not sh.has_table:
                continue
            t = sh.table
            if t.cell(0, 0).text.strip().lower() != "mailing":
                continue
            dated = [t.cell(r, 0).text.strip() for r in range(1, len(t.rows))]
            dated = [d for d in dated if _MAILING_MONTH.match(d)]
            if len(dated) > stated:
                out.append(("FAIL", idx,
                            f"mailing table lists {len(dated)} mailings but the program has run "
                            f"{stated} — leftover template rows: {', '.join(dated[stated:])}"))
    return out


# ================================================================ extract cross-check
def extract_findings(prs, extract, texts=None):
    """FAIL a headline figure from base_extract.json that is not in the deck verbatim.

    Eligible ARS accounts are sourced from the ODD (n_eligible), not the workbook
    DCO figure, so dco_eligible is intentionally not required.
    """
    if not extract:
        return []
    texts = texts if texts is not None else slide_texts(prs)
    allnum = " ".join(b for _, bl in texts for b in bl)
    out = []

    def want(label, s):
        if s not in allnum:
            out.append(("FAIL", 0, f"base_extract {label} = {s} not found verbatim in deck"))
    # Formatted through brand.usd_compact, the SAME function the builders render
    # with. This carried its own `/1e6:.2f}M` and became the fifth copy of that rule
    # to disagree: the moment the decks started writing $830K under a million, the
    # cross-check went looking for "$0.83M" and failed a correct deck (2026-09-11).
    # An expected value formatted differently from the rendered one is not a check.
    def want_money(label, v):
        """Either rendering of the same figure: compact, or the exact dollars.

        ARS Financial Performance was a set of tiles written through usd_compact; since
        2026-10-02 it is the P&L, which states the figure to the dollar. Both say it — a
        check that insists on one of two correct renderings is a check that fails a correct
        deck, which is how the $830K-vs-$0.83M version of this failed one in 2026-09.
        """
        forms = [_usd(v), f"${v:,.0f}", f"${abs(v):,.0f}"]
        # The P&L table states a total as the sum of its own rounded lines, so it can differ from the
        # extract's unrounded total by one dollar (Rally CU 2026.10: lines add to $35,733,424, the extract
        # is 35,733,424.51 = $35,733,425). That is the same figure rendered two correct ways: a dollar
        # either side of the extract's rounding is accepted, and nothing wider.
        whole = round(abs(v))
        forms += [f"${whole - 1:,.0f}", f"${whole + 1:,.0f}"]
        if not any(f in allnum for f in forms):
            out.append(("FAIL", 0, f"base_extract {label} = {forms[0]} not found in the deck, "
                                   f"in that form or as {forms[1]}"))

    if "ltd_revenue" in extract:
        want_money("ltd_revenue", extract["ltd_revenue"])
    if "ltd_profit" in extract:
        want_money("ltd_profit", extract["ltd_profit"])
    if "months" in extract:
        want("months", f"{extract['months']} months")
    if "mailings" in extract:
        want("mailings", str(extract['mailings']))
    return out


# ================================================================ labelled metrics
def labelled_metric_findings(prs, texts=None):
    """REVIEW a labelled metric that shows more than two distinct values deck-wide.

    The older, hardcoded cousin of figure_identity_findings — kept because its
    four labels are the ones most often quoted in prose.
    """
    texts = texts if texts is not None else slide_texts(prs)
    out = []
    for label in ["take rate", "opt-in", "profitability", "response"]:
        vals = set()
        for _, bl in texts:
            for b in bl:
                for m in re.finditer(r"([\d.]+)\s*%?\s*" + label, b.lower()):
                    vals.add(m.group(1))
        if len(vals) > 2:
            out.append(("REVIEW", 0, f"metric '{label}' shows {len(vals)} different values {sorted(vals)} — confirm each is a distinct measure"))
    return out


# ================================================================ runner
def run(path, extract=None):
    """Every rule, in order, over one deck. Returns [(level, slide, message)] sorted
    FAIL first, then by slide."""
    prs = Presentation(path)
    texts = slide_texts(prs)
    findings = []
    findings += package_findings(path)
    findings += reference_leak_findings(path, prs)
    findings += single_line_overflow_findings(prs)
    findings += pill_wrap_findings(prs)
    findings += stale_template_caption_findings(prs, path)
    findings += figure_identity_findings(prs)
    findings += period_findings(prs, find_period_pack(path))
    findings += source_note_findings(path, prs)
    findings += closing_month_findings(prs)
    findings += table_label_fit_findings(prs)
    findings += tile_label_findings(prs)
    findings += account_population_findings(prs)
    findings += ptd_ratio_findings(prs)
    findings += figure_sidecar_findings(path)
    findings += claim_consistency_findings(prs)
    findings += text_rule_findings(prs, texts)
    findings += geometry_findings(prs)
    findings += text_collision_findings(prs)
    findings += autofit_findings(prs)
    findings += mailing_table_findings(prs, texts)
    findings += extract_findings(prs, extract, texts)
    findings += labelled_metric_findings(prs, texts)
    order = {"FAIL": 0, "REVIEW": 1}
    findings.sort(key=lambda f: (order[f[0]], f[1]))
    return findings


RULES = (package_findings, reference_leak_findings, single_line_overflow_findings,
         stale_template_caption_findings, figure_identity_findings, period_findings,
         source_note_findings, figure_sidecar_findings, claim_consistency_findings,
         text_rule_findings, geometry_findings, text_collision_findings,
         autofit_findings, mailing_table_findings, extract_findings,
         labelled_metric_findings, summit_date_findings, closing_month_findings,
         table_label_fit_findings, tile_label_findings)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # Findings quote slide text full of em dashes, curly quotes and arrows.
    # Printing one to a PIPE on Windows encodes as cp1252 and raises part-way
    # through the report — the summary line lands and every finding after it is
    # lost. A gate that cannot say what failed is not a gate.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not argv:
        print(__doc__)
        sys.exit(2)
    path = argv[0]
    extract = json.load(open(argv[1], encoding="utf-8")) if len(argv) > 1 else None
    findings = run(path, extract)
    fails = [f for f in findings if f[0] == "FAIL"]
    print(f"validate_deck: {path}")
    print(f"  {len(fails)} FAIL, {len(findings)-len(fails)} REVIEW\n")
    for lvl, idx, msg in findings:
        where = f"slide {idx}" if idx else "deck-wide"
        print(f"  [{lvl:6}] {where:9} {msg}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
