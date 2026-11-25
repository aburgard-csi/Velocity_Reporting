"""
ils_review_runs.py: the ILS Review card on a client's page in CSM Sheila (Aaron, 2026-11-24: "We need to build the
ability to generate the ILS review decks into Sheila").

The card builds the ILS Program Analysis deck (build/ils_analysis, `python -m ils_review.cli`, called as its own
command line and never changed here) for a client on the ILS analysts' review schedule, from that client's newest
landed data pull, and puts it in `Outputs/<CSM>/ILS/` when it passes validate_deck at 0 FAIL. A second button merges
the client's prep slides in (build/ils_analysis/merge_review.py) when a prep deck is on hand.

    review_doc(cid)      the card: readiness checks, the prep deck it would merge, the decks in Outputs, a run
    scheduled_clients()  {id: {name, csm}} of the clients on the schedule now (Sheila lists them)
    run_review(args)     the run itself, in the child process (scripts/ils_job.py, analysis "review")

**Readiness** reads only what the landing step (scripts/land_ils_analysis.py) leaves in `Inputs/ILS Analysis/_schedule/`
and the landed pull itself, never the analysts' shares:

  unknown        the data root or Inputs cannot be read (off the VPN): never "ready"
  waiting        nothing landed yet, the landing step has not reached the client, or the newest pull is an earlier
                 review's (`pulls.json` "current" false): "waiting for this review's data pull", with both dates
  not_scheduled  the client is not on the schedule snapshot
  blocked        the pull has a problem, or its ZAccounts extract (the one file the builder cannot do without) is not
                 on hand
  ready          everything the build needs; ZTrend, the other extracts, the peer metrics table and the cycle's
                 industry file are reported (a missing one costs the sections that need it, said on the Data Notes
                 slide) but never block

**The run.** The pull is staged UNZIPPED into the local cache (`<ti_cache_root>/ils_review/<id>/<pull>/`, kept inside
`build/local_cache.py`'s size and age limits with the Transaction Intelligence cache), the builder runs into
`Build Artifacts/ils/review/<id>/<pull>/` (the deck and `charts/`), validate_deck runs on the deck, and only a 0 FAIL
deck with the validator's own zero exit is copied to `Outputs/<CSM>/ILS/` as `<id>-<yyyy.mm>-ILS-ANL-<Client> ILS
Analysis.pptx` (ils_job.deliver; the deck it replaces moves to `ILS/_Archive/`). Anything else stays in Build
Artifacts and the card says why. `yyyy.mm` is the pull month, as the builder names it.

**With the prep slides.** The prep folder is `RPE_ILS_PREP_DIR` (environment, else the repo's `.env`, else the default
below; read on every call), and the client's prep deck is its newest `<id>-<yyyy.mm>-ILS-<Client> Prep Slides*.pptx`,
matched by CLIENT NUMBER: the prep deck is named for the upcoming review month and the analysis deck for the pull
month, so the periods never agree. The analysis deck is built again without its own matrix section (merge_review puts
the prep deck's Matrix Parameters / Overrides slides at the start of each risk analysis; built with both, the matrix
slides appear twice) into `with_prep/`, merged, validated, and delivered as `<id>-<yyyy.mm>-ILS-REV-<Client> ILS
Review.pptx`. No folder, or no prep deck for the client: the button is not offered.

**Contact Us.** The builder draws the client's CSM card itself. The ILS consultant card is the schedule row's
`consultant` (a NAME only: the snapshot never copies contact details) looked up in CSM Contacts.csv
(`rpe_env.contact_by_name`); no name, no row, or the consultant being the client's CSM means no second card, and the
card says which.

Import-safe: nothing touches the share until a function is called.
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for _p in (REPO / "build", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rpe_env as R                                             # noqa: E402

KIND = "review"
PREP_ENV = "RPE_ILS_PREP_DIR"
_DEFAULT_PREP_DIR = r"C:\Data Pipelines\ILS Pipeline"
BUILDER_DIR = REPO / "build" / "ils_analysis"
MERGE_TOOL = BUILDER_DIR / "merge_review.py"
VALIDATOR = REPO / "validation" / "validate_deck.py"
VALIDATION_SUFFIX = ".validation.txt"
CACHE_SUB = "ils_review"
PREP_RX = r"^{cid}-(\d{{4}}\.\d{{2}})-ILS-.*Prep Slides.*\.pptx$"
DECK_PERIOD_RX = re.compile(r"^\d{3,5}-(\d{4}\.\d{2})-ILS-")
VERDICT_RX = re.compile(r"(\d+) FAIL, (\d+) REVIEW")
# The builder lines the card carries into the result (build/ils_analysis/ils_review/build.py prints them).
NOTE_RX = re.compile(r"^\s*(?:! )?(The deck has \d+ slides.*|Done — .*|\d+ section\(s\) reported an error.*|Deck checks.*|"
                     r"(?:FAIL|REVIEW) slide .*)$")
MAX_NOTES = 14
# The analysis deck's own matrix section, left out when the prep deck's matrix slides are merged in.
MATRIX_SECTION = "matrix"


# ------------------------------------------------------------------ where
def prep_dir():
    """The folder the prep slides are in, or None when the setting names no folder on this PC (the button is hidden)."""
    raw = os.environ.get(PREP_ENV) or R._load_dotenv().get(PREP_ENV) or _DEFAULT_PREP_DIR
    p = Path(raw)
    try:
        return p if p.is_dir() else None
    except OSError:
        return None


def prep_deck(cid, folder=None):
    """{name, path, period} of the client's newest prep deck (by its period, then modified time), else None. Matched by
    client number, never by period. Office's `~$` lock files are not decks."""
    folder = Path(folder) if folder else prep_dir()
    if folder is None:
        return None
    rx = re.compile(PREP_RX.format(cid=re.escape(str(cid))), re.I)
    found = []
    try:
        for p in folder.glob(f"{cid}-*.pptx"):
            m = rx.match(p.name)
            if m and not p.name.startswith("~$") and p.is_file():
                found.append((m.group(1), p.stat().st_mtime, p))
    except OSError:
        return None
    if not found:
        return None
    period, _, p = max(found)
    return {"name": p.name, "path": str(p), "period": period}


