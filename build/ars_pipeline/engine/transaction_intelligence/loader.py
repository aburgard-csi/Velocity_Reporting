"""Transaction-file loader.

What the files look like (1615, issue #5):

    line 1   pipe-delimited banner:  1615|4/5/2026 7:16:16 AM||31004|Monthly Transaction File|6.0.6.0
    lines 2+ tab-delimited, headerless, positional columns

Positional column order is the legacy contract (txn_setup/04). A file may
carry 12 or 13 of them; names are assigned by position and the count is
reported, never assumed.

Files accumulate per client under 01-Data/Txn Files/{client}/ with the file
date in the name: 1615_31004_[2026.04.05][07.16.16]_monthly_transactions_file_(debit).txt
A file dated the 5th of a month carries the prior month's transactions.

Design rules, learned from where v4 fell over:
  - never hold a raw file in memory as text; pandas reads it in chunks
  - each raw file is cached once as parquet, LOCALLY under 03-Output/_cache,
    keyed by name + mtime + size; a re-delivered file misses and re-reads
  - only the columns the analysis needs are kept; strings become categories
  - nothing here touches a network drive; the files are wherever 01-Data is
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

try:
    from rpe_env import open_txn          # build/rpe_env.py: the zip member, read in place
except ImportError:                       # pragma: no cover - only when build/ is not on the path
    import sys as _sys
    _sys.path.append(str(Path(__file__).resolve().parents[3]))
    from rpe_env import open_txn

from .txn_common import norm_accounts
from .merchant import merchant_key

CACHE_VERSION = 7  # v7: account ids normalised at read (norm_accounts); v6: QUOTE_NONE
                   # bump when the cached frame's columns OR the parse change

COLUMNS = ["transaction_date", "primary_account_num", "transaction_type", "amount",
           "mcc_code", "merchant_name", "terminal_location_1", "terminal_location_2",
           "terminal_id", "merchant_id", "institution", "card_present",
           "transaction_code"]
KEEP = ["transaction_date", "primary_account_num", "transaction_type", "amount",
        "mcc_code", "merchant_name", "merchant_id", "card_present"]

CHUNK_ROWS = 250_000
FILE_DATE_RE = re.compile(r"\[(\d{4})\.(\d{2})\.(\d{2})\]")
# The unbracketed M-D-YY a client may use: ..._9-8-25.txt, ..._10-7-25.txt.
# Anchored to a separator and the extension so it cannot swallow part of an
# account number or a client id.
LOOSE_DATE_RE = re.compile(r"[_ -](\d{1,2})-(\d{1,2})-(\d{2})(?=\D*$)")
# "tran" covers transaction(s), monthlytran, trandata, debit_card_trans etc.
TXN_NAME_RE = re.compile(r"tran", re.I)
# ...but a deposits extract is NOT a transaction file, however it is named.
# The rolling-365 deposits file lands in the same folder often enough that it
# is worth excluding by name: it is millions of rows of a different shape, and
# parsing it positionally produces garbage rather than an error.
NOT_TXN_RE = re.compile(r"depos", re.I)
TXN_DIRS = ("Txn Files", "TXN Files", "txn", "TXN")


@dataclass
class LoadReport:
    files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    cached: int = 0
    read: int = 0
    rows: int = 0
    columns_found: int | None = None
    banner_lines: int = 0
    warnings: list[str] = field(default_factory=list)
    short: list[str] = field(default_factory=list)   # files that parsed short


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def file_date(path: Path) -> pd.Timestamp | None:
    """The delivery date in the file's name, in either shape we have seen.

    The bracketed [YYYY.MM.DD] form is the core's own. RALLY sends
    `1100_507_combined transaction_9-8-25.txt` instead -- M-D-YY, no brackets
    -- and twelve of those were skipped as undated, which left the whole
    transaction chapter empty.

    M-D-YY is read as US month-first. That is an assumption, but a checked
    one: the same client's deposits extract is named 8-1-25to7-31-26, a range
    that only parses as 1 Aug 2025 to 31 Jul 2026.
    """
    m = FILE_DATE_RE.search(path.name)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = LOOSE_DATE_RE.search(path.name)
    if m:
        month, day, year = (int(g) for g in m.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return pd.Timestamp(2000 + year, month, day)
    return None


def _data_name(p: Path) -> str:
    """The transaction file's own name: `X.txt` for `X.txt.zip` (files are stored zipped)."""
    return p.name[:-4] if p.suffix.lower() == ".zip" else p.name


