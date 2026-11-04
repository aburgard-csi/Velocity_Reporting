"""
Extraction and inference over the parsed Matrix Validation export.

This is the data half of the old Matrix Deck Generator, carried over intact —
it has been exercised against every client export to date and copes with the
per-client format differences that matter:

  * booleans written as 1/0, True/False or Y/N
  * tier tables with uniform score bands or variable-width bands
  * whatever trending model the client uses: repositories are discovered from
    the file and their factor grids inferred from the rule text, so a new trend
    type needs no code change
  * exports that truncate long rule text — affected axis labels are
    reconstructed positionally from the rows that survive intact, and the
    slide is footnoted (factor values sit in the last column and are always
    exact)

Nothing here knows about slide geometry; rendering lives in matrix_slides.py.
"""
from __future__ import annotations

import re
from collections import OrderedDict, defaultdict

from . import theme as T

# ── value formatting / truthiness ───────────────────────────────────────────


def is_true(v):
    """Format-agnostic truthiness: 1/0, True/False, Y/N, Yes/No, T/F."""
    return str(v).strip().lower() in ("1", "true", "t", "y", "yes")


def yesno(v):
    return "Yes" if is_true(v) else "No"


def factor_color(v):
    """Green for a positive factor, red for negative, grey for zero."""
    try:
        f = float(str(v).replace(",", "").replace("%", "").replace("$", ""))
    except (ValueError, TypeError):
        return T.DARK
    if f < 0:
        return T.RED
    if f == 0:
        return T.GRAY
    return T.GREEN


def fmt_factor(v):
    s = str(v).strip()
    is_pct = s.endswith("%")
    core = s[:-1] if is_pct else s
    try:
        f = float(core.replace(",", ""))
    except (ValueError, TypeError):
        return s
    if f == 0:
        return "0%" if is_pct else "0"          # avoid "-0" / "-0%"
    return f"{f:,.0f}%" if is_pct else f"{f:,.0f}"