def work_dir(cid, pull, with_prep=False):
    d = R.build_artifacts() / "ils" / "review" / str(cid) / str(pull)
    return d / "with_prep" if with_prep else d


def cache_root():
    import local_cache
    return local_cache.ti_cache_root() / CACHE_SUB


def ils_outputs(cid):
    import ils_job
    return R.client_outputs(cid) / ils_job.ILS_DIRNAME


# ------------------------------------------------------------------ the schedule, as the landing step left it
def _landed():
    import ils_analysis_landed as L
    return L


def _schedule_row(cid, rows):
    L = _landed()
    return L.in_scope(rows).get(str(cid))


def scheduled_clients():
    """{id: {"name", "csm"}} for every client on the schedule snapshot now; {} when it cannot be read."""
    try:
        L = _landed()
        return {r["fi_id"]: {"name": _clean_name(r["fi_id"], r.get("fi_name")), "csm": (r.get("csm") or "").strip()}
                for r in L.scheduled()}
    except (OSError, SystemExit, ValueError, KeyError):
        return {}


def share_readable():
    """True when Inputs can be read now. The schedule readers answer {} / [] when they cannot read, which looks the
    same as "nothing scheduled", so the ILS Decks list asks this first and reads every row as not checked when it is
    False: an unreadable share never reads as "no review scheduled", let alone Ready."""
    try:
        return R.inputs().is_dir()
    except (OSError, SystemExit):
        return False


