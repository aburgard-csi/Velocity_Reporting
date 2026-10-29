"""
ils_runs.py — what Sheila's ILS tab reads and starts: the clients with an ILS extract landed, the two
steps of a run as background jobs, and the codes each client's last run was confirmed with.

James Gilmore, 2026-10-28: "a CSM can run either ILS analysis option from the Sheila webpage". The two
options are James's v5 engines, unchanged under build/ils_pipeline/:

  pgl      the pre-go-live review:  Inputs/ILS PGL/<id>/      -> Build Artifacts/ils/PGL/<id>/<yyyymmdd>/
  kickoff  the kickoff analysis:    Inputs/ILS Kickoff/<id>/  -> Build Artifacts/ils/kickoff/<id>/<yyyy-mm>/

Both are two-step, and the tab keeps that: step 1 reads the newest extract and shows the field summary
(the distinct values of each code field, with counts) and computes nothing; step 2 runs on the codes the
CSM confirmed. Which value means open, personal, OD-eligible or opted in is the client's answer, never
the tool's: the codes a client's last run used are offered back, labelled with that run's date and file,
and nothing runs on them until the CSM presses Build.

Each step runs in its own process (scripts/ils_job.py), as Sheila's deck builds do. Reveal opens only a
file under Build Artifacts/ils, so the Outputs-only rule for decks (ars_launcher_web.reveal) is unchanged.
"""
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import rpe_env as R

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

KINDS = {
    "pgl": {"label": "Pre-go-live", "input": "ILS PGL", "out": "PGL"},
    "kickoff": {"label": "Kickoff", "input": "ILS Kickoff", "out": "kickoff"},
}
# the code fields each engine takes, in the order the tab shows them
FIELDS = {
    "pgl": ["open_status", "od_eligible", "rege_opt_in", "rege_opt_out"],
    "kickoff": ["personal_code", "business_code", "open_code", "eligible_stat_codes", "rege_opt_in",
                "rege_opt_out"],
}
REQUIRED = {"pgl": ["open_status", "od_eligible", "rege_opt_in"],
            "kickoff": ["personal_code", "business_code", "open_code", "eligible_stat_codes"]}
CID_RX = re.compile(r"^\d{3,5}$")
PERIOD_RX = re.compile(r"^\d{4}-\d{2}$")
RESULT_RX = re.compile(r"^ILS_RESULT (\{.*\})\s*$")
STAMP_RX = re.compile(r"(\d{8})")
ZIP_RX = re.compile(r"^(\d{3,5})(?!\d).*\.zip$", re.I)


def _input_root(kind):
    return R.input_dir(KINDS[kind]["input"], create=False)


def _out_root(kind):
    return R.build_artifacts() / "ils" / KINDS[kind]["out"]


def _codes_file(kind, cid):
    return _out_root(kind) / str(cid) / "confirmed_codes.json"


def _extract(kind, cid):
    """The extract the engine would read, as the engine finds it (its own resolver), or None."""
    folder = _input_root(kind) / str(cid)
    try:
        if kind == "pgl":
            from ils_pipeline.pre_go_live import loader
            found = loader.find_extract(_input_root(kind), cid)
            return found.path
        from ils_pipeline.kickoff.core import io
        return io.resolve_data_file(_input_root(kind), str(cid), "")
    except (FileNotFoundError, OSError, ValueError):
        return None
    except Exception:            # an engine import failing must not take the tab down
        return next(iter(sorted(folder.glob("*"))), None) if folder.is_dir() else None


def _landed_zips(cid):
    from ils_pipeline import pgl_input
    return pgl_input.landed_zips(_input_root("pgl"), cid)


def default_period(path):
    """The kickoff's period (it names the output folder): the month of the date in the extract's name."""
    m = STAMP_RX.search(Path(path).name) if path else None
    if m:
        try:
            return _dt.datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m")
        except ValueError:
            pass
    return _dt.date.today().strftime("%Y-%m")