def fmt_num(x):
    """10 -> '10', 1.50 -> '1.5', 2.25 -> '2.25'."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    return f"{f:.4f}".rstrip("0").rstrip(".")


def fmt_money(v):
    n = _num(v)
    return f"${n:,.0f}" if n is not None else (str(v).strip() or "—")


def clean_range(rng):
    s = re.sub(r"^\[\d+\]\s*-\s*", "", str(rng))     # drop leading "[00] - "
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)            # drop trailing "(0.00, 0.00)"
    return s.strip()


def ridx(rng):
    m = re.match(r"\[(\d+)\]", str(rng))
    return int(m.group(1)) if m else 999


def _num(x):
    try:
        return float(str(x).replace(",", "").replace("$", "").replace("%", ""))
    except (ValueError, TypeError):
        return None


def find_col(row, *needles, exclude_suffixes=("_id", "id", "xml")):
    """First key in `row` matching a needle, exact match preferred.

    Two passes, because substring-only matching picks the wrong column in these
    exports with real consequences: a search for 'rule' hits `RULE_ID` (a GUID)
    before `CALC`, and a search for 'score' hits `DEPOSIT_SCORE_ID` (always the
    matrix id) before any real score column. Exact names win first, and columns
    ending in an id/xml suffix are skipped in the fuzzy pass unless the needle
    explicitly asks for one.
    """
    keys = list(row)
    lower = {str(k).strip().lower(): k for k in keys}
    for needle in needles:                       # pass 1: exact column name
        n = needle.strip().lower()
        if n in lower:
            return lower[n]
    for needle in needles:                       # pass 2: all words appear
        parts = [p.lower() for p in needle.split()]
        wants_suffix = any(needle.strip().lower().endswith(s) for s in exclude_suffixes)
        for k in keys:
            kl = str(k).strip().lower()
            if not wants_suffix and any(kl.endswith(s) for s in exclude_suffixes):
                continue
            if all(p in kl for p in parts):
                return k
    return None


def _live(v):
    s = str(v).strip()
    return s and s.upper() not in ("NULL", "NONE", "—", "N/A")


# ── section access ──────────────────────────────────────────────────────────
def section(S, *names):
    """Rows of the first matching section (case-insensitive), else []."""
    for name in names:
        for k in S:
            if k.strip().lower() == name.strip().lower():
                return S[k]["rows"]
    return []


def detect_types(S):
    """Ordered account types, their matrix codes, and their settings rows."""
    rows = section(S, "ACCOUNT TYPES AND MIN/MAX LIMITS")
    types, codes, settings = [], {}, {}
    for r in rows:
        t = (r.get("Account Type") or "").strip()
        if not t:
            continue
        types.append(t)
        codes[t] = (r.get("Matrix Code") or "").strip()
        settings[t] = r
    return types, codes, settings


def overrides_by_type(S, types):
    d = {t: [] for t in types}
    for r in section(S, "OVERRIDES"):
        t = r.get("Account Type", "")
        if t in d:
            d[t].append(r)
    for t in d:
        d[t].sort(key=lambda r: int(r["Order Index"])
                  if str(r.get("Order Index", "")).strip().isdigit() else 99)
    return d


def categories(S):
    """Distinct factor categories in first-seen order."""
    seen = OrderedDict()
    for r in section(S, "RANGES AND FACTORS"):
        c = (r.get("Category") or "").strip()
        if c:
            seen[c] = True
    return list(seen)


def range_grid(S, category, types):
    """[{'label': ..., <type>: factor, ...}] sorted by range index."""
    g = {}
    for r in section(S, "RANGES AND FACTORS"):
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


# ── trending: structure inferred from the Calculation text ──────────────────
# Trend repositories differ by client (Deposit Regularity, Windfall Deposit,
# OD Repayment, …). Rather than hard-code each one, every repository is
# discovered and its factor grid inferred from the SQL-ish Calculation: each row
# is a conjunction of range conditions on one or two variables, and the
# variables that vary across rows become the grid dimensions.

_BETWEEN_RE = re.compile(
    r"(\[[^\]]+\](?:\s*/\s*\[[^\]]+\])?)\s+BETWEEN\s+([-\d.]+)\s+AND\s+([-\d.]+)", re.I)
_CMP_RE = re.compile(
    r"(\(?\s*\[[^\]]+\]\s*(?:/\s*\[[^\]]+\]\s*)?\)?)\s*(<=|>=|<|>)\s*([-\d.]+)")


def _key_norm(lhs):
    return re.sub(r"[\s()]", "", lhs)


def _key_caption(lhs):
    s = lhs.replace("[", "").replace("]", "").replace("(", "").replace(")", "")
    s = re.sub(r"\s*/\s*", " / ", s)
    return re.sub(r"\s+", " ", s).strip()


def _range_label(tokens):
    """tokens: [('cmp',op,num) | ('rng',a,b)] -> one range label."""
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
    """One Calculation -> {key: [caption, [tokens]]}."""
    out = {}
    for m in _BETWEEN_RE.finditer(calc):
        lhs, a, b = m.group(1), m.group(2), m.group(3)
        out.setdefault(_key_norm(lhs), [_key_caption(lhs), []])[1].append(("rng", a, b))
    work = _BETWEEN_RE.sub(" ", calc)
    for m in _CMP_RE.finditer(work):
        lhs, op, num = m.group(1), m.group(2), m.group(3)
        out.setdefault(_key_norm(lhs), [_key_caption(lhs), []])[1].append(("cmp", op, num))
    return out


def trend_repositories(S):
    """Repository names in first-seen order."""
    seen = OrderedDict()
    for r in section(S, "TRENDS"):
        rn = (r.get("Repository Name") or "").strip()
        if rn:
            seen[rn] = True
    return list(seen)


def _repo_rows(S, repo, account_type=None):
    rows = [r for r in section(S, "TRENDS") if r.get("Repository Name") == repo]
    if account_type is None:
        account_type = rows[0].get("Account Type") if rows else None
    return [r for r in rows if r.get("Account Type") == account_type]


def _richer(new, old):
    """Prefer the more complete label: a full range beats a partial/None."""
    if old is None:
        return True
    if ("–" in new) != ("–" in old):
        return "–" in new
    return len(new) > len(old)


def _repo_shared(S, repo):
    seqs = set()
    for t in {r.get("Account Type") for r in section(S, "TRENDS")
              if r.get("Repository Name") == repo}:
        seqs.add(tuple(rr.get("Factor") for rr in _repo_rows(S, repo, t)))
    return len(seqs) <= 1


def trend_structure(S, repo):
    """Infer a repository's factor grid.

    Returns {'dims': [(caption, [labels]), ...], 'factors': {label-tuple: factor},
             'shared': bool, 'truncated': bool}, using the first account type's
    rows — grids are shared across account types in every export seen, and
    'shared' records whether that held here.
    """
    rows = _repo_rows(S, repo)
    parsed = [_parse_calc(r.get("Calculation", "") or "") for r in rows]
    facs = [r.get("Factor", "") for r in rows]

    key_order, caps = [], {}
    for p in parsed:
        for k, (cap, _) in p.items():
            if k not in key_order:
                key_order.append(k)
                caps[k] = cap

    def lab(p, k):
        return _range_label(p[k][1]) if k in p else None

    # Primary dimension: the first key present in EVERY row whose label varies.
    # It sits at the start of the Calculation text, so it survives the export's
    # column-width truncation intact.
    dimA = None
    for k in key_order:
        present = sum(1 for p in parsed if k in p)
        if present == len(rows) and len({lab(p, k) for p in parsed}) > 1:
            dimA = k
            break
    if dimA is None and key_order:
        dimA = max(key_order, key=lambda k: sum(1 for p in parsed if k in p))

    shared = _repo_shared(S, repo)
    if dimA is None:
        return {"dims": [], "factors": {}, "shared": shared, "truncated": False}

    a_labels_row = [lab(p, dimA) for p in parsed]
    others = [k for k in key_order if k != dimA]

    groups = OrderedDict()
    for i, al in enumerate(a_labels_row):
        groups.setdefault(al, []).append(i)
    sizes = {len(v) for v in groups.values()}

    # 2-D grid: uniform group size > 1 and a secondary variable exists
    if others and len(sizes) == 1 and next(iter(sizes)) > 1:
        G = next(iter(sizes))
        bkey = others[0]
        col_labels = [None] * G
        truncated = False
        for idxs in groups.values():
            for j, ri in enumerate(idxs):
                cand = lab(parsed[ri], bkey)
                if cand and _richer(cand, col_labels[j]):
                    col_labels[j] = cand
        for j in range(G):
            if col_labels[j] is None:
                col_labels[j] = f"Band {j + 1}"
                truncated = True
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


def trend_trigger_rows(S, types):
    """One row per (account type, repository) with its non-null trigger minimums."""
    out = []
    for t in types:
        for repo in trend_repositories(S):
            rows = _repo_rows(S, repo, t)
            if not rows:
                continue
            s = rows[0]

            def g(k, _s=s):
                v = str(_s.get(k, "")).strip()
                return v if v and v.upper() != "NULL" else "—"

            out.append({"type": t, "repo": repo,
                        "dep_cnt": g("Min. Deposit Count"),
                        "dep_amt": g("Min. Deposit Amount"),
                        "od_cnt": g("Min. Overdraft Count")})
    return out


# ── tiers ───────────────────────────────────────────────────────────────────
def tier_summary(S):
    """Per-account-type tier stats for whichever types have their own tier table.

    Handles uniform score bands and variable-width bands; `band_w` is set only
    when every band has the same width.
    """
    byt = defaultdict(list)
    for r in section(S, "TIERS AND ROUNDING"):
        byt[r.get("Account Type", "")].append(r)
    out = {}
    for at, rows in byt.items():
        if not at:
            continue
        lims = [x for x in (_num(r.get("Limit Value")) for r in rows) if x is not None]
        mins = [_num(r.get("Min Value")) for r in rows]
        maxs = [_num(r.get("Max Value")) for r in rows]
        # The top/catch-all band uses a huge Max (e.g. 999,999,999.99); its
        # Limit Value is the real maximum granted limit.
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
            "score_max": max_limit,
            "max_limit": max_limit,
            "code": rows[0].get("Matrix Code", ""),
            "rows": rows,
        }
    return out


# ── optional-section predicates ─────────────────────────────────────────────
LN_FIELDS = [
    ("Limit Notification", "Enabled"),
    ("Limit Notification Cycle On", "Cycle on"),
    ("Limit Notification Zero Setting", "Zero setting"),
    ("Limit Notification Recovery Setting", "Recovery setting"),
    ("Limit Notification Reinstatement", "Reinstatement"),
]


def has_limit_notification(settings):
    return any(_live(row.get(k)) for row in settings.values() for k, _ in LN_FIELDS)


def has_cashplease(settings):
    keys = ("CashPlease Max %", "CashPlease Max $", "CashPlease Elig",
            "MRPC Max %", "MRPC Max $", "MRPC Elig")
    for row in settings.values():
        for k in keys:
            col = find_col(row, k)
            if col and _live(row.get(col)):
                return True
    return False


def has_comm_strategies(S):
    return bool(section(S, "COMMUNICATION STRATEGIES"))


def has_deposit_score(S):
    return bool(section(S, "DEPOSIT SCORE MATRIX"))


def has_ds_rules(S):
    return bool(section(S, "DEPOSIT SCORE MATRIX RULES"))


def active_comm_strategies(S):
    rows = section(S, "COMMUNICATION STRATEGIES")
    return [r for r in rows if is_true(r.get("ACTIVE"))]


def deposit_score_label(S):
    """A short description of the deposit-score regression tree."""
    matrices = section(S, "DEPOSIT SCORE MATRIX")
    ruleset = section(S, "DEPOSIT SCORE MATRIX RULES")
    if not matrices and not ruleset:
        return ""
    if not ruleset:
        return "Deposit Score 1–5 (matrix rules not included in this export)"
    active_rules = [r for r in ruleset if is_true(r.get("ENABLE"))]
    active_matrices = [r for r in matrices if is_true(r.get("ACTIVE"))]
    names = ", ".join((r.get("NAME") or "").strip() for r in active_matrices) or "—"
    inactive = [(r.get("NAME") or "").strip() for r in matrices if not is_true(r.get("ACTIVE"))]
    label = f"{len(active_rules)} active rules ({names}"
    if inactive:
        label += f"; {', '.join(inactive)} inactive"
    return label + ")"


# ── pagination helper shared by the long component tables ───────────────────
ROWS_PER_SLIDE = 22          # the 20 x 11.25 canvas holds far more than the old 15


def paginate(items, per, show_all):
    """[(page_items, page_no, total_pages)] — one page when not show_all."""
    if not show_all:
        return [(items[:per], 1, 1)]
    pages = [items[i:i + per] for i in range(0, len(items), per)] or [[]]
    return [(p, i + 1, len(pages)) for i, p in enumerate(pages)]
