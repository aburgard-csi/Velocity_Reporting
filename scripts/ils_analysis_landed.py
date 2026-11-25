#!/usr/bin/env python3
"""ils_analysis_landed.py — what Inputs/ILS Analysis holds for the ILS analysis review, read without the analysts' shares.

    scheduled()                    the clients on the analysts' review schedule now (from the snapshot the landing step keeps)
    pulls_status()                 the landing step's judgement per scheduled client: newest pull, landed kinds, current or not
    landed_files(client, pull)     {kind: path} of a landed pull, raw or zipped
    stage(client, pull, dest_dir)  the pull's extracts written UNZIPPED under their canonical names, for
                                   `python -m ils_review.cli --from-folder <dest_dir>`

`scripts/land_ils_analysis.py` writes everything this reads (Aaron, 2026-11-24): the newest pull of each scheduled client,
each extract as `<id>/<pull>/<canonical name>.zip` with one member of that name, and `_schedule/` beside the client folders
holding the schedule snapshot and `pulls.json`. Files landed earlier are raw; every reader here takes either form.

The schedule rules live here, so the landing step, the morning watch and CSM Sheila apply one reading of it:

* **On the schedule** (`in_scope`): a row whose review date is from today to `HORIZON_DAYS` ahead, or whose status says
  OVERDUE, and not cancelled; the analysts' weekly scheduling email selects the same way (today onwards, plus OVERDUE).
  One row per client: its earliest upcoming review, else its latest overdue one.
* **A current pull** (`judge`): one run no more than `CURRENT_WINDOW_DAYS` before that review date (or any time after it).
  Calibrated on the analysts' schedule history (2026-11-24, read only): of about 300 reviews held since June 2025, the newest
  pull before the review was a median of 22 days earlier, 48 days at the 90th percentile and 56 at the 95th. A pull further
  back is an earlier review's data: landing it does no harm, but the review deck must wait for the new one. A pull folder
  dated by month only (`DataPull_202611`) counts from the first of the month. The status is reported, never decisive: the
  sheet's statuses lag the pulls. The horizon equals the window on purpose: a review further out than that cannot have a
  current pull yet.

Import-safe: nothing touches a share or the data root until a function is called.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (HERE.parent / "build", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ils_analysis_inputs as IA                                 # noqa: E402

SCHEDULE_DIR = "_schedule"
SNAPSHOT_NAME = "current_scheduled_analysis.csv"
SNAPSHOT_META = "schedule_read.json"
PULLS_NAME = "pulls.json"
# Only the columns these rules read. The analysts' live workbook also carries technical contacts and notes: never copied.
SNAPSHOT_COLUMNS = ("fi_id", "fi_name", "review_date", "tentative_date", "pull_by", "status", "csm")
REQUIRED_COLUMNS = ("fi_id", "status", "review_date")
CURRENT_WINDOW_DAYS = 60
HORIZON_DAYS = CURRENT_WINDOW_DAYS
# What a review deck cannot be built without, and the six the builder looks for (`ils_review.cli.find_inputs`).
REQUIRED_KINDS = ("zaccounts", "ztrend")
BUILDER_KINDS = ("zaccounts", "ztrend", "matrixval", "dbic", "debitdeclines", "refundhistory")
CHUNK = 16 * 1024 * 1024


# ── where ────────────────────────────────────────────────────────────────────
def root() -> Path:
    import rpe_env
    return rpe_env.inputs() / rpe_env.INPUT_KIND_DIRS["ILS analysis"]


def schedule_dir(base=None) -> Path:
    return Path(base if base is not None else root()) / SCHEDULE_DIR


# ── the schedule ─────────────────────────────────────────────────────────────
def parse_date(v):
    """A date from a schedule cell: a datetime / date, or text as 10/21/2022, 2022-10-21 or 2022-10-21 00:00:00. None if blank."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _client_id(v):
    """'7001', 7001 or 7001.0 -> '7001'; anything else -> None."""
    s = str(v if v is not None else "").strip()
    m = re.fullmatch(r"(\d{3,5})(?:\.0+)?", s)
    return m.group(1) if m else None


def _rows_from_table(header, rows):
    names = [str(h).strip().lower() if h is not None else "" for h in header]
    missing = [c for c in REQUIRED_COLUMNS if c not in names]
    if missing:
        raise ValueError("the schedule has no " + ", ".join(missing) + " column")
    ix = {c: names.index(c) for c in SNAPSHOT_COLUMNS if c in names}
    out = []
    for r in rows:
        if not r:
            continue
        cell = lambda c: r[ix[c]] if c in ix and ix[c] < len(r) else None      # noqa: E731
        cid = _client_id(cell("fi_id"))
        if not cid:
            continue
        rec = {"fi_id": cid}
        for c in SNAPSHOT_COLUMNS[1:]:
            v = cell(c)
            if c.endswith("_date") or c == "pull_by":
                d = parse_date(v)
                rec[c] = d.isoformat() if d else ""
            else:
                rec[c] = "" if v is None else str(v).strip()
        out.append(rec)
    return out


