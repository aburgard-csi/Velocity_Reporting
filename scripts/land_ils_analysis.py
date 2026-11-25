#!/usr/bin/env python3
"""land_ils_analysis.py — copy the newest data pull of each client on the ILS analysts' review schedule into
`Inputs/ILS Analysis/`, each extract zipped, so CSM Sheila can build the ILS analysis review without reaching their shares.

    python scripts/land_ils_analysis.py                  # dry run (the default): the plan, nothing written
    python scripts/land_ils_analysis.py --apply          # land it
    python scripts/land_ils_analysis.py --client 1130    # one client (repeat for several)

Aaron, 2026-11-24: the scope is the clients on the analysts' review schedule, and each one's newest pull is copied once,
zipped, as its own step, verified and never overwriting. The two sources are the analysts' and are READ ONLY:

  * the schedule, `deck_status.SRC_ILS_SCHEDULE` (`RPE_SRC_ILS_SCHEDULE`): the share's `current_scheduled_analysis.csv`
    by default, or the analysts' live `.xlsx` (the same columns). Which rows count, and when a pull is current, is
    `ils_analysis_landed.in_scope` / `judge` — read there.
  * the client analysis share, `deck_status.SRC_ILS_ANALYSIS` (`RPE_SRC_ILS_ANALYSIS`): one folder per client
    (`<Name>_<id>`, `<Name> - <id>`; the id read by `ils_review.peer_pull.client_id_of`), each holding dated pulls, as a
    folder or a zip (`DataPull_20260911`, `DataPull_2024.8.22`, `DataPull_202605` holding `1048_DataPull_20260504.zip`).
    A client number that matches two folders is reported and left: never guessed.

What lands: every extract of the newest pull that holds one (`ils_analysis_inputs.kind_of`: ZAccounts, ZTrend, debit
declines, refunds, MatrixVal, DBIC, DataOps, adjustments ...), as `<id>/<pull>/<canonical name>.zip` with ONE member of the
canonical name (`ils_analysis_inputs.target`: `<id>_<kind>_<yyyymmdd>.<ext>`). The analysts' own .pptm / .pbix / workbooks
are their outputs, not inputs, and are never copied; a .csv/.txt the convention does not know is listed, not landed.

  * Each file is written as `.zip.part`, checked (member name, size and CRC against the source, the zip read back whole)
    and renamed into place; then its presence is checked again. The share's security agent has deleted zips silently
    before (`land_txn_files.py`, `watch_sources._land_odd_member_only`): a zip that is gone or emptied is landed raw
    instead, through its own `.part`, checked the same way.
  * A file on hand at the same size (the zip's member, or a raw file) is skipped; one at another size is reported and
    left. Nothing is ever overwritten or deleted, here or on the source.
  * Smallest files first, across every client; a soft budget (`--budget-minutes`, 45) stops between files and says what is
    left, and the next run picks up from there.
  * The schedule is kept as `_schedule/current_scheduled_analysis.csv` (only the columns the rules read; replaced only when
    its content changes; `schedule_read.json` records each read), and each scheduled client's newest pull, landed kinds
    and current judgement go to `_schedule/pulls.json`, for Sheila. Every landing is logged to
    `Build Artifacts/ils_analysis/landings.json`, and an --apply run's report to `landing_latest.md` / `landing.log` there.
  * Either source unreachable: reported, exit 2, nothing written.

Not part of the 08:00 watch (its 50-minute limit): `scripts/register_ils_landing_task.ps1` registers it as its own task.
The watch's `--ils-analysis` step only LISTS new pulls (`watch()` below).

Import-safe: nothing touches a share until a function is called.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
import zipfile
import zlib
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for _p in (REPO / "build", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ils_analysis_inputs as IA                                 # noqa: E402
import ils_analysis_landed as L                                  # noqa: E402

PULL_RX = re.compile(r"data[\s_-]*pull", re.I)
CHUNK = 16 * 1024 * 1024
# Level 6, as zip_txn_files: the time goes on WRITING to the share, not on compressing. On a real 50 MB ZAccounts extract
# (2026-11-24) deflate took 0.7 s at level 6 for 13 MB against 0.2 s at level 1 for 22 MB, while the whole landing took
# 26 s; fewer bytes written is the faster landing.
COMPRESSLEVEL = 6
ZIP_MB_PER_S = 2.0                     # source MB landed per second, from that landing; the dry run's time estimate only
BUDGET_MINUTES = 45
SCHEDULE_STALE_DAYS = 30
LANDINGS_NAME = "landings.json"
WATCH_STATE_NAME = "watch_state.json"


def artifacts_dir() -> Path:
    import rpe_env
    d = rpe_env.build_artifacts() / "ils_analysis"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sources(source=None, schedule=None):
    import deck_status as DS
    return (source or DS.SRC_ILS_ANALYSIS), (schedule or DS.SRC_ILS_SCHEDULE)


# ── the analysis share ───────────────────────────────────────────────────────
def client_folders(src_root):
    """{client id: [folder names]} of the client folders on the analysis share (folders only)."""
    analysis = str(REPO / "build" / "ils_analysis")
    if analysis not in sys.path:
        sys.path.insert(0, analysis)
    from ils_review.peer_pull import client_id_of               # the one reading of a client folder's name
    out = {}
    with os.scandir(src_root) as it:
        for e in it:
            if e.is_dir():
                cid = client_id_of(e.name)
                if cid:
                    out.setdefault(cid, []).append(e.name)
    return {k: sorted(v) for k, v in out.items()}


def _stem(name):
    return name[:-4] if name.lower().endswith(".zip") else name


def name_stamp(name):
    """The pull date a folder or zip NAME carries (yyyymmdd, else yyyymm), else ''."""
    s = _stem(name)
    return IA.date_in(s) or IA.month_in(s) or ""


def candidates(client_dir):
    """[(stamp, name, path)] of a client's pull folders and zips, newest first (a folder before a zip of the same date)."""
    out = []
    with os.scandir(client_dir) as it:
        for e in it:
            if not PULL_RX.search(e.name):
                continue
            is_dir = e.is_dir()
            if is_dir or e.name.lower().endswith(".zip"):
                st = name_stamp(e.name)
                out.append((st, e.name, e.path, is_dir))
    out.sort(key=lambda c: (c[0].ljust(8, "0"), c[3], c[1]), reverse=True)
    return [(st, n, p) for st, n, p, _d in out]


