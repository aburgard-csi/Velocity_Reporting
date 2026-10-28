# Ported from v5 02-Scripts/ils/pre_go_live/system_view.py at 7ba1e63. Logic unchanged; copied whole (here at g11-02 because run's needs_codes reply attaches the system view).
"""The ILS system's own view: matrix settings + integrity check.

Alongside the account extract, the ILS vendor can export two SQL dumps:

    {client}_..._MatrixValidation.txt   how limits are CONFIGURED (status
        mapping, min/max per account type, overrides in priority order,
        factor ranges, rounding tiers, change history)
    {client}_..._IntegrityCheck.txt     what the system is DOING (account
        metrics, daily calc history, limit distribution, OD status breakout,
        deposit/OD history, deletions)

Both are fixed-width tables under "=== SECTION ===" headers; the dashes line
under each header gives the column extents, so parsing is positional and
tolerant of spaces inside values. Everything is optional: no files, no keys,
one warn -- the sections that read `sysv_*` decline the same way.

Keys: sysv_* .
"""

from __future__ import annotations

import re
from pathlib import Path

MATRIX_PAT = re.compile(r"matrix.?validation", re.I)
INTEGRITY_PAT = re.compile(r"integrity.?check", re.I)
_DASHES = re.compile(r"^[-\s]+$")


# ---------------------------------------------------------------------------
# generic fixed-width table parsing
# ---------------------------------------------------------------------------

def _sections(text: str) -> dict:
    """{section name: [lines]} split on === NAME === headers."""
    out: dict[str, list[str]] = {}
    name = None
    for line in text.replace("﻿", "").splitlines():
        m = re.match(r"^===\s*(.+?)\s*===\s*$", line)
        if m:
            name = m.group(1).upper()
            out[name] = []
        elif name is not None:
            out[name].append(line.rstrip("\n"))
    return out


def _table(lines: list[str]) -> list[dict]:
    """First fixed-width table in the lines -> list of {column: value}."""
    dash_i = next((i for i, l in enumerate(lines)
                   if l.strip() and _DASHES.match(l) and "-" in l), None)
    if dash_i is None or dash_i == 0:
        return []
    header = lines[dash_i - 1]
    spans = [(m.start(), m.end()) for m in re.finditer(r"-+", lines[dash_i])]
    names = [header[a:b].strip() or f"col{i}" for i, (a, b) in enumerate(spans)]
    rows = []
    for line in lines[dash_i + 1:]:
        if not line.strip() or line.strip().startswith("("):
            break
        row = {}
        for (a, b), n in zip(spans, names):
            v = line[a:b].strip() if a < len(line) else ""
            row[n] = None if v in ("", "NULL") else v
        rows.append(row)
    return rows


def _num(v, default=None):
    if v is None:
        return default
    try:
        f = float(str(v).replace(",", ""))
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return default


def _get(row: dict, *starts):
    """Value of the first column whose name starts with any prefix (the dump
    truncates long headers, e.g. 'TotalOverrid')."""
    for s in starts:
        for k, v in row.items():
            if k.upper().startswith(s.upper()):
                return v
    return None


# ---------------------------------------------------------------------------
# matrix validation
# ---------------------------------------------------------------------------

