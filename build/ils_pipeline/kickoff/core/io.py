# Ported from v5 02-Scripts/ils/kickoff_analysis/core/io.py at 7ba1e63. Logic unchanged; the folder lookup reads Inputs/ILS Kickoff/ (ils_pipeline/kickoff_input.py).
"""Data loading for the ILS Kickoff pipeline.

Resolves a client's one-time data extract from the standard layout:

    01-Data\\ILS\\{YYYY-MM}\\{client}\\{client}_OneTimeData_{date}.{csv,xlsx}

and normalizes its columns to a fixed canonical set, so every analysis
module can rely on the same column names regardless of what the raw
export happened to call them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Canonical column names every analysis module should rely on.
# ---------------------------------------------------------------------------

ACCT_NO = "AcctNo"
ACCOUNT_STATUS = "Account Status"      # values: 'O' = open, etc.
BUSINESS_FLAG = "Business Flag"        # values: 'P' = personal, 'B' = business
STAT_CODE = "Stat Code"
PRODUCT_CODE = "Product Code"
TOTAL_ITEMS = "Total Items"
PAID_ITEMS = "Paid Items"
RETURNED_ITEMS = "Returned Items"
OD_LIMIT = "OD Limit"
OPEN_DATE = "Open Date"
AVG_BALANCE = "Avg Collected Balance"
DEPOSIT_COUNT = "Deposit Count"
DEPOSIT_AMOUNT = "Deposit Amount"
REG_E_FLAG = "Reg E Flag"
# Items excluding waived ones -- the real presented total on extracts that
# carry it. 1840 had both and no analysis read either, which is how every
# pay rate came out at 100%: Total Items had resolved to the paid column.
OD_ITEMS = "OD Items"
NSF_ITEMS = "NSF Items"
# Fee income, separate from item counts. Kept apart deliberately: a fee is
# not an item, and a rate built by dividing one by the other is nonsense.
PAID_FEE_YTD = "Paid Item Fee YTD"
RETURN_FEE_YTD = "Return Item Fee YTD"
PAID_FEE_LYR = "Paid Item Fee LYR"
RETURN_FEE_LYR = "Return Item Fee LYR"
SWIPES = "Swipes"
TRANS_AMT = "TransAmt"


@dataclass
class CodeConfig:
    """
    The raw codes that distinguish personal/business accounts, open
    status, and OD eligibility. These varied across clients in the
    source notebook (and were hardcoded per-cell, inconsistently). Set
    these once per run instead of editing code.

    Defaults match the notebook's later, internally-consistent cells --
    override any of them for a client whose file uses different values.
    """
    personal_code: str = "P"
    business_code: str = "B"
    open_status_code: str = "O"
    # OD ELIGIBILITY -- the OD Status (Stat Code). What the client is
    # eligible for.
    eligible_stat_codes: list[str] = field(default_factory=lambda: ["ODP Account"])
    # REG E OPT-IN -- a SEPARATE variable: whether the member opted in.
    # Deliberately EMPTY by default. "Y" means opted in is a guess that
    # happens to hold on some clients: 1842 carries only "D" and no yeses,
    # 1840 will carry yeses. An unconfirmed mapping is reported, never
    # guessed, which is the same rule the Stat Codes follow.
    rege_opt_in: list[str] = field(default_factory=list)
    rege_opt_out: list[str] = field(default_factory=list)

    def is_eligible(self, stat_code_series: pd.Series) -> pd.Series:
        return stat_code_series.astype(str).isin(self.eligible_stat_codes)


def _norm(s: str) -> str:
    """Lowercase, strip, drop spaces/underscores for alias matching."""
    return str(s).strip().lower().replace(" ", "").replace("_", "")


# Alias map: normalized raw name -> canonical name. Ported and de-duped
# from the notebook's to_canonical(); extend here as new client exports
# turn up new spellings.
_ALIAS_MAP = {
    "swipes": SWIPES,
    "trancount": SWIPES,
    "transamt": TRANS_AMT,
    "acctno": ACCT_NO,
    "accountnumber": ACCT_NO,
    "totalitems": TOTAL_ITEMS,
    "items": TOTAL_ITEMS,
    "totalnsf": TOTAL_ITEMS,
    "itemspaid": PAID_ITEMS,
    "paiditems": PAID_ITEMS,
    "paid": PAID_ITEMS,
    "numberofitemspaid": PAID_ITEMS,
    # 1840 FNB KY (2026-09-28 extract): Items = Paid Annualized + Returned
    # Annualized on every account (12,919 = 10,379 + 2,540), so these are
    # the item counts under another name.
    "paidannualized": PAID_ITEMS,
    "returneditems": RETURNED_ITEMS,
    "returned": RETURNED_ITEMS,
    "returnedannualized": RETURNED_ITEMS,
    "odlimit": OD_LIMIT,
    "overdraftlimit": OD_LIMIT,
    "limitod": OD_LIMIT,
    "statcode": STAT_CODE,
    "odcode": STAT_CODE,
    "prodcode": PRODUCT_CODE,
    "productcode": PRODUCT_CODE,
    "business?": BUSINESS_FLAG,
    "business": BUSINESS_FLAG,
    "businessflag": BUSINESS_FLAG,
    "regeflag": REG_E_FLAG,
    "rege": REG_E_FLAG,
    "acctstat": ACCOUNT_STATUS,
    "accountstatus": ACCOUNT_STATUS,
    "opstatus": ACCOUNT_STATUS,
    "dateopen": OPEN_DATE,
    "opendate": OPEN_DATE,
    "avgbal": AVG_BALANCE,
    "avgcolbal": AVG_BALANCE,
    "averagecollectedbalance": AVG_BALANCE,
    "#ofdeposits": DEPOSIT_COUNT,
    "numberofdeposits": DEPOSIT_COUNT,
    "deps": DEPOSIT_COUNT,
    "nbrdeplastmonth": DEPOSIT_COUNT,
    "depsamt": DEPOSIT_AMOUNT,
    "deps_amt": DEPOSIT_AMOUNT,
    "depositamount": DEPOSIT_AMOUNT,
    "amountdeplastmonth": DEPOSIT_AMOUNT,
    "monthlydeposits": DEPOSIT_AMOUNT,
    "oditems(nowaivers)": OD_ITEMS,
    "oditemsnowaivers": OD_ITEMS,
    "oditems": OD_ITEMS,
    "nsfitems(nowaivers)": NSF_ITEMS,
    "nsfitemsnowaivers": NSF_ITEMS,
    "nsfitems": NSF_ITEMS,
    "paiditemfeeytd": PAID_FEE_YTD,
    "returnitemfeeytd": RETURN_FEE_YTD,
    "paiditemfeelyr": PAID_FEE_LYR,
    "returnitemfeelyr": RETURN_FEE_LYR,
}

REQUIRED_COLUMNS = [
    ACCT_NO, ACCOUNT_STATUS, BUSINESS_FLAG, STAT_CODE,
    TOTAL_ITEMS, PAID_ITEMS,
]


def to_canonical(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Rename columns to canonical names. Returns (df, changed, unmapped).

    Refuses a collision rather than creating it. Three raw spellings map to
    Business Flag; a file carrying two of them used to produce two columns of
    that name, and the failure surfaced later as a pandas reindex error from
    inside a segment filter, naming neither column. Which of the two is
    authoritative is the client's answer, not a guess this module can make.
    """
    rename_map: dict[str, str] = {}
    for col in df.columns:
        normalized = _norm(col)
        rename_map[col] = _ALIAS_MAP.get(normalized, col)

    collisions: dict[str, list[str]] = {}
    for raw, canonical in rename_map.items():
        collisions.setdefault(canonical, []).append(raw)
    clashing = {c: raws for c, raws in collisions.items() if len(raws) > 1}
    if clashing:
        detail = "; ".join(f"{c!r} <- {raws}" for c, raws in sorted(clashing.items()))
        raise ValueError(
            f"Two or more raw columns map to the same canonical name: {detail}. "
            f"Drop or rename the one that is not authoritative before running; "
            f"keeping both would silently pick one.")

    changed = [(old, new) for old, new in rename_map.items() if old != new]
    df = df.rename(columns=rename_map)

    canonical_values = set(_ALIAS_MAP.values())
    unmapped = [c for c in df.columns if c not in canonical_values]

    return df, changed, unmapped