def landed_pulls():
    """{client id: newest pull stamp} of the pulls landed in Inputs/ILS Analysis/<id>/<yyyymmdd>/ (the landing step's
    folders, never the analysts' share); {} when the folder cannot be read. For the ILS Decks list's pull column."""
    out = {}
    try:
        base = _landed().root()
        clients = [d for d in base.iterdir() if d.is_dir() and re.fullmatch(r"\d{3,5}", d.name)]
    except (OSError, SystemExit):
        return out
    for d in clients:
        try:
            pulls = [p.name for p in d.iterdir() if p.is_dir() and re.fullmatch(r"\d{8}", p.name)]
        except OSError:
            continue
        if pulls:
            out[d.name] = max(pulls)
    return out


def _clean_name(cid, name):
    """The schedule's fi_name can lead with the client number ("7001 - Harbor FCU"): the name alone."""
    s = str(name or "").strip()
    return re.sub(rf"^{re.escape(str(cid))}\s*[-_:]\s*", "", s).strip()


def client_name(cid, given="", row=None):
    """The name the deck carries: the one the page shows, else the Client CSM List's, else the schedule's."""
    if str(given or "").strip():
        return str(given).strip()
    try:
        import csv
        p = R.csm_list_file()
        if p and p.is_file():
            with open(p, encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    if (r.get("client_id") or "").strip() == str(cid) and (r.get("client_name") or "").strip():
                        return r["client_name"].strip()
    except (OSError, SystemExit):
        pass
    return _clean_name(cid, (row or {}).get("fi_name") or (row or {}).get("name")) or str(cid)


def consultant_card(cid, name):
    """(contact dict or None, sentence). The schedule's consultant, looked up in CSM Contacts.csv."""
    name = str(name or "").strip()
    if not name:
        return None, "The schedule names no ILS consultant (or the snapshot predates the consultant column): Contact Us carries the CSM card only."
    try:
        csm = R.client_csm(cid)
    except (OSError, SystemExit):
        csm = None
    if csm and csm.casefold() == name.casefold():
        return None, f"The ILS consultant, {name}, is also the client's CSM: Contact Us carries that one card."
    try:
        c = R.contact_by_name(name, cid)
    except (OSError, SystemExit):
        return None, f"The ILS consultant, {name}, has no usable row in CSM Contacts.csv: Contact Us carries the CSM card only."
    return c, f"Contact Us adds the ILS consultant card for {name}."


def _age_days(path):
    try:
        return int((_dt.datetime.now().timestamp() - Path(path).stat().st_mtime) // 86400)
    except OSError:
        return None


def _peer_and_industry(today=None):
    """Checks for the two files the builder reads from Build Artifacts/ils_analysis (it never stops for want of them)."""
    out = []
    base = R.build_artifacts() / "ils_analysis"
    peers = sorted(glob.glob(str(base / "peers" / "ils_peer_metrics*.csv")), key=lambda p: os.path.getmtime(p))
    if peers:
        age = _age_days(peers[-1])
        out.append({"level": "ok", "text": f"Peer metrics: {len(peers)} table(s), the newest {age} day(s) old."})
    else:
        out.append({"level": "warn", "text": "No peer metrics table (Build Artifacts/ils_analysis/peers): the peer "
                                             "comparison slides say no peers could be read."})
    month = (today or _dt.date.today()).strftime("%Y-%m")
    ind = sorted(glob.glob(str(base / "standard" / "industry_*.json")))
    want = f"industry_{month}.json"
    if any(os.path.basename(p) == want for p in ind):
        out.append({"level": "ok", "text": f"Industry update: {want} is on hand."})
    elif ind:
        out.append({"level": "warn", "text": f"Industry update: no {want}; the deck uses the newest on hand, "
                                             f"{os.path.basename(ind[-1])}."})
    else:
        out.append({"level": "warn", "text": f"Industry update: no industry file (Build Artifacts/ils_analysis/standard): "
                                             f"those slides are skipped."})
    return out


def pull_period(pull):
    """yyyy.mm of a pull stamp (yyyymmdd or yyyymm), the month the builder names its deck for; None if unreadable."""
    s = str(pull or "")
    return f"{s[:4]}.{s[4:6]}" if re.fullmatch(r"\d{6}(\d{2})?", s) else None


def _decks_in_outputs(cid, pull=None):
    """{"analysis": {...}, "review": {...}} for the newest delivered deck of each kind, or None for a kind with none.
    Each carries `current`: its period is the month of `pull`, this review's data. Reviews recur, so a deck from an
    earlier review's pull is listed but never makes the card read as done."""
    import ils_job
    out = {}
    try:
        d = ils_outputs(cid)
    except (OSError, SystemExit):
        return {"analysis": None, "review": None}
    for key, kind in (("analysis", "review"), ("review", "review_prep")):
        tag = ils_job.TITLES[kind][0]
        try:
            decks = sorted(d.glob(f"{cid}-*-ILS-{tag}-*.pptx"), key=lambda p: p.stat().st_mtime)
        except OSError:
            decks = []
        want = pull_period(pull)
        out[key] = ({"deck": str(decks[-1]), "name": decks[-1].name,
                     "when": _dt.datetime.fromtimestamp(decks[-1].stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                     "current": bool(want) and (DECK_PERIOD_RX.match(decks[-1].name) or [None, None])[1] == want}
                    if decks else None)
    return out


# ------------------------------------------------------------------ readiness
def readiness(cid, today=None):
    """The card's facts and its state. See the module docstring for the states."""
    cid = str(cid)
    doc = {"label": "ILS Review", "state": "unknown", "why": "", "checks": [], "pull": None, "review_date": None,
           "name": None, "consultant": None, "prep": None, "prep_dir": None}
    L = _landed()

    def stop(state, why, level="stop"):
        doc["state"], doc["why"] = state, why
        doc["checks"].append({"level": level, "text": why})
        return doc

    try:
        inputs = R.inputs()
        if not inputs.is_dir():
            raise OSError(f"{inputs} is not a folder")
    except (OSError, SystemExit) as e:
        return stop("unknown", f"The share cannot be read now ({e}); connect to the VPN and Check again. "
                               "Nothing can be said about this client's ILS review until then.")
    base = L.root()
    sched = L.schedule_dir(base)
    snap = sched / L.SNAPSHOT_NAME
    try:
        have_snap = snap.is_file()
    except OSError as e:
        return stop("unknown", f"{sched} cannot be read now ({e}).")
    if not have_snap:
        return stop("waiting", "No review schedule has been landed yet: the ILS analysis landing step "
                               "(scripts/land_ils_analysis.py) keeps it, and has not run on this share.", "warn")
    try:
        rows = L.snapshot_rows(base)
        row = _schedule_row(cid, rows)
    except (OSError, ValueError) as e:
        return stop("unknown", f"The schedule snapshot cannot be read ({e}).")
    if row is None:
        return stop("not_scheduled", "Not on the ILS analysts' review schedule (a review in the next "
                                     f"{L.HORIZON_DAYS} days, or overdue).", "warn")
    doc["review_date"] = row.get("review_date") or None
    doc["status"] = row.get("status") or ""
    doc["name"] = client_name(cid, "", row)
    doc["checks"].append({"level": "ok", "text": f"On the review schedule: review {row.get('review_date') or 'date not set'}"
                                                 f" ({row.get('status') or 'no status'})."})
    pulls = L.pulls_status(base)
    if not pulls:
        return stop("waiting", "The landing step has not recorded any pulls yet (no _schedule/pulls.json): waiting for "
                               "its first run.", "warn")
    ent = (pulls.get("clients") or {}).get(cid)
    if not ent:
        return stop("waiting", f"The landing step has not reached this client yet (pulls.json written "
                               f"{pulls.get('written') or '?'}): waiting for this review's data pull.", "warn")
    pull = ent.get("pull")
    doc["pull"] = pull
    if ent.get("problem"):
        return stop("blocked", f"The landing step could not land this client's pull: {ent['problem']}")
    if not pull:
        return stop("waiting", f"Waiting for this review's data pull: none on the analysis share yet "
                               f"(review {doc['review_date'] or 'date not set'}).", "warn")
    if not ent.get("current"):
        return stop("waiting", f"Waiting for this review's data pull: the newest pull is {pull}, the review is "
                               f"{doc['review_date'] or 'not dated'}" + (f" ({ent['reason']})." if ent.get("reason")
                                                                         else "."), "warn")
    live = L.landed_files(cid, pull, base)
    differs = set(ent.get("differs") or [])
    zacc = live.get("zaccounts")
    if zacc is None or any(d.startswith(f"{cid}_zaccounts_") for d in differs):
        return stop("blocked", f"The pull {pull} has no ZAccounts extract on hand in Inputs/ILS Analysis/{cid}/{pull}/, "
                               "and the deck cannot be built without it.")
    doc["checks"].append({"level": "ok", "text": f"Data pull {pull}, current for the review: {ent.get('reason') or ''}".strip()})
    if "ztrend" not in live:
        doc["checks"].append({"level": "warn", "text": "No ZTrend extract in the pull: the notice, fee and scoring "
                                                       "sections are skipped and said on the Data Notes slide."})
    others = [k for k in L.BUILDER_KINDS if k not in live and k not in ("zaccounts", "ztrend")]
    doc["checks"].append({"level": "ok", "text": "Extracts on hand: " + ", ".join(sorted(live))
                          + (f". Not in the pull: {', '.join(others)} (the sections that need them are skipped)." if others else ".")})
    doc["checks"] += _peer_and_industry(today)
    card, sentence = consultant_card(cid, row.get("consultant") or ent.get("consultant"))
    doc["consultant"] = card["name"] if card else None
    doc["checks"].append({"level": "ok", "text": sentence})
    try:
        csm = R.client_csm(cid)
        dest = ils_outputs(cid)
    except (OSError, SystemExit):
        csm, dest = None, None
    doc["checks"].append({"level": "ok" if csm else "warn",
                          "text": (f"Goes to {dest} when it passes validation." if csm else
                                   f"No CSM in the Client CSM List for {cid}: the deck goes to {dest} and has no "
                                   "Contact Us slide.")})
    doc["state"], doc["why"] = "ready", ""
    return doc


def review_doc(cid, job=None):
    """The ILS Review card for /api/ils/client: readiness, the prep deck (hidden when none), the decks in Outputs, a run."""
    try:
        doc = readiness(cid)
    except Exception as e:                       # the card must never take the client page down
        doc = {"label": "ILS Review", "state": "unknown", "why": f"{type(e).__name__}: {e}",
               "checks": [{"level": "stop", "text": f"The ILS Review card could not be read: {type(e).__name__}: {e}"}]}
    try:
        folder = prep_dir()
        doc["prep_dir"] = str(folder) if folder else None
        doc["prep"] = prep_deck(cid, folder) if folder else None
    except (OSError, SystemExit):
        doc["prep"] = None
    try:
        doc["decks"] = _decks_in_outputs(cid, doc.get("pull"))
    except (OSError, SystemExit):
        doc["decks"] = {"analysis": None, "review": None}
    doc["job"] = job
    return doc


# ------------------------------------------------------------------ the run (child process)
def stage_pull(cid, pull, say=print):
    """The pull's extracts, unzipped, in the local cache; the client's other pulls there are removed first."""
    # No trim here: a review is not in Sheila's build queue, so trimming the shared cache now could evict a client a
    # Transaction Intelligence build is using. The cache is trimmed when Sheila starts and at each TI stage, and
    # ils_review/ is one of its SUBDIRS, so these files are counted there.
    import local_cache
    L = _landed()
    client_dir = cache_root() / str(cid)
    if client_dir.is_dir():
        for old in client_dir.iterdir():
            if old.is_dir() and old.name != str(pull):
                shutil.rmtree(old, ignore_errors=True)
    dest = client_dir / str(pull)
    say(f"staging pull {pull} into the local cache ({dest})")
    staged = L.stage(cid, pull, dest)
    local_cache.touch(cid)
    say("staged: " + ", ".join(f"{k} ({p.stat().st_size / 1_048_576:,.1f} MB)" for k, p in sorted(staged.items())))
    return dest


def builder_cmd(stage_dir, name, cid, out_dir, chart_dir, consultant=None, sections=None):
    cmd = [sys.executable, "-m", "ils_review.cli", "--from-folder", str(stage_dir), "--client", name,
           "--client-id", str(cid), "--out-dir", str(out_dir), "--chart-dir", str(chart_dir)]
    if consultant:
        cmd += ["--consultant", "|".join(str(consultant.get(k) or "").replace("|", "/")
                                         for k in ("name", "role", "phone", "email"))]
    if sections:
        cmd += ["--sections", ",".join(sections)]
    return cmd


def run_streamed(cmd, cwd, say=print):
    """(exit code, every line) of a child run, each line said as it comes (no timeout, as Sheila's other runs)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    lines = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", env=env, cwd=str(cwd))
    for line in proc.stdout:
        line = line.rstrip("\r\n")
        lines.append(line)
        say(line)
    return proc.wait(), lines


def default_sections_without_matrix():
    """The builder's default sections less its matrix section. Read from the builder's config as text, so Sheila's
    process never imports the builder."""
    text = (BUILDER_DIR / "ils_review" / "config.py").read_text(encoding="utf-8")
    m = re.search(r"^DEFAULT_SECTIONS\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    if not m:
        raise ValueError("the builder's DEFAULT_SECTIONS could not be read")
    keys = re.findall(r'"([a-z_]+)"', re.sub(r"#.*", "", m.group(1)))
    if MATRIX_SECTION not in keys:
        raise ValueError("the builder's default sections carry no matrix section to leave out")
    return [k for k in keys if k != MATRIX_SECTION]


def _deck_from(lines, out_dir):
    hit = next((ln.split("Saved:", 1)[1].strip() for ln in reversed(lines) if ln.strip().startswith("Saved:")), None)
    if hit and Path(hit).is_file():
        return Path(hit)
    decks = sorted(Path(out_dir).glob("*-ILS-*ILS Analysis.pptx"), key=lambda p: p.stat().st_mtime)
    return decks[-1] if decks else None


def builder_notes(lines):
    """The builder's own lines the CSM should see: slide count against its cap, failed sections, its deck checks."""
    out = [m.group(1) for m in (NOTE_RX.match(ln) for ln in lines) if m]
    return out[:MAX_NOTES] + ([f"... and {len(out) - MAX_NOTES} more deck-check line(s) in the log"]
                              if len(out) > MAX_NOTES else [])


def validate(deck, say=print):
    """(passed, verdict, FAIL lines). Fails closed: only a parsed `0 FAIL` with the validator's own zero exit passes.
    The report is kept beside the deck (`<deck>.validation.txt`)."""
    r = subprocess.run([sys.executable, str(VALIDATOR), str(deck)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(REPO))
    out = r.stdout or ""
    try:
        Path(str(deck) + VALIDATION_SUFFIX).write_text(out + (r.stderr or ""), encoding="utf-8")
    except OSError:
        pass
    m = None
    for m in VERDICT_RX.finditer(out):
        pass
    fails = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("[FAIL")]
    if m is None:
        verdict = "no verdict (the validator did not finish)"
        tail = (r.stderr or out).strip().splitlines()[-1:] or [""]
        say(f"validation: {verdict} {tail[0]}")
        return False, verdict, fails
    verdict = f"{m.group(1)} FAIL, {m.group(2)} REVIEW"
    say(f"validation: {verdict}")
    for f in fails[:20]:
        say("  " + f)
    return (r.returncode == 0 and m.group(1) == "0"), verdict, fails


def run_review(a, say=print):
    """The ILS Review run for the client in `a` ({"client", "client_name", "merge_prep"}). -> the ILS_RESULT dict."""
    import ils_job
    cid = str(a["client"])
    merge = bool(a.get("merge_prep"))
    out = {"ok": False, "needs_codes": False, "deck": None, "folder": None, "notes": [], "verdict": None,
           "delivered": False, "merge_prep": merge, "prep": None}
    doc = readiness(cid)
    if doc["state"] != "ready":
        out["error"] = doc["why"] or f"not ready ({doc['state']})"
        say(f"[STOP] {out['error']}")
        return out
    prep = None
    if merge:
        prep = prep_deck(cid)
        if not prep:
            out["error"] = f"no prep deck for {cid} in {prep_dir() or 'the prep folder (' + PREP_ENV + ' is not set here)'}"
            say(f"[STOP] {out['error']}")
            return out
        out["prep"] = prep["name"]
        say(f"prep slides to merge: {prep['name']}")
    pull = doc["pull"]
    L = _landed()
    row = _schedule_row(cid, L.snapshot_rows())
    name = client_name(cid, a.get("client_name"), row)
    card, sentence = consultant_card(cid, (row or {}).get("consultant"))
    say(sentence)
    stage_dir = stage_pull(cid, pull, say)
    work = work_dir(cid, pull, with_prep=merge)
    work.mkdir(parents=True, exist_ok=True)
    out["folder"] = str(work)
    sections = default_sections_without_matrix() if merge else None
    if merge:
        say("building the analysis deck without its own matrix section (the prep deck's matrix slides go in its place)")
    cmd = builder_cmd(stage_dir, name, cid, work, work / "charts", card, sections)
    say(f"building the ILS Program Analysis deck for {name} ({cid}), pull {pull}")
    code, lines = run_streamed(cmd, BUILDER_DIR, say)
    out["notes"] = builder_notes(lines)
    deck = _deck_from(lines, work)
    if code != 0 or deck is None:
        out["error"] = f"the builder stopped (exit {code}) before a deck was saved" if deck is None else \
            f"the builder exited {code}"
        say(f"[STOP] {out['error']}")
        return out
    try:
        from pptx import Presentation
        n = len(Presentation(str(deck)).slides)
        say(f"deck: {deck} ({n} slides)")
    except Exception as e:                       # noqa: BLE001 — the validator below says what is wrong with it
        say(f"[note] the deck could not be opened to count its slides: {e}")
    period = (DECK_PERIOD_RX.match(deck.name) or [None, None])[1]
    if not period:
        out["error"] = f"the deck's name {deck.name} carries no <yyyy.mm>"
        say(f"[STOP] {out['error']}")
        return out
    kind = "review"
    if merge:
        safe = re.sub(r'[<>:"/\\|?*]', "", name).strip() or cid
        merged = work / f"{cid}-{period}-ILS-{safe} ILS Review.pptx"
        say(f"merging {prep['name']} into it")
        mcode, mlines = run_streamed([sys.executable, str(MERGE_TOOL), str(deck), "--prep", prep["path"],
                                      "--out", str(merged)], REPO, say)
        if mcode != 0 or not merged.is_file():
            out["error"] = f"the prep merge stopped (exit {mcode})"
            say(f"[STOP] {out['error']}")
            return out
        out["notes"].append(next((ln for ln in reversed(mlines) if "->" in ln), "").split(" -> ")[0])
        deck, kind = merged, "review_prep"
    passed, verdict, fails = validate(deck, say)
    out["verdict"] = verdict
    out["deck"] = str(deck)
    if not passed:
        out["error"] = (f"validation: {verdict}. The deck stays in {work} and is not put in Outputs"
                        + (f"; first: {fails[0]}" if fails else "."))
        say(f"[STOP] {out['error']}")
        return out
    try:
        dest = ils_job.deliver(kind, cid, deck, period, name)
    except (OSError, SystemExit) as e:
        out["error"] = f"the deck passed but could not be put in Outputs ({e}); it is in {work}"
        say(f"[WARN] {out['error']}")
        return out
    out.update(ok=True, deck=str(dest), delivered=True)
    return out
