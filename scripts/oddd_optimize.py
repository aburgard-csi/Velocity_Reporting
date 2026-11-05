#!/usr/bin/env python3
"""
oddd_optimize.py  —  Optimize a raw ODDD (Overdraft Data Dump) CSV into a
compact, deck-ready data pack for the Retail Performance Engine PowerPoint.

Raw ODDD dumps are one row per account with ~225 monthly columns and can be
hundreds of MB. They must NEVER be loaded into an LLM context. This script
streams the file in chunks with pandas and emits two small artifacts:

  <out>/oddd_pack.md      human/LLM-readable data pack (mirrors VIP-Data style)
  <out>/oddd_metrics.json machine-readable series for chart building

Usage:
  python3 oddd_optimize.py --input "<path to ODDD .zip or .csv>" [--out "<dir>"]
  python3 oddd_optimize.py --input "../ODDD/1075_ODDD.zip"
  python3 oddd_optimize.py --input "..." --client 1537 --name "FNBT Chickasha"

Input may be the client's `<id>_ODDD.zip` (read in-stream, nothing extracted to disk)
or a bare CSV. Zip is preferred — it avoids writing the multi-hundred-MB CSV to disk.

Robustness notes (learned from the real files):
  * 4 preamble rows; the real header is the row whose first data cell == 'Acct ID'.
  * Column 1 is a running row index ('5','6',...) — ignored.
  * Trailing all-empty padding columns exist — dropped.
  * Cells contain NUL bytes (\\x00), the misspelling 'No Response Recevied',
    '$'/','/parenthesis-negative money formatting — all normalized.
  * Month columns look like 'May26 Elig', 'Nov24 OD Limit', 'Mar25 Resp',
    'Nov24 Sig $', 'Nov24 MTD', etc. Parsed generically by regex.
    `<mon> MTD/YTD/PYTD` are NSF/OD ITEM COUNTS, not dollars — see odd_rows.nsf().
"""
import argparse, csv, json, re, sys, os, io, zipfile
from collections import defaultdict
import pandas as pd
import numpy as np
try:                       # optional accelerator: ~13x on the money-cleaning pass
    import pyarrow as pa
    import pyarrow.compute as pc
    _HAVE_ARROW = True
except Exception:
    _HAVE_ARROW = False

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
MIDX = {m: i for i, m in enumerate(MONTHS)}
MONTH_RE = re.compile(r"^([A-Z][a-z]{2})(\d{2})\s+(.*)$")
CHUNK = 100_000

# Cells in money/count columns that are not numbers, per column. A row with one extra
# field (an unquoted comma in a text cell) is kept by pandas with its cells shifted, so
# text such as 'Customer Opt In' lands in a numeric column: 3 of 28,930 rows in 1147
# Sutton's 2026.09 extract. Such a cell counts as missing and is reported in the pack's
# flags, never silently summed and never fatal (2026-09-14).
NON_NUMERIC = defaultdict(int)
_NUMBER_RX = r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$"


def month_key(mon, yy):
    """Sortable key: 20YY*12 + monthindex."""
    return (2000 + int(yy)) * 12 + MIDX[mon]


def clean_money(series):
    """Vectorized: '$1,234.50' / '(50)' / '\\x00' / '' -> float, NaN->0."""
    # pandas 3.0 str dtype keeps NA distinct from 'nan'; coerce NA->'' first.
    s = series.fillna("").astype(str)
    s = s.str.replace("\x00", "", regex=False).str.strip()
    neg = s.str.startswith("(") & s.str.endswith(")")
    s = s.str.replace(r"[\$,()]", "", regex=True)
    out = pd.to_numeric(s, errors="coerce")
    out = out.where(~neg, -out)
    return out.fillna(0.0)


