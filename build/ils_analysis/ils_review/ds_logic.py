"""
Deposit Score rule-logic slides — the actual CALC logic each matrix uses.

Renders every rule's conditions (Age of Account ≥ 90, Relationship Balance
≥ 9000, …) and the 0–5 score it assigns, one group of slides per matrix that
has rules, so Business/Commercial rules render the same way when they exist.

Rules whose logic was truncated at 256 characters in the export are flagged and
footnoted; they render in full once query 1822 is re-exported with a wider
column, with no code change needed.

Many clients' exports omit the Deposit Score sections entirely (their matrix is
limit-tiered rather than score-driven). `has_rules` reports that, and the
section is skipped with a note rather than failing.
"""
from __future__ import annotations

import re

from pptx.enum.text import PP_ALIGN

from . import matrix_data as MD
from . import theme as T

X = 0.42
W = T.SLIDE_W - 2 * X

SCORE_FILL = {5: T.TEAL, 4: T.STEEL_SOFT, 3: T.GOLD, 2: T.ORANGE, 1: T.RED, 0: T.GRAY}

TRUNCATION_LEN = 256


def has_rules(S):
    return MD.has_ds_rules(S)


def has_matrices(S):
    return MD.has_deposit_score(S)


# ── rule parsing ────────────────────────────────────────────────────────────
_COND_SPLIT = re.compile(r"\s+AND\s+", re.I)
_CLEAN = re.compile(r"[\[\]]")

# The export writes rule logic as prose — 'If Age of Account is greater than or
# equal to 90 and Relationship Balance is less than 9000 then set ...' — so the
# comparison phrases are folded to symbols to fit the slide. Longest phrases
# first, or 'is greater than' would swallow 'is greater than or equal to'.
_OPS = [
    ("is greater than or equal to", "≥"), ("is less than or equal to", "≤"),
    ("is not equal to", "≠"), ("is greater than", ">"), ("is less than", "<"),
    ("is equal to", "="), ("does not equal", "≠"),
    ("is not one of", "∉"), ("is one of", "∈"),
    ("is not", "≠"), ("is", "="),
]
_THEN = re.compile(r"\bthen\b", re.I)


# The assigned score lives at the tail of the rule text — 'then set Deposit
# Score to 3', 'then score = 3'. There is no score column in the export: the
# only numeric columns are ids.
_SCORE_TAIL = re.compile(
    r"then\b[^.]*?(?:score|value|result)\D{0,24}?(-?\d+(?:\.\d+)?)", re.I)


def _score_of(row):
    """The 0–5 score a rule assigns, or None when the export truncated it away."""
    col = MD.find_col(row, "score", "deposit score", "value", "result")
    if col and not str(col).strip().lower().endswith("_id"):
        v = MD._num(row.get(col))
        if v is not None and 0 <= v <= 5:
            return int(v)
    m = _SCORE_TAIL.search(_calc_of(row))
    if m:
        try:
            v = float(m.group(1))
            if 0 <= v <= 5:
                return int(v)
        except ValueError:
            pass
    return None


def _calc_of(row):
    col = MD.find_col(row, "calc", "calculation", "logic", "criteria")
    return str(row.get(col, "")).strip() if col else ""


def _name_of(row):
    col = MD.find_col(row, "name", "rule name", "description")
    return str(row.get(col, "")).strip() if col else ""


def _matrix_of(row, matrix_names=None):
    """The matrix a rule belongs to, resolved through DEPOSIT_SCORE_ID."""
    col = MD.find_col(row, "matrix name", "matrix")
    if col:
        v = str(row.get(col, "")).strip()
        if v and v.upper() != "NULL":
            return v
    if matrix_names:
        idcol = MD.find_col(row, "deposit_score_id", exclude_suffixes=())
        if idcol:
            key = str(row.get(idcol, "")).strip()
            if key in matrix_names:
                return matrix_names[key]
    return ""


def _matrix_names(S):
    """{matrix id: matrix name} from the DEPOSIT SCORE MATRIX section."""
    out = {}
    for m in MD.section(S, "DEPOSIT SCORE MATRIX"):
        idcol = MD.find_col(m, "id", exclude_suffixes=())
        namecol = MD.find_col(m, "name")
        if idcol and namecol:
            out[str(m.get(idcol, "")).strip()] = str(m.get(namecol, "")).strip()
    return out