def find_txn_dirs(data_root: Path, client_id: str) -> list[Path]:
    """The client's transaction folder under the pipeline root: `Inputs/Txn Files/<id>/`,
    the one place rpe_env files them (INPUT_KIND_DIRS["Txn"]). v5 searched several legacy
    spellings; the pipeline has one."""
    d = Path(data_root) / "Inputs" / "Txn Files" / str(client_id)
    return [d] if d.is_dir() else []


def find_txn_dir(data_root: Path, client_id: str) -> Path | None:
    """Back-compat single-dir lookup (first hit)."""
    dirs = find_txn_dirs(data_root, client_id)
    return dirs[0] if dirs else None


def discover(txn_dir: Path | list[Path], months: int, anchor: pd.Timestamp | None, rpt: LoadReport) -> list[Path]:
    """Transaction files, newest `months` by file date, oldest first.

    Accepts one folder or several (canonical layout = one folder per month)."""
    dirs = txn_dir if isinstance(txn_dir, (list, tuple)) else [txn_dir]
    files = []
    seen_names: set[str] = set()
    dup_names: list[str] = []
    # dirs arrive canonical-layout first (TXN/{month}/), legacy last -- during
    # the migration window the SAME file can sit in both places; load it once,
    # preferring the canonical copy.
    for d in dirs:
        for p in sorted(d.iterdir()):
            if not (p.is_file() and _data_name(p).lower().endswith((".txt", ".csv"))
                    and TXN_NAME_RE.search(p.name) and not p.name.startswith("~$")):
                continue
            if p.suffix.lower() != ".zip" and p.with_name(p.name + ".zip").exists():
                continue            # the zipped copy is the one rpe_env reads
            if NOT_TXN_RE.search(p.name):
                rpt.skipped.append(f"{p.name} (deposits extract, not transactions)")
                continue
            if p.name in seen_names:
                dup_names.append(p.name)
                continue
            seen_names.add(p.name)
            files.append(p)
    if dup_names:
        rpt.warnings.append(
            f"{len(dup_names)} file(s) present in both the new TXN layout and "
            f"the legacy folder -- loaded ONCE (canonical copy wins): {dup_names[:3]}")
    dated = [(file_date(p), p) for p in files]
    undated = [p.name for d, p in dated if d is None]
    if undated:
        rpt.warnings.append(f"{len(undated)} transaction file(s) without a "
                            f"[YYYY.MM.DD] date in the name, skipped: {undated[:3]}")
    dated = sorted((d, p) for d, p in dated if d is not None)
    if anchor is not None:
        # A file dated in month M carries month M-1. Keep the files whose
        # DATA month falls in [anchor - (months-1), anchor]; anything newer
        # than the anchor is left out too -- the window ends where the ODD does.
        anchor_idx = anchor.year * 12 + anchor.month
        lo, hi = anchor_idx - (months - 1), anchor_idx
        kept, skipped = [], []
        for d, p in dated:
            data_idx = d.year * 12 + d.month - 1
            (kept if lo <= data_idx <= hi else skipped).append((d, p))
        rpt.skipped.extend(p.name for _, p in skipped)
        newer = [p.name for d, p in skipped if d.year * 12 + d.month - 1 > hi]
        if newer:
            rpt.warnings.append(f"{len(newer)} transaction file(s) newer than the ODD "
                                f"data month left out of the window: {newer[:2]}")
    else:
        kept = dated[-months:]
        rpt.skipped.extend(p.name for d, p in dated[:-months])
    return [p for _, p in kept]


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