def money_block(df, names):
    """Sum each money/count column, plus a >0 count per column, in one pass.

    Money cells look like '$1,234.50' / '(50)' / '\\x00' / ''. When pyarrow is present
    this runs the character-strip + cast in C++ (~13x faster than the per-column pandas
    path); otherwise it falls back to clean_money. Returns (sums, gt0counts) keyed by name.
    """
    if _HAVE_ARROW:
        tbl = pa.Table.from_pandas(df[names], preserve_index=False)
        csum, cgt0 = {}, {}
        for name in names:
            a = tbl.column(name).combine_chunks().cast(pa.string())
            a = pc.replace_substring(a, "\x00", "")
            a = pc.utf8_trim_whitespace(a)
            neg = pc.and_(pc.starts_with(a, pattern="("), pc.ends_with(a, pattern=")"))
            for chx in ("$", ",", "(", ")"):
                a = pc.replace_substring(a, chx, "")
            a = pc.if_else(pc.equal(a, ""), pa.scalar(None, pa.string()), a)
            # The strict cast died on shifted text; the pandas path below always coerced
            # it to missing. Same rule on both paths now, and the cells are counted.
            isnum = pc.match_substring_regex(a, pattern=_NUMBER_RX)
            nbad = pc.sum(pc.and_kleene(pc.is_valid(a), pc.invert(isnum))).as_py() or 0
            if nbad:
                NON_NUMERIC[name] += int(nbad)
            a = pc.if_else(isnum, a, pa.scalar(None, pa.string()))
            f = pc.cast(a, pa.float64(), safe=False)
            f = pc.if_else(neg, pc.multiply(f, pa.scalar(-1.0)), f)
            f = pc.fill_null(f, 0.0)
            csum[name] = pc.sum(f).as_py() or 0.0
            cgt0[name] = pc.sum(pc.greater(f, 0)).as_py() or 0
        return csum, cgt0
    csum, cgt0 = {}, {}
    for name in names:
        s = df[name].fillna("").astype(str).str.replace("\x00", "", regex=False).str.strip()
        s = s.str.replace(r"[\$,()]", "", regex=True)
        nbad = int(((s != "") & pd.to_numeric(s, errors="coerce").isna()).sum())
        if nbad:
            NON_NUMERIC[name] += nbad
        v = clean_money(df[name])
        csum[name] = float(v.sum()); cgt0[name] = int((v > 0).sum())
    return csum, cgt0


def norm_text(series):
    # fillna('') so NA-valued cells count as blank (pandas 3.0 str dtype keeps NA).
    return series.fillna("").astype(str).str.replace("\x00", "", regex=False).str.strip()


# ---- Standardized category vocabularies (same for every client build) ----
# Reg E opt-in status. Cores word this differently (Marine: "Opt-In Accepted /
# Opt-In Declined / No Response Recevied"; Austin: "Reg E Opt In / Opt Out /
# Default"). Every core is normalized to these three canonical values. A non-blank
# value that matches no rule is passed through unchanged so the caller flags it and
# ASKS Aaron before guessing. Blank = not applicable (closed/business) -> excluded.
# The wording rules themselves live in build/ars_pipeline/odd_rows.rege_label, the one
# definition metrics_gen also reads (2026-09-16: the two had drifted apart).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "build", "ars_pipeline"))
from odd_rows import rege_label, REGE_IN, REGE_OUT, REGE_DEFAULT, client_status_codes  # noqa: E402


def classify_rege(series):
    raw = norm_text(series)
    # Unmapped wording passes through unchanged so the pack's flags surface it. One dict lookup per cell:
    # the lambda this replaced ran 12 million times on a 1M-row extract (10 s, profiled 2026-10-26).
    mapping = {v: (v if (lab := rege_label(v)) is None else lab) for v in raw.unique()}
    return raw.map(mapping)

# Account status. Normalized to these seven buckets for every client. Unknown
# non-blank values fall to "Other" and are surfaced (with their raw text) so they
# can be confirmed/ASKed rather than silently bucketed.
STATUS_BUCKETS = ["Open", "Closed", "Dormant", "Inactive", "Frozen", "Charged Off", "Other"]

# `Stat Desc` is not populated by every core. 1549 Wellworth fills `Stat Code`
# (O / C / X) and leaves `Stat Desc` BLANK on every non-open account — 18,274 of
# 50,218 rows, which classify_status returned as "Other" because it only ever read
# the description. Codes confirmed by Aaron 2026-08-28: O = Open, C = Closed,
# X = Charged Off. The description still wins whenever it carries text.
STAT_CODE_MAP = {"O": "Open", "A": "Open", "C": "Closed", "X": "Charged Off"}