def _zip_members(zpath):
    rows = []
    with zipfile.ZipFile(zpath) as z:
        for i in z.infolist():
            if i.is_dir() or i.filename.count("/") > 1 or i.file_size == 0:
                continue                                        # a pull's files sit at the top or in one folder
            try:
                mt = datetime(*i.date_time).timestamp()
            except (ValueError, OverflowError):
                mt = None
            rows.append({"name": os.path.basename(i.filename), "src": str(zpath), "member": i.filename,
                         "size": i.file_size, "crc": i.CRC, "mtime": mt})
    return rows


def _dir_files(d):
    rows = []
    with os.scandir(d) as it:
        for e in it:
            if e.is_file() and not e.name.endswith(".part"):
                st = e.stat()
                if st.st_size:
                    rows.append({"name": e.name, "src": e.path, "member": None, "size": st.st_size, "crc": None,
                                 "mtime": st.st_mtime})
    return rows


def pull_contents(path):
    """(files, inner dates, notes) of one pull: its own files, a pull zip or pull folder inside it (one level), or a
    zip's members. Other folders inside a pull (`uncleaned data`) are not read, and are noted."""
    files, inner, notes = [], [], []
    p = Path(path)
    if p.is_dir():
        with os.scandir(p) as it:
            entries = sorted(it, key=lambda e: e.name)
        for e in entries:
            if e.is_dir():
                if PULL_RX.search(e.name):
                    inner.append(name_stamp(e.name))
                    files += _dir_files(e.path)
                else:
                    notes.append(f"folder `{e.name}` in the pull not read")
            elif e.name.lower().endswith(".zip") and PULL_RX.search(e.name):
                inner.append(name_stamp(e.name))
                files += _zip_members(e.path)
            elif e.is_file() and not e.name.endswith(".part") and e.stat().st_size:
                st = e.stat()
                files.append({"name": e.name, "src": e.path, "member": None, "size": st.st_size, "crc": None,
                              "mtime": st.st_mtime})
    else:
        files += _zip_members(p)
    return files, [d for d in inner if d], notes


