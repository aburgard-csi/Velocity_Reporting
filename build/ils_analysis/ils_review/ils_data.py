"""
One load of the account-level extracts, shared by every section.

The three tools this app consolidates each loaded the z-files their own way:
`deck_builder` read a column subset (necessary — these extracts run 60-190 MB
and 80+ columns), while the Deposit Score tool read zaccounts whole. Here the
union of columns every section needs is read exactly once and handed to all of
them, which is both faster and guarantees the sections agree on the numbers.

Also solved here: branch classification. Which branch codes are back-office vs.
digital vs. physical retail was previously eyeballed per institution (a noted
limitation of the old tool). `classify_branches` infers it from branch names,
so a new client works out of the box, and explicit overrides still win.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

# ── column aliases ──────────────────────────────────────────────────────────
# canonical -> accepted spellings (matched case-insensitively)
ZACCOUNTS_COLUMNS = {
    "acctid": ["acctid"],
    "branch": ["branch"],
    "branchname": ["branchname"],
    "opendate": ["opendate"],
    "closeddate": ["closeddate"],
    "acctstatus": ["acctstatus"],
    "accttype": ["accttype"],
    "prodcode": ["prodcode"],
    "odstatuscode": ["odstatuscode"],
    "IsPersonal": ["ispersonal"],
    "CanOverdraft": ["canoverdraft"],
    "autodeposit": ["autodeposit"],
    "employee": ["employee"],
    "Institution": ["institution"],
    "lastupdate": ["lastupdate"],
    "lastdepdate": ["lastdepdate"],
    "min_notice_dt": ["min_notice_dt"],
    "max_notice_dt": ["max_notice_dt"],
    # balances & limits
    "balance": ["balance"],
    "AvgCollectedBalance": ["avgcollectedbalance"],
    "ODLimit": ["odlimit"],
    "MaxODLimit": ["maxodlimit"],
    "MinODLimit": ["minodlimit"],
    "UniqueODLimit": ["uniqueodlimit"],
    "AvgODLimit": ["avgodlimit"],
    "InitODLimit": ["initodlimit"],
    "ODLOCAmount": ["odlocamount"],
    # deposits
    "DepCount33": ["depcount33"],
    "DepAmt33": ["depamt33"],
    "DepCount66": ["depcount66"],
    "DepAmt66": ["depamt66"],
    "DepCount99": ["depcount99"],
    "DepAmt99": ["depamt99"],
    "depCount365": ["depcount365"],
    "depAmt365": ["depamt365"],
    "avgdaysbetweendeposits": ["avgdaysbetweendeposits"],
    "WindfallRatio": ["windfallratio"],
    # items, fees, outcomes
    "items365": ["items365"],
    "PD_365": ["pd_365"],
    "PD_Amt_365": ["pd_amt_365"],
    "RT_365": ["rt_365"],
    "RT_Amt_365": ["rt_amt_365"],
    "Refund_365": ["refund_365"],
    "Refund_Amt_365": ["refund_amt_365"],
    "PossibleFees365": ["possiblefees365"],
    "CollectedFees365": ["collectedfees365"],
    "declines_365": ["declines_365"],
    "declines_amt_365": ["declines_amt_365"],
    "sixty_od": ["sixty_od"],
    "avgrepaymentrate": ["avgrepaymentrate"],
    "fdicoccasionsrolling12months": ["fdicoccasionsrolling12months"],
    "Chargeoff_Account": ["chargeoff_account"],
    "Chargeoff_Date": ["chargeoff_date"],
    "Chargeoff_Amt_365": ["chargeoff_amt_365"],
    "Recovery_Amt_365": ["recovery_amt_365"],
    # program flags
    "Deposit_Score": ["deposit_score"],
    "RDI33": ["rdi33"],
    "RDIAmt33": ["rdiamt33"],
    "RDI90Days": ["rdi90days"],
    "RegEOptinvalue": ["regeoptinvalue"],
    "SIG_365": ["sig_365"],
    "PIN_365": ["pin_365"],
    "RegEResponseDate": ["regeresponsedate"],
    "MRPC_Eligible": ["mrpc_eligible"],
    "MRPC_Loan_Eligible": ["mrpc_loan_eligible"],
    "RepaymentTrendCount33": ["repaymenttrendcount33"],
    "DepositTrendCount33": ["deposittrendcount33"],
    "WindfallTrendCount33": ["windfalltrendcount33"],
    "CashFlowTrendCount33": ["cashflowtrendcount33"],
    "Deleted": ["deleted"],
}

ZTREND_COLUMNS = {
    # per-notice channel flags (one item per row): the exception-items chart
    "ACH": ["ach"], "ATM": ["atm"], "CHK": ["chk"], "INT": ["int"], "CSR": ["csr"],
    "BPY": ["bpy"], "OTH": ["oth"], "POS": ["pos"],
    "acctid": ["acctid"],
    "noticedate": ["noticedate"],
    "noticeid": ["noticeid"],
    "Items": ["items"],
    "PD": ["pd"],
    "Item_Amts": ["item_amts"],
    "PossibleFees": ["possiblefees"],
    "CollectedFees": ["collectedfees"],
    "Min_Bal": ["min_bal"],
    "limit": ["limit"],
    "deptotal33": ["deptotal33"],
    "depcount33": ["depcount33"],
    "deptotal66": ["deptotal66"],
    "Next_Positive_Date": ["next_positive_date"],
    "Last_Positive_Date": ["last_positive_date"],
    "ItemDesc": ["itemdesc"],
}

# ── branch classification ───────────────────────────────────────────────────
# Names that mark a code as a non-retail unit rather than a physical branch.
BACK_OFFICE_PATTERNS = [
    r"\bcorporate\b", r"\badmin", r"\bhead\s?office\b", r"\bmain\s?office\b",
    r"\bcall\s?cent", r"\bcontact\s?cent", r"\bmember\s+service\s+cent",
    r"\boperations?\b", r"\bback\s?office\b", r"\bcollection", r"\brecovery\b",
    r"\bmortgage\b", r"\bconstruction\b", r"\bcommercial\b", r"\bbusiness\s+services\b",
    r"\bindirect\b", r"\bconsumer\s+lending\b", r"\bloan\s+cent", r"\bloan\s+dept",
    r"\boutbound\b", r"\bunderwrit", r"\bpayment\s+services\b", r"\bcard\s+services\b",
    r"\bit\b", r"\binformation\s+(technology|services|systems)\b",
    r"\bfinance\b", r"\baccounting\b",
    r"\bmarketing\b", r"\bhuman\s+resources\b", r"\bhr\b", r"\btraining\b",
    r"\bsecurity\b", r"\bcompliance\b", r"\baudit\b", r"\bresearch\b", r"\blegal\b",
    r"\bfacilit", r"\breserved\b", r"\bunassigned\b", r"\bundefined\b", r"\bunknown\b",
    r"\bclosed\b", r"\bdo\s+not\s+use\b", r"\bmisc", r"\bdefault\b", r"\bn/?a\b",
    r"\btest\b", r"\bconversion\b", r"\bdept\b", r"\bdepartment\b", r"\bwarehouse\b",
    r"\btrust\b", r"\binsurance\b", r"\binvestment", r"\bwealth\b",
    # Relationship-banking desks, not walk-in branches. Their deposit intensity
    # runs several times the retail average and swamps the branch comparison.
    r"\bprivate\s+banking\b",
]
DIGITAL_PATTERNS = [
    r"\bonline\b", r"\be-?branch\b", r"\bebranch\b", r"\be-?services\b",
    r"\bvirtual\b", r"\bdigital\b",
    r"\bremote\b", r"\binternet\b", r"\bweb\b", r"\bmobile\b", r"\bitm\b",
    r"\bvideo\s?bank", r"\bself\s?service\b", r"\bdirect\b",
]


def _matches(name, patterns):
    n = f" {re.sub(r'[^a-z0-9]+', ' ', str(name).lower()).strip()} "
    return any(re.search(p, n) for p in patterns)


@dataclass
class BranchClassification:
    """How each branch code was bucketed, and why."""
    retail: set = field(default_factory=set)
    back_office: set = field(default_factory=set)
    digital: set = field(default_factory=set)
    names: dict = field(default_factory=dict)
    reasons: dict = field(default_factory=dict)

    @property
    def excluded(self):
        return self.back_office | self.digital

    def summary(self):
        return (f"{len(self.retail)} retail, {len(self.digital)} digital, "
                f"{len(self.back_office)} back-office")

    def table(self):
        """Rows of (code, name, bucket, reason) sorted by bucket then code."""
        rows = []
        for code in sorted(self.names, key=lambda c: str(c)):
            bucket = ("Retail" if code in self.retail else
                      "Digital" if code in self.digital else "Back-office")
            rows.append((code, self.names[code], bucket, self.reasons.get(code, "")))
        return rows


def classify_branches(za, *, exclude=None, digital=None, retail=None,
                      min_accounts=25, dominant_share=0.20):
    """Bucket branch codes into retail / digital / back-office.

    Inference order (later rules only apply to codes not already decided):
      1. explicit `exclude` / `digital` / `retail` overrides
      2. branch *name* matched against the digital and back-office vocabularies
      3. a single code holding more than `dominant_share` of all open accounts
         is treated as back-office — that pattern is the core's default/holding
         branch (UCCU's 'Corporate' carries 54% of open accounts), never a real
         branch, and leaving it in flattens every per-branch chart
      4. codes with fewer than `min_accounts` open accounts are set aside as
         operational noise rather than plotted as branches
    """
    exclude = {str(c) for c in (exclude or [])}
    digital = {str(c) for c in (digital or [])}
    retail_force = {str(c) for c in (retail or [])}

    opn = za[za["acctstatus"].astype(str).str.upper() == "O"]
    counts = opn.groupby("branch", observed=True).size()
    total = int(counts.sum()) or 1
    names = {}
    for code, grp in opn.groupby("branch", observed=True):
        nm = ""
        if "branchname" in grp.columns:
            vals = grp["branchname"].dropna().astype(str)
            nm = vals.iloc[0] if len(vals) else ""
        names[code] = nm or str(code)

    c = BranchClassification(names=names)
    for code, n in counts.items():
        key = str(code)
        name = names[code]
        if key in retail_force:
            c.retail.add(code); c.reasons[code] = "forced retail"
        elif key in digital:
            c.digital.add(code); c.reasons[code] = "specified as digital"
        elif key in exclude:
            c.back_office.add(code); c.reasons[code] = "specified as excluded"
        elif _matches(name, DIGITAL_PATTERNS):
            c.digital.add(code); c.reasons[code] = "name looks like a digital channel"
        elif _matches(name, BACK_OFFICE_PATTERNS):
            c.back_office.add(code); c.reasons[code] = "name looks like a back-office unit"
        elif n / total > dominant_share:
            c.back_office.add(code)
            c.reasons[code] = f"holds {n / total * 100:.0f}% of open accounts — core default branch"
        elif n < min_accounts:
            c.back_office.add(code); c.reasons[code] = f"only {n} open accounts"
        else:
            c.retail.add(code); c.reasons[code] = "physical retail branch"
    return c


# ── loading ─────────────────────────────────────────────────────────────────
def _rename_map(columns, alias_map):
    lower = {str(c).strip().lower(): c for c in columns}
    out = {}
    for canonical, aliases in alias_map.items():
        for a in aliases:
            if a in lower:
                out[lower[a]] = canonical
                break
    return out


def _read_selective(path, alias_map, **kw):
    """Read only the columns this app uses — these extracts are 60-190 MB."""
    kw.setdefault("encoding", "utf-8-sig")            # the exports carry a BOM
    header = pd.read_csv(path, nrows=0, **kw)
    rename = _rename_map(header.columns, alias_map)
    df = pd.read_csv(path, usecols=list(rename.keys()), low_memory=False, **kw)
    return df.rename(columns=rename)


def date_from_name(path):
    """Snapshot date out of a filename: 20260826 or 2026.8.26 both work."""
    base = os.path.basename(str(path))
    for pat in (r"(\d{4})[._-](\d{1,2})[._-](\d{1,2})", r"(\d{4})(\d{2})(\d{2})"):
        m = re.search(pat, base)
        if m:
            y, mo, d = (int(x) for x in m.groups())
            try:
                return datetime(y, mo, d)
            except ValueError:
                continue
    return None


def client_from_folder(path):
    """A guess at the client name from the containing folder path."""
    p = os.path.abspath(str(path))
    parts = [x for x in p.split(os.sep) if x]
    skip = re.compile(r"^(analysis|data|files?|raw|\d{4}([-_.]\d{1,2})?|"
                      r"20\d{2}|q[1-4]|documents|onedrive.*|banks?|clients?)$", re.I)
    for part in reversed(parts[:-1]):
        if not skip.match(part.strip()):
            return part.strip()
    return ""


@dataclass
class Loaded:
    zaccounts: pd.DataFrame
    ztrend: Optional[pd.DataFrame]
    snapshot: datetime            # DATA as-of date (max lastupdate), what every window is measured from
    branches: BranchClassification
    notes: list = field(default_factory=list)
    file_date: Optional[datetime] = None     # the pull stamp in the file name (the extract was pulled this day)
    declines: Optional[pd.DataFrame] = None
    refunds: Optional[pd.DataFrame] = None

    @property
    def has_trend(self):
        return self.ztrend is not None

    @property
    def date_label(self):
        return f"{self.snapshot.strftime('%B')} {self.snapshot.day}, {self.snapshot.year}"


def infer_snapshot(za, zaccounts_path=None):
    """The data as-of date: the data's own maximum `lastupdate` first, then the file stamp.

    CHANGED from the analysis team's code, which took the file name first. Achieva's pull is
    stamped 2026-09-11 but its slides say "Data as of: 2026-09-10", which is the data maximum;
    windows measured from the file stamp are a day off. The file stamp is kept as `file_date`
    and goes in the speaker-note sources.
    """
    best = None
    for col in ("lastupdate", "max_notice_dt"):
        if col in za.columns:
            m = pd.to_datetime(za[col], errors="coerce").max()
            if pd.notna(m) and (best is None or m > best):
                best = m
    if best is not None:
        return best.to_pydatetime()
    d = date_from_name(zaccounts_path) if zaccounts_path else None
    return d or datetime.today()


def load(zaccounts_path, ztrend_path=None, *, exclude_branches=None,
         digital_branches=None, retail_branches=None, include_digital=True,
         snapshot_date=None, progress=None, declines_path=None, refunds_path=None):
    """Read the extracts once and return everything downstream needs."""
    say = progress or (lambda m: None)
    notes = []

    say(f"Loading zaccounts — {os.path.basename(str(zaccounts_path))}…")
    za = _read_selective(zaccounts_path, ZACCOUNTS_COLUMNS)
    missing = [c for c in ("acctid", "branch", "acctstatus", "accttype") if c not in za.columns]
    if missing:
        raise ValueError(
            f"zaccounts file is missing required column(s): {', '.join(missing)}. "
            f"Is this an ILS ZAccounts export?")

    za["acctid"] = za["acctid"].astype(str).str.strip()
    for c in ("opendate", "closeddate", "lastdepdate", "Chargeoff_Date",
              "lastupdate", "max_notice_dt", "min_notice_dt", "RegEResponseDate"):
        if c in za.columns:
            za[c] = pd.to_datetime(za[c], errors="coerce")
    if "branchname" not in za.columns:
        za["branchname"] = za["branch"].astype(str)
    za["branchname"] = za["branchname"].astype(str).str.strip()
    if "Deleted" in za.columns:
        n_del = int(_truthy(za["Deleted"]).sum())
        if n_del:
            za = za[~_truthy(za["Deleted"])].copy()
            notes.append(f"{n_del:,} rows flagged Deleted were excluded.")
    say(f"  {len(za):,} accounts, {len(za.columns)} columns in scope.")

    snapshot = snapshot_date or infer_snapshot(za, zaccounts_path)

    # opendate sanity: placeholder dates (1900/1901) break age banding
    if "opendate" in za.columns:
        bad = za["opendate"] < pd.Timestamp("1950-01-01")
        if bad.any():
            za.loc[bad, "opendate"] = pd.NaT
            notes.append(f"{int(bad.sum()):,} accounts had a placeholder opendate "
                         f"before 1950; treated as unknown.")

    zt = None
    if ztrend_path:
        say(f"Loading ztrend — {os.path.basename(str(ztrend_path))}…")
        zt = _read_selective(ztrend_path, ZTREND_COLUMNS)
        if "acctid" not in zt.columns or "noticedate" not in zt.columns:
            notes.append("ztrend file lacks acctid/noticedate; trend-based analyses skipped.")
            zt = None
        else:
            zt["acctid"] = zt["acctid"].astype(str).str.strip()
            for c in ("noticedate", "Next_Positive_Date", "Last_Positive_Date"):
                if c in zt.columns:
                    zt[c] = pd.to_datetime(zt[c], errors="coerce")
            for c in ("deptotal33", "CollectedFees", "PossibleFees", "Item_Amts",
                      "Items", "PD", "Min_Bal", "limit", "depcount33"):
                if c in zt.columns:
                    zt[c] = pd.to_numeric(zt[c], errors="coerce").astype("float32")
            say(f"  {len(zt):,} notice rows.")

    branches = classify_branches(za, exclude=exclude_branches, digital=digital_branches,
                                 retail=retail_branches)
    say(f"Branch classification: {branches.summary()}.")

    za["is_retail"] = za["branch"].isin(branches.retail)
    za["is_digital"] = za["branch"].isin(branches.digital)
    # Branch-metric scope. Digital channels are in by default: they originate and
    # hold real accounts, so leaving them out understates the portfolio. Only
    # back-office codes are held out. is_retail/is_digital stay as the honest
    # classification, which the Data Notes slide reports.
    za["in_branch_scope"] = za["is_retail"] | (za["is_digital"] if include_digital
                                               else False)

    dd = rf = None
    if declines_path:
        say(f"Loading debit declines — {os.path.basename(str(declines_path))}…")
        dd = pd.read_csv(declines_path, encoding="utf-8-sig", low_memory=False,
                         usecols=lambda c: str(c).strip().lower() in
                         ("acctid", "odstatuscode", "prodcode", "decline_date", "transaction_type",
                          "transaction_amount", "mcc_code"))
        dd.columns = [str(c).strip().lower() for c in dd.columns]
        dd["acctid"] = dd["acctid"].astype(str).str.strip()
        dd["decline_date"] = pd.to_datetime(dd["decline_date"], errors="coerce")
        say(f"  {len(dd):,} decline rows.")
    if refunds_path:
        say(f"Loading refund history — {os.path.basename(str(refunds_path))}…")
        rf = pd.read_csv(refunds_path, encoding="utf-8-sig", low_memory=False)
        rf.columns = [str(c).strip() for c in rf.columns]
        rf["AcctID"] = rf["AcctID"].astype(str).str.strip()
        rf["Date"] = pd.to_datetime(rf["Date"], errors="coerce")
        say(f"  {len(rf):,} refund rows.")
    return Loaded(zaccounts=za, ztrend=zt, snapshot=snapshot, branches=branches, notes=notes,
                  file_date=date_from_name(zaccounts_path), declines=dd, refunds=rf)


# ── shared little helpers ───────────────────────────────────────────────────
def _truthy(series):
    return series.astype(str).str.strip().str.lower().isin(("1", "true", "t", "y", "yes"))


def num(series):
    return pd.to_numeric(series, errors="coerce")


def open_accounts(za, accttype=None, *, branch_scope_only=True):
    df = za[za["acctstatus"].astype(str).str.upper() == "O"]
    if branch_scope_only:
        df = df[df["in_branch_scope"]]
    if accttype:
        df = df[df["accttype"] == accttype]
    return df


def account_types(za, *, min_open=250):
    """Material account types, Personal and Business first."""
    opn = za[za["acctstatus"].astype(str).str.upper() == "O"]
    counts = opn["accttype"].value_counts()
    keep = [t for t, n in counts.items() if n >= min_open]
    lead = [t for t in ("Personal", "Business") if t in keep]
    return lead + [t for t in counts.index if t in keep and t not in lead]


def money(x, decimals=0):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"${x:,.{decimals}f}"


def pct(x, decimals=1):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{x:.{decimals}f}%"


def count(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{int(round(x)):,}"