def read_schedule(path):
    """Every row of the analysts' schedule, as {column: text} for SNAPSHOT_COLUMNS, dates as yyyy-mm-dd. A .csv (the share's
    copy) or a .xlsx (the analysts' live workbook, first sheet). Raises OSError when it cannot be read, ValueError when a
    required column is missing."""
    p = str(path)
    raw = open(p, "rb").read()                                  # read once into memory: no handle held on the analysts' file
    if p.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        try:
            it = wb.worksheets[0].iter_rows(values_only=True)
            header = next(it, None) or ()
            rows = [list(r) for r in it]
        finally:
            wb.close()
        return _rows_from_table(header, rows)
    for enc in ("utf-8-sig", "cp1252", "latin-1"):            # latin-1 decodes any byte: the last resort
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    table = list(csv.reader(io.StringIO(text)))
    if not table:
        raise ValueError("the schedule is empty")
    return _rows_from_table(table[0], table[1:])


def in_scope(rows, today=None, horizon_days=HORIZON_DAYS):
    """{client id: row} for the clients on the schedule now: see the module docstring."""
    today = today or date.today()
    last = today + timedelta(days=horizon_days)
    upcoming, overdue = {}, {}
    for r in rows:
        status = (r.get("status") or "").upper()
        if "CANCEL" in status:
            continue
        rd = parse_date(r.get("review_date"))
        if rd and today <= rd <= last:
            cur = upcoming.get(r["fi_id"])
            if cur is None or rd < parse_date(cur["review_date"]):
                upcoming[r["fi_id"]] = r
        elif "OVERDUE" in status:
            cur = overdue.get(r["fi_id"])
            if cur is None or (rd and rd > (parse_date(cur["review_date"]) or date.min)):
                overdue[r["fi_id"]] = r
    out = dict(overdue)
    out.update(upcoming)                                        # an upcoming review wins over an overdue one
    return dict(sorted(out.items(), key=lambda kv: (kv[1].get("review_date") or "", kv[0])))


def pull_day(pull, month_end=False):
    """The day a pull stamp stands for: yyyymmdd, or for yyyymm the first of the month (the last with `month_end`).
    None when unreadable."""
    s = str(pull or "")
    try:
        if re.fullmatch(r"\d{8}", s):
            return date(int(s[:4]), int(s[4:6]), int(s[6:]))
        if re.fullmatch(r"\d{6}", s):
            first = date(int(s[:4]), int(s[4:6]), 1)
            return (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1) if month_end else first
    except ValueError:
        return None
    return None


def judge(pull, row, window_days=CURRENT_WINDOW_DAYS, month_end=False):
    """(current, reason) for a client's newest pull against its scheduled review. `month_end` reads a month-only stamp
    as the month's last day: the watch's listing, which reads folder names only, says "waiting" only when it is sure."""
    review = parse_date((row or {}).get("review_date"))
    status = (row or {}).get("status") or "no status"
    if not pull:
        return False, f"no data pull on the analysis share ({status})"
    day = pull_day(pull, month_end)
    if day is None:
        return False, f"the pull's date {pull!r} cannot be read ({status})"
    if review is None:
        return False, f"the schedule gives no review date ({status})"
    month = " (dated by month only)" if len(str(pull)) == 6 else ""
    if day > review:
        return True, f"pulled {pull}{month}, after the review date {review.isoformat()} ({status})"
    gap = (review - day).days
    if gap <= window_days:
        return True, f"pulled {pull}{month}, {gap} days before the review on {review.isoformat()} ({status})"
    return False, (f"pulled {pull}{month}, {gap} days before the review on {review.isoformat()}: more than "
                   f"{window_days} days, so an earlier review's data; waiting for the new pull ({status})")


# ── the snapshot the landing step keeps ──────────────────────────────────────
def snapshot_text(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(SNAPSHOT_COLUMNS), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in SNAPSHOT_COLUMNS})
    return buf.getvalue()