def saved_codes(kind, cid):
    try:
        return json.loads(_codes_file(kind, cid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_codes(kind, cid, codes, extract, options):
    p = _codes_file(kind, cid)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"codes": codes, "options": options, "extract": Path(extract).name if extract else None,
           "confirmed": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "by": os.environ.get("USERNAME") or os.environ.get("USER") or ""}
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return rec


def last_output(kind, cid):
    """The newest deck a run wrote for the client, with its folder, or None."""
    base = _out_root(kind) / str(cid)
    try:
        decks = sorted(base.glob("*/*.pptx"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    if not decks:
        return None
    d = decks[-1]
    return {"deck": str(d), "name": d.name, "folder": str(d.parent),
            "when": _dt.datetime.fromtimestamp(d.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}


def landed_clients():
    """Every client with a folder under either ILS input kind: Sheila lists them, so a client who is on
    ILS alone (a pre-go-live prospect, a kickoff) can be opened and run from the client page."""
    out = set()
    for kind in KINDS:
        try:
            root = _input_root(kind)
            out.update(d.name for d in root.iterdir() if d.is_dir() and CID_RX.match(d.name))
            if kind == "pgl":            # a pre-go-live delivery may land as <id>_..._PGL_<date>.zip
                out.update(m.group(1) for m in (ZIP_RX.match(p.name) for p in root.iterdir()
                                                if p.is_file()) if m)
        except (OSError, SystemExit):
            continue
    return out


def client_doc(cid):
    """The client page's ILS cards: for each analysis, where its extract lands, the extract the engine
    would read, the period (kickoff), the codes last confirmed, the newest deck, and a running job."""
    out = {}
    for kind, k in KINDS.items():
        try:
            folder = _input_root(kind) / str(cid)
        except (OSError, SystemExit) as e:
            out[kind] = {"label": k["label"], "folder": None, "error": str(e)}
            continue
        landed = folder.is_dir() or (kind == "pgl" and bool(_landed_zips(cid)))
        ex = _extract(kind, cid) if landed else None
        out[kind] = {"label": k["label"], "folder": str(folder), "exists": landed,
                     "extract": ex.name if ex else None,
                     "period": default_period(ex) if kind == "kickoff" else None,
                     "saved": saved_codes(kind, cid), "last": last_output(kind, cid),
                     "job": job_doc(kind, cid)}
    return {"client": str(cid), "kinds": out, "fields": FIELDS, "required": REQUIRED}


# ------------------------------------------------------------------ jobs
class IlsJob:
    def __init__(self, kind, cid, args):
        self.kind, self.cid, self.args = kind, cid, args
        self.step = 2 if args.get("codes") else 1
        self.lines, self.done, self.code, self.result = [], False, None, None
        self.started, self.finished = time.time(), None

    def run(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        cmd = [sys.executable, str(HERE / "ils_job.py"), json.dumps(self.args)]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", env=env, cwd=str(REPO))
            for line in proc.stdout:
                line = line.rstrip("\r\n")
                m = RESULT_RX.match(line)
                if m:
                    try:
                        self.result = json.loads(m.group(1))
                    except ValueError:
                        pass
                    continue
                self.lines.append(line)
            self.code = proc.wait()
        except OSError as e:
            self.lines.append(f"[STOP] The run could not start: {e}")
            self.code = 1
        if self.step == 2 and self.result and self.result.get("ok"):
            try:
                save_codes(self.kind, self.cid, self.args["codes"], _extract(self.kind, self.cid),
                           {k: self.args[k] for k in ("fee", "include_deleted", "current_only",
                                                     "items_from_calc", "period") if k in self.args})
            except OSError as e:
                self.lines.append(f"[note] the codes were not saved for next time: {e}")
        self.finished = time.time()
        self.done = True

    def to_json(self):
        r = self.result or {}
        return {"kind": self.kind, "client": self.cid, "step": self.step, "lines": self.lines,
                "done": self.done, "code": self.code, "ok": bool(r.get("ok")) if self.done else None,
                "needs_codes": bool(r.get("needs_codes")), "deck": r.get("deck"), "folder": r.get("folder"),
                "error": r.get("error"),
                "seconds": round((self.finished or time.time()) - self.started)}


_jobs = {}
_lock = threading.Lock()


def job_doc(kind, cid):
    j = _jobs.get((kind, cid))
    return j.to_json() if j else None


def start(body):
    """POST /api/ils/run: step 1 when no codes are given, step 2 with them. 409 while one runs."""
    kind = str(body.get("kind", ""))
    cid = str(body.get("client", "")).strip()
    if kind not in KINDS:
        return 400, {"error": "not an ILS analysis"}
    if not CID_RX.match(cid):
        return 400, {"error": "not a client number"}
    args = {"analysis": kind, "client": cid}
    codes = body.get("codes") or None
    if codes:
        codes = {f: str(codes.get(f) or "").strip() for f in FIELDS[kind]}
        missing = [f for f in REQUIRED[kind] if not codes[f]]
        if missing:
            return 400, {"error": "confirm these codes first: " + ", ".join(missing)}
        args["codes"] = codes
    if kind == "kickoff":
        period = str(body.get("period") or "").strip() or default_period(_extract(kind, cid))
        if not PERIOD_RX.match(period):
            return 400, {"error": "the period is YYYY-MM"}
        args["period"] = period
        args["items_from_calc"] = bool(body.get("items_from_calc"))
    else:
        fee = body.get("fee")
        if fee not in (None, ""):
            try:
                args["fee"] = float(fee)
            except (TypeError, ValueError):
                return 400, {"error": "the fee is a number"}
        args["include_deleted"] = bool(body.get("include_deleted"))
        args["current_only"] = bool(body.get("current_only"))
    with _lock:
        j = _jobs.get((kind, cid))
        if j and not j.done:
            return 409, {"error": "a run is already going for this client", "job": j.to_json()}
        j = IlsJob(kind, cid, args)
        _jobs[(kind, cid)] = j
    threading.Thread(target=j.run, daemon=True).start()
    return 200, {"job": j.to_json()}


def reveal(path):
    """Show an ILS output in File Explorer — only a file or folder under Build Artifacts/ils."""
    try:
        p = Path(path).resolve()
        root = (R.build_artifacts() / "ils").resolve()
    except (OSError, SystemExit, TypeError):
        return 403, {"error": "Build Artifacts is not reachable."}
    if root not in p.parents or not p.exists():
        return 403, {"error": "Only an ILS output can be shown."}
    if p.is_file():
        subprocess.Popen(["explorer", "/select,", str(p)])
    else:
        subprocess.Popen(["explorer", str(p)])
    return 200, {"ok": True}