def resolve_data_file(data_root: Path, client_id: str, period: str) -> Path:
    """
    Find the one-time data extract for a client/period under:
        {data_root}\\{period}\\{client_id}\\{client_id}_OneTimeData_*.{csv,xlsx}

    period is YYYY-MM, matching the ARS convention.
    """
    from ils_pipeline.kickoff_input import client_dir as _client_dir
    client_dir = _client_dir(data_root, client_id, period)
    if not client_dir.exists():
        raise FileNotFoundError(f"No data folder for client {client_id}, period {period}: {client_dir}")

    candidates = sorted(set(
        list(client_dir.glob("*OneTimeData*.csv"))
        + list(client_dir.glob("*OneTimeData*.xlsx"))
    ))
    if not candidates:
        raise FileNotFoundError(f"No OneTimeData file found in {client_dir}")
    # Newest by the date in the filename, matching pre_go_live next door. The
    # old order took the FIRST alphabetically, so 20260901 beat 20261001 and a
    # client who sent a corrected extract got the superseded one -- reported as
    # a clean run. An undated file sorts below every dated one rather than
    # winning on name length.
    return max(candidates, key=lambda p: (_stamp(p.name), p.name))


_STAMP_RE = re.compile(r"(20\d{6})")


def _stamp(name: str) -> str:
    """The YYYYMMDD in a filename, or '' so undated files sort below dated."""
    m = _STAMP_RE.search(name)
    return m.group(1) if m else ""


