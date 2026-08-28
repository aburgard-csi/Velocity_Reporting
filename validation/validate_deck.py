#!/usr/bin/env python3
"""
validate_deck.py — a lint pass for a built ARS/Executive-Review .pptx.

Catches the classes of defect that slipped through on the 1038 Sugar River v1
build: banned words, impossible counts (a sub-count larger than its total),
opt-in "higher/lower" claims that fight the numbers, unverified superlatives,
chart captions that promise a comparison the image may not deliver, any headline
figure that disagrees with the base_extract.json, and layout defects — shapes that run
off the slide or collide with the slide number / logo (the `fit_layout` pass prevents these).

It is a *text + structure* linter — it cannot see inside a rendered chart PNG,
so anything image-dependent is reported as REVIEW (look with your eyes), not FAIL.

Usage:
    python3 validate_deck.py <deck.pptx> [base_extract.json]

Exit code 0 if no FAIL-level findings, 1 otherwise. Wire this into the build
right after prs.save(): a non-zero exit should block the deck from going out.
"""
import os, sys, re, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
from pptx import Presentation
from pptx.util import Emu

def _in(v): return Emu(v).inches if v is not None else None
def _box(sh):
    l,t,w,h=_in(sh.left),_in(sh.top),_in(sh.width),_in(sh.height)
    return None if None in (l,t,w,h) else (l,t,l+w,t+h)
def _overlap(a,b,pad=0.05):
    return (min(a[2],b[2])-max(a[0],b[0]))>pad and (min(a[3],b[3])-max(a[1],b[1]))>pad
def _is_num(sh):
    if not (sh.has_text_frame and sh.text_frame.text.strip().isdigit()): return False
    b=_box(sh); return b is not None and b[1]>6.5 and b[0]<1.7 and (b[2]-b[0])<1.4
def _is_logo(sh):
    if sh.shape_type!=13: return False
    b=_box(sh); return b is not None and (b[2]-b[0])<3.15 and (b[3]-b[1])<1.2
def _is_summit(s):
    t=" ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
    return "Executive Summit" in t or "About the Summit" in t
def _lbl(sh):
    return (sh.text_frame.text.strip()[:34] if sh.has_text_frame and sh.text_frame.text.strip() else "chart/table")

BANNED = ["robust", "comprehensive", "leverage", "seamless", "delve", "lift",
          "lifted", "ramp", "ramping", "healthy", "predominantly", "companion",
          "seasoned book", "annuity"]
# banned words that legitimately appear as data labels/among fixed template terms
BANNED_ALLOW_CONTEXT = ["lift matrix"]   # 'Lift Matrix' is a named slide/table, allowed
SUPERLATIVES = ["strongest", "weakest", "best", "worst", "highest", "lowest",
                "largest", "smallest", "top-performing", "#1", "record ", "all-time"]
# filler / AI-tell phrases to keep off client-facing slides (keep to the notes/narration)
AI_PHRASES = ["onboarding opportunity", "clear opportunity", "unlock", "empower",
              "at the end of the day", "when it comes to", "in today's landscape",
              "game-changer", "seamless", "leverage"]


# --- reference-client leakage -------------------------------------------------
# Every program template is trimmed from a real client's deck, so the reference
# client's name is baked into any literal the builder forgets to swap. All seven
# 2026.08 ICS decks shipped at 0 FAIL carrying "Union Financial  •  July 2026" on
# the Questions & Discussion slide (found 2026-08-21). A deck naming someone
# else's client is the worst thing we can hand a client, so it FAILs.
REFERENCE_CLIENTS = ["Union Financial", "Marine FCU", "Marine Federal Credit Union",
                     "Sugar River", "CoastLife", "Wellworth", "Canandaigua",
                     "Bank Name"]

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
                    rec(sh.shapes); continue
                if sh.has_text_frame and sh.text_frame.text.strip():
                    top = _in(sh.top) or 0
                    (header if top < 1.3 else body).append(sh.text_frame.text)
        rec(slide.shapes)
        head_low = "  ".join(header).lower()
        body_join = "  ".join(body)
        for name in REFERENCE_CLIENTS:
            if name.lower() in own or name.lower() in head_low:
                continue
            m = re.search(r"[^\n]*\b" + re.escape(name) + r"\b[^\n]*", body_join, re.I)
            if m:
                out.append(("FAIL", idx,
                            f"reference-client leakage: '{name}' appears on a deck for a "
                            f"different client — …{m.group(0).strip()[:70]}…"))
    return out