MAX_PREAMBLE = 5
MIN_TABLE_DELIMS = 5

# Named-header layouts (1585, issue #16) map columns by header text, not
# position. The account column's header cell is a raw hash in that export,
# caught by _HASH_HEADER_RE below.
HEADER_MAP = {
    "DDA POSTING DATE": "transaction_date", "POSTING DATE": "transaction_date",
    "TRANSACTION DATE": "transaction_date", "DATE": "transaction_date",
    "PRIMARY ACCOUNT NUMBER": "primary_account_num",
    "ACCOUNT NUMBER": "primary_account_num",
    "DDA ACCOUNT": "primary_account_num",              # 1441 FNB Alaska (2026-09-29)
    "TRANSACTION TYPE": "transaction_type",
    "EXTERNAL TRANSACTION CODE": "transaction_type",   # 1441: CHK / PIN / SIG; a SECOND one is the code
    "DESCRIPTION1": "merchant_name", "DESCRIPTION 1": "merchant_name", "DESCRIPTION": "merchant_name",
    "INSTITUTION NUMBER": "institution",
    "TRANSACTION AMOUNT": "amount", "AMOUNT": "amount",
    "MCC CODE": "mcc_code", "MCC": "mcc_code",
    "MERCHANT NAME": "merchant_name",
    "TERMINAL LOCATION 1": "terminal_location_1",
    "TERMINAL LOCATION 2": "terminal_location_2",
    "TERMINAL ID NUMBER": "terminal_id",
    "MERCHANT ID NUMBER": "merchant_id",
    "INSTITUTION": "institution",
    "CARD PRESENT TRANSACTION": "card_present",
    "DDA TRAN CODE": "transaction_code", "TRAN CODE": "transaction_code",
}
# Header cells whose presence marks a line as a NAMED header row (a data
# cell can never equal one of these).
_HEADER_MARKERS = {"TRANSACTION TYPE", "TRANSACTION AMOUNT",
                   "DDA POSTING DATE", "MCC CODE", "MERCHANT NAME", "DDA ACCOUNT"}
_HASH_HEADER_RE = re.compile(r"^[0-9A-F]{20,}$")


def _names_from_header(cells: list[str]) -> list[str]:
    names = []
    for i, cell in enumerate(cells):
        u = str(cell).strip().upper()
        if u in HEADER_MAP:
            name = HEADER_MAP[u]
            if name == "transaction_type" and "transaction_type" in names:
                name = "transaction_code"      # 1441 carries External Transaction Code twice
            names.append(name)
        elif _HASH_HEADER_RE.fullmatch(u):
            names.append("primary_account_num")
        else:
            names.append(f"extra_{i}")
    if "merchant_name" not in names and "terminal_location_1" in names:
        # 1585 carries no Merchant Name column; the description lives in
        # Terminal Location 1 (city / phone in Terminal Location 2)
        names[names.index("terminal_location_1")] = "merchant_name"
    return names


def _sniff(path: Path) -> tuple[int, str, list[str] | None]:
    """(lines to skip, delimiter, header names or None).

    Layouts seen: 1615 = one pipe banner then headerless positional tab
    rows; 1585 (issue #16) = pipe banner + 'Report 1' + a NAMED tab header
    row. The delimiter comes from the LAST sampled line (a data row in
    every layout seen) because the pipe banner itself has 5 pipes.
    Preamble = leading lines without a table's worth of delimiters."""
    with open_txn(path, "r", encoding="latin-1") as fh:
        lines = [fh.readline() for _ in range(MAX_PREAMBLE + 1)]
    lines = [ln for ln in lines if ln]
    probe = lines[-1] if lines else ""
    delim = "\t" if probe.count("\t") >= MIN_TABLE_DELIMS else \
        ("|" if probe.count("|") >= MIN_TABLE_DELIMS else ",")
    skip = 0
    for ln in lines[:MAX_PREAMBLE]:
        if ln.count(delim) >= MIN_TABLE_DELIMS:
            break
        skip += 1
    first_table = lines[skip] if skip < len(lines) else ""
    cells = [c.strip() for c in first_table.rstrip("\n").split(delim)]
    if _HEADER_MARKERS & {c.upper() for c in cells}:
        return skip + 1, delim, _names_from_header(cells)
    return skip, delim, None