def _is_alias(name):
    return re.sub(r"[^a-z]", "", os.path.splitext(name)[0].lower()) in IA.ALIASES


def resolve(client, folders, src_root):
    """The newest pull of one client that holds an extract: {"folder", "pull_name", "pull", "extracts": {canonical: file},
    "duplicates", "unrecognised", "missing", "notes", "passed_over"} — or {"problem": why}."""
    if not folders:
        return {"problem": "no client folder on the analysis share"}
    if len(folders) > 1:
        return {"problem": "the client number matches %d folders (%s); not guessed" % (len(folders), ", ".join(folders))}
    cdir = os.path.join(src_root, folders[0])
    try:
        cands = candidates(cdir)
    except OSError as e:
        return {"problem": f"cannot list the client folder: {e}", "folder": folders[0]}
    if not cands:
        return {"problem": "no DataPull folder or zip in the client folder", "folder": folders[0]}
    passed = []
    for _st, name, path in cands:
        try:
            files, inner, notes = pull_contents(path)
        except (OSError, zipfile.BadZipFile) as e:
            passed.append(f"{name} (cannot be read: {e})")
            continue
        ext = [f for f in files if IA.kind_of(f["name"])]
        if not ext:
            passed.append(f"{name} (no extract)")
            continue
        pull = IA.pull_date(_stem(name), [IA.date_in(f["name"]) for f in ext], inner)
        if not pull:
            passed.append(f"{name} (no date)")
            continue
        groups = {}
        for f in ext:
            canon = IA.target(client, [_stem(name), f["name"]], pull)[0][-1]
            groups.setdefault(canon, []).append(f)
        chosen, dups = {}, []
        for canon, fs in sorted(groups.items()):
            fs.sort(key=lambda f: (_is_alias(f["name"]), -f["size"], f["name"]))
            chosen[canon] = fs[0]
            dups += [f"{x['name']} (same name as {fs[0]['name']}: not landed)" for x in fs[1:]]
        kinds = {IA.kind_of(f["name"]) for f in chosen.values()}
        unrec = sorted(f["name"] for f in files
                       if not IA.kind_of(f["name"]) and os.path.splitext(f["name"])[1].lower() in IA.EXTRACT_EXTS)
        return {"folder": folders[0], "pull_name": name, "pull": pull, "extracts": chosen, "duplicates": dups,
                "unrecognised": unrec, "missing": [k for k in L.REQUIRED_KINDS if k not in kinds], "notes": notes,
                "passed_over": passed}
    return {"problem": "no extract in any pull: " + "; ".join(passed[:4]), "folder": folders[0]}


# ── the plan ─────────────────────────────────────────────────────────────────
def on_hand(dest_dir, canonical, size):
    """Why this file need not land: "on hand" (the zip's member or the raw file, same size), "differs" (present at
    another size: left alone, reported), or None when it is wanted."""
    raw, z = Path(dest_dir) / canonical, Path(dest_dir) / (canonical + ".zip")
    if raw.is_file():
        return "on hand" if raw.stat().st_size == size else "differs"
    if z.is_file():
        try:
            with zipfile.ZipFile(z) as zf:
                infos = [i for i in zf.infolist() if not i.is_dir()]
        except (OSError, zipfile.BadZipFile):
            return "differs"
        if len(infos) == 1 and infos[0].filename == canonical and infos[0].file_size == size:
            return "on hand"
        return "differs"
    return None


def plan(resolved, dest_root):
    """(wanted, skipped): items to land, smallest first, and [(item, why)] for the rest. `resolved` is {client: resolve()}."""
    wanted, skipped = [], []
    for client, r in resolved.items():
        if r.get("problem"):
            continue
        d = Path(dest_root) / client / r["pull"]
        for canon, f in r["extracts"].items():
            item = {"client": client, "pull": r["pull"], "canonical": canon, "dest_dir": d, "file": f,
                    "pull_name": r["pull_name"]}
            why = on_hand(d, canon, f["size"])
            (skipped.append((item, why)) if why else wanted.append(item))
    wanted.sort(key=lambda i: (i["file"]["size"], i["client"], i["canonical"]))
    return wanted, skipped