def parse_matrix(text: str) -> dict:
    sec = _sections(text)
    out: dict = {}
    hist = _table(sec.get("ILS MATRIX CHANGE HISTORY", []))
    if hist:
        dates = [r.get("LOG_DATE") for r in hist if r.get("LOG_DATE")]
        out["sysv_matrix_changes_n"] = len(hist)
        out["sysv_matrix_last_change"] = max(dates) if dates else None
    smap = _table(sec.get("OD STATUS CODE MAPPING", []))
    if smap:
        out["sysv_matrix_status_map"] = [
            [r.get("STATUS_CODE"), _num(r.get("ILS_CALC")), _num(r.get("CAN_OVERDRAFT"))]
            for r in smap]
    prod = _table(sec.get("PRODUCT CODE MAPPING", []))
    if prod:
        out["sysv_matrix_product_codes_n"] = len(prod)
        out["sysv_matrix_products_mrpc_ineligible"] = [
            r.get("ProdCode") for r in prod if _num(r.get("MRPC_Eligible")) == 0]
    # the dump spells it ACCCOUNT; accept both
    types = _table(sec.get("ACCCOUNT TYPES AND MIN/MAX LIMITS",
                           sec.get("ACCOUNT TYPES AND MIN/MAX LIMITS", [])))
    if types:
        out["sysv_matrix_types"] = [
            [r.get("Account Type"), r.get("Matrix Code"), _num(r.get("Min")),
             _num(r.get("Max")), r.get("Enabled?"), r.get("Matrix Modified Date")]
            for r in types]
    ov = _table(sec.get("OVERRIDES", []))
    if ov:
        out["sysv_matrix_overrides"] = [
            [r.get("Account Type"), r.get("Override Criteria"), r.get("Override Value"),
             _num(_get(r, "Stop")), _num(_get(r, "Order"))]
            for r in ov]
        out["sysv_matrix_overrides_columns"] = ["type", "criteria", "value", "stop", "order"]
    rf = _table(sec.get("RANGES AND FACTORS", []))
    if rf:
        cats: dict = {}
        for r in rf:
            key = (r.get("Account Type"), r.get("Category"))
            f = _num(r.get("Factor"))
            entry = cats.setdefault(key, {"n": 0, "min": None, "max": None})
            entry["n"] += 1
            if f is not None:
                entry["min"] = f if entry["min"] is None else min(entry["min"], f)
                entry["max"] = f if entry["max"] is None else max(entry["max"], f)
        out["sysv_matrix_factors"] = [
            [t, c, v["n"], v["min"], v["max"]] for (t, c), v in cats.items()]
        out["sysv_matrix_factors_columns"] = ["type", "category", "ranges", "min_factor", "max_factor"]
    tiers = _table(sec.get("TIERS AND ROUNDING", []))
    if len(tiers) >= 2:
        step = _num(tiers[1].get("Limit Value"), 0) - _num(tiers[0].get("Limit Value"), 0)
        out["sysv_matrix_rounding_step"] = step or None
    return out


# ---------------------------------------------------------------------------
# integrity check
# ---------------------------------------------------------------------------