def source_lines(path: Path) -> int:
    """Lines in the raw file, counted in blocks so a 5m-row file costs a
    second rather than a gigabyte."""
    n = 0
    try:
        with open_txn(path, "rb") as fh:
            while True:
                block = fh.read(8 * 1024 * 1024)
                if not block:
                    break
                n += block.count(b"\n")
    except OSError:
        return -1
    return n


# A parse that loses more than this share of the file's DATA lines is not a
# parse with some bad rows in it, it is a parse that stopped. Both tests have
# to pass: a share AND an absolute floor, because on a five-line fixture one
# skipped row is 20% and means nothing, while on RALLY the shortfall was 3.3
# to 4.0 million rows a file.
SHORT_READ_TOLERANCE = 0.02
SHORT_READ_FLOOR = CHUNK_ROWS


def is_short(rows: int, lines: int, skip: int = 0) -> bool:
    """Did the parse account for the file. `lines` is raw, `skip` the preamble."""
    data = max(lines - skip, 0)
    if data <= 0:
        return False
    return (rows < data * (1 - SHORT_READ_TOLERANCE)
            and data - rows > SHORT_READ_FLOOR)


def field_widths(path: Path, delim: str, skip: int = 0) -> tuple[int, int, int]:
    """(fields on the first data line, widest line, lines wider than the first).

    The C parser sets the expected width from the first row and treats every
    WIDER line as a bad line, which on_bad_lines="skip" then drops. A file
    stitched from two extracts, the second with an extra column or a trailing
    tab, therefore parses to exactly the first extract and stops, silently
    (#256: nine of RALLY 1100's files, all at 1,500,004 rows). Knowing the
    widest line lets the read declare that width, so nothing is a bad line.
    """
    sep = delim.encode("latin-1")
    first = widest = wider = 0
    try:
        with open_txn(path, "rb") as fh:
            for i, line in enumerate(fh):
                if i < skip:
                    continue
                n = line.count(sep) + 1
                if not first:
                    first = n
                if n > widest:
                    widest = n
                if n > first:
                    wider += 1
    except OSError:
        return 0, 0, 0
    return first, widest, wider


def _cache_path(cache_dir: Path, path: Path) -> Path:
    st = path.stat()
    stem = Path(_data_name(path)).stem
    return cache_dir / f"{stem}.{int(st.st_mtime)}.{st.st_size}.v{CACHE_VERSION}.parquet"


