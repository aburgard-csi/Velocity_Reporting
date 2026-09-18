"""Machine-local configuration for the RPE pipelines.

Two things differ between Aaron's Mac and the CSI Windows machine, and both
have failed silently before:

  * The pipeline data root. It is set in .env — the CSI share folder
    \\\\PADMIS105\\Velocity_company\\CSM_Reporting since 2026-09-14 — and cannot be
    hardcoded.

  * Font availability. matplotlib SUBSTITUTES a missing font family rather than
    raising, so a chart renders in the wrong face and nothing tells you. The
    only way to catch it is to check before drawing.

Usage:

    from rpe_env import data_root, inputs, outputs, use_font

    wb = inputs() / "1705-2026.08-CoastLife Credit Union-Workbook_v2_1_0.xlsx"
    use_font("Carlito")

Resolution order for RPE_DATA_ROOT: real environment variable first (so an
agent or CI run can override), then the .env file at the repo root. Absent
from both, or pointing somewhere that isn't a directory, raises.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = REPO_ROOT / "fonts"

_env_cache: dict[str, str] | None = None


def _load_dotenv() -> dict[str, str]:
    """Parse the repo-root .env. Values are taken raw to the end of the line.

    No unescaping: a Windows path like C:\\Data Pipelines\\RPE Pipeline must survive,
    and values contain spaces, so nothing is stripped beyond surrounding
    whitespace and one optional layer of matching quotes.
    """
    global _env_cache
    if _env_cache is not None:
        return _env_cache

    _env_cache = {}
    path = REPO_ROOT / ".env"
    if not path.exists():
        return _env_cache

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        _env_cache[key.strip()] = value

    return _env_cache


def data_root() -> Path:
    """The pipeline folder holding Inputs/, Outputs/ and Build Artifacts/."""
    raw = os.environ.get("RPE_DATA_ROOT") or _load_dotenv().get("RPE_DATA_ROOT")

    if not raw:
        raise SystemExit(
            "RPE_DATA_ROOT is not set.\n"
            f"  Copy {REPO_ROOT / '.env.example'} to {REPO_ROOT / '.env'} and\n"
            "  set it to the pipeline root, e.g.\n"
            "    \\\\PADMIS105\\Velocity_company\\CSM_Reporting"
        )

    root = Path(raw).expanduser()
    if not root.is_dir():
        raise SystemExit(
            f"RPE_DATA_ROOT points at {root!s}, which is not a directory.\n"
            "  If the path looks right, the folder may not exist yet — check "
            "it in Explorer and try again."
        )
    return root


def inputs() -> Path:
    return _require_subdir("Inputs")


def outputs() -> Path:
    return _require_subdir("Outputs")


# ------------------------------------------------------------------ outputs by CSM
# Finished decks are filed in a folder per CSM, `Outputs/<CSM>/` (Aaron, 2026-09-14:
# "sort the Outputs folder by CSM"), now that the project covers all five CSMs' books.
# The archive is `Outputs/_Archive/`: the underscore keeps it at the top of Outputs, above the
# CSM folders (Aaron, 2026-09-15: "add to the archive folder names so they stay at the top,
# above my name"); it was `Outputs/Archive/`, which sorted between "Aaron Burgard" and the rest.
# Readers go through `output_decks()`, which also still reads the flat root, so a deck
# dropped there by hand is found; writers go through `client_outputs()`.
CSM_LIST_NAME = "Client CSM List.csv"
UNASSIGNED_CSM = "_Unassigned"
ARCHIVE_DIRNAME = "_Archive"
_OUTPUT_SKIP_DIRS = {ARCHIVE_DIRNAME, "Archive"}   # the old name too, so a leftover is never read as a CSM
_csm_cache = {}


def csm_list_file() -> Path | None:
    """`<RPE_DATA_ROOT>/Client CSM List.csv` — client id to CSM for every CSM's book.
    `RPE_CSM_LIST` replaces the path (a subprocess test build points it at a synthetic list)."""
    if os.environ.get("RPE_CSM_LIST"):
        return Path(os.environ["RPE_CSM_LIST"])
    try:
        return data_root() / CSM_LIST_NAME
    except SystemExit:
        return None


def client_csm(client_id) -> str | None:
    """The CSM for a client: the Client CSM List, else the CashPlease roster's CSM
    column in clients.md (CashPlease-only clients are not on the reports share the list
    is built from), else None. Never a default CSM: a deck filed under whoever seems
    likely is lost to the CSM who owns it."""
    cid = str(client_id).strip()
    p = csm_list_file()
    key = str(p)
    if key not in _csm_cache:
        found = {}
        if p is not None and p.is_file():
            import csv
            with open(p, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    if (row.get("client_id") or "").strip() and (row.get("csm") or "").strip():
                        found[row["client_id"].strip()] = row["csm"].strip()
        try:
            import sys as _sys
            _scripts = str(REPO_ROOT / "scripts")
            if _scripts not in _sys.path:
                _sys.path.append(_scripts)
            from build_month import read_cashplease_roster
            for r in read_cashplease_roster():
                if r.get("csm"):
                    found.setdefault(r["client_id"], r["csm"])
        except Exception:
            pass
        _csm_cache[key] = found
    return _csm_cache[key].get(cid)


# ------------------------------------------------------------------ the Contact Us card
# Every deck's Contact Us card names the client's MANAGING CSM (Aaron, 2026-09-16: "James's
# name would go on the contact card. The contact card should always show the managing
# CSM."). The builders used to print one CSM's card on every deck, whoever managed the
# client. The card comes from `<RPE_DATA_ROOT>/CSM Contacts.csv` (one row per CSM, taken
# from their email signatures) for the CSM `client_csm` names — and never falls back to
# another CSM: a card naming the wrong person sends the client to the wrong person.
CSM_CONTACTS_NAME = "CSM Contacts.csv"
_contacts_cache = {}


def csm_contacts_file() -> Path:
    """`<RPE_DATA_ROOT>/CSM Contacts.csv`; `RPE_CSM_CONTACTS` replaces the path."""
    if os.environ.get("RPE_CSM_CONTACTS"):
        return Path(os.environ["RPE_CSM_CONTACTS"])
    return data_root() / CSM_CONTACTS_NAME


def format_phone(raw) -> str:
    """'(NNN) NNN-NNNN' -> 'NNN-NNN-NNNN'; an 'ext. N' is kept; '' when blank.
    A number that is not ten digits is returned as written rather than reshaped."""
    raw = str(raw or "").strip()
    if not raw:
        return ""
    m = re.search(r"(?i)\b(?:ext\.?|x)\s*(\d+)\s*$", raw)
    main, ext = (raw[:m.start()], m.group(1)) if m else (raw, "")
    digits = re.sub(r"\D", "", main)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    out = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else main.strip()
    return f"{out} ext. {ext}" if ext else out


def csm_contact(client_id) -> dict:
    """{'name', 'role', 'phone', 'email'} for the client's managing CSM.

    role is the CSM's title; phone is the cell, else the office line (with any extension),
    else '' — the card then has no phone line; email is lowercased. Raises SystemExit with a
    plain sentence when the client has no CSM on file, the contacts file is missing, or the
    CSM has no row (or no title/email) in it. The file is read once per process.
    """
    cid = str(client_id).strip()
    csm = client_csm(cid)
    if not csm:
        raise SystemExit(
            f"Client {cid or '(no id)'} has no managing CSM in {CSM_LIST_NAME}, so its Contact Us "
            f"card cannot be filled. Add the client to the list; the card never names another CSM.")
    return contact_by_name(csm, cid)


# The ICS program's own contact, a second card on standalone ICS decks after the managing CSM
# (Aaron, 2026-09-16: "Add Cindy on ICS"). Her row lives in CSM Contacts.csv like every card.
ICS_PROGRAM_CONTACT = "Cindy Draper"


def contact_by_name(csm, client_id="") -> dict:
    """{'name', 'role', 'phone', 'email'} for the person named `csm` in CSM Contacts.csv (see csm_contact)."""
    cid = str(client_id).strip()
    path = csm_contacts_file()
    key = str(path)
    if key not in _contacts_cache:
        if not path.is_file():
            raise SystemExit(f"{CSM_CONTACTS_NAME} was not found at {path}, so no Contact Us card "
                             f"can be filled for client {cid} ({csm}).")
        import csv
        rows = {}
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("csm") or "").strip()
                if name:
                    rows[name.casefold()] = {k: (v or "").strip() for k, v in row.items() if k}
        _contacts_cache[key] = rows
    row = _contacts_cache[key].get(csm.casefold())
    if row is None:
        raise SystemExit(f"{csm}, the managing CSM for client {cid}, has no row in {CSM_CONTACTS_NAME} "
                         f"({path}). Add their title, phone and email there; the card never falls "
                         f"back to another CSM.")
    missing = [f for f in ("title", "email") if not row.get(f)]
    if missing:
        raise SystemExit(f"{csm}'s row in {CSM_CONTACTS_NAME} has no {' or '.join(missing)}, so the "
                         f"Contact Us card for client {cid} cannot be filled.")
    return {"name": row["csm"], "role": row["title"],
            "phone": format_phone(row.get("cell") or row.get("office")),
            "email": row["email"].lower()}


def client_outputs(client_id, root=None, create=False) -> Path:
    """The folder a client's finished decks are delivered to: `Outputs/<CSM>/`,
    or `Outputs/_Unassigned/` when nothing names the CSM. `root` replaces Outputs/
    (promote_month's --outputs); `create` makes the folder."""
    base = Path(root) if root is not None else outputs()
    csm = re.sub(r'[<>:"/\\|?*]', "", client_csm(client_id) or "").strip()
    d = base / (csm or UNASSIGNED_CSM)
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def output_decks(pattern, root=None) -> list[Path]:
    """Finished files matching `pattern` in Outputs/ and every `Outputs/<CSM>/` folder —
    never the archive (`_Archive/`, or `Archive/` from before), never an Office lock file (`~$`)."""
    base = Path(root) if root is not None else outputs()
    if any(s in pattern for s in ("/", "\\", "**")):
        dirs = [base]
        if base.is_dir():
            dirs += [d for d in sorted(base.iterdir())
                     if d.is_dir() and d.name not in _OUTPUT_SKIP_DIRS and not d.name.startswith(".")]
        hits = [p for d in dirs for p in d.glob(pattern)
                if p.is_file() and not p.name.startswith("~$")]
        return sorted(hits, key=lambda p: (p.name, str(p)))
    # One directory listing per folder, with the file/folder type read from the listing itself: on the
    # share a separate is_dir()/is_file() per entry is a round trip each (2026-09-17). fnmatch folds case
    # on Windows, as glob does.
    import fnmatch
    hits = []
    for d in [base] + _output_csm_dirs(base):
        try:
            with os.scandir(d) as it:
                hits += [d / e.name for e in it
                         if fnmatch.fnmatch(e.name, pattern) and not e.name.startswith("~$") and e.is_file()]
        except OSError:
            continue
    return sorted(hits, key=lambda p: (p.name, str(p)))


def _output_csm_dirs(base) -> list[Path]:
    try:
        with os.scandir(base) as it:
            return [base / e.name for e in sorted(it, key=lambda e: e.name)
                    if e.is_dir() and e.name not in _OUTPUT_SKIP_DIRS and not e.name.startswith(".")]
    except OSError:
        return []


# ------------------------------------------------------------------ input kinds
# One folder per kind of input, sorted on arrival by scripts/watch_sources.py
# (Aaron, 2026-09-09). Everything used to land in one "ARS & MRPC Reports"
# folder: DCOs, ARS workbooks, MRPC analyses, ICS workbooks, ICS Charts and the
# weekly summaries, 55 files deep and growing, with the kind readable only from
# the filename.
#
# THIS MAPPING IS THE ONLY PLACE THE FOLDER NAMES LIVE. Renaming a folder is a
# one-line change here plus a move on disk; every reader and the copier resolve
# through `input_dir()` / `report_dirs()`.
INPUT_KIND_DIRS = {
    "ODDD": "ODDD",                       # <id>_ODDD.zip, from the ODDD share
    "DCO": "DCOs",
    "Workbook": "ARS Workbooks",
    "MRPCPM": "MRPC Analyses",
    "ICS workbook": "ICS Workbooks",
    "ICS charts": "ICS Charts",           # "<Client> Charts 2026.xlsx" — mystery shops
    "weekly": "Weekly Summaries",         # MRPCEnrollmentSummary weeklies
    "CP weekly": "CashPlease",            # CashPleaseSummary weeklies + ILS-DDA-Count-<date>.txt (Aaron, 2026-09-16)
    "CP settings": "Product Settings",    # <id>_cp_settings.json, Velocity Product Settings app
    "ARS codes": "ARS Settings",          # ars_code_tables.json, the ARS database's code tables
    "Code sheets": "Code Sheets",         # clients' code sheets, saved by the data team
    # A client with no VIP ICS sheet (1776 CoastHills CU, Aaron 2026-09-16): the CSM lands the
    # detailed referral export and the direct-mail new-accounts list here by hand, and
    # build/ics_pipeline/ics_local_sheet.py builds the ICS sheet from them.
    "ICS referrals": "ICS Referrals",     # <id>_ics_detailed referral_v<N>.xls
    "ICS direct mail": "ICS Direct Mail", # <id>-<yyyy.mm>-ICS-<Client>-Direct Mail New Accounts Opened PTD.xlsx
    # One row per name a source has given a client's branch number (Aaron, 2026-09-17);
    # kept by the morning source check, read by branch_names.client_map.
    "Branch names": "Branch Names",       # branch_names.csv
    # Clients' monthly debit-card transaction files, one folder per client (`<id>/`), stored
    # zipped (Aaron, 2026-09-17): one .zip per file, named the original plus ".zip". Read them
    # through txn_files() / open_txn(), which take either form.
    "Txn": "Txn Files",
}

# Kinds resolved by exact path, never by scanning for workbook-ish files. Neither
# report_dirs() nor the copier/pruner in watch_sources.py looks inside these.
# The two ICS local-file kinds are hand-landed, carry member-level rows, and have no
# "newer version" the watcher's copier or pruner understands, so neither may touch them.
NOT_SCANNED_KINDS = ("ODDD", "CP settings", "ARS codes", "Code sheets",
                     "ICS referrals", "ICS direct mail", "Branch names", "Txn")

# The flat folder everything used to land in. Kept as a READ location for good:
# a file dropped there by hand still resolves, and the migration does not have to
# be perfect for a build to work. Nothing is written here any more.
LEGACY_REPORTS_DIRNAME = "ARS & MRPC Reports"


def input_dir(kind: str, create: bool = True) -> Path:
    """Where a file of this kind belongs. Unknown kinds go to the legacy folder,
    which is where an unrecognised file would have landed anyway."""
    name = INPUT_KIND_DIRS.get(kind, LEGACY_REPORTS_DIRNAME)
    p = inputs() / name
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def report_dirs() -> list:
    """Every folder that can hold a workbook-ish input, newest scheme first.

    Readers glob across all of them rather than one, so the sort can happen
    incrementally and a stray file in the old folder is still found. `ODDD/` and
    `Product Settings/` are NOT here — both are resolved by exact path.
    """
    I = inputs()
    names = [v for k, v in INPUT_KIND_DIRS.items() if k not in NOT_SCANNED_KINDS]
    names.append(LEGACY_REPORTS_DIRNAME)
    # One listing of Inputs rather than an is_dir() per kind: each is a round trip on the share (2026-09-17).
    fold = str.casefold if os.name == "nt" else (lambda s: s)
    try:
        with os.scandir(I) as it:
            present = {fold(e.name) for e in it if e.is_dir()}
    except OSError:
        return [I / n for n in names if (I / n).is_dir()]
    return [I / n for n in names if fold(n) in present]


def cp_settings_file(client_id):
    """A CashPlease client's production settings, or None when none are on file.

    `Inputs/Product Settings/<id>_cp_settings.json` — one client's record from the
    CashPlease page of the Velocity Product Settings Power BI app, with a `_source`
    key naming the app and its data-updated stamp (Aaron, 2026-09-14). It is a
    snapshot of configuration, not a period's figures, so it carries no period in
    its name and is replaced in place when re-pulled.
    """
    p = inputs() / INPUT_KIND_DIRS["CP settings"] / f"{client_id}_cp_settings.json"
    return p if p.is_file() else None


def report_files(pattern: str = "*") -> list:
    """Every workbook-ish input matching `pattern`, across all report folders.

    Sorted by name so callers that pick a "newest" by string comparison behave
    the same as they did against one folder.
    """
    out = []
    for d in report_dirs():
        out.extend(d.glob(pattern))
    return sorted(out, key=lambda p: p.name)


# ------------------------------------------------------------------ build scratch in the system temp folder
# A build unzips the ODD extract (up to 1.8 GB) and renders images into the system temp
# folder. Those directories were never removed: on 2026-09-16 the C: drive reached 0.11 GB
# free with 1,241 of them (about 180 GB) left over since 2026-08-31, and two builds died with
# "No space left on device". Every build scratch directory now comes from `temp_dir`, which
# removes it when the process exits, and every build starts with `sweep_temp`, which removes
# what a crashed or killed build left behind (Aaron: "make sure temp drive cleanup is part of
# the process").
TEMP_PREFIXES = ("oddd_", "oddcsv_", "ars_assets_", "ars_phase_")
TEMP_MAX_AGE_HOURS = 6      # a build takes minutes; older scratch belongs to no live build


def temp_dir(prefix: str) -> str:
    """A scratch directory in the system temp folder, removed when this process exits."""
    import atexit
    import shutil
    import tempfile
    if not prefix.startswith(TEMP_PREFIXES):
        raise ValueError(f"temp_dir prefix {prefix!r} is not in TEMP_PREFIXES, so sweep_temp would never clean it")
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path


def sweep_temp(max_age_hours: float = TEMP_MAX_AGE_HOURS, root=None, now=None) -> tuple:
    """Remove pipeline scratch directories older than `max_age_hours`. Returns (removed, bytes freed).

    Only directories named with a TEMP_PREFIXES prefix, directly in the temp folder, are touched;
    anything younger than the cutoff may belong to a build still running and is left alone.
    """
    import shutil
    import tempfile
    import time
    root = Path(root or tempfile.gettempdir())
    cutoff = (now or time.time()) - max_age_hours * 3600
    removed = freed = 0
    try:
        entries = list(root.iterdir())
    except OSError:
        return 0, 0
    for d in entries:
        try:
            if not d.is_dir() or not d.name.startswith(TEMP_PREFIXES) or d.stat().st_mtime >= cutoff:
                continue
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            shutil.rmtree(d)
            removed += 1
            freed += size
        except OSError:
            continue            # in use or already gone: the next sweep tries again
    return removed, freed


def extract_odd_csv(zip_path, prefix: str = "oddd_") -> str:
    """Extract ONLY the ODD extract from an ODDD zip into a `temp_dir`, and return its path.

    Several zips also carry the month's transaction file as a .csv, sometimes the larger of the two,
    so the ODD member is chosen by name and only falls back to the largest .csv.
    Extracting the whole zip wrote the transaction file to disk too, for nothing.
    """
    # Which member is the ODD is odd_rows.odd_member's decision, shared by every reader.
    # odd_rows lives in the ARS pipeline (the ODD is an ARS input); imported here lazily so
    # this shared module never depends on it at import time.
    import sys
    _ars = str(REPO_ROOT / "build" / "ars_pipeline")
    if _ars not in sys.path:
        sys.path.append(_ars)
    from odd_rows import extract_odd
    return extract_odd(zip_path, temp_dir(prefix))


# Analysis output written beside the data (1441's output_txn/), not transaction files.
TXN_SKIP_DIRS = ("output_txn",)


def txn_files(client_id=None, root=None) -> list[Path]:
    """Every transaction file on hand, zipped or not, sorted by path.

    `Inputs/Txn Files/<id>/`, or every client's folder when `client_id` is None. A file
    and its `.zip` side by side (the moment between zipping and removing the original)
    are listed once, as the zip. Empty files, `.part` files and anything under
    TXN_SKIP_DIRS are left out.
    """
    base = Path(root) if root is not None else inputs() / INPUT_KIND_DIRS["Txn"]
    if client_id is not None:
        base = base / str(client_id)
    if not base.is_dir():
        return []
    hits = []
    for p in base.rglob("*"):
        rel = p.relative_to(base).parts
        if (not p.is_file() or p.name.endswith(".part") or p.name.startswith("~$")
                or any(d in TXN_SKIP_DIRS for d in rel[:-1])):
            continue
        if p.stat().st_size == 0:
            continue
        if p.suffix.lower() != ".zip" and p.with_name(p.name + ".zip").is_file():
            continue
        hits.append(p)
    return sorted(hits, key=str)


def open_txn(path, mode: str = "rb", encoding: str = "utf-8", errors: str = "replace"):
    """Open a transaction file for reading, whether it is stored zipped or not.

    Takes the `.zip` or the original name: `x.csv` opens `x.csv.zip` when only the zip is
    there, so a caller holding a pre-zip path keeps working. The zip is read in place,
    never extracted to disk. `mode` is "rb" or "r"; "r" decodes with `encoding`/`errors`
    and leaves newlines untranslated, as `open(newline="")` would for the csv module.
    """
    import io
    import zipfile
    if mode not in ("r", "rb"):
        raise ValueError(f"open_txn reads only ('r' or 'rb'), not {mode!r}")
    p = Path(path)
    if p.suffix.lower() != ".zip" and not p.is_file() and p.with_name(p.name + ".zip").is_file():
        p = p.with_name(p.name + ".zip")
    if p.suffix.lower() == ".zip":
        # Closing the ZipFile here is safe: the archive's file handle is shared and
        # reference-counted, so it stays open until the member is closed too.
        with zipfile.ZipFile(p) as z:
            members = [i for i in z.infolist() if not i.is_dir()]
            if len(members) != 1:
                raise ValueError(f"{p} holds {len(members)} files; a transaction zip holds exactly one")
            raw = z.open(members[0])
    else:
        raw = open(p, "rb")
    if mode == "rb":
        return raw
    return io.TextIOWrapper(raw, encoding=encoding, errors=errors, newline="")


BUILD_ARTIFACTS_DIRNAME = "Build Artifacts"


def build_artifacts() -> Path:
    """Where a build drops evidence that is NOT a deliverable.

    `Outputs/` is the delivery folder and holds finished decks only. Provenance
    sidecars, phase files and anything else a build emits to prove itself belong
    here instead (Aaron, 2026-08-29).

    Created on demand — unlike inputs()/outputs(), whose absence means a broken
    mount and must raise. Falls back to a repo-local directory when
    RPE_DATA_ROOT is unset, so a build never fails for want of somewhere to put
    its bookkeeping.
    """
    try:
        path = data_root() / BUILD_ARTIFACTS_DIRNAME
    except SystemExit:
        path = REPO_ROOT / "build_artifacts"
    # The mkdir runs once per folder per process (2026-09-17). On the share every mkdir is a round
    # trip, and CSM Sheila's client list called this once per client: 50 mkdirs, 2.3 s, for a folder
    # that already existed.
    if str(path) in _ARTIFACTS_MADE:
        return path
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return REPO_ROOT / "build_artifacts"
    _ARTIFACTS_MADE.add(str(path))
    return path


_ARTIFACTS_MADE: set = set()


VIP_DATA_DIRNAME = "VIP Data"


def vip_data() -> Path | None:
    """`Inputs/VIP Data/` under RPE_DATA_ROOT, or None if it is not there.

    ICS and MRPC read a per-client JSON (`<id>_ics.json`, `<id>_mrpc.json`)
    assembled from the VIP dashboards — `1075_mrpc.json` names its own source as
    "VIP MyRewards Premium Cards dashboards (Enrollments, Performance,
    Retention, Revenue to FI) + MRPCPM Analysis workbook". It is real client
    data, correctly gitignored, so it does not travel with the repo — which
    means a fresh checkout on the CSI machine has the code and none of the
    ICS/MRPC inputs, and PRD success criterion 1 ("the same client built on both
    machines produces identical decks") is unreachable for two of the three
    programs.

    Unlike inputs()/outputs() this never raises: the folder is a migration
    target, and until every client JSON has moved there the repo-local
    `build/<program>_pipeline/data/` is still a legitimate place to find one.
    resolve_client_json() prefers this and falls back to that.
    """
    try:
        path = data_root() / "Inputs" / VIP_DATA_DIRNAME
    except SystemExit:
        return None
    return path if path.is_dir() else None


VIP_MANIFEST = "manifest.json"


def vip_manifest() -> list | None:
    """The `clients` list from `Inputs/VIP Data/manifest.json`, or None.

    The manifest is the authoritative index of the VIP store: one row per file
    with program, client id, period, pull date and the relative path. Preferred
    over walking the tree because it also records WHICH pull a file is, and two
    copies of a client can differ by pull date.
    """
    root = vip_data()
    if root is None:
        return None
    try:
        with open(root / VIP_MANIFEST, encoding="utf-8") as fh:
            return json.load(fh).get("clients") or None
    except (OSError, ValueError):
        return None


def _client_id_of(arg) -> str:
    """The leading client id in `1705`, `1705_ics.json`, `1705-CoastLife...`."""
    m = re.match(r"(\d{3,5})", os.path.basename(str(arg)))
    return m.group(1) if m else ""


def resolve_client_json(arg, program) -> Path:
    """Find a client's ICS/MRPC data sheet in the VIP store.

    Accepts a path (used as-is when it exists) or a bare `1705_ics.json` / `1705`.

    Search order:

      1. the literal argument, if it exists;
      2. `Inputs/VIP Data/manifest.json` — the authoritative index, which also
         records each file's period and pull date;
      3. `Inputs/VIP Data/<PROGRAM>/<id>-<Name>/<id>_<program>.json`, in case the
         manifest is stale.

    There is NO repo fallback (Aaron, 2026-08-29). `build/<program>_pipeline/data/`
    held copies that drifted: the store carried 2026-08-29 pulls while the repo
    still had 2026-08-10, and a build reading the repo shipped month-old figures
    that validated perfectly because they were internally consistent. Two stores
    for one fact is the problem; `Inputs/VIP Data/` is the fact.
    """
    if not arg:
        raise SystemExit(f"resolve_client_json: no {program} client file given")
    candidate = Path(arg)
    if candidate.exists():
        return candidate

    prog = program.lower()
    cid = _client_id_of(arg)
    name = os.path.basename(str(arg))
    if not name.endswith(".json"):
        name = f"{cid or name}_{prog}.json"

    root = vip_data()
    if root is None:
        raise SystemExit(
            f"Inputs/VIP Data is not available, so {name!r} cannot be resolved.\n"
            "  Set RPE_DATA_ROOT for this machine (see .env.example) and check\n"
            "  that Inputs/VIP Data exists under it."
        )

    tried = []
    if cid:
        for row in (vip_manifest() or []):
            if (str(row.get("program", "")).lower() == prog
                    and str(row.get("client_id", "")) == cid):
                hit = root / row["file"]
                tried.append(hit)
                if hit.exists():
                    return hit
        for hit in sorted(root.glob(f"{program.upper()}/{cid}-*/{name}")):
            tried.append(hit)
            if hit.exists():
                return hit

    where = "\n  ".join(str(t) for t in [candidate] + tried) or str(root)
    raise SystemExit(
        f"Could not find the {program.upper()} client file {name!r} in the VIP store.\n"
        f"  Looked in:\n  {where}\n"
        "  Refresh it from VIP per Inputs/VIP Data/README.md, or check\n"
        "  the client id."
    )


def client_logo(client_id) -> Path | None:
    """The client's own logo, or None. Never raises — a missing logo degrades.

    Lives in `Inputs/Logos/<clientid>.<ext>`, alongside the other client inputs
    rather than in the repo: it is the client's brand asset and nothing
    client-identifiable belongs in git: data under RPE_DATA_ROOT, code in git.

    Filenames in that folder are not uniform — 1075 has both a .jpg and a .png, and
    1539 carries no extension at all while still being a valid PNG. So candidates are
    tried in preference order and each is OPENED before being accepted; an unreadable
    or non-image file is skipped rather than handed to python-pptx, which fails the
    whole build on a bad picture.
    """
    cid = str(client_id).strip()
    if not cid:
        return None
    try:
        folder = data_root() / "Inputs" / "Logos"
    except SystemExit:
        return None
    if not folder.is_dir():
        return None
    # .png first (transparency), then jpg, then the extensionless form
    cands = [folder / f"{cid}.png", folder / f"{cid}.PNG",
             folder / f"{cid}.jpg", folder / f"{cid}.jpeg", folder / cid]
    for c in cands:
        if not c.is_file():
            continue
        try:
            from PIL import Image
            with Image.open(c) as im:
                im.verify()
            return c
        except Exception:
            continue
    return None


def trim_logo(img_path, out_dir):
    """Crop a logo to its ink and return the new path (or the original, untouched).

    Client logo files are not tightly cropped, and the padding is not always the same
    kind: 1549 is a 2940x1532 canvas whose artwork sits in the top-left with the rest
    OPAQUE WHITE, while 1676 carries 56% TRANSPARENT margin. Fitting the raw canvas
    renders a correctly-sized box containing a tiny logo — how it first shipped on the
    agenda slide (Aaron, 2026-08-28).

    Two passes, and which one applies is decided by the file, not guessed:

      * transparent padding -> the alpha bbox already bounds the ink; use it.
      * opaque canvas -> subtract the background colour, sampled from the border RING
        rather than the four corners. 1539's bottom-right corner is semi-transparent
        teal ARTWORK; sampling corners took that as the background and masked the logo
        down to 115x97 of its 420x128.

    Returns the original path when nothing can be trimmed, so an already-tight logo is
    never re-encoded.
    """
    try:
        from PIL import Image, ImageChops
    except Exception:
        return img_path
    try:
        im = Image.open(img_path).convert("RGBA")
    except Exception:
        return img_path
    w, h = im.size
    if not w or not h:
        return img_path

    alpha = im.getchannel("A")
    ink = alpha.point(lambda v: 255 if v > 8 else 0)
    abox = ink.getbbox()
    if not abox:
        return img_path
    a_w, a_h = abox[2] - abox[0], abox[3] - abox[1]

    # Real transparency already bounds the ink; only an (effectively) opaque canvas
    # needs the background colour subtracted.
    if a_w >= w * 0.97 and a_h >= h * 0.97:
        px = im.load()
        step = max(1, min(w, h) // 64)
        ring = []
        for x in range(0, w, step):
            ring.append(px[x, 0]); ring.append(px[x, h - 1])
        for y in range(0, h, step):
            ring.append(px[0, y]); ring.append(px[w - 1, y])
        # Only a mostly OPAQUE border is a canvas. A transparent logo whose artwork merely touches the
        # edges also spans the full alpha box (1776 CoastHills: the lettering runs to all four sides).
        # Its ring is mostly transparent, and the opaque pixels in it are ARTWORK, so taking their
        # colour as the background cut the logo's own colour out of it: 21 of 122 logos were clipped,
        # 1183 to 632x28 and 1072 to 133x134 of 1195x258 (2026-09-15).
        opaque = [c for c in ring if c[3] > 200]
        ring = opaque if len(opaque) >= len(ring) * 0.9 else []
        if ring:
            bg = max(set(ring), key=ring.count)
            # only trust it if the border is genuinely uniform
            if ring.count(bg) >= len(ring) * 0.7:
                flat = Image.new("RGB", im.size, bg[:3])
                diff = ImageChops.difference(im.convert("RGB"), flat).convert("L")
                not_bg = diff.point(lambda v: 255 if v > 12 else 0)
                ink = ImageChops.multiply(ink, not_bg)

    bbox = ink.getbbox()
    if not bbox:
        bbox = (0, 0, w, h)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if bw <= 0 or bh <= 0:
        bbox, bw, bh = (0, 0, w, h), w, h
    tight = bw >= w * 0.97 and bh >= h * 0.97

    # python-pptx accepts only BMP/GIF/JPEG/PNG/TIFF/WMF and goes by CONTENT, not
    # extension. 1539.png is really a WEBP: PIL opens it happily, so it passed
    # client_logo's check, and add_picture then refused the whole image. Re-encode
    # anything outside that set even when there is nothing to crop.
    fmt = (getattr(im, "format", None) or "").upper()
    if tight and fmt in ("BMP", "GIF", "JPEG", "JPG", "PNG", "TIFF", "WMF"):
        return img_path                       # already tight and already usable

    pad = max(1, int(round(min(bw, bh) * 0.02)))
    box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
           min(w, bbox[2] + pad), min(h, bbox[3] + pad))
    try:
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"logo_trim_{os.path.basename(str(img_path))}.png")
        im.crop(box).save(out)
        return out
    except Exception:
        return img_path