# ── landing one file ─────────────────────────────────────────────────────────
@contextlib.contextmanager
def _open_source(f):
    with contextlib.ExitStack() as st:
        if f["member"] is None:
            yield st.enter_context(open(f["src"], "rb"))
        else:
            z = st.enter_context(zipfile.ZipFile(f["src"]))
            yield st.enter_context(z.open(f["member"]))


def _check(zip_path, name, size, crc):
    """Raise unless the zip holds exactly `name`, `size` bytes, decompressing to `crc`."""
    with zipfile.ZipFile(zip_path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) != 1 or infos[0].filename != name:
            raise ValueError(f"expected one member {name!r}, found {[i.filename for i in infos]}")
        if infos[0].file_size != size or infos[0].CRC != crc:
            raise ValueError(f"member is {infos[0].file_size:,} bytes CRC {infos[0].CRC:08x}; "
                             f"source is {size:,} bytes CRC {crc:08x}")
        got = 0
        with z.open(infos[0]) as fh:
            while True:
                b = fh.read(CHUNK)
                if not b:
                    break
                got = zlib.crc32(b, got)
        if got != crc:
            raise ValueError(f"member decompresses to CRC {got:08x}, expected {crc:08x}")


def _land_raw(f, target, crc):
    part = Path(str(target) + ".part")
    got, size = 0, 0
    with _open_source(f) as src, open(part, "wb") as fp:
        while True:
            b = src.read(CHUNK)
            if not b:
                break
            got = zlib.crc32(b, got)
            size += len(b)
            fp.write(b)
        fp.flush()
        os.fsync(fp.fileno())
    if size != f["size"] or got != crc or not part.is_file() or part.stat().st_size != size:
        with contextlib.suppress(OSError):
            part.unlink()
        raise OSError(f"the raw copy did not verify ({size:,} bytes CRC {got:08x}; expected {f['size']:,} CRC {crc:08x})")
    os.replace(part, target)
    if not target.is_file() or target.stat().st_size != size:
        raise OSError("the raw copy is gone from the share after landing")
    if f["mtime"]:
        os.utime(target, (f["mtime"], f["mtime"]))


def land_one(item):
    """Land one extract as `<dest_dir>/<canonical>.zip` (one member, the canonical name), verified; raw if the share
    will not keep the zip. -> a result row."""
    f, d, name = item["file"], Path(item["dest_dir"]), item["canonical"]
    target, part = d / (name + ".zip"), d / (name + ".zip.part")
    res = {"client": item["client"], "pull": item["pull"], "name": name, "source": f["src"] + (
        "::" + f["member"] if f["member"] else ""), "size": f["size"], "zip_size": None, "status": None, "error": None}
    try:
        d.mkdir(parents=True, exist_ok=True)
        if part.exists():
            part.unlink()
        info = zipfile.ZipInfo(name)
        if f["mtime"]:
            info.date_time = datetime.fromtimestamp(f["mtime"]).timetuple()[:6]
        info.compress_type = zipfile.ZIP_DEFLATED
        crc, size = 0, 0
        with _open_source(f) as src, open(part, "wb") as fp:
            with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED, compresslevel=COMPRESSLEVEL) as z, \
                    z.open(info, "w", force_zip64=f["size"] > 2 ** 31) as dst:
                while True:
                    b = src.read(CHUNK)
                    if not b:
                        break
                    crc = zlib.crc32(b, crc)
                    size += len(b)
                    dst.write(b)
            fp.flush()
            os.fsync(fp.fileno())
        if size != f["size"]:
            raise ValueError(f"read {size:,} bytes from the source, expected {f['size']:,}")
        if f["crc"] is not None and crc != f["crc"]:
            raise ValueError(f"the source read back as CRC {crc:08x}; its zip says {f['crc']:08x}")
        kept = part.is_file() and part.stat().st_size > 0
        if kept:
            _check(part, name, size, crc)
            os.replace(part, target)
            kept = target.is_file() and target.stat().st_size > 0
        if not kept:
            # The share's security agent removed or emptied the zip (see the module docstring): keep the file raw.
            with contextlib.suppress(OSError):
                part.unlink()
            _land_raw(f, d / name, crc)
            res.update(status="landed raw", zip_size=(d / name).stat().st_size,
                       error="the share did not keep this file zipped; landed raw")
            return res
        if f["mtime"]:
            os.utime(target, (f["mtime"], f["mtime"]))
        res.update(status="landed", zip_size=target.stat().st_size)
    except Exception as e:                                      # noqa: BLE001 — reported per file
        res.update(status="FAILED", error=f"{type(e).__name__}: {e}")
        with contextlib.suppress(OSError):
            part.unlink()
    return res