def slide_texts(prs):
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

def has_chart_image(prs, idx):
    s = list(prs.slides)[idx - 1]
    for sh in s.shapes:
        if sh.shape_type == 13:  # picture
            try:
                rId = sh._element.blipFill.blip.rEmbed
                pn = str(s.part.rels[rId].target_part.partname)
                if not pn.endswith("image1.png"):  # image1 = logo
                    return True
            except Exception:
                pass
    return False

def package_findings(path):
    """OOXML package integrity — the layer python-pptx will happily lie about.

    Added 2026-08-17 after all seven ICS decks shipped at 0 FAIL while being
    structurally broken: 50 slide parts, 28 sldId entries, and six parts each
    referenced TWICE. python-pptx enumerates a duplicated reference as two
    slides, so every text/geometry rule passed — but LibreOffice refused to open
    the file and PowerPoint silently reordered it (title slide gone, Contact Us
    near the front). Nothing above this function can see that class of defect.

    Checks: no duplicate slide references, no dangling references, no orphaned
    slide parts, and parts == entries == distinct targets.
    """
    import zipfile, re as _re
    from collections import Counter
    out = []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        return [("FAIL", 0, f"package will not open as a zip: {e}")]
    try:
        parts = [n for n in z.namelist()
                 if _re.match(r"ppt/slides/slide\d+\.xml$", n)]
        pres = z.read("ppt/presentation.xml").decode("utf-8", "replace")
        rids = _re.findall(r"<p:sldId[^>]*r:id=\"(rId\d+)\"", pres)
        rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8", "replace")
        rmap = dict(_re.findall(r"Id=\"(rId\d+)\"[^>]*Target=\"([^\"]+)\"", rels))
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


def single_line_overflow_findings(prs):
    """FAIL a one-line label whose glyphs are wider than its box.

    Added 2026-08-27. The ICS Financial Summary shipped "Billed Expense for 46,195
    Accounts" in a 3.9in box: 3.80in of Montserrat against 3.70in of usable width, so it
    wrapped onto the value beneath it. Everything already in this file passed, because:

      * the deck asks for Calibri 14pt but enforce_min_font floors runs at 16 and the
        font-role pass rewrites them to Montserrat, which is far wider (3.10in -> 3.80in);
      * the LibreOffice render substitutes a narrower face, so it looked clean there.

    So measure the ACTUAL run font and size against the box minus its own margins. Scoped
    to boxes only tall enough for one line — a deliberately wrapping paragraph is fine.
    """
    try:
        sys.path.insert(0, os.path.join(HERE, os.pardir, "build"))
        from textfit import text_width_in
    except Exception:
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
            # A caption box two lines tall wrapping to two lines is correct — only flag text
            # that needs MORE lines than its own box can show.
            if need <= holds:
                continue
            # Spilling past your own box is normal in this deck — captions are sized tight and
            # the extra line simply renders below. It is only a DEFECT when the spill lands on
            # another shape, which is what "Billed Expense for 46,195 Accounts" did to the
            # value beneath it. So flag only a spill that collides.
            spill_top = _in(sh.top) + _in(sh.height)
            spill_bot = spill_top + (need - holds) * line_in
            l, r = _in(sh.left), _in(sh.left) + _in(sh.width)
            hit = None
            for other in slide.shapes:
                if other is sh or other.top is None or other.height is None:
                    continue
                # Spilling over a chart or picture is tolerated by this deck's layout — the
                # captions are sized tight on purpose and the art sits below with clearance.
                # Landing on ANOTHER TEXT shape is the defect (the ICS billed-expense label
                # wrapped onto its own value), so only text-on-text counts.
                if not (other.has_text_frame and other.text_frame.text.strip()):
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
                            f"\u2026{text[:44]}\u2026 spills onto "
                            f"\u2026{(_lbl(hit) or '')[:28]}\u2026"))
    return out


_MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}\b")


def stale_template_caption_findings(prs, deck_path=None, template_path=None):
    """FAIL a dated caption still byte-identical to the TEMPLATE's.

    The builder swaps numbers into captions but for a dozen date phrases it never
    swapped anything, so the reference client's month shipped verbatim: 1549
    Wellworth ran on a Jul 2026 extract and its deck read "Monthly debit spend
    (June 2026)", "opt-in status as of June 2026" and "Jul 2023 – Jun 2026 (36
    months)" — on a client with five months of data (Aaron, 2026-08-28).

    The tell is exact identity with the template: a swapped caption always differs
    somewhere (its own counts), so an untouched dated paragraph is a caption no swap
    reached. Only paragraphs carrying a Month-Year are considered, which is why a
    genuinely static line like a section header never trips this.
    """
    if template_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(here, os.pardir, "templates", "ars_template.pptx")
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
    # Only captions carrying the TEMPLATE'S OWN reporting month can be stale — that is
    # the value a swap has to replace. A caption naming a fixed historical window (the
    # Kaplan-Meier cohort starts at Jul 2021 for every client) is correct precisely
    # BECAUSE it still matches the template, and must not be flagged.
    ref = None
    for s_ in tpl.slides:
        for sh in s_.shapes:
            if sh.has_text_frame:
                m = re.search(r"\b([A-Z][a-z]+)\s+(\d{4})\s+Data\b", sh.text_frame.text)
                if m:
                    ref = (m.group(1), m.group(2)); break
        if ref: break
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
                    # Long CAPTION prose only. A short date PILL ("PTD · June 2026",
                    # "June 2026 Data") is a derived value with its own guard — the ARS
                    # builder hard-fails if its pill swap matches nothing — and in a
                    # combined deck the ICS section's pill legitimately reports an older
                    # month, because ICS financials are quarterly and carry forward
                    # (CLAUDE.md cadence). 1705 CoastLife's ICS section correctly reads
                    # "PTD · June 2026" against a Jul 2026 ARS section, and this check
                    # failed all four of those slides (Aaron, 2026-08-28).
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


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    prs = Presentation(sys.argv[1])
    extract = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    texts = slide_texts(prs)
    findings = []  # (level, slide, msg)
    findings += package_findings(sys.argv[1])
    findings += reference_leak_findings(sys.argv[1], prs)
    findings += single_line_overflow_findings(prs)
    findings += stale_template_caption_findings(prs, sys.argv[1])

    for idx, blocks in texts:
        joined = "  ".join(blocks)
        low = joined.lower()

        # 1) banned words
        lift_slide = "lift matrix" in low   # the ARS Lift Matrix slide is entirely about lift — give it a pass
        for w in BANNED:
            for m in re.finditer(r"\b" + re.escape(w) + r"\b", low):
                ctx = low[max(0, m.start()-25):m.start()+25]
                if any(a in ctx for a in BANNED_ALLOW_CONTEXT):
                    continue
                if w in ("lift", "lifted") and lift_slide:
                    continue
                findings.append(("FAIL", idx, f"banned word '{w}' — …{ctx.strip()}…"))

        # 1a) singular/plural agreement on counts the builder interpolates. "1 mailings"
        # is how a one-mailing client reads on a template built for 81 (1549, 2026-08-20).
        for m in re.finditer(r"\b1 (mailings|months|responders|accounts|branches|customers)\b", joined):
            findings.append(("FAIL", idx, f"count/plural disagreement: '1 {m.group(1)}'"))

        # 1b) a stated comparison against a threshold must match the stated ratio.
        # Added 2026-08-20: the Program Overview bullet was a template literal the builder
        # only swapped the ratio into, so 1549 shipped "0.2 : 1 is well above the 2 : 1
        # threshold". The number was right and the sentence around it was false.
        for m in re.finditer(r"([\d.]+)\s*:\s*1\s+is\s+(well above|above|below|under)\s+the\s+([\d.]+)\s*:\s*1", joined):
            got, word, thr = float(m.group(1)), m.group(2), float(m.group(3))
            claims_above = word in ("well above", "above")
            if claims_above != (got >= thr):
                findings.append(("FAIL", idx,
                    f"threshold claim contradicts the ratio: {got} : 1 described as "
                    f"'{word} the {thr} : 1 threshold'"))

        # 2) impossible counts: "N of M" with N > M
        for m in re.finditer(r"([\d,]+)\s+of\s+([\d,]+)", joined):
            n, tot = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
            if n > tot:
                findings.append(("FAIL", idx, f"impossible count: {n} of {tot} (sub-count exceeds total)"))

        # 2b) "X% of <group> (N ...)": check N vs any total for that group on the slide
        for m in re.finditer(r"([\d.]+)%\s+of\s+(\w+)\s*\(([\d,]+)", joined):
            pct = float(m.group(1)); cnt = int(m.group(3).replace(",", ""))
            # find a plausible total for the group elsewhere on the slide
            tot = None
            for mm in re.finditer(r"([\d,]{3,})", joined):
                v = int(mm.group(1).replace(",", ""))
                if v >= cnt and abs(cnt / v * 100 - pct) < 1.5:
                    tot = v; break
            if tot and cnt > tot:
                findings.append(("FAIL", idx, f"{cnt} exceeds total {tot} on same slide"))
            if tot is None:
                findings.append(("REVIEW", idx,
                    f"'{pct}% of {m.group(2)} ({cnt})' — confirm {cnt}/{pct}% ties to the chart total"))

        # 2c) AI-tell / filler phrases (belong in narration, not on the slide)
        for ph in AI_PHRASES:
            if ph in low:
                findings.append(("REVIEW", idx, f"filler/AI-tell phrase '{ph}' — move to narration/notes"))

        # 3) unverified superlatives
        for w in SUPERLATIVES:
            if w in low:
                s = next((b for b in blocks if w in b.lower()), "")
                findings.append(("REVIEW", idx, f"superlative '{w.strip()}' — verify vs. the ranking: “{s[:90]}”"))

        # 4) higher/lower rate claims
        for m in re.finditer(r"(higher|lower)\s+rate[^.]{0,60}?([\d.]+)%", low):
            findings.append(("REVIEW", idx,
                f"'{m.group(1)} rate: {m.group(2)}%' — confirm direction vs. the baseline it compares to"))

        # 5) caption promises a comparison — chart must actually show 2 series
        if has_chart_image(prs, idx):
            if re.search(r"\bvs\.?\b|versus|compared with|both .* and |mailed .* responded", low):
                findings.append(("REVIEW", idx,
                    "caption implies a comparison — confirm the chart draws BOTH series (not one)"))
            if "in orange" in low or "shown in orange" in low:
                findings.append(("REVIEW", idx,
                    "caption references an orange highlight — confirm the highlighted bars actually render orange"))

    # 8) geometry: content running off the slide, or colliding with the slide number / logo
    for idx, s in enumerate(prs.slides, 1):
        if _is_summit(s):
            continue
        zones = [(_box(sh), "slide number") for sh in s.shapes if _is_num(sh)]
        zones += [(_box(sh), "logo") for sh in s.shapes if _is_logo(sh)]
        for sh in s.shapes:
            if _is_num(sh) or _is_logo(sh):
                continue
            has = (sh.has_text_frame and sh.text_frame.text.strip()) or sh.shape_type == 13 or sh.has_table
            b = _box(sh)
            if not has or b is None:
                continue
            if b[3] > 7.56 or b[2] > 13.42:
                findings.append(("FAIL", idx, f"runs off the slide (right={b[2]:.2f}\", bottom={b[3]:.2f}\") — {_lbl(sh)!r}"))
                continue
            gb = b
            if sh.has_text_frame and sh.text_frame.text.strip():
                # glyph-aware: a centered line's glyphs may clear the corner even if its box doesn't
                _t9 = sh.text_frame.text.strip()
                _p9 = [r.font.size.pt for pa in sh.text_frame.paragraphs for r in pa.runs if r.font.size]
                _cw9 = 0.0066*(max(_p9) if _p9 else 16.0)
                _tw9 = min(len(_t9)*_cw9, b[2]-b[0])
                try: _c9 = str(sh.text_frame.paragraphs[0].alignment) == "CENTER (2)"
                except Exception: _c9=False
                if _c9:
                    _cx9=(b[0]+b[2])/2; gb=(_cx9-_tw9/2, b[1], _cx9+_tw9/2, b[3])
                else:
                    gb=(b[0], b[1], b[0]+_tw9, b[3])
            hit = next((zn for zb, zn in zones if zb and _overlap(gb, zb)), None)
            if hit:
                findings.append(("FAIL", idx, f"collides with the {hit} — {_lbl(sh)!r}"))
        # estimated text overflow: a bottom text box whose rendered lines likely spill past its
        # box into the slide-number band (box geometry alone misses this — glyphs overflow)
        for sh in s.shapes:
            if not (sh.has_text_frame and sh.text_frame.text.strip()):
                continue
            b = _box(sh)
            if b is None or b[1] < 5.8:
                continue
            txt = sh.text_frame.text.strip()
            width = max(0.5, b[2]-b[0])
            # font-size-aware: char width ~0.0066*pt in, line height ~0.0163*pt in
            import math as _m
            _pts=[r.font.size.pt for pa in sh.text_frame.paragraphs for r in pa.runs if r.font.size]
            _pt=max(_pts) if _pts else 16.0
            _cw=0.0066*_pt; _lh=0.0163*_pt
            est_lines = max(1, _m.ceil(len(txt)*_cw/width))
            est_bottom = b[1] + 0.08 + est_lines*_lh
            # corner-aware: only FAIL when the estimated glyph run reaches the number/logo corners
            try: _cen = str(sh.text_frame.paragraphs[0].alignment) == "CENTER (2)"
            except Exception: _cen=False
            _tw=min(len(txt)*_cw, width)
            if _cen:
                _cx=(b[0]+b[2])/2; _gl=_cx-_tw/2; _gr=_cx+_tw/2
            else:
                _gl=b[0]; _gr=b[0]+_tw
            if est_bottom > 7.10 and est_bottom > b[3] + 0.05 and (_gl < 1.25 or _gr > 11.15):
                findings.append(("FAIL", idx, f"caption likely overflows its box into the bottom corners (est {est_lines} lines, est bottom {est_bottom:.2f}\") — {_lbl(sh)!r}"))
        # chart image overlapping a callout/tile autoshape = FAIL (charts must stop at the rail)
        _tiles = []
        for sh in s.shapes:
            if sh.shape_type == 1:
                tb = _box(sh)
                if tb and (tb[2]-tb[0]) < 6.5 and (tb[3]-tb[1]) < 4.0:   # tiles, not backgrounds
                    _tiles.append(tb)
        for sh in s.shapes:
            if sh.shape_type != 13 or _is_logo(sh):
                continue
            pb = _box(sh)
            if pb is None or (pb[2]-pb[0]) <= 3.0:
                continue
            for tb in _tiles:
                ox = min(pb[2], tb[2]) - max(pb[0], tb[0]); oy = min(pb[3], tb[3]) - max(pb[1], tb[1])
                if ox > 0.1 and oy > 0.1 and ox*oy > 0.15:
                    tile_area = (tb[2]-tb[0])*(tb[3]-tb[1])
                    if tile_area and (ox*oy)/tile_area > 0.6:
                        continue    # tile sits mostly ON the picture = an annotation, by design
                    findings.append(("FAIL", idx, f"chart overlaps a callout/tile by {ox*oy:.1f} sq in — cap the chart at the tile rail"))
                    break
        # text overlapping a chart image (letterboxed whitespace can make this benign -> REVIEW)
        charts = [_box(sh) for sh in s.shapes if sh.shape_type == 13 and not _is_logo(sh)
                  and _box(sh) and (_box(sh)[2]-_box(sh)[0]) > 3.0]
        for sh in s.shapes:
            if not (sh.has_text_frame and sh.text_frame.text.strip()):
                continue
            b = _box(sh)
            if b is None:
                continue
            for cb in charts:
                ox = min(b[2], cb[2]) - max(b[0], cb[0]); oy = min(b[3], cb[3]) - max(b[1], cb[1])
                if ox > 0.5 and oy > 0.12 and ox * oy > 0.25:
                    findings.append(("REVIEW", idx, f"text overlaps a chart image ({ox*oy:.1f} sq in) — check for collision: {_lbl(sh)!r}"))
                    break

    # 9) PowerPoint autofit shrink: fontScale hides overflow — text renders smaller in
    # PowerPoint than the nominal sizes (LibreOffice renders ignore it). Size text to fit.
    from pptx.oxml.ns import qn as _qn9
    for idx, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if not sh.has_text_frame:
                continue
            _na = sh.text_frame._txBody.bodyPr.find(_qn9('a:normAutofit'))
            if _na is not None and _na.get('fontScale') and int(_na.get('fontScale')) < 90000:
                findings.append(("FAIL", idx,
                    f"PowerPoint autofit shrinks this text to {int(_na.get('fontScale'))//1000}% — remove autofit and size to fit: {_lbl(sh)!r}"))

    # 10) a mailing table must not list more mailings than the program has run.
    # set_table only overwrote the rows the client's data reached and left the rest of the
    # template standing, so 1549 (one mailing) shipped eleven of the reference client's
    # mailings underneath its own (2026-08-20). Any table whose first column is "Mailing"
    # is checked against the mailing count the deck states elsewhere.
    _allj = " ".join(b for _, bl in texts for b in bl)
    _mc = re.search(r"across (\d[\d,]*) mailings?\b", _allj)
    if _mc:
        _stated = int(_mc.group(1).replace(",", ""))
        _mon = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}$")
        for idx, s in enumerate(prs.slides, 1):
            for sh in s.shapes:
                if not sh.has_table:
                    continue
                t = sh.table
                if t.cell(0, 0).text.strip().lower() != "mailing":
                    continue
                dated = [t.cell(r, 0).text.strip() for r in range(1, len(t.rows))]
                dated = [d for d in dated if _mon.match(d)]
                if len(dated) > _stated:
                    findings.append(("FAIL", idx,
                        f"mailing table lists {len(dated)} mailings but the program has run "
                        f"{_stated} — leftover template rows: {', '.join(dated[_stated:])}"))

    # 6) cross-check headline figures against base_extract.json
    if extract:
        allnum = " ".join(b for _, bl in texts for b in bl)
        def want(label, s):
            if s not in allnum:
                findings.append(("FAIL", 0, f"base_extract {label} = {s} not found verbatim in deck"))
        if "ltd_revenue" in extract: want("ltd_revenue", f"${extract['ltd_revenue']/1e6:.2f}M")
        if "ltd_profit" in extract:  want("ltd_profit",  f"${extract['ltd_profit']/1e6:.2f}M")
        if "months" in extract:      want("months", f"{extract['months']} months")
        if "mailings" in extract:    want("mailings", str(extract['mailings']))
        # eligible ARS accounts are sourced from the ODD (n_eligible), not the workbook
        # DCO figure — so dco_eligible is intentionally not required verbatim in the deck.

    # 7) conflicting values for the same labelled metric
    for label in ["take rate", "opt-in", "profitability", "response"]:
        vals = set()
        for _, bl in texts:
            for b in bl:
                for m in re.finditer(r"([\d.]+)\s*%?\s*" + label, b.lower()):
                    vals.add(m.group(1))
        if len(vals) > 2:
            findings.append(("REVIEW", 0, f"metric '{label}' shows {len(vals)} different values {sorted(vals)} — confirm each is a distinct measure"))

    # report
    order = {"FAIL": 0, "REVIEW": 1}
    findings.sort(key=lambda f: (order[f[0]], f[1]))
    fails = [f for f in findings if f[0] == "FAIL"]
    print(f"validate_deck: {sys.argv[1]}")
    print(f"  {len(fails)} FAIL, {len(findings)-len(fails)} REVIEW\n")
    for lvl, idx, msg in findings:
        where = f"slide {idx}" if idx else "deck-wide"
        print(f"  [{lvl:6}] {where:9} {msg}")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