def read_file(path: Path, cache_dir: Path, rpt: LoadReport) -> pd.DataFrame:
    """One raw file -> trimmed frame, via the local parquet cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = _cache_path(cache_dir, path)
    if cached.exists():
        frame = pd.read_parquet(cached)
        if len(frame) and frame["transaction_date"].isna().all():
            # a stale/poisoned cache (e.g. parsed by an older loader) must
            # never mask a readable raw file -- discard and re-read
            rpt.warnings.append(f"{path.name}: cached parquet had no parseable "
                                f"dates -- cache discarded, raw file re-read")
            cached.unlink()
        else:
            # Does the cache actually account for the file it claims to be?
            # The key is name + mtime + size, which says the FILE has not
            # changed -- it says nothing about whether the parse that built
            # the parquet finished. On RALLY nine files of 4-5m lines each sat
            # in cache at exactly 1,500,000 rows and were served that way on
            # every subsequent run, reported only as "12 cached, 0 read".
            lines = source_lines(path)
            skip_n = _sniff(path)[0] if lines > 0 else 0
            if lines > 0 and is_short(len(frame), lines, skip_n):
                rpt.warnings.append(
                    f"{path.name}: cached parquet holds {len(frame):,} rows "
                    f"but the source file has {lines:,} lines "
                    f"({100 * len(frame) / lines:.1f}%). The cache was written "
                    f"from a short read -- discarded and re-reading.")
                cached.unlink()
            else:
                rpt.cached += 1
                return frame

    skip, delim, header_names = _sniff(path)
    if header_names is not None and "primary_account_num" not in header_names:
        # Stated, never silent: every account would read as None and nothing would join the ODD.
        known = ", ".join(n for n in header_names if not n.startswith("extra_")) or "nothing"
        rpt.warnings.append(f"{path.name}: named header carries no account column the loader knows "
                            f"(mapped: {known}); add its name to loader.HEADER_MAP")
    rpt.banner_lines += skip
    parts = []
    ncols = None
    # QUOTE_NONE is not a preference, it is the fix for issue #179. These
    # extracts do not quote fields; the `"` that appear are inches and stray
    # punctuation inside merchant names (`H-E-B 12" PIZZA`). Under the default
    # QUOTE_MINIMAL a `"` at the START of a field opens a quoted field, and
    # every line up to the next `"` in the file is swallowed into it as one
    # value. On RALLY's 1100 that turned 5,533,493 lines into 1,500,004 rows
    # -- silently, because a swallow is not a bad line and on_bad_lines never
    # sees it. An unbalanced quote at EOF raises instead; a balanced pair
    # loses everything between them and says nothing.
    #
    # Declare the WIDEST line's field count up front. Without it the parser
    # takes the first row's width as law and drops every wider line as bad;
    # a file whose rows widen partway then parses to exactly the rows before
    # that point and stops, with nothing to say so (#256).
    first_width, widest, wider = field_widths(path, delim, skip)
    if wider:
        rpt.warnings.append(
            f"{path.name}: {wider:,} line(s) are wider than the first row "
            f"({first_width} fields at the top, up to {widest} later). Read "
            f"with the wider frame; the extra fields are ignored. A file "
            f"stitched from two extracts looks like this.")
    names = list(range(max(widest, 1)))
    for chunk in pd.read_csv(open_txn(path, "rb"), sep=delim, header=None, skiprows=skip,
                             names=names, dtype=str, encoding="latin-1",
                             on_bad_lines="skip", quoting=csv.QUOTE_NONE,
                             chunksize=CHUNK_ROWS, engine="c"):
        if ncols is None:
            ncols = first_width or chunk.shape[1]
        if header_names is not None:
            names = list(header_names) + [f"extra_x{i}" for i in
                                          range(max(0, chunk.shape[1]
                                                    - len(header_names)))]
            chunk.columns = names[:chunk.shape[1]]
        else:
            chunk = chunk.iloc[:, :len(COLUMNS)]
            chunk.columns = COLUMNS[:chunk.shape[1]]
        for col in KEEP:
            if col not in chunk.columns:
                chunk[col] = None
        chunk = chunk[KEEP]
        chunk["amount"] = pd.to_numeric(chunk["amount"], errors="coerce")
        chunk["transaction_date"] = pd.to_datetime(chunk["transaction_date"],
                                                   errors="coerce", format="mixed")
        chunk["merchant_name"] = chunk["merchant_name"].str.strip()
        chunk["primary_account_num"] = norm_accounts(chunk["primary_account_num"]).values
        parts.append(chunk)
    frame = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=KEEP)
    # The raw field is a description; the key is the grouping label.
    frame["merchant_key"] = merchant_key(frame["merchant_name"]).astype("category")
    for col in ("transaction_type", "mcc_code", "merchant_id", "card_present"):
        frame[col] = frame[col].astype("category")
    frame["source_file"] = _data_name(path)
    if rpt.columns_found is None:
        rpt.columns_found = ncols
    elif ncols != rpt.columns_found:
        rpt.warnings.append(f"{path.name}: {ncols} columns, earlier files had "
                            f"{rpt.columns_found}")
    # A parse that lands on an EXACT multiple of the chunk size did not end
    # where the data ended -- it ended where a chunk boundary was. Real files
    # do not have row counts divisible by 250,000. Kept as a cheap backstop,
    # but note it never fired on the incident below: the real counts were
    # 1,500,004, four rows past six chunks, which is why the guard that
    # matters is the source-line comparison underneath it.
    #
    # On RALLY nine of twelve monthly files came back at ~1,500,004 rows from
    # 4.8-5.5m lines and were cached that way. Every later run read the cache,
    # reported "12 cached, 0 read", and nothing said the parse had stopped
    # short. Cause, found by probe_txn_file.py: a quoted-field swallow, fixed
    # by QUOTE_NONE above. The only visible symptom had been a reconciliation
    # warning on the three months that were fine.
    lines = source_lines(path)
    short = lines > 0 and is_short(len(frame), lines, skip)
    if short:
        rpt.short.append(_data_name(path))
        rpt.warnings.append(
            f"{path.name}: READ SHORT -- {len(frame):,} rows parsed from a "
            f"file of {lines:,} lines ({100 * len(frame) / max(lines - skip, 1):.1f}% "
            f"of the data rows). Every figure from this file is understated. "
            f"Not a small month: the parser stopped.")
    elif len(frame) and len(frame) % CHUNK_ROWS == 0:
        rpt.warnings.append(
            f"{path.name}: parsed to exactly {len(frame):,} rows, "
            f"{len(frame) // CHUNK_ROWS} x the {CHUNK_ROWS:,}-row chunk size. "
            f"A real file does not end on a chunk boundary.")

    rpt.read += 1
    if not short:
        # A short frame is never the file. Caching it would serve the short
        # read on every later run as "cached", which is how nine files sat
        # at 1,500,004 rows for weeks.
        tmp = cached.with_suffix(".tmp.parquet")
        frame.to_parquet(tmp, index=False)
        tmp.replace(cached)
    return frame


def load(txn_dir: Path, cache_dir: Path, months: int = 12,
         anchor: pd.Timestamp | None = None) -> tuple[pd.DataFrame, LoadReport]:
    rpt = LoadReport()
    paths = discover(txn_dir, months, anchor, rpt)
    if not paths:
        rpt.warnings.append(f"no transaction files found in {txn_dir}")
        return pd.DataFrame(columns=KEEP), rpt
    frames = []
    for p in paths:
        try:
            frames.append(read_file(p, cache_dir, rpt))
            rpt.files.append(p.name)
        except Exception as exc:
            rpt.warnings.append(f"{p.name}: could not read ({type(exc).__name__}: {exc})")
    if not frames:
        return pd.DataFrame(columns=KEEP), rpt
    df = pd.concat(frames, ignore_index=True)
    for col in ("transaction_type", "mcc_code", "merchant_id", "card_present", "source_file", "merchant_key"):
        df[col] = df[col].astype("category")
    rpt.rows = len(df)
    bad_dates = int(df["transaction_date"].isna().sum())
    if bad_dates:
        rpt.warnings.append(f"{bad_dates:,} rows with an unparseable date, dropped")
        df = df[df["transaction_date"].notna()]
    blank_amounts = int(df["amount"].isna().sum())
    if blank_amounts:
        rpt.warnings.append(f"{blank_amounts:,} rows with a blank/unparseable "
                            f"amount, kept as $0 (they still count as "
                            f"transactions)")
    return df, rpt