def parse_integrity(text: str) -> dict:
    sec = _sections(text)
    out: dict = {}
    am = _table(sec.get("ACCOUNT METRICS SUMMARY", []))
    if am:
        out["sysv_accounts"] = [
            [r.get("Acct Type"), _num(_get(r, "Total Accts")), _num(_get(r, "Open/Active")),
             _num(_get(r, "Open %")), _num(_get(r, "Can Overdraft")),
             _num(_get(r, "Eligible %")), _num(_get(r, "RegE Opt-In")),
             _num(_get(r, "RegE Opt-In %"))]
            for r in am]
        out["sysv_accounts_columns"] = ["type", "total", "open", "open_pct",
                                        "can_overdraft", "can_od_pct", "rege_optin", "rege_pct"]
    calc = _table(sec.get("PROCESS CALCULATION HISTORY", []))
    if calc:
        last = calc[-1]
        out["sysv_calc_latest"] = {
            "date": _get(last, "ProcessCalculationStart"),
            "accounts": _num(_get(last, "ProcessAccounts")),
            "avg_limit": _num(_get(last, "ProcessAvg")),
            "zero_limit": _num(_get(last, "AcctsReceivingZeroLimit")),
            "overrides": _num(_get(last, "TotalOverrid")),
        }
        out["sysv_calc_days"] = len(calc)
    ld = _table(sec.get("LIMIT DISTRIBUTION", []))
    if ld:
        zero = nonzero = 0
        dollars = 0.0
        top = 0.0
        for r in ld:
            lim = _num(r.get("ILS_OD_Limit"), 0) or 0
            n = _num(_get(r, "Account_Count"), 0) or 0
            if lim > 0:
                nonzero += n
                dollars += lim * n
                top = max(top, lim)
            else:
                zero += n
        out["sysv_ils_limits"] = {"zero": zero, "nonzero": nonzero,
                                  "dollars": round(dollars),
                                  "avg": round(dollars / nonzero) if nonzero else 0,
                                  "max": top,
                                  "effective": _get(ld[0], "EFFECTIVE_DATE")}
    ob = _table(sec.get("OD STATUS CODE BREAKOUT", []))
    if ob:
        out["sysv_od_status"] = [
            [r.get("STATUS_CODE"), _num(r.get("ILS_CALC")), _num(r.get("CAN_OVERDRAFT")),
             _num(r.get("ACCOUNTS"))]
            for r in ob]
        out["sysv_od_status_unmapped"] = [
            [r.get("STATUS_CODE"), _num(r.get("ACCOUNTS"))]
            for r in ob if r.get("ILS_CALC") is None]
    dele = _table(sec.get("COUNT OF DELETED ACCOUNTS", []))
    if dele:
        out["sysv_deleted"] = [[r.get("DELETED"),
                                _num(_get(r, "Count of Accounts"))] for r in dele]
        out["sysv_deleted_total"] = sum(r[1] or 0 for r in out["sysv_deleted"])
        out["sysv_deleted_note"] = ("largest deletion batches from the dump "
                                    "(top-N, not the exhaustive list)")
    dep = _table(sec.get("DEPOSIT HISTORY", []))
    if dep:
        counts = [_num(r.get("DepositCount"), 0) or 0 for r in dep]
        sums = [_num(r.get("DepositSum"), 0) or 0 for r in dep]
        active = [c for c in counts if c > 0]
        out["sysv_deposits"] = {
            "days": len(dep), "active_days": len(active),
            "avg_daily_count": round(sum(active) / len(active)) if active else 0,
            "avg_daily_dollars": round(sum(sums) / len(active)) if active else 0,
            "no_deposit_20d_latest": _num(_get(dep[-1], "Accounts w/o")),
        }
    od = _table(sec.get("OVERDRAFT HISTORY", []))
    if od:
        counts = [(_num(r.get("Account_Count"), 0) or 0, r.get("OD_Date")) for r in od]
        active = [c for c, _ in counts if c > 0]
        peak = max(counts, key=lambda t: t[0]) if counts else (0, None)
        out["sysv_overdrafts"] = {
            "days": len(od),
            "avg_daily_accounts": round(sum(active) / len(active)) if active else 0,
            "peak_accounts": peak[0], "peak_date": peak[1],
        }
    ovb = _table(sec.get("OVERRIDE BREAKOUT", []))
    if ovb:
        # the dump can append a SQL warning line ("Null value is eliminated
        # by an aggregate...") that parses as a countless row; drop it
        out["sysv_override_breakout"] = [
            [r.get("Override Calc"), _num(_get(r, "Override Count"))]
            for r in ovb if _num(_get(r, "Override Count")) is not None]
    return out


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def load(folder: Path, warn) -> dict:
    """Parse whichever of the two dumps sit next to the extract."""
    out: dict = {"sysv_files": []}
    txts = sorted(p for p in Path(folder).iterdir()
                  if p.suffix.lower() == ".txt" and not p.name.startswith("~"))
    for pat, parser, label in ((MATRIX_PAT, parse_matrix, "matrix validation"),
                               (INTEGRITY_PAT, parse_integrity, "integrity check")):
        matches = [p for p in txts if pat.search(p.name)]
        if not matches:
            warn(f"no {label} export next to the extract; system-view "
                 f"sections decline (ask the vendor for the {label} dump)")
            continue
        path = matches[-1]
        try:
            out.update(parser(path.read_text(encoding="utf-8", errors="replace")))
            out["sysv_files"].append(path.name)
        except Exception as exc:
            warn(f"{label} file unreadable ({type(exc).__name__}: {exc})")
    return out
