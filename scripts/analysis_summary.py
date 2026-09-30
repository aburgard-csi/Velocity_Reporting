"""One command after a build with RPE_ANALYSIS=1: what the engine saw for one client.

    python scripts/analysis_summary.py <period> <client_id> [--log <staging>/<id>/build.log]

Reads Build Artifacts/analysis/<period>/<id>/ (txn_metrics.json, metrics.json, report.md)
and prints the transaction read, the ODD join, the reconciliation lines from the build log,
and the warnings. Nothing is written. Safe to run in a second window while a build runs.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "build" / "ars_pipeline"))

TXN_KEYS = ("txn_files_read", "txn_files_cached", "txn_files_skipped_n", "txn_rows",
            "txn_months_covered", "txn_columns_found", "txn_accounts", "txn_account_hashed_pct",
            "txn_odd_join_key", "txn_odd_accounts_matched", "txn_odd_match_pct", "txn_odd_join_candidates")


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def summarise(folder, log=None):
    """-> list of lines. `folder` is the client's analysis folder."""
    folder = Path(folder)
    out = [f"analysis folder: {folder}"]
    if not folder.is_dir():
        out.append("  NOT FOUND: the engine did not write here (flags off, or an older period spelling)")
        return out
    txn = _load(folder / "txn_metrics.json")
    if txn is None:
        out.append("  txn_metrics.json: missing (no transaction folder for this client, or the txn run failed)")
    else:
        out.append("transaction read and ODD join:")
        for k in TXN_KEYS:
            if k in txn:
                out.append(f"  {k:<28} {json.dumps(txn[k])}")
        for k in sorted(txn):
            if k.startswith("fin_") and not isinstance(txn[k], (list, dict)):
                out.append(f"  {k:<28} {json.dumps(txn[k])}")
        out.append("competition (scalars):")
        for k in sorted(txn):
            if k.startswith(("comp_", "ovl_")) and not isinstance(txn[k], (list, dict)):
                out.append(f"  {k:<36} {json.dumps(txn[k])}")
        for label, rows in (("competitors ranked (comp_institutions)", txn.get("comp_institutions")),
                            ("local competitors (comp_local.institutions)", (txn.get("comp_local") or {}).get("institutions")),
                            ("providers (fin_top_providers, by category)", txn.get("fin_top_providers")),
                            ("flight-risk destinations (ovl_destinations)", txn.get("ovl_destinations"))):
            if isinstance(rows, dict):
                rows = [[cat] + list(r) for cat, rs in rows.items() for r in (rs or [])[:3]]
            out.append(f"{label}: {len(rows) if rows else 0} rows")
            out += [f"  {json.dumps(r)[:150]}" for r in (rows or [])[:15]]
        warns = txn.get("warnings") or []
        out.append(f"transaction warnings ({len(warns)}):")
        out += [f"  {w}" for w in warns[:25]]
    m = _load(folder / "metrics.json")
    if m is not None:
        gt = {k: m[k] for k in sorted(m) if k.startswith("gt_") and k != "gt_months"}
        out.append("2:1 guarantee tracker:" if gt else "2:1 guarantee tracker: none read (see ODD warnings)")
        out += [f"  {k:<28} {json.dumps(v)}" for k, v in gt.items()]
        warns = m.get("warnings") or []
        out.append(f"ODD warnings ({len(warns)}):")
        out += [f"  {w}" for w in warns[:25]]
    if log and Path(log).exists():
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        i = text.find("analysis engine")
        if i >= 0:
            out.append("build log, reconciliation:")
            out += ["  " + ln for ln in text[i:].splitlines()[:16]]
        else:
            out.append("build log: no 'analysis engine' lines (RPE_ANALYSIS was not 1 for that build)")
    report = folder / "report.md"
    if report.exists():
        hits = [ln for ln in report.read_text(encoding="utf-8", errors="replace").splitlines()
                if re.search(r"warn|POSSIBLE|declin|skipped", ln, re.I)]
        out.append(f"report.md lines to read ({len(hits)}):")
        out += [f"  {h[:140]}" for h in hits[:25]]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("period", help="YYYY.MM, e.g. 2026.09")
    ap.add_argument("client_id")
    ap.add_argument("--log", help="the client's build.log from the staging folder")
    ap.add_argument("--root", help="analysis root (default: <RPE_DATA_ROOT>/Build Artifacts/analysis)")
    a = ap.parse_args(argv)
    if a.root:
        folder = Path(a.root) / a.period / a.client_id
    else:
        import rpe_env
        folder = Path(rpe_env.build_artifacts()) / "analysis" / a.period / a.client_id
    print("\n".join(summarise(folder, a.log)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
