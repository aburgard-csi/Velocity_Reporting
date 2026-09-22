"""Build the review decks for the James-gap branch — ARS only, James views ON.

NOT a delivery: everything lands in Build Artifacts/james_gaps_<period>/<id>/ and nothing is
copied to Outputs. Two clients on purpose, one per revenue model, because the workbook-driven
views read 'All Months Rollup MM' and an SM client has no such sheet — the slides have to say
so rather than fail.

    python scratch_sample_build.py [1539 1038 ...]
"""
import json
import os
import sys
import time
from pathlib import Path

REPO = r"C:\Projects\RPE-james-gaps"
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"),
                os.path.join(REPO, "validation")]

import build_month as BM     # noqa: E402
import rpe_env as R          # noqa: E402
import validate_deck as V    # noqa: E402

PERIOD = "2026.09"
CLIENTS = sys.argv[1:] or ["1539", "1038"]
WORK = R.build_artifacts() / f"james_gaps_{PERIOD}"
WORK.mkdir(parents=True, exist_ok=True)
os.environ["RPE_JAMES_SLIDES"] = "1"

roster = {c: (n, mm, p) for c, n, mm, p in BM.read_roster()[0]}
out = {}
for cid in CLIENTS:
    if cid not in roster:
        print(f"{cid}: not on the clients.md roster — skipped")
        continue
    name, mmsm, _progs = roster[cid]
    t = time.time()
    rec = {"name": name, "path": mmsm}
    try:
        err, made = BM.build_client(cid, name, mmsm, ["ARS"], PERIOD, str(WORK))
        if err:
            raise RuntimeError(f"build_client stopped at {err}")
        deck = Path(made["DELIVERABLE"])
        base = WORK / cid / "base.json"
        rec["deck"] = str(deck)
        rec["gate"] = BM.validate(str(deck), str(base) if base.exists() else None)
        rec["package"] = [str(x) for x in V.package_findings(str(deck))]
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["seconds"] = round(time.time() - t)
    out[cid] = rec
    print(f"{cid} {name[:24]:<24} {mmsm:<3} {rec.get('gate', '-'):<22} "
          f"{rec.get('error') or Path(rec.get('deck', '')).name} ({rec['seconds']}s)", flush=True)

(WORK / "_sample_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("wrote", WORK / "_sample_results.json")