def _condition_text(calc):
    """The 'If …' part of a rule, with the 'then …' consequent removed."""
    if not calc:
        return ""
    body = _THEN.split(calc, maxsplit=1)[0]
    return re.sub(r"^\s*if\s+", "", body, flags=re.I).strip()


def _conditions(calc):
    """Split a rule into readable conditions, one per conjunct."""
    text = _condition_text(calc)
    if not text:
        return []
    out = []
    for part in _COND_SPLIT.split(text):
        p = _CLEAN.sub("", part).strip()
        p = re.sub(r"\bACCOUNTS\.", "", p)
        p = re.sub(r"\s+", " ", p).strip()
        if not p:
            continue
        for phrase, sym in _OPS:
            new = re.sub(rf"\s+{re.escape(phrase)}\s+", f" {sym} ", p, flags=re.I)
            if new != p:
                p = new
                break
        p = p.replace(">=", "≥").replace("<=", "≤").replace("<>", "≠")
        out.append(p.strip())
    return out


def is_truncated(calc):
    """True when the export cut the rule text off before its 'then' clause."""
    if not calc:
        return False
    return len(calc) >= TRUNCATION_LEN or not _THEN.search(calc)


def rule_variables(S):
    """Raw variable names referenced by the rules — feeds the alignment charts."""
    names = []
    for r in MD.section(S, "DEPOSIT SCORE MATRIX RULES"):
        for cond in _conditions(_calc_of(r)):
            m = re.match(r"^([A-Za-z][A-Za-z0-9 _/()]*?)\s*(?:≥|≤|≠|∈|∉|=|<|>)", cond)
            if m:
                nm = m.group(1).strip()
                if nm and nm not in names:
                    names.append(nm)
    return names


def _rules_by_matrix(S):
    """{matrix name: [rules]} keeping export order, enabled rules only."""
    names = _matrix_names(S)
    out = {}
    for r in MD.section(S, "DEPOSIT SCORE MATRIX RULES"):
        if not MD.is_true(r.get("ENABLE", "1")):
            continue
        out.setdefault(_matrix_of(r, names) or "Deposit Score Matrix", []).append(r)
    return out


# ── slides ──────────────────────────────────────────────────────────────────
def _overview(dk, S, *, section):
    matrices = MD.section(S, "DEPOSIT SCORE MATRIX")
    ruleset = MD.section(S, "DEPOSIT SCORE MATRIX RULES")
    slide = dk.content("Deposit Score — logic overview",
                       "Each configured Deposit Score matrix, whether it is active, and how "
                       "many of its rules are enabled",
                       section=section)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, 12.0, "  DEPOSIT SCORE MATRICES")
    by_matrix = {}
    for r in ruleset:
        key = _matrix_of(r) or "—"
        d = by_matrix.setdefault(key, [0, 0])
        d[1] += 1
        if MD.is_true(r.get("ENABLE", "1")):
            d[0] += 1
    rows = []
    for m in matrices:
        name = (m.get("NAME") or "").strip() or "—"
        on, total = by_matrix.get(name, [0, 0])
        rows.append([name, MD.yesno(m.get("ACTIVE")), f"{on} of {total}"])
    for name, (on, total) in by_matrix.items():
        if not any(r[0] == name for r in rows):
            rows.append([name, "—", f"{on} of {total}"])
    if not rows:
        rows = [["—", "—", "0 of 0"]]
    tbl = dk.table(slide, X, y + 0.50, 12.0, [6.0, 3.0, 3.0], len(rows) + 1, row_h=0.46)
    T.fill_table(tbl, ["Matrix", "Active?", "Rules enabled"], rows,
                 align=[PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER])

    rx = X + 12.4
    rw = T.SLIDE_W - rx - X
    T.band_label(slide, rx, y, rw, "  HOW THE SCORE IS ASSIGNED")
    T.bullets(slide, rx + 0.05, y + 0.62, rw - 0.1, T.CONTENT_BOTTOM - y - 0.70, [
        "Rules are evaluated in order; the first rule whose conditions all hold "
        "assigns the account's 0–5 Deposit Score.",
        "A higher score means a stronger, lower-risk deposit relationship — the "
        "charge-off experience on the risk-categorisation slide is what validates that.",
        "An account matching no rule is left unscored rather than defaulted to a value.",
    ], 12.5)
    return slide