def write_snapshot(rows, source, source_mtime=None, base=None, now=None):
    """Keep the schedule under `_schedule/`, so nothing downstream has to reach the analysts' share. The csv is replaced only
    when its content changes; the read is recorded every time. -> True when the content changed."""
    d = schedule_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    text = snapshot_text(rows)
    path = d / SNAPSHOT_NAME
    try:
        old = path.read_text(encoding="utf-8")
    except OSError:
        old = None
    changed = old != text
    meta_path = d / SNAPSHOT_META
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    if changed:
        _write_text(path, text)
        meta["changed_at"] = stamp
    meta.update({"read_at": stamp, "source": str(source), "rows": len(rows),
                 "source_modified": (datetime.fromtimestamp(source_mtime).isoformat(timespec="seconds")
                                     if source_mtime else None)})
    _write_text(meta_path, json.dumps(meta, indent=1))
    return changed


def snapshot_rows(base=None):
    """Every row of the snapshot ([] when there is none)."""
    try:
        with open(schedule_dir(base) / SNAPSHOT_NAME, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def scheduled(today=None, horizon_days=HORIZON_DAYS, base=None):
    """The snapshot rows on the schedule now (`in_scope`), earliest review first."""
    return list(in_scope(snapshot_rows(base), today, horizon_days).values())


def pulls_status(base=None):
    """`_schedule/pulls.json` as the landing step last wrote it: {"written", "schedule", "clients": {id: {...}}}; {} if none."""
    try:
        return json.loads((schedule_dir(base) / PULLS_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_pulls_status(doc, base=None):
    d = schedule_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    _write_text(d / PULLS_NAME, json.dumps(doc, indent=1))


def _write_text(path, text):
    part = Path(str(path) + ".part")
    part.write_text(text, encoding="utf-8")
    os.replace(part, path)


# ── a landed pull ────────────────────────────────────────────────────────────
def _canonical_kind(client, name):
    """The kind of a file named by the convention (`<client>_<kind>_<date>.<ext>`, raw or `.zip`), else None."""
    base = name[:-4] if name.lower().endswith(".zip") else name
    m = re.fullmatch(re.escape(str(client)) + r"_([a-z_]+)_(\d{6}|\d{8})\.(csv|txt)", base)
    return m.group(1) if m and m.group(1) in IA.EXTRACT_KINDS else None


def landed_files(client, pull, base=None):
    """{kind: Path} of the extracts landed for one pull, raw or zipped. A raw file wins over its zip (nothing to unpack);
    two of one kind (two dates in one pull) -> the later name."""
    d = Path(base if base is not None else root()) / str(client) / str(pull)
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return {}
    out = {}
    for n in names:
        if n.endswith(".part"):
            continue
        k = _canonical_kind(client, n)
        if not k or not (d / n).is_file():
            continue
        prev = out.get(k)
        raw_n = n[:-4] if n.lower().endswith(".zip") else n
        if prev is not None:
            prev_raw = prev.name[:-4] if prev.name.lower().endswith(".zip") else prev.name
            if prev_raw == raw_n and not prev.name.lower().endswith(".zip"):
                continue                                        # the raw copy is already chosen
            if prev_raw > raw_n:
                continue
        out[k] = d / n
    return out


def unzipped_size(path):
    """The size of a landed file's content: the one member's for a zip, the file's own for a raw file. None if unreadable."""
    p = Path(path)
    try:
        if p.name.lower().endswith(".zip"):
            with zipfile.ZipFile(p) as z:
                infos = [i for i in z.infolist() if not i.is_dir()]
            return infos[0].file_size if len(infos) == 1 else None
        return p.stat().st_size
    except (OSError, zipfile.BadZipFile):
        return None


def stage(client, pull, dest_dir, base=None, kinds=None):
    """Write a landed pull's extracts UNZIPPED into `dest_dir` under their canonical names, for the builder's --from-folder.
    A file already staged at the right size is left. -> {kind: staged Path}."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, src in landed_files(client, pull, base).items():
        if kinds and k not in kinds:
            continue
        zipped = src.name.lower().endswith(".zip")
        name = src.name[:-4] if zipped else src.name
        target = dest / name
        want = unzipped_size(src)
        if target.is_file() and want is not None and target.stat().st_size == want:
            out[k] = target
            continue
        part = dest / (name + ".part")
        if zipped:
            with zipfile.ZipFile(src) as z:
                info = [i for i in z.infolist() if not i.is_dir()][0]
                with z.open(info) as fh, open(part, "wb") as fp:       # a bad CRC raises at the end of the read
                    shutil.copyfileobj(fh, fp, CHUNK)
        else:
            shutil.copyfile(src, part)
        got = part.stat().st_size
        if want is not None and got != want:
            part.unlink()
            raise OSError(f"staged {name} at {got} bytes, expected {want}")
        os.replace(part, target)
        out[k] = target
    return out