def record(results, path):
    """Append the landings to `landings.json` (bookkeeping, in Build Artifacts)."""
    try:
        old = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = []
    when = datetime.now().isoformat(timespec="seconds")
    old += [dict(r, when=when) for r in results]
    part = Path(str(path) + ".part")
    part.write_text(json.dumps(old, indent=1), encoding="utf-8")
    os.replace(part, path)


# ── the judgement Sheila reads ───────────────────────────────────────────────
def status_doc(scope, resolved, dest_root, schedule_meta):
    clients = {}
    for cid, row in scope.items():
        r = resolved.get(cid, {})
        pull = r.get("pull")
        current, reason = L.judge(pull, row)
        if r.get("problem"):
            reason = r["problem"]
        landed = sorted(L.landed_files(cid, pull, dest_root)) if pull else []
        clients[cid] = {
            "name": row.get("fi_name", ""), "status": row.get("status", ""), "review_date": row.get("review_date", ""),
            "pull_by": row.get("pull_by", ""), "tentative_date": row.get("tentative_date", ""), "csm": row.get("csm", ""),
            "folder": r.get("folder"), "pull": pull, "pull_source": r.get("pull_name"),
            "kinds_on_share": sorted({IA.kind_of(f["name"]) for f in (r.get("extracts") or {}).values()}),
            "landed_kinds": landed, "missing_kinds": r.get("missing", list(L.REQUIRED_KINDS)),
            "unrecognised": r.get("unrecognised", []), "problem": r.get("problem"),
            "current": bool(current and not r.get("problem")), "reason": reason}
    return {"written": datetime.now().isoformat(timespec="seconds"), "schedule": schedule_meta, "clients": clients}


# ── the run ──────────────────────────────────────────────────────────────────
def _mb(n):
    return f"{n / 1_048_576:,.1f} MB"


def read_sources(source, schedule, say):
    """(rows, schedule meta, client folders) or None when either source cannot be reached (said)."""
    try:
        rows = L.read_schedule(schedule)
        mtime = os.path.getmtime(schedule)
    except (OSError, ValueError) as e:
        say(f"the schedule cannot be read ({schedule}): {e}")
        return None
    try:
        folders = client_folders(source)
    except OSError as e:
        say(f"the analysis share cannot be reached ({source}): {e}")
        return None
    age = (datetime.now() - datetime.fromtimestamp(mtime)).days
    meta = {"source": str(schedule), "source_modified": datetime.fromtimestamp(mtime).isoformat(timespec="seconds"),
            "rows": len(rows), "warning": None}
    if age > SCHEDULE_STALE_DAYS:
        meta["warning"] = (f"the schedule file was last written {datetime.fromtimestamp(mtime):%Y-%m-%d}, {age} days ago; "
                           "if that is not the analysts' live schedule, set RPE_SRC_ILS_SCHEDULE to the one that is")
    return rows, meta, folders