def classify_status(raw, code=None, client_id=None):
    """Wording first, then STAT_CODE_MAP; what neither knows is read from the client's
    code sheet (odd_rows.client_status_codes), where a blank code is a real code when
    the sheet lists it (1585, 2026-11-02)."""
    t = raw.str.lower().str.strip()
    out = pd.Series("Other", index=raw.index, dtype="object")
    if code is not None:
        c = code.fillna("").astype(str).str.strip().str.upper()
        blank = t.eq("")
        for k, label in STAT_CODE_MAP.items():
            out = out.mask(blank & c.eq(k), label)
        # a blank description with an unmapped code stays "Other" and is flagged
        # by the caller's unmapped-value pass — never guessed at.
    def setb(pattern, label):
        nonlocal out
        out = out.mask((out == "Other") & t.ne("") & t.str.contains(pattern, regex=True), label)
    setb(r"charge[sd]?[\s-]?off|chargeoff", "Charged Off")   # catch 'Charged Off' (the trailing d), not just 'charge off'
    # Core-specific lifecycle wording (Aaron 2026-07-25) — must run BEFORE the generic
    # patterns: "closeout"/"activation" do not match "closed"/"active".
    setb(r"purge at year\s?end|pending close\s?out", "Closed")
    setb(r"new this cycle|pending activation", "Open")
    setb(r"closed|closd", "Closed")
    setb(r"dormant", "Dormant")
    setb(r"inactive", "Inactive")        # before "active" so it wins
    setb(r"frozen|freeze", "Frozen")
    setb(r"\bopen\b|active", "Open")
    sheet = client_status_codes(client_id) if code is not None else None
    if sheet:
        c = code.fillna("").astype(str).str.strip().str.upper()
        other = out.eq("Other") & ~t.str.contains(EXPLICIT_OTHER, regex=True)
        out = out.mask(other & c.isin(sheet[0]), "Open")
        out = out.mask(other & c.isin(sheet[1]), "Closed")
    return out


# Raw statuses that map to "Other" DELIBERATELY (Aaron-confirmed). Values matching this
# are real 'Other', not unmapped — they must NOT surface in the pack's flags block.
EXPLICIT_OTHER = r"manually controlled"


def open_source(src):
    """Normalize a .csv or .zip input into (stream_factory, display_basename).

    stream_factory() returns a fresh latin-1 text stream over the ODD CSV. For a
    .zip we stream the single CSV member directly (pandas decompresses on the fly —
    no full CSV is ever written to disk), which is faster and lighter than unzipping.
    """
    if src.lower().endswith(".zip"):
        zf = zipfile.ZipFile(src)
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise SystemExit(f"ERROR: no .csv inside {src}")
        # Prefer the ODD dump if several CSVs are bundled.
        member = next((m for m in members if "-ODD" in os.path.basename(m)), members[0])
        base = os.path.basename(member)

        def factory():
            return io.TextIOWrapper(zf.open(member), encoding="latin-1", newline="")

        return factory, base

    base = os.path.basename(src)

    def factory():
        return open(src, "r", encoding="latin-1", newline="")

    return factory, base


def find_header_row(stream_factory):
    """Return the 0-based line index of the real header (cell == 'Acct ID')."""
    with stream_factory() as fh:
        r = csv.reader(fh)
        for i, row in enumerate(r):
            if i > 25:
                break
            if any(c.strip() == "Acct ID" for c in row):
                return i
    raise SystemExit("ERROR: could not locate 'Acct ID' header row in first 25 lines")