def load_client_data(data_root: Path, client_id: str, period: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Load and canonicalize a client's one-time ILS data extract.
    Returns (df, warnings).
    """
    warnings: list[str] = []
    path = resolve_data_file(data_root, client_id, period)

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    else:
        df = pd.read_excel(path)

    df, changed, unmapped = to_canonical(df)
    if unmapped:
        warnings.append(_unmapped_detail(df, unmapped))

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(
            f"Missing required column(s) after canonicalization: {missing}. "
            f"Add the raw spelling to _ALIAS_MAP in core/io.py."
        )

    # Coerce the numeric fields analyses depend on.
    for col in [TOTAL_ITEMS, PAID_ITEMS, RETURNED_ITEMS, OD_LIMIT,
                DEPOSIT_COUNT, DEPOSIT_AMOUNT, SWIPES, AVG_BALANCE, TRANS_AMT,
                OD_ITEMS, NSF_ITEMS, PAID_FEE_YTD, RETURN_FEE_YTD,
                PAID_FEE_LYR, RETURN_FEE_LYR]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    blank = blank_item_columns(df)
    if blank:
        warnings.append(_blank_items_detail(df, blank))

    df.attrs["source_path"] = str(path)
    df.attrs["client_id"] = client_id
    df.attrs["period"] = period
    return df, warnings


# Item counts some extracts carry only as a calculation from fees (1842,
# 2026-09-01: Items / Paid / Returned blank on all 5,554 rows; "Paid Items #
# Calc" holds 117.67 on one account). Never read unless the run is told to.
_CALC_ITEMS = {"paiditems#calc": PAID_ITEMS, "returneditems#calc": RETURNED_ITEMS}


def blank_item_columns(df: pd.DataFrame) -> list[str]:
    """The item columns that are present but blank on every row."""
    return [c for c in (TOTAL_ITEMS, PAID_ITEMS, RETURNED_ITEMS)
            if c in df.columns and not df[c].notna().any()]


def _calc_columns(df: pd.DataFrame) -> dict[str, str]:
    """{canonical item column: raw '# Calc' column} for those the file carries."""
    return {_CALC_ITEMS[_norm(c)]: c for c in df.columns if _norm(c) in _CALC_ITEMS}


def _blank_items_detail(df: pd.DataFrame, blank: list[str]) -> str:
    calc = _calc_columns(df)
    msg = (f"Item counts are blank on every row: {blank}. Every NSF, pay-rate and "
           f"item analysis would read zero.")
    if calc:
        sums = ", ".join(f"{raw!r} (sum {pd.to_numeric(df[raw], errors='coerce').sum():,.0f})"
                         for raw in calc.values())
        msg += (f" The file carries {sums}: estimates calculated from fees, not counted "
                f"items. Ask the client for the counted items, or run with "
                f"--items-from-calc to use the estimates, labelled as such.")
    return msg


def resolve_item_columns(df: pd.DataFrame, items_from_calc: bool = False) -> list[str]:
    """Refuse a file whose item counts are blank, or, on request, fill them from
    the '# Calc' estimates. Returns the warnings to carry onto the deck."""
    blank = blank_item_columns(df)
    if not blank:
        return []
    calc = _calc_columns(df)
    if not (items_from_calc and PAID_ITEMS in calc):
        raise ValueError(_blank_items_detail(df, blank))
    for canonical, raw in calc.items():
        df[canonical] = pd.to_numeric(df[raw], errors="coerce").fillna(0)
    if RETURNED_ITEMS not in df.columns:
        df[RETURNED_ITEMS] = 0.0
    df[TOTAL_ITEMS] = df[PAID_ITEMS] + df[RETURNED_ITEMS]
    used = ", ".join(repr(r) for r in calc.values())
    return [f"ESTIMATED ITEM COUNTS: the extract's item columns {blank} were blank, so "
            f"Paid / Returned Items were taken from {used} and Total Items = paid + returned "
            f"({df[TOTAL_ITEMS].sum():,.0f}). These are calculated from fees, not counted, and "
            f"are not whole numbers. Where the warnings call {used} unread, they are read here. "
            f"Confirm with the client before this deck is shown."]


def personal_open(df: pd.DataFrame, codes: CodeConfig) -> pd.DataFrame:
    """Filter to personal, open accounts per the given code config."""
    return df[
        (df[BUSINESS_FLAG] == codes.personal_code) & (df[ACCOUNT_STATUS] == codes.open_status_code)
    ].copy()


def business_open(df: pd.DataFrame, codes: CodeConfig) -> pd.DataFrame:
    """Filter to business, open accounts per the given code config."""
    return df[
        (df[BUSINESS_FLAG] == codes.business_code) & (df[ACCOUNT_STATUS] == codes.open_status_code)
    ].copy()


def segment_warnings(df: pd.DataFrame, codes: CodeConfig) -> list[str]:
    """Do the two segments account for every OPEN account?

    personal_open and business_open each match one exact code, so an open
    account whose flag is blank, lower-cased, or spelled the notebook's older
    way ('Personal' / 'Business') lands in neither and used to vanish without
    trace -- every tab still rendering, on a fraction of the book.

    Closed accounts are excluded by design and are not reported.
    """
    if BUSINESS_FLAG not in df.columns or ACCOUNT_STATUS not in df.columns:
        return []

    open_rows = df[df[ACCOUNT_STATUS] == codes.open_status_code]
    if open_rows.empty:
        return []

    known = {codes.personal_code, codes.business_code}
    stray = open_rows[~open_rows[BUSINESS_FLAG].isin(known)]
    if stray.empty:
        return []

    seen = sorted({str(v) for v in stray[BUSINESS_FLAG].unique()})[:10]
    return [
        f"{len(stray)} of {len(open_rows)} open accounts are in neither segment: "
        f"their {BUSINESS_FLAG} is none of {sorted(known)}. Values found: {seen}. "
        f"Every personal/business table below is computed without them -- set "
        f"personal_code/business_code for this client before presenting it."
    ]


_CLIENT_DIR_RE = re.compile(r"^\d{4}$")


def check_output_dir(client_id: str, output_dir: Path) -> Path:
    """Refuse to write one client's output into another client's folder.

    Ran 1840 with `--output-dir ...\\2026-09\\1842` and the workbook and deck
    landed in 1842's directory, named for 1840, with no warning. The filename
    carrying the right id is not a defence: the folder is what a person
    browses by, and two clients' files in one directory is the worst thing
    this tool can produce.

    Only a bare four-digit path segment counts as a client id, so `2026-09`
    and any scratch directory pass untouched.
    """
    for part in Path(output_dir).parts:
        if _CLIENT_DIR_RE.match(part) and part != str(client_id):
            raise ValueError(
                f"Refusing to run client {client_id} into a folder that "
                f"belongs to client {part}: {output_dir}. Point --output-dir "
                f"at {client_id}'s folder, or omit it and one will be derived.")
    return Path(output_dir)


def default_output_dir(root: Path, client_id: str, period: str) -> Path:
    """Where this client's output goes when nobody says otherwise."""
    return Path(root) / "03-Output" / "ILS" / period / str(client_id)


def field_summary(df: pd.DataFrame, limit: int = 12) -> dict:
    """The distinct values of every column a code decision depends on.

    The first call of a kickoff run should return this, not numbers. Which
    value means personal, which means open, and which Stat Code means Reg-E
    eligible are the client's answers, and the defaults came from one
    notebook for one client -- on 1840 the Reg-E rule matched 0 of 4,559
    accounts because nobody was asked. Same reasoning as pre_go_live's
    two-step flow.
    """
    out = {}
    for col in (BUSINESS_FLAG, ACCOUNT_STATUS, STAT_CODE, PRODUCT_CODE,
                REG_E_FLAG):
        if col not in df.columns:
            out[col] = None                      # absent, not empty
            continue
        counts = df[col].astype(str).value_counts()
        out[col] = [[value, int(n)] for value, n in
                    list(counts.items())[:limit]]
    return out


def summarise_fields(df: pd.DataFrame) -> str:
    """field_summary as text, for a caller that can only return a string."""
    lines = [f"{len(df):,} rows in the extract.", "",
             "Confirm these before the run -- they decide who is counted:"]
    for col, values in field_summary(df).items():
        if values is None:
            lines.append(f"  {col}: COLUMN ABSENT")
            continue
        shown = ", ".join(f"{v!r} ({n:,})" for v, n in values)
        lines.append(f"  {col}: {shown}")
    lines += ["",
              "Ask which value means personal, which means business, which "
              "means an OPEN account, and which Stat Code(s) mean OD-eligible. "
              "Never choose them yourself.",
              "",
              "Eligibility is the OD Status (Stat Code). Reg E Flag is a "
              "SEPARATE variable -- whether the member opted in -- and is not "
              "an eligibility rule. The kickoff cross-tabs one by the other; "
              "it does not derive either from the other."]
    return "\n".join(lines)


def rege_warnings(df: pd.DataFrame, codes: CodeConfig) -> list[str]:
    """Is the Reg E opt-in mapping confirmed, and does it cover the column?

    Reg E Flag is not an eligibility rule -- it is whether the member opted
    in -- and which value means that is the client's answer. Two ways it goes
    wrong, and both used to pass silently:

      - nobody confirmed the mapping, so the tab shows raw codes and a reader
        assumes "Y" means yes
      - a mapping was confirmed on one client and a second client uses a
        value neither list mentions, so those accounts are counted as neither
    """
    if REG_E_FLAG not in df.columns:
        return []
    present = df[REG_E_FLAG].astype(str).str.strip()
    values = sorted(v for v in present.unique() if v and v.lower() != "nan")
    if not values:
        return []

    if not codes.rege_opt_in:
        return [f"Reg E opt-in not confirmed. The column holds {values}; "
                f"which of those mean the member OPTED IN is the client's "
                f"answer, and nothing here assumes one. Reg E tables show the "
                f"raw values until it is set."]

    # Opt-in is the only question worth asking: there are one or two opted-in
    # values and everything else is opted out by definition (James,
    # 2026-09-09). Asking for the complement made the operator enumerate a
    # list they do not think in, and every value they forgot became an
    # account counted as neither.
    return []


def pay_rate_warnings(df: pd.DataFrame, unmapped=()) -> list[str]:
    """Is every item paid, or is the total actually the paid column?

    1840 reported a 100% pay rate on every table -- "This doesn't make
    sense. There are returned fees." It does not: a book with return fees
    has returned items. Total Items and Paid Items resolving to the same
    underlying column produces exactly this, and 1840's load left
    "OD Items (No Waivers)", "NSF Items (No Waivers)" and the return-fee
    columns unmapped, which is where the returns most likely are.

    Reported, not corrected: which column is the true total is the client's
    answer, and guessing it is what produced the 100%.
    """
    if PAID_ITEMS not in df.columns:
        return []
    total, source = true_item_total(df)
    if total is None:
        return []
    paid = pd.to_numeric(df[PAID_ITEMS], errors="coerce").fillna(0)
    if total.sum() <= 0 or paid.sum() < total.sum():
        return []
    if source != TOTAL_ITEMS:
        # The waiver-excluded columns were used and STILL every item is paid.
        # That is a real finding about the book, not a mapping symptom.
        return [f"Pay rate is 100% using {source} ({int(total.sum()):,} items) "
                f"as the denominator, not Total Items. Every item presented "
                f"was paid. Worth confirming with the client, but this is the "
                f"book, not a column mix-up."]

    returned = (pd.to_numeric(df[RETURNED_ITEMS], errors="coerce").fillna(0).sum()
                if RETURNED_ITEMS in df.columns else 0)
    candidates = []
    for c in unmapped:
        if not any(w in str(c).lower() for w in ("item", "return", "nsf", "od")):
            continue
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce")
            if v.notna().sum():
                candidates.append((str(c), float(v.sum())))
    lines = [
        f"PAY RATE IS 100% AND PROBABLY WRONG.",
        f"  what the run used:  Total Items = {int(total.sum()):,}, "
        f"Paid Items = {int(paid.sum()):,}. Identical, so every pay rate on "
        f"every slide reads 100%.",
    ]
    if returned:
        lines.append(f"  what contradicts it: the extract also reports "
                     f"{int(returned):,} returned items. A book cannot pay "
                     f"every item and return {int(returned):,} of them.")
    if candidates:
        lines.append("  columns nothing reads that may be the real total:")
        for col, value in candidates:
            lines.append(f"      {col} = {value:,.0f}")
    lines += [
        "  what it means: Total Items has almost certainly resolved to the "
        "paid column, so the denominator is the numerator.",
        "  what to do: confirm with the client which column is the true item "
        "total, then add its spelling to _ALIAS_MAP in core/io.py. Until "
        "then, ignore every pay rate in this deck -- the account and deposit "
        "figures beside them are unaffected.",
    ]
    return ["\n".join(lines)]


def _unmapped_detail(df: pd.DataFrame, unmapped: list) -> str:
    """What the columns nothing reads actually contain.

    "Unmapped columns kept as-is" told an operator a fact and left them with
    a question (James, 2026-09-09). These columns are in the frame and NO
    analysis reads them -- they are carried, not used. Whether that matters
    depends on what is in them, so say what is in them.
    """
    parts = []
    for col in unmapped:
        series = df[col]
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum():
            parts.append(f"{col} (sum {numeric.sum():,.0f})")
        else:
            parts.append(f"{col} ({series.notna().sum():,} non-empty)")
    return (f"{len(unmapped)} column(s) in the file that NO analysis reads: "
            + "; ".join(parts)
            + ". They are carried through untouched. If one of these is the "
              "real item total, the fee income, or anything else worth "
              "reporting, add its spelling to _ALIAS_MAP in core/io.py or say "
              "so and it becomes a new analysis.")


def true_item_total(df: pd.DataFrame) -> tuple[pd.Series, str] | tuple[None, str]:
    """The presented-item total, preferring the columns that exclude waivers.

    OD Items (No Waivers) + NSF Items (No Waivers) is the real presented
    total on extracts that carry them (James, 2026-09-09). Total Items is the
    fallback, and on 1840 it had resolved to the paid column -- which is why
    every pay rate read 100%.

    Returns the series and the name of what it used, so the run can SAY which
    denominator produced the number rather than leaving it inferred.
    """
    have = [c for c in (OD_ITEMS, NSF_ITEMS) if c in df.columns]
    if have:
        total = sum(pd.to_numeric(df[c], errors="coerce").fillna(0) for c in have)
        if total.sum() > 0:
            return total, " + ".join(have)
    if TOTAL_ITEMS in df.columns:
        return pd.to_numeric(df[TOTAL_ITEMS], errors="coerce").fillna(0), TOTAL_ITEMS
    return None, "no item column"


def fee_income(df: pd.DataFrame) -> dict:
    """Fee income by kind. A fee is not an item -- kept apart on purpose."""
    out = {}
    for label, col in (("paid item fees, YTD", PAID_FEE_YTD),
                       ("returned item fees, YTD", RETURN_FEE_YTD),
                       # LYR: last year or last rolling twelve is UNCONFIRMED
                       # (James, 2026-09-09). Labelled as the prior period so
                       # nobody reads a calendar year off a rolling window.
                       ("paid item fees, prior period (LYR)", PAID_FEE_LYR),
                       ("returned item fees, prior period (LYR)", RETURN_FEE_LYR)):
        if col in df.columns:
            v = pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
            if v:
                out[label] = float(v)
    return out


def item_column_relationships(df: pd.DataFrame) -> list[str]:
    """What the item columns actually are, read off the data.

    The working understanding is that OD Items is paid and NSF Items is
    returned, and that the two sum to the presented total (James,
    2026-09-09) -- but it is unconfirmed, and this is exactly the kind of
    assumption that produced a 100% pay rate. So the run measures it and
    reports what it found, and whoever asks the client arrives with numbers
    rather than a recollection.
    """
    def col(name):
        return (pd.to_numeric(df[name], errors="coerce").fillna(0)
                if name in df.columns else None)

    od, nsf = col(OD_ITEMS), col(NSF_ITEMS)
    paid, returned, total = col(PAID_ITEMS), col(RETURNED_ITEMS), col(TOTAL_ITEMS)
    if od is None or nsf is None:
        return []

    lines = [f"Item columns as this extract actually holds them:",
             f"  OD Items {od.sum():,.0f} + NSF Items {nsf.sum():,.0f} "
             f"= {od.sum() + nsf.sum():,.0f}"]

    def verdict(a, b, a_name, b_name):
        if b is None:
            return f"  {b_name}: not in this extract"
        if a.equals(b):
            return f"  {a_name} == {b_name} exactly, row for row"
        gap = (a.sum() - b.sum())
        return (f"  {a_name} {a.sum():,.0f} vs {b_name} {b.sum():,.0f} "
                f"-- differ by {gap:,.0f}")

    lines.append(verdict(od, paid, "OD Items", "Paid Items"))
    lines.append(verdict(nsf, returned, "NSF Items", "Returned Items"))
    if total is not None:
        lines.append(verdict(od + nsf, total, "OD + NSF", "Total Items"))
    lines.append("  Take these to the client: if OD Items is paid and NSF "
                 "Items is returned, the first two lines agree exactly. If "
                 "they do not, the working assumption is wrong.")
    return ["\n".join(lines)]