def fit_box(img_path, max_w_in, max_h_in):
    """(width, height) in inches that fits `img_path` inside the box, aspect kept.

    Client logos run from 1.50 to 4.47 in aspect, so a fixed width stretches or
    overflows depending on the client. Returns None if the image cannot be read.
    """
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            w, h = im.size
    except Exception:
        return None
    if not w or not h:
        return None
    scale = min(max_w_in / w, max_h_in / h)
    return w * scale, h * scale


def _require_subdir(name: str) -> Path:
    path = data_root() / name
    if not path.is_dir():
        raise SystemExit(
            f"Expected {path!s} to exist.\n"
            "  Check RPE_DATA_ROOT in .env — this folder is created by the "
            "pipeline, not by a build."
        )
    return path


def register_bundled_fonts() -> list[str]:
    """Hand every .ttf under fonts/ to matplotlib.

    Fonts committed to the repo are identical on both machines, so anything
    registered here needs no OS-level install and can't drift.
    """
    from matplotlib import font_manager

    added = []
    for ttf in sorted(FONT_DIR.rglob("*.ttf")):
        font_manager.fontManager.addfont(str(ttf))
        added.append(ttf.name)
    return added


def use_font(family: str) -> None:
    """Set matplotlib's font family, failing loudly if it isn't available.

    matplotlib's default behaviour is to warn and substitute. A substituted
    face is a silent rendering difference between machines, which is exactly
    the class of bug this module exists to prevent.
    """
    import matplotlib
    from matplotlib import font_manager

    register_bundled_fonts()

    if family not in set(font_manager.get_font_names()):
        raise SystemExit(
            f"Font {family!r} is not available to matplotlib.\n"
            f"  Charts would silently render in a substitute face and the deck\n"
            f"  would not match the other machine.\n"
            f"  Fix: install {family}, or commit its .ttf files under "
            f"{FONT_DIR!s} so both machines share one copy."
        )

    matplotlib.rcParams["font.family"] = family


if __name__ == "__main__":
    print(f"repo root:  {REPO_ROOT}")
    print(f"data root:  {data_root()}")
    print(f"inputs:     {inputs()}")
    print(f"outputs:    {outputs()}")
    fonts = register_bundled_fonts()
    print(f"bundled fonts registered: {len(fonts)}")
    for name in ("Carlito", "Montserrat", "Calibri"):
        from matplotlib import font_manager
        mark = "ok " if name in set(font_manager.get_font_names()) else "MISSING"
        print(f"  {mark} {name}")
