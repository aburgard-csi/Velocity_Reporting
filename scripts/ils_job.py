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
    out = {"ok": bool(res.ok), "needs_codes": res.status == "needs_codes", "deck": None, "folder": None}
    if res.ok and res.status != "needs_codes":
        from ils_pipeline.core import layout
        from ils_pipeline.pre_go_live.deck import build
        folder = Path(res.outputs["metrics"]).parent
        deck = build(res, layout.TEMPLATE, folder / f"{a['client']}_{folder.name}_ILS_PreGoLive.pptx",
                     include_golive=not a.get("current_only"))
        print(f"\ndeck: {deck.path} ({deck.slides} slides, {deck.charts} charts"
              + (f"; skipped {deck.skipped}" if deck.skipped else "") + ")")
        out.update(deck=str(deck.path), folder=str(folder))
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