def _rule_slides(dk, S, matrix_name, rules, *, section, show_all=False):
    """Rule tables for one matrix, paginated."""
    out = []
    truncated_any = False
    per = 14
    pages = [rules[i:i + per] for i in range(0, len(rules), per)] or [[]]
    if not show_all:
        pages = pages[:1]
    for pi, page in enumerate(pages, 1):
        sub = f"{len(rules)} enabled rule(s)"
        if len(pages) > 1:
            sub += f"  ·  page {pi} of {len(pages)}"
        slide = dk.content(f"Deposit Score logic — {matrix_name}", sub, section=section)
        y = T.CONTENT_TOP
        T.band_label(slide, X, y, W, "  RULE CONDITIONS → SCORE")
        rows, scores = [], []
        for r in page:
            calc = _calc_of(r)
            conds = _conditions(calc)
            score = _score_of(r)
            cut = is_truncated(calc)
            if cut:
                truncated_any = True
            # A truncated rule loses its 'then set score to N' tail, so the score
            # is genuinely unknown — show ⚠ rather than an invented value.
            score_txt = ("⚠" if score is None and cut
                         else ("—" if score is None else str(score)))
            rows.append([_name_of(r) or "—",
                         "   ·   ".join(conds) if conds else (calc or "—"),
                         score_txt])
            scores.append(score)
        rh = min(0.55, max(0.32, (T.CONTENT_BOTTOM - y - 1.0) / max(1, len(rows))))
        tbl = dk.table(slide, X, y + 0.50, W, [4.0, 13.2, 1.9], len(rows) + 1, row_h=rh)
        T.fill_table(tbl, ["Rule", "Conditions (all must hold)", "Score"], rows,
                     size=min(15, rh * 26),
                     align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER])
        for i, sc in enumerate(scores, 1):
            if sc is None:
                continue
            c = tbl.cell(i, 2)
            c.fill.solid()
            c.fill.fore_color.rgb = SCORE_FILL.get(sc, T.GRAY)
            for p in c.text_frame.paragraphs:
                for run in p.runs:
                    run.font.color.rgb = T.WHITE
                    run.font.bold = True
        # Footnotes go in one block: the second line used to sit at +0.36, which
        # is inside the layout's bottom logo band.
        foot = []
        if truncated_any:
            foot.append("⚠ = the export truncated this rule's logic at 256 characters, so "
                        "the score it assigns is not recoverable. Conditions shown are "
                        "exact as far as they go; re-export query 1822 with a wider CALC "
                        "column to complete them.")
        if not show_all and len(rules) > len(page):
            foot.append(f"Showing {len(page)} of {len(rules)} rules — enable 'show all "
                        f"rows' for the full set.")
        if foot:
            # Footnotes start right of the layout's bottom-left logo, on the same
            # x as the footer strip, so a wrapped second line stays clear of it.
            T.textbox(slide, T.FOOTER_X, T.CONTENT_BOTTOM + 0.08,
                      T.SLIDE_W - T.FOOTER_X - X, 0.60,
                      "  ".join(foot), 10.5, color=T.MUTED, italic=True)
        out.append(slide)
    return out


def add_ds_logic_slides(dk, S, *, section, logic_image=None, show_all=False):
    """Deposit Score logic section. Returns (slides_added, notes)."""
    notes = []
    if not has_matrices(S) and not has_rules(S):
        return 0, ["The matrix export contains no Deposit Score Matrix sections, so the "
                   "Deposit Score rule-logic slides were skipped. This is expected for "
                   "clients whose matrix is limit-tiered rather than score-driven."]
    n = 0
    _overview(dk, S, section=section)
    n += 1

    if logic_image:
        slide = dk.content("Deposit Score logic — decision tree",
                           "The complete score logic as a diagram; the per-rule table "
                           "follows as a backup view",
                           section=section)
        T.image(slide, logic_image, X, T.CONTENT_TOP + 0.05, W,
                T.CONTENT_BOTTOM - T.CONTENT_TOP - 0.05)
        n += 1

    by_matrix = _rules_by_matrix(S)
    if not by_matrix:
        notes.append("The export lists Deposit Score matrices but no enabled rules, so only "
                     "the logic overview is shown.")
    for matrix_name, rules in by_matrix.items():
        n += len(_rule_slides(dk, S, matrix_name, rules, section=section,
                              show_all=show_all))
    return n, notes
