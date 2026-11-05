"""
The DBIC export — Daily Batch Integrity Check.

A per-client operational report that ships alongside the ZAccounts / ZTrend /
Matrix files and, until now, went unused. It is the same dashed-table text
format as the matrix export, so `matrix_report.parse` reads it directly — but
its ~25 result sets carry no `=== SECTION ===` banners, so each one has to be
identified by its column signature. That is what `sections()` does.

What is in it that the other exports don't have:

  * the ILS calculation run log — one row per nightly run, with accounts
    processed, the average limit granted, how many got a zero limit, override
    counts, and any error. This is the only place the engine's own health and
    the limit trend are visible.
  * Reg E opt-in, open/active and eligible counts per account type — the
    numbers behind the house "Eligibility Drilldown" slides, which are pasted
    in by hand today.
  * 61 days of daily feeds, weekend-flagged: deposits, overdrawn accounts,
    debit declines, and notice items with fees assessed vs. possible (i.e. the
    fee collection rate).
  * override effectiveness — for each override rule, how many accounts it hit
    and what limit, account age and days-overdrawn those accounts actually had.
  * exception items split by channel (POS / ACH / CHK / ATM / …) and by paid
    vs. returned.

Column signatures vary slightly between clients (a newer export adds
`Avg_Mobile_Deposit_Risk` to the run log, for instance), so matching is on a
required subset of columns rather than an exact list.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .matrix_report import parse

# key -> (required columns, human label). A section matches when every required
# column is present, so an export with extra columns still resolves.
SIGNATURES = {
    "integrity_errors": (
        {"Table", "ErrDescription"},
        "Data integrity exceptions"),
    "eligibility": (
        {"Acct Type", "Opt-In", "Open/Active", "Can Overdraft", "Total Accts"},
        "Opt-in and eligibility by account type"),
    "deposits": (
        {"DepositDate", "DepositCount", "DepositSum"},
        "Daily deposit feed"),
    "calc_runs": (
        {"ProcessCalculationStart", "ProcessAccounts", "ProcessAvg",
         "AcctsReceivingZeroLimit"},
        "ILS calculation run log"),
    "overrides": (
        {"Override ID", "Override Calc", "Override Count", "Actual Average Limit"},
        "Override effectiveness"),
    "limit_dist": (
        {"ILS_OD_Limit", "ACCOUNT_TYPE", "Account_Count"},
        "Granted limit distribution"),
    "od_accounts": (
        {"OD_Date", "Account_Count"},
        "Accounts overdrawn per day"),
    "declines": (
        {"Decline_Date", "Decline_Count", "Account_Count"},
        "Daily debit declines"),
    "notices": (
        {"Notice_Date", "Item_Count", "Paid_Item_Count", "Fees_Assessed",
         "Possible_Fees"},
        "Daily notice items and fee collection"),
    "channels": (
        {"Acct Type", "PD/RT", "POS-60", "ACH-60", "CHK-60"},
        "Exception items by channel"),
    "adjustments": (
        {"Type", "Date", "Account Count", "NSF/OD Fees (Sum)"},
        "Refunds and recoveries"),
    "status_codes": (
        {"STATUS_CODE", "DESCRIPTION", "ACCOUNTS"},
        "OD status codes with account counts"),
    "deleted": (
        {"DELETED", "Count of Accounts Marked Deleted"},
        "Accounts marked deleted"),
}

# Single-cell advisory sections: {key: the column name that carries the text}
NOTE_SIGNATURES = {
    "note_limits_old": "Calculated limit records 60 or more days ago",
    "note_core_limit": "Today's average core overdraft limit",
    "note_declines_old": "ATM/POS Debit Declines 60 or more days ago",
    "note_notices_old": "Notice items 60 or more days ago",
    "note_adjustments_old": "Adjustment items 60 or more days ago",
}


def _num(v):
    """A DBIC numeric cell -> float, or None for NULL/blank."""
    s = str(v).strip()
    if not s or s.upper() in ("NULL", "NONE", "N/A", "-"):
        return None
    try:
        return float(s.replace(",", "").replace("$", "").replace("%", ""))
    except ValueError:
        return None


def _date(v):
    s = str(v).strip()
    if not s or s.upper() == "NULL":
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "t", "y", "yes")


def sections(path):
    """{key: rows} for every DBIC section this module knows how to read.

    Sections are matched on a required column subset. Where a client's export
    splits one logical set across two blocks (the run log is one such), the
    rows are concatenated in file order.
    """
    raw = parse(path)
    out = {}
    for name, d in raw.items():
        cols = {c for c in d["columns"] if c}
        rows = d["rows"]
        if not rows:
            # keep empty integrity blocks: "zero exceptions" is a real result
            matched = [k for k, (req, _) in SIGNATURES.items() if req <= cols]
            for k in matched:
                out.setdefault(k, [])
            continue
        for key, (req, _) in SIGNATURES.items():
            if req <= cols:
                out.setdefault(key, []).extend(rows)
                break
        else:
            for key, col in NOTE_SIGNATURES.items():
                if col in cols:
                    out.setdefault(key, []).extend(rows)
                    break
    return out


# ── derived metrics ─────────────────────────────────────────────────────────
@dataclass
class CalcHealth:
    """The nightly ILS calculation log, summarised."""
    n_runs: int = 0
    n_success: int = 0
    first: Optional[datetime] = None
    last: Optional[datetime] = None
    dates: list = field(default_factory=list)
    accounts: list = field(default_factory=list)
    avg_limit: list = field(default_factory=list)
    zero_limit: list = field(default_factory=list)
    overrides: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    median_runtime_min: Optional[float] = None

    @property
    def success_rate(self):
        return self.n_success / self.n_runs * 100 if self.n_runs else None

    @property
    def zero_limit_pct(self):
        """Share of processed accounts granted a zero limit, latest run."""
        if not self.accounts or not self.zero_limit:
            return None
        a, z = self.accounts[-1], self.zero_limit[-1]
        return z / a * 100 if a else None

    def trend(self, series):
        """(first, last, change) for a series, ignoring gaps."""
        vals = [v for v in series if v is not None]
        if len(vals) < 2:
            return None
        return vals[0], vals[-1], vals[-1] - vals[0]


def calc_health(rows):
    h = CalcHealth()
    for r in rows:
        start = _date(r.get("ProcessCalculationStart"))
        end = _date(r.get("ProcessCalculationEnd"))
        h.n_runs += 1
        if _truthy(r.get("ProcessCalculationSuccess")):
            h.n_success += 1
        err = str(r.get("ErrorMessage", "")).strip()
        if err and err.upper() != "NULL":
            h.errors.append((start, err))
        if start:
            h.dates.append(start)
            if h.first is None or start < h.first:
                h.first = start
            if h.last is None or start > h.last:
                h.last = start
        h.accounts.append(_num(r.get("ProcessAccounts")))
        h.avg_limit.append(_num(r.get("ProcessAvg")))
        h.zero_limit.append(_num(r.get("AcctsReceivingZeroLimit")))
        h.overrides.append(_num(r.get("TotalOverrides")))
    runtimes = []
    for r in rows:
        s, e = (_date(r.get("ProcessCalculationStart")),
                _date(r.get("ProcessCalculationEnd")))
        if s and e and e > s:
            runtimes.append((e - s).total_seconds() / 60)
    if runtimes:
        runtimes.sort()
        h.median_runtime_min = runtimes[len(runtimes) // 2]
    return h


@dataclass
class Eligibility:
    rows: list = field(default_factory=list)     # per account type
    total_accts: int = 0
    total_open: int = 0
    total_eligible: int = 0
    total_optin: int = 0

    @property
    def optin_rate(self):
        # Against accounts on file, not open accounts — that is the denominator
        # the export's own per-type "Opt-In %" uses, and mixing the two makes the
        # totals row disagree with the rows above it.
        return (self.total_optin / self.total_accts * 100
                if self.total_accts else None)

    @property
    def eligible_rate(self):
        return (self.total_eligible / self.total_accts * 100
                if self.total_accts else None)


def eligibility(rows):
    e = Eligibility()
    for r in rows:
        t = str(r.get("Acct Type", "")).strip()
        if not t:
            continue
        rec = {
            "type": t,
            "optin": _num(r.get("Opt-In")),
            "optin_pct": _num(r.get("Opt-In %")),
            "open": _num(r.get("Open/Active")),
            "open_pct": _num(r.get("Open %")),
            "eligible": _num(r.get("Can Overdraft")),
            "eligible_pct": _num(r.get("Eligible %")),
            "total": _num(r.get("Total Accts")),
        }
        e.rows.append(rec)
        for key, attr in (("total", "total_accts"), ("open", "total_open"),
                          ("eligible", "total_eligible"), ("optin", "total_optin")):
            if rec[key]:
                setattr(e, attr, getattr(e, attr) + int(rec[key]))
    return e


@dataclass
class DailySeries:
    """A weekend-flagged daily series out of one of the 61-day blocks."""
    label: str = ""
    dates: list = field(default_factory=list)
    weekend: list = field(default_factory=list)
    series: dict = field(default_factory=dict)   # name -> [values]

    @property
    def business_days(self):
        return [i for i, w in enumerate(self.weekend) if not w]

    def business_values(self, name):
        vals = self.series.get(name, [])
        return [vals[i] for i in self.business_days
                if i < len(vals) and vals[i] is not None]

    def total(self, name):
        vals = [v for v in self.series.get(name, []) if v is not None]
        return sum(vals) if vals else None

    def mean_business(self, name):
        v = self.business_values(name)
        return sum(v) / len(v) if v else None

    def zero_business_days(self, name):
        """Business days where the feed reported nothing — a gap worth flagging."""
        vals = self.series.get(name, [])
        return [self.dates[i] for i in self.business_days
                if i < len(vals) and (vals[i] is None or vals[i] == 0)]

    def business_only(self, *names):
        """(dates, {name: values}) with weekends dropped.

        Weekend rows are blank by design, and a line chart renders each blank as
        a break — 61 days then draws as nine disconnected week-long segments,
        which reads as erratic data rather than as "the bank was shut". Charting
        business days only gives one continuous line; the weekend information is
        not lost, it drives the feed-gap check instead.
        """
        idx = self.business_days
        dates = [self.dates[i] for i in idx]
        out = {}
        for n in names:
            vals = self.series.get(n, [])
            out[n] = [vals[i] if i < len(vals) else None for i in idx]
        return dates, out


def daily(rows, date_col, value_cols, label=""):
    d = DailySeries(label=label)
    d.series = {c: [] for c in value_cols}
    for r in rows:
        dt = _date(r.get(date_col))
        if dt is None:
            continue
        d.dates.append(dt)
        d.weekend.append(bool(str(r.get("Weekend", "")).strip()))
        for c in value_cols:
            d.series[c].append(_num(r.get(c)))
    return d


def notice_metrics(rows):
    """Daily notice items plus the portfolio fee collection rate."""
    d = daily(rows, "Notice_Date",
              ["Item_Count", "Paid_Item_Count", "Fees_Assessed", "Possible_Fees",
               "Account_Count", "Average_Tran_Amount"],
              label="Notice items")
    assessed = d.total("Fees_Assessed") or 0.0
    possible = d.total("Possible_Fees") or 0.0
    items = d.total("Item_Count") or 0.0
    paid = d.total("Paid_Item_Count") or 0.0
    return d, {
        "fees_assessed": assessed,
        "fees_possible": possible,
        "collection_rate": (assessed / possible * 100) if possible else None,
        "forgone": max(0.0, possible - assessed),
        "items": items,
        "paid_items": paid,
        "pay_ratio": (paid / items * 100) if items else None,
    }


def channel_mix(rows):
    """{(acct type, PD|RT): {channel: count}} plus channel totals."""
    chans = ["POS", "PIN", "SIG", "ATM", "ACH", "CHK", "CSR", "BPY", "INT", "OTH"]
    mix, totals = {}, {c: 0.0 for c in chans}
    for r in rows:
        t = str(r.get("Acct Type", "")).strip()
        kind = str(r.get("PD/RT", "")).strip().upper()
        if not t or kind not in ("PD", "RT"):
            continue
        row = {}
        for c in chans:
            v = _num(r.get(f"{c}-60")) or 0.0
            row[c] = v
            totals[c] += v
        mix[(t, kind)] = row
    live = [c for c in chans if totals[c] > 0]
    return mix, {c: totals[c] for c in live}


def override_rows(rows):
    """Override effectiveness, most-hit first, de-duplicated by rule id."""
    seen = {}
    for r in rows:
        oid = str(r.get("Override ID", "")).strip()
        cnt = _num(r.get("Override Count")) or 0.0
        rec = {
            "id": oid,
            "calc": re.sub(r"\s+", " ", str(r.get("Override Calc", ""))).strip()
                      .replace("[", "").replace("]", ""),
            "count": cnt,
            "accounts": _num(r.get("Accounts")),
            "value": str(r.get("Override Limit Value", "")).strip(),
            "avg_limit": _num(r.get("Actual Average Limit")),
            "avg_age": _num(r.get("Actual Avg Acct Age")),
            "avg_days_od": _num(r.get("Actual Avg Days OD")),
        }
        # a client's export can repeat a rule across calculation dates
        if oid not in seen or cnt > seen[oid]["count"]:
            seen[oid] = rec
    return sorted(seen.values(), key=lambda r: -(r["count"] or 0))


def limit_distribution(rows, *, top=14):
    """Accounts by granted limit, aggregated over account types and dates."""
    by_limit, by_type = {}, {}
    for r in rows:
        lim = _num(r.get("ILS_OD_Limit"))
        n = _num(r.get("Account_Count")) or 0.0
        t = str(r.get("ACCOUNT_TYPE", "")).strip()
        if lim is None:
            continue
        by_limit[lim] = by_limit.get(lim, 0.0) + n
        if t:
            by_type.setdefault(t, {})
            by_type[t][lim] = by_type[t].get(lim, 0.0) + n
    ordered = sorted(by_limit.items())
    total = sum(by_limit.values()) or 1.0
    zero = by_limit.get(0.0, 0.0)
    # keep the largest buckets so the chart stays legible
    biggest = sorted(ordered, key=lambda kv: -kv[1])[:top]
    return {
        "by_limit": ordered,
        "by_type": by_type,
        "chart": sorted(biggest),
        "total_accounts": total,
        "zero_limit": zero,
        "zero_pct": zero / total * 100,
        "n_distinct": len(ordered),
    }


def integrity(rows):
    """Exception counts grouped by the error description."""
    groups = {}
    for r in rows:
        desc = re.sub(r"\s+", " ", str(r.get("ErrDescription", ""))).strip()
        if not desc or desc.upper() == "NULL":
            continue
        tbl = str(r.get("Table", "")).strip()
        col = str(r.get("Column", "")).strip()
        key = (tbl, desc)
        g = groups.setdefault(key, {"table": tbl, "desc": desc, "n": 0,
                                    "columns": set(), "types": set()})
        g["n"] += 1
        if col and col.upper() != "NULL":
            g["columns"].add(col)
        at = str(r.get("AcctType", "")).strip()
        if at and at.upper() != "NULL":
            g["types"].add(at)
    return sorted(groups.values(), key=lambda g: -g["n"])


def advisories(secs):
    """The one-line advisory notes, cleaned up."""
    out = []
    for key, col in NOTE_SIGNATURES.items():
        for r in secs.get(key, []):
            txt = re.sub(r"\s+", " ", str(r.get(col, ""))).strip()
            if not txt or txt.upper() == "NULL":
                continue
            if txt.lower().startswith("warning: null value is eliminated"):
                continue          # SQL noise, not a finding
            out.append(txt)
    return out


def deleted_counts(rows):
    out = []
    for r in rows:
        flag = str(r.get("DELETED", "")).strip()
        n = _num(r.get("Count of Accounts Marked Deleted"))
        if flag and n is not None:
            out.append((flag, int(n)))
    return out


@dataclass
class Dbic:
    """Everything the slides need, resolved once."""
    path: str = ""
    secs: dict = field(default_factory=dict)
    calc: Optional[CalcHealth] = None
    elig: Optional[Eligibility] = None
    deposits: Optional[DailySeries] = None
    od: Optional[DailySeries] = None
    declines: Optional[DailySeries] = None
    notices: Optional[DailySeries] = None
    fees: dict = field(default_factory=dict)
    channels: tuple = ()
    overrides: list = field(default_factory=list)
    limits: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    deleted: list = field(default_factory=list)
    status_codes: list = field(default_factory=list)

    @property
    def available(self):
        return bool(self.secs)


def load(path):
    """Read a DBIC export and derive every metric the section renders."""
    d = Dbic(path=str(path))
    d.secs = sections(path)
    if not d.secs:
        return d
    d.calc = calc_health(d.secs.get("calc_runs", []))
    d.elig = eligibility(d.secs.get("eligibility", []))
    d.deposits = daily(d.secs.get("deposits", []), "DepositDate",
                       ["DepositCount", "DepositSum", "ReturnedDepositItemCount",
                        "ReturnedDepositItemSum",
                        "Accounts w/o a Deposit in the last 20 days"],
                       label="Deposits")
    d.od = daily(d.secs.get("od_accounts", []), "OD_Date", ["Account_Count"],
                 label="Accounts overdrawn")
    d.declines = daily(d.secs.get("declines", []), "Decline_Date",
                       ["Decline_Count", "Account_Count", "Average_Tran_Amount"],
                       label="Debit declines")
    d.notices, d.fees = notice_metrics(d.secs.get("notices", []))
    d.channels = channel_mix(d.secs.get("channels", []))
    d.overrides = override_rows(d.secs.get("overrides", []))
    d.limits = limit_distribution(d.secs.get("limit_dist", []))
    d.errors = integrity(d.secs.get("integrity_errors", []))
    d.notes = advisories(d.secs)
    d.deleted = deleted_counts(d.secs.get("deleted", []))
    d.status_codes = d.secs.get("status_codes", [])
    return d