def classify_columns(cols):
    """Group month columns by metric family -> {family: {monthkey: colname}}."""
    fam = defaultdict(dict)          # family -> {mkey: col}
    snap = {}                        # latest-snapshot fields: base metric -> (mkey,col)
    for c in cols:
        m = MONTH_RE.match(c.strip())
        if not m:
            continue
        mon, yy, rest = m.group(1), m.group(2), m.group(3).strip()
        fam[rest][month_key(mon, yy)] = c
    return fam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--client", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--topn", type=int, default=12)
    a = ap.parse_args()

    src = a.input
    stream_factory, base = open_source(src)  # accepts .csv or .zip (reads zip in-stream)
    # Derive client id / name from the CSV filename '<id>-<yyyy-mm>-<Name>-ODD ...'
    fm = re.match(r"(\d+)-(\d{4})-(\d{2})-(.+?)-ODD", base)
    client = a.client or (fm.group(1) if fm else "0000")
    name = a.name or (fm.group(4).strip() if fm else "Unknown")
    period = f"{fm.group(2)}-{fm.group(3)}" if fm else "?"

    # Default output: sibling "Retail Performance Engine" dir next to ODDD/ .
    # ODDD file lives in <Work>/ODDD/, so go up two levels to <Work>.
    work_dir = os.path.dirname(os.path.dirname(src))
    out = a.out or os.path.join(
        work_dir, "Retail Performance Engine", f"{client}-{name}")
    os.makedirs(out, exist_ok=True)

    hdr_idx = find_header_row(stream_factory)
    header = pd.read_csv(stream_factory(), skiprows=hdr_idx, nrows=0).columns.tolist()
    # Drop the running-index first col + trailing unnamed padding cols.
    keep = [c for c in header if str(c).strip() and not str(c).startswith("Unnamed")]
    fam = classify_columns(keep)

    # Identify latest month present in the 'Elig' snapshot family.
    elig_months = fam.get("Elig", {})
    latest_mk = max(elig_months) if elig_months else None
    latest_lbl = None
    if latest_mk is not None:
        yy, mi = divmod(latest_mk, 12)
        latest_lbl = f"{MONTHS[mi]}{str(yy)[-2:]}"

    # Accumulators
    total_rows = 0
    counts = defaultdict(lambda: defaultdict(int))   # snapshot categorical counts
    money = defaultdict(lambda: defaultdict(float))   # family -> mkey -> sum$
    numc = defaultdict(lambda: defaultdict(float))    # family -> mkey -> sum count
    regE = defaultdict(lambda: defaultdict(int))      # mkey -> {Accepted/Declined/NoResp}
    campaign = defaultdict(lambda: defaultdict(int))  # 'Mail'/'Resp' -> mkey -> count
    branch_enr = defaultdict(int)                     # branch -> enrolled (latest)
    branch_od = defaultdict(float)                    # branch -> NSF/OD ITEM COUNT, latest MTD
    product_enr = defaultdict(int)
    status_ct = defaultdict(int)
    status_other_raw = defaultdict(int)  # raw Stat Desc values that fell to 'Other'

    latest_elig_col = elig_months.get(latest_mk)
    latest_prog_col = fam.get("Prog", {}).get(latest_mk)
    latest_rege_col = fam.get("Reg E Desc", {}).get(latest_mk)

    usecols = set(keep)
    reader = pd.read_csv(stream_factory(), skiprows=hdr_idx, usecols=lambda c: c in usecols,
                         dtype=object, chunksize=CHUNK, on_bad_lines="skip")

    # MTD/YTD/PYTD are NSF/OD ITEM COUNTS, not dollars (the ODD carries no
    # OD-fee dollar column) — they are summed by the same money_block pass only
    # because the cleaning is identical. See odd_rows.nsf().
    money_fams = ["OD Limit", "Sig $", "PIN $"]
    num_fams = ["Sig #", "PIN #", "MTD", "YTD", "PYTD"]

    for ch in reader:
        ch = ch.rename(columns=lambda c: c.strip())
        n = len(ch)
        total_rows += n

        # snapshot categoricals
        if "Business?" in ch:
            for k, v in norm_text(ch["Business?"]).value_counts().items():
                counts["Business"][k] += int(v)
        if "Stat Desc" in ch:
            raw_stat = norm_text(ch["Stat Desc"])
            # pass Stat Code so a core that leaves Stat Desc blank still classifies
            raw_code = norm_text(ch["Stat Code"]) if "Stat Code" in ch else None
            mapped_stat = classify_status(raw_stat, raw_code, client)
            for k, v in mapped_stat.value_counts().items():
                status_ct[k] += int(v)
            om = mapped_stat.eq("Other")
            if om.any():
                for k, v in raw_stat[om].replace("", "(blank)").value_counts().items():
                    # blanks fall to Other by design; EXPLICIT_OTHER values are confirmed Other
                    if k == "(blank)" or re.search(EXPLICIT_OTHER, str(k), re.I):
                        continue
                    status_other_raw[k] += int(v)
        if latest_elig_col and latest_elig_col in ch:
            for k, v in norm_text(ch[latest_elig_col]).value_counts().items():
                counts["Elig"][k] += int(v)
        if latest_prog_col and latest_prog_col in ch:
            prog = norm_text(ch[latest_prog_col])
            for k, v in prog.value_counts().items():
                counts["Prog"][k] += int(v)
        if latest_rege_col and latest_rege_col in ch:
            for k, v in classify_rege(ch[latest_rege_col]).value_counts().items():
                if k:
                    counts["RegE_latest"][k] += int(v)

        # enrolled-by-branch / product / status (latest month, Prog==Yes)
        if latest_prog_col and latest_prog_col in ch:
            enr = norm_text(ch[latest_prog_col]).eq("Yes")
            if "Branch" in ch:
                for k, v in norm_text(ch.loc[enr, "Branch"]).value_counts().items():
                    branch_enr[k] += int(v)
            if "Prod Desc" in ch:
                for k, v in norm_text(ch.loc[enr, "Prod Desc"]).value_counts().items():
                    product_enr[k] += int(v)

        # branch NSF/OD items (latest MTD)
        latest_mtd = fam.get("MTD", {}).get(latest_mk)
        if latest_mtd and latest_mtd in ch and "Branch" in ch:
            tmp = pd.DataFrame({"b": norm_text(ch["Branch"]),
                                "v": clean_money(ch[latest_mtd])})
            for k, v in tmp.groupby("b")["v"].sum().items():
                branch_od[k] += float(v)

        # monthly money + count families — one cleaned pass over all such columns
        num_set = set(num_fams)
        mcols = [(f, mk, col) for f in money_fams + num_fams
                 for mk, col in fam.get(f, {}).items() if col in ch]
        if mcols:
            csum, cgt0 = money_block(ch, [c for _, _, c in mcols])
            for f, mk, col in mcols:
                if f in num_set:
                    numc[f][mk] += float(csum[col])
                else:
                    money[f][mk] += float(csum[col])
                if f == "OD Limit":   # accounts with a positive limit
                    numc["OD Limit #>0"][mk] += int(cgt0[col])

        # Reg E monthly (label-agnostic via classify_rege)
        for mk, col in fam.get("Reg E Desc", {}).items():
            if col in ch:
                vc = classify_rege(ch[col]).value_counts()
                regE[mk][REGE_IN] += int(vc.get(REGE_IN, 0))
                regE[mk][REGE_OUT] += int(vc.get(REGE_OUT, 0))
                regE[mk][REGE_DEFAULT] += int(vc.get(REGE_DEFAULT, 0))

        # Mail / Resp campaigns. Cells hold a campaign/response CODE (e.g.
        # 'TH-10','NU','NU 1-4') or are blank. Non-blank == mailed / responded.
        EMPTY = {"", "nan", "none", "null", "na"}
        for fnm in ("Mail", "Resp"):
            for mk, col in fam.get(fnm, {}).items():
                if col in ch:
                    v = norm_text(ch[col]).str.lower()
                    campaign[fnm][mk] += int((~v.isin(EMPTY)).sum())

    # ---- assemble outputs ----
    def lbl(mk):
        yy, mi = divmod(mk, 12)
        return f"{MONTHS[mi]}{str(yy)[-2:]}"

    def series(d):
        return {lbl(mk): round(d[mk], 2) for mk in sorted(d)}

    accepted = counts["RegE_latest"].get(REGE_IN, 0)
    declined = counts["RegE_latest"].get(REGE_OUT, 0)
    noresp = counts["RegE_latest"].get(REGE_DEFAULT, 0)
    rege_unmapped = {k: v for k, v in counts["RegE_latest"].items()
                     if k not in (REGE_IN, REGE_OUT, REGE_DEFAULT)}
    optin_base = accepted + declined
    optin_rate = (accepted / optin_base * 100) if optin_base else 0.0
    eligible = counts["Elig"].get("Yes", 0)
    enrolled = counts["Prog"].get("Yes", 0)
    open_ct = status_ct.get("Open", 0)

    metrics = {
        "client": client, "name": name, "period": period,
        "source_file": base, "total_accounts": total_rows,
        "latest_month": latest_lbl,
        "funnel": {
            "total_accounts": total_rows, "open_accounts": open_ct,
            "eligible": eligible, "enrolled": enrolled,
            "penetration_of_eligible_pct": round(enrolled / eligible * 100, 1) if eligible else 0,
            "regE_optin_accepted": accepted, "regE_optin_declined": declined,
            "regE_no_response": noresp, "regE_optin_rate_pct": round(optin_rate, 1),
        },
        "mix": {
            "business": dict(counts["Business"]),
            "status": dict(sorted(status_ct.items(), key=lambda x: -x[1])),
        },
        "nsf_od_items_MTD": {lbl(mk): int(v) for mk, v in sorted(numc["MTD"].items())},
        "nsf_od_items_YTD": {lbl(mk): int(v) for mk, v in sorted(numc["YTD"].items())},
        "od_limit_total": series(money["OD Limit"]),
        "od_limit_accts_gt0": {lbl(mk): int(v) for mk, v in sorted(numc["OD Limit #>0"].items())},
        "interchange": {
            "sig_count": {lbl(mk): int(v) for mk, v in sorted(numc["Sig #"].items())},
            "sig_dollars": series(money["Sig $"]),
            "pin_count": {lbl(mk): int(v) for mk, v in sorted(numc["PIN #"].items())},
            "pin_dollars": series(money["PIN $"]),
        },
        "regE_trend": {lbl(mk): regE[mk] for mk in sorted(regE)},
        "campaigns": {
            "mailed": {lbl(mk): int(v) for mk, v in sorted(campaign["Mail"].items())},
            "responded": {lbl(mk): int(v) for mk, v in sorted(campaign["Resp"].items())},
        },
        "top_branches_by_enrollment": dict(sorted(branch_enr.items(), key=lambda x: -x[1])[:a.topn]),
        "top_branches_by_nsf_od_items_latest": {k: int(v) for k, v in sorted(branch_od.items(), key=lambda x: -x[1])[:a.topn]},
        "top_products_by_enrollment": dict(sorted(product_enr.items(), key=lambda x: -x[1])[:a.topn]),
        "flags": {
            "regE_unmapped": dict(sorted(rege_unmapped.items(), key=lambda x: -x[1])),
            "status_other_raw": dict(sorted(status_other_raw.items(), key=lambda x: -x[1])),
            # Text in money/count columns (shifted malformed rows), counted as missing.
            "non_numeric_cells": {"total": int(sum(NON_NUMERIC.values())),
                                  "columns": dict(sorted(NON_NUMERIC.items(), key=lambda x: -x[1])[:12])},
        },
    }

    # campaign response rates
    resp_rates = {}
    for mk in sorted(campaign["Mail"]):
        m = campaign["Mail"][mk]
        r = campaign["Resp"].get(mk, 0)
        if m:
            resp_rates[lbl(mk)] = {"mailed": m, "responded": r, "rate_pct": round(r / m * 100, 1)}
    metrics["campaign_response_rates"] = resp_rates

    with open(os.path.join(out, "oddd_metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    # ---- markdown pack ----
    L = []
    A = L.append
    A(f"# {client} {name} — ODDD Retail Performance data pack")
    A("")
    A(f"**Source:** {base}")
    A(f"**Period label:** {period}  |  **Latest data month:** {latest_lbl}")
    A(f"**Total accounts in dump:** {total_rows:,}  ({open_ct:,} Open)")
    A("**Notes:** Auto-generated by oddd_optimize.py. All $ are program totals summed across accounts.")
    A("")
    A("---")
    A("")
    A("## Program Funnel (latest month)")
    A(f"Total accounts = {total_rows:,}")
    A(f"Eligible = {eligible:,}")
    pen = metrics['funnel']['penetration_of_eligible_pct']
    pen_note = "  [!] enrolled > current-eligible flag; treat Elig/Prog as raw counts, confirm program semantics with FI" if pen > 100 else ""
    A(f"Enrolled (Program=Yes) = {enrolled:,}  ({pen}% of Elig=Yes count){pen_note}")
    if accepted + declined + noresp == 0 and not rege_unmapped:
        A("Reg E: not present in THIS ODD dump — populate the Reg E slides from the client's "
          "Reg E source (workbook/core); do NOT drop them.")
    else:
        A(f"Reg E: {REGE_IN} = {accepted:,}, {REGE_OUT} = {declined:,}, {REGE_DEFAULT} = {noresp:,}")
        A(f"Reg E opt-in rate ({REGE_IN} / ({REGE_IN} + {REGE_OUT})) = {optin_rate:.1f}%")
        if rege_unmapped:
            A("Reg E [!] UNMAPPED value(s) — ASK Aaron how to map, do NOT guess: "
              + ", ".join(f"{k!r}={v:,}" for k, v in rege_unmapped.items()))
    A("")
    biz = counts["Business"]
    A("## Consumer vs Business")
    A(", ".join(f"{k}={v:,}" for k, v in sorted(biz.items(), key=lambda x: -x[1])))
    A("")
    A("## Account Status mix")
    A("Buckets: " + ", ".join(STATUS_BUCKETS))
    A(", ".join(f"{k}={status_ct[k]:,}" for k in STATUS_BUCKETS if status_ct.get(k)))
    if status_other_raw:
        A("Other includes (raw Stat Desc): "
          + ", ".join(f"{k}={v:,}" for k, v in sorted(status_other_raw.items(), key=lambda x: -x[1]))
          + "  [!] confirm/ASK Aaron if any of these should be a named bucket (e.g. Frozen)")
    A("")

    def md_series(title, d, money_fmt=False):
        if not d:
            return
        A(f"## {title}")
        if money_fmt:
            A(", ".join(f"{k}=${v:,.0f}" for k, v in d.items()))
        else:
            A(", ".join(f"{k}={v:,}" for k, v in d.items()))
        A("")

    md_series("NSF/OD Items — Monthly (MTD, program total)", metrics["nsf_od_items_MTD"])
    md_series("OD Limit — Total extended, monthly", metrics["od_limit_total"], True)
    md_series("OD Limit — Accounts with limit > 0, monthly", metrics["od_limit_accts_gt0"])
    md_series("Debit Interchange — Signature $ monthly", metrics["interchange"]["sig_dollars"], True)
    md_series("Debit Interchange — PIN $ monthly", metrics["interchange"]["pin_dollars"], True)

    A("## Reg E Opt-In Trend (Reg E Opt In / Opt Out / Default per month)")
    if not any(regE[mk][REGE_IN] + regE[mk][REGE_OUT] + regE[mk][REGE_DEFAULT] for mk in regE):
        A("NOT POPULATED for this FI — no Reg E values in any month.")
    for mk in sorted(regE):
        d = regE[mk]
        base_ = d[REGE_IN] + d[REGE_OUT]
        rate = f"{d[REGE_IN]/base_*100:.1f}%" if base_ else "n/a"
        A(f"{lbl(mk)}: {REGE_IN}={d[REGE_IN]:,}, {REGE_OUT}={d[REGE_OUT]:,}, {REGE_DEFAULT}={d[REGE_DEFAULT]:,}  (opt-in {rate})")
    A("")

    if resp_rates:
        A("## Mail Campaign Performance (mailed → responded)")
        last_k = list(resp_rates)[-1]
        for k, v in resp_rates.items():
            tail = "  [!] most recent campaign — responses still arriving, rate not final" if (k == last_k and v['responded'] == 0) else ""
            A(f"{k}: mailed={v['mailed']:,}, responded={v['responded']:,}, response rate={v['rate_pct']}%{tail}")
        A("")

    A("## Top Branches by Enrollment (latest)")
    A(", ".join(f"{k}={v:,}" for k, v in metrics["top_branches_by_enrollment"].items()))
    A("")
    A("## Top Branches by NSF/OD Items (latest MTD)")
    A(", ".join(f"{k}={v:,}" for k, v in metrics["top_branches_by_nsf_od_items_latest"].items()))
    A("")
    A("## Top Products by Enrollment")
    A(", ".join(f"{k}={v:,}" for k, v in metrics["top_products_by_enrollment"].items()))
    A("")
    A("## DERIVED (for Key Metrics slide)")
    ytd_vals = list(metrics["nsf_od_items_YTD"].values())
    A(f"Latest YTD NSF/OD items = {ytd_vals[-1]:,}" if ytd_vals else "Latest YTD NSF/OD items = n/a")
    mtd_vals = list(metrics["nsf_od_items_MTD"].values())
    if mtd_vals:
        avg = sum(mtd_vals) / len(mtd_vals)
        A(f"Avg monthly NSF/OD items (over {len(mtd_vals)} mo) = {avg:,.0f}")
    A("NSF/OD REVENUE IS NOT IN THE ODD — the MTD/YTD columns are item counts. "
      "Fee dollars come from the client workbook (Total NSF Revenue).")
    A(f"Active/Open accounts = {open_ct:,}")
    A(f"Enrolled accounts = {enrolled:,}")

    with open(os.path.join(out, "oddd_pack.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    # stdout summary
    optin_str = f"{optin_rate:.1f}%" if (accepted + declined) else "n/a (Reg E not populated)"
    print(f"OK {client} {name}: {total_rows:,} accts | enrolled {enrolled:,} | "
          f"opt-in {optin_str} | latest {latest_lbl}")
    print(f"  -> {os.path.join(out, 'oddd_pack.md')}")
    print(f"  -> {os.path.join(out, 'oddd_metrics.json')}")


if __name__ == "__main__":
    main()
