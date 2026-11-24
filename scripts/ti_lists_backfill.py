"""Put the mail lists from earlier Transaction Intelligence builds in Outputs (Aaron, 2026-11-23).

Since #170 (2026-11-16) a TI build copies its mail lists beside the deck, into
`Outputs/<CSM>/<id>-<period>-TI-Lists/` (`ars_launcher.ti_lists_to_outputs`). A build made before that left
them in its staging folder, `Build Artifacts/launcher/<period>/<id>/ti/lists/`, where no CSM looks. This
copies those into each client's CSM folder the same way, with the same function.

    python scripts/ti_lists_backfill.py            # dry run: what would be copied, and why not
    python scripts/ti_lists_backfill.py --apply    # copy

A build's lists are copied only when its TI deck for that period is in Outputs, which is the rule a build
follows (lists go out with a delivered deck, never without one). A client whose lists folder is already in
Outputs is skipped: a newer build put it there. Copy-only; nothing in Build Artifacts is changed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "scripts", REPO / "build"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import rpe_env as R                 # noqa: E402
import ars_launcher as L            # noqa: E402


def candidates(root: Path | None = None):
    """(client id, period, staging dir, client name) for every TI build that left mail lists."""
    base = Path(root) if root else R.build_artifacts() / "launcher"
    if not base.is_dir():
        return
    for lists in sorted(base.glob("*/*/ti/lists")):
        if not any(lists.glob("*.csv")):
            continue
        tdir = lists.parent
        period, cid = tdir.parent.parent.name, tdir.parent.name
        name = ""
        try:
            name = json.loads((tdir / "ti_pack.json").read_text(encoding="utf-8")).get("client_name") or ""
        except (OSError, ValueError):
            pass
        yield cid, period, tdir, name


def plan(root: Path | None = None):
    """Each candidate with what to do: ("copy" | "skip", reason)."""
    out = []
    for cid, period, tdir, name in candidates(root):
        if not R.output_decks(f"{cid}-{period}-{L.TI_TAG}-*.pptx"):
            out.append((cid, period, tdir, name, "skip", "no TI deck for this period in Outputs"))
            continue
        dest = R.client_outputs(cid) / f"{cid}-{period}-{L.TI_TAG}-Lists"
        if dest.exists():
            out.append((cid, period, tdir, name, "skip", f"already in Outputs: {dest}"))
            continue
        out.append((cid, period, tdir, name, "copy", str(dest)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="copy (default: dry run)")
    a = ap.parse_args(argv)
    rows = plan()
    if not rows:
        print("No earlier TI build left mail lists in Build Artifacts.")
        return 0
    bad = 0
    for cid, period, tdir, name, action, why in rows:
        if action == "skip":
            print(f"skip  {cid} {period}: {why}")
            continue
        if not a.apply:
            print(f"copy  {cid} {period} -> {why}")
            continue
        level, msg = L.ti_lists_to_outputs(cid, tdir, period, name)
        print(f"{'ok' if level == L.OK else 'WARN':5} {cid} {period}: {msg}")
        bad += level != L.OK
    if not a.apply:
        print("\nDry run. Re-run with --apply to copy.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