def run(apply=False, clients=None, source=None, schedule=None, dest_root=None, today=None,
        horizon_days=L.HORIZON_DAYS, budget_minutes=BUDGET_MINUTES, current_only=False, say=print):
    """The whole step. -> exit status: 0 done (or dry run), 1 a file failed, 2 a source unreachable."""
    source, schedule = sources(source, schedule)
    got = read_sources(source, schedule, say)
    if got is None:
        return 2
    rows, meta, folders = got
    today = today or date.today()
    scope = L.in_scope(rows, today, horizon_days)
    if clients:
        scope = {k: v for k, v in scope.items() if k in set(clients)}
    meta["in_scope"] = len(scope)
    if meta["warning"]:
        say("!! " + meta["warning"])
    say(f"schedule: {len(rows)} rows, {len(scope)} client(s) with a review from {today} to "
        f"{horizon_days} days ahead or OVERDUE" + (f" (limited to {', '.join(clients)})" if clients else ""))
    dest_root = Path(dest_root) if dest_root else L.root()
    resolved = {cid: resolve(cid, folders.get(cid, []), source) for cid in scope}
    to_land = resolved
    if current_only:
        to_land = {cid: r for cid, r in resolved.items() if L.judge(r.get("pull"), scope[cid])[0]}
        say(f"--current-only: {len(to_land)} of {len(resolved)} client(s) have a current pull; only those are landed")
    wanted, skipped = plan(to_land, dest_root)
    total = sum(i["file"]["size"] for i in wanted)
    for cid, row in scope.items():
        r = resolved[cid]
        current, why = L.judge(r.get("pull"), row)
        tag = "PROBLEM" if r.get("problem") else ("current" if current else "stale")
        n_want = [i for i in wanted if i["client"] == cid]
        say(f"- {cid} review {row.get('review_date') or '?'} [{row.get('status') or '-'}]: {tag}; "
            + (r["problem"] if r.get("problem") else
               f"pull {r['pull']} ({r['pull_name']}), {len(r['extracts'])} extract(s), "
               f"{len(n_want)} to land ({_mb(sum(i['file']['size'] for i in n_want))})"))
        if not r.get("problem"):
            say(f"    {why}")
            for label, items in (("missing", r["missing"]), ("not recognised", r["unrecognised"]),
                                 ("duplicates", r["duplicates"]), ("newer pulls passed over", r["passed_over"]),
                                 ("notes", r["notes"])):
                if items:
                    say(f"    {label}: " + ", ".join(items))
    differs = [(i, w) for i, w in skipped if w == "differs"]
    for i, _w in differs:
        say(f"  differs (left alone): {i['client']}/{i['pull']}/{i['canonical']}")
    say(f"{len(wanted)} file(s) to land, {_mb(total)} (about {total / 1_048_576 / ZIP_MB_PER_S / 60:,.0f} min to zip); "
        f"{len(skipped) - len(differs)} on hand; {len(differs)} differ")
    if not apply:
        say("dry run: nothing written (add --apply).")
        return 0

    L.write_snapshot(rows, schedule, os.path.getmtime(schedule), base=dest_root)
    t0, results, left = time.time(), [], []
    for n, item in enumerate(wanted, 1):
        if time.time() - t0 > budget_minutes * 60:
            left = wanted[n - 1:]
            break
        r = land_one(item)
        results.append(r)
        say(f"[{n}/{len(wanted)}] {r['status']} {r['client']}/{r['pull']}/{r['name']} {_mb(r['size'])}"
            + (f" -> {_mb(r['zip_size'])}" if r["zip_size"] else "") + (f"  ({r['error']})" if r["error"] else ""))
    if results:
        record(results, artifacts_dir() / LANDINGS_NAME)
    if left:
        say(f"stopped at the {budget_minutes}-minute budget: {len(left)} file(s), {_mb(sum(i['file']['size'] for i in left))}"
            " left for the next run")
    L.write_pulls_status(status_doc(scope, resolved, dest_root, meta), base=dest_root)
    failed = sum(1 for r in results if r["status"] == "FAILED")
    say(f"landed {len(results) - failed}, failed {failed}; status written to "
        f"{L.schedule_dir(dest_root) / L.PULLS_NAME}")
    return 1 if failed else 0


