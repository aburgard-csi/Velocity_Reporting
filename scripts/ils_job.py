#!/usr/bin/env python3
"""
ils_job.py — one step of an ILS run, in its own process, for Sheila's ILS tab (scripts/ils_runs.py).

    python scripts/ils_job.py '<json>'

The json names the analysis ("pgl" or "kickoff"), the client, and — for step 2 — the codes the CSM
confirmed. With no codes it is step 1: the engine reads the newest extract and prints the field
summary (the distinct values of each code field, with counts) and computes nothing. With codes it is
step 2: the engine's report (PGL) or workbook (kickoff) and the deck.

The engines are James's v5 ones, unchanged (build/ils_pipeline/). This file only calls them as their
own command lines do, prints what they print, and ends with one line
`ILS_RESULT {"ok": ..., "deck": ..., "folder": ...}` for Sheila to read. A run in its own process
keeps v5's pandas-2 string setting and its memory out of Sheila's.
"""
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for p in (REPO / "build", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


ILS_DIRNAME = "ILS"
TITLES = {"pgl": ("PGL", "ILS Pre-Go-Live Review"), "kickoff": ("KO", "ILS Kickoff")}


def deliver(kind, cid, deck, period, client_name):
    """Copy a finished deck to `Outputs/<CSM>/ILS/` as `<id>-<yyyy.mm>-ILS-<PGL|KO>-<client> <title>.pptx`
    (James Gilmore, 2026-10-29: "the decks should be going in the respective output folders").

    A subfolder, not `Outputs/<CSM>/` itself: the ARS readers (the rebuild check, the In Outputs chip,
    deck readiness, the dashboard, the supersede step) take any `<id>-<period>-*.pptx` there for the
    client's RPE deck, and none of them looks below a CSM's folder. The run's own folder under Build
    Artifacts keeps its copy. A deck it replaces moves to `ILS/_Archive/`, never deleted."""
    import datetime as _d
    import re
    import shutil
    import rpe_env as R
    tag, title = TITLES[kind]
    name = re.sub(r'[<>:"/\\|?*]', "", str(client_name or cid)).strip() or str(cid)
    dest_dir = R.client_outputs(cid, create=True) / ILS_DIRNAME
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / f"{cid}-{period}-ILS-{tag}-{name} {title}.pptx"
    if dest.exists():
        arch = dest_dir / R.ARCHIVE_DIRNAME
        arch.mkdir(exist_ok=True)
        stamp = _d.date.today().isoformat()
        old, k = arch / f"{dest.stem} (superseded {stamp}){dest.suffix}", 1
        while old.exists():
            k += 1
            old = arch / f"{dest.stem} (superseded {stamp}-{k}){dest.suffix}"
        shutil.move(str(dest), str(old))
        print(f"archived the deck it replaces: {old}")
    shutil.copy2(str(deck), str(dest))
    print(f"in Outputs: {dest}")
    return dest


def _codes_list(v):
    """A code field as the CSM typed it: commas or spaces between values."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        parts = [str(x) for x in v]
    else:
        parts = str(v).replace(",", " ").split()
    parts = [x.strip() for x in parts if x.strip()]
    return parts or None


def pgl(a):
    from ils_pipeline.pre_go_live import report, run
    codes = a.get("codes") or None
    if codes:
        codes = {k: _codes_list(codes.get(k)) for k in ("open_status", "od_eligible", "rege_opt_in",
                                                         "rege_opt_out")}
    fee = a.get("fee")
    res = run(a["client"], codes=codes, fee=float(fee) if fee not in (None, "") else None,
              include_deleted=bool(a.get("include_deleted")))
    print(report(res))
    # the report prints the figures, not why a run stopped: say that too, or the card shows "stopped" alone
    for e in getattr(res, "errors", None) or []:
        print(f"[STOP] {e}")
    out = {"ok": bool(res.ok), "needs_codes": res.status == "needs_codes", "deck": None, "folder": None}
    if not res.ok and getattr(res, "errors", None):
        out["error"] = res.errors[0]
    # the codes the ILS dumps hold (pre_go_live/dump_codes.py), for the card to fill in for the CSM to confirm
    dc = (res.metrics or {}).get("pgl_dump_codes") or {}
    out["suggested"] = {k: ", ".join(v["codes"]) for k, v in dc.items() if v.get("codes")}
    out["suggested_basis"] = {k: v["basis"] for k, v in dc.items()}
    # James Gilmore, 2026-10-29: every OD code is eligible on a PGL, since the client mass-maintains codes the night
    # before go-live; the matrix's own reading stays in the basis for the CSM to see
    held = (dc.get("od_eligible") or {}).get("basis") or "no ILS matrix dump with the extract"
    out["suggested"]["od_eligible"] = "ALL"
    out["suggested_basis"]["od_eligible"] = (f"every OD status in the extract (the codes are mass-maintained "
                                             f"the night before go-live). The matrix today: {held}")
    if res.ok and res.status != "needs_codes":
        # the Velocity PGL review in Sheila's format (pre_go_live/sheila_deck.py, 2026-10-28)
        from ils_pipeline import pgl_input
        from ils_pipeline.pre_go_live import matrix_chapter, sheila_deck
        folder = Path(res.outputs["metrics"]).parent
        found = pgl_input.find_extract(a["client"])
        S, mfile = matrix_chapter.load(found.path.parent)
        path = sheila_deck.build(res.metrics, a["client"], a.get("client_name") or a["client"],
                                 folder / f"{a['client']} ILS Program Analysis - PGL Review {folder.name}.pptx",
                                 inputs=a.get("inputs") or {}, codes=res.metrics.get("pgl_codes_used"),
                                 extract=found.path.name, extract_date=found.date.date(),
                                 matrix=matrix_chapter.facts(S) if S else None,
                                 matrix_file=mfile.name if mfile else None)
        from pptx import Presentation
        print(f"\ndeck: {path} ({len(Presentation(str(path)).slides)} slides)")
        try:
            path = deliver("pgl", a["client"], path, found.date.strftime("%Y.%m"), a.get("client_name"))
        except OSError as e:
            print(f"[WARN] the deck could not be put in Outputs ({e}); it is in {folder}")
        out.update(deck=str(path), folder=str(folder))
    return out


def kickoff(a):
    from ils_pipeline import kickoff_input as K
    codes = a.get("codes") or {}
    period = a["period"]
    text = K.run_kickoff(a["client"], period,
                         personal_code=codes.get("personal_code", ""),
                         business_code=codes.get("business_code", ""),
                         open_code=codes.get("open_code", ""),
                         eligible_stat_codes=",".join(_codes_list(codes.get("eligible_stat_codes")) or []),
                         rege_opt_in=",".join(_codes_list(codes.get("rege_opt_in")) or []),
                         rege_opt_out=",".join(_codes_list(codes.get("rege_opt_out")) or []),
                         deck=bool(codes), items_from_calc=bool(a.get("items_from_calc")))
    print(text)
    # run_kickoff returns text either way; its first words say which (kickoff_input.run_kickoff)
    summary = text.startswith(f"{a['client']} {period} -- kickoff, step 1 of 2.")
    done = text.startswith(f"{a['client']} {period} kickoff complete.")
    deck = next((ln.split("deck:", 1)[1].strip() for ln in text.splitlines()
                 if ln.strip().startswith("deck:") and "NOT built" not in ln), None)
    if done and deck:
        try:
            deck = str(deliver("kickoff", a["client"], deck, period.replace("-", "."), a.get("client_name")))
        except OSError as e:
            print(f"[WARN] the deck could not be put in Outputs ({e}); it is in {deck}")
    return {"ok": done if codes else summary, "needs_codes": summary, "deck": deck,
            "folder": str(K.output_dir(a["client"], period)) if done else None}


def main(argv):
    a = json.loads(argv[1])
    try:
        if a.get("analysis") == "pgl":
            out = pgl(a)
        elif a.get("analysis") == "kickoff":
            from ils_pipeline.kickoff._v5.compat import legacy_strings
            with legacy_strings():
                out = kickoff(a)
        else:
            raise ValueError(f"unknown analysis {a.get('analysis')!r}")
    except Exception as exc:
        traceback.print_exc()
        out = {"ok": False, "needs_codes": False, "deck": None, "folder": None,
               "error": f"{type(exc).__name__}: {exc}"}
    print("ILS_RESULT " + json.dumps(out))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