# ── the morning watch's listing ──────────────────────────────────────────────
def watch(state_path=None, source=None, schedule=None, today=None, dry_run=False, horizon_days=L.HORIZON_DAYS):
    """The source watch's `--ils-analysis` step: each scheduled client's newest pull on the analysis share, by NAME only
    (no zip is opened, nothing is copied), against the last run's. -> report lines. Unreachable: said, state kept."""
    source, schedule = sources(source, schedule)
    out = ["", "## ILS analysis pulls", ""]
    msgs = []
    got = read_sources(source, schedule, msgs.append)
    if got is None:
        return out + ["- unreachable: " + "; ".join(msgs) + " (the last listing is kept)"]
    rows, meta, folders = got
    scope = L.in_scope(rows, today or date.today(), horizon_days)
    state_path = Path(state_path) if state_path else artifacts_dir() / WATCH_STATE_NAME
    try:
        old = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = None
    seen = (old or {}).get("clients", {})
    now, new, waiting, problems = {}, [], [], []
    for cid, row in scope.items():
        fs = folders.get(cid, [])
        if len(fs) != 1:
            problems.append(f"- {cid}: " + ("no client folder" if not fs else f"{len(fs)} folders match ({', '.join(fs)})"))
            continue
        try:
            cands = candidates(os.path.join(source, fs[0]))
        except OSError as e:
            problems.append(f"- {cid}: cannot list the client folder ({e})")
            continue
        newest = cands[0] if cands else None
        now[cid] = {"pull": newest[1] if newest else None, "stamp": newest[0] if newest else None}
        # New = a different newest pull from the one listed last time. A client the last listing did not have (newly on
        # the schedule) starts from what is there now, as the first listing does.
        if newest and cid in seen and seen[cid].get("pull") != newest[1]:
            new.append(f"- {cid}: new pull `{newest[1]}` (review {row.get('review_date') or '?'})")
        current, why = L.judge(newest[0] if newest else None, row, month_end=True)
        if not current:
            waiting.append(f"- {cid}: {why}")
    if meta["warning"]:
        out.append("- !! " + meta["warning"])
    out.append(f"- {len(scope)} scheduled client(s) (review in the next {horizon_days} days, or OVERDUE)")
    if old is None:
        out.append("- first listing: recorded as the baseline")
    out += new or (["- no new pulls since the last check"] if old is not None else [])
    if waiting:
        out += ["", f"Waiting for a current pull ({len(waiting)}):"] + waiting
    if problems:
        out += ["", "Not listed:"] + problems
    if new:
        out.append("- land them: `python scripts/land_ils_analysis.py --apply` (or the RPE ILS Analysis Landing task)")
    if not dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        part = Path(str(state_path) + ".part")
        part.write_text(json.dumps({"checked": datetime.now().isoformat(timespec="seconds"), "clients": now}, indent=1),
                        encoding="utf-8")
        os.replace(part, state_path)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="land the files (default: a dry run that writes nothing)")
    ap.add_argument("--client", action="append", help="client id; repeat for several (default: every scheduled client)")
    ap.add_argument("--source", help="the client analysis share (default: deck_status.SRC_ILS_ANALYSIS)")
    ap.add_argument("--schedule", help="the schedule .csv or .xlsx (default: deck_status.SRC_ILS_SCHEDULE)")
    ap.add_argument("--root", help="the ILS Analysis folder (default: Inputs/ILS Analysis under RPE_DATA_ROOT)")
    ap.add_argument("--horizon-days", type=int, default=L.HORIZON_DAYS)
    ap.add_argument("--budget-minutes", type=float, default=BUDGET_MINUTES)
    ap.add_argument("--current-only", action="store_true",
                    help="land only the clients whose newest pull is current for their review (default: every scheduled "
                         "client's newest pull, as Aaron chose; a stale one is landed and marked not current)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    lines = []

    def say(s):
        lines.append(s)
        print(s, flush=True)
    rc = run(apply=a.apply, clients=a.client, source=a.source, schedule=a.schedule, dest_root=a.root,
             horizon_days=a.horizon_days, budget_minutes=a.budget_minutes, current_only=a.current_only, say=say)
    if a.apply:
        # The scheduled task runs under pythonw, which has no console: the report goes to Build Artifacts too.
        text = f"# ILS analysis landing, {datetime.now():%Y-%m-%d %H:%M}\n\n" + "\n".join(lines) + "\n"
        try:
            d = artifacts_dir()
            (d / "landing_latest.md").write_text(text, encoding="utf-8")
            with open(d / "landing.log", "a", encoding="utf-8") as fh:
                fh.write(text + "\n---\n\n")
        except OSError as e:
            print(f"!! could not write the landing report: {e}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
