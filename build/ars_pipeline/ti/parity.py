"""
parity.py — does a ported analysis produce the figures v5 produced?

A v5 run leaves, per client and period, the frame it computed on (`enriched.parquet`) and
the figures it computed (`metrics.json`, `txn_metrics.json`). The check feeds the SAME frame
and the same client config to the ported code and compares every key it returns with v5's.
Running on v5's own frame separates the logic from the data: a difference here is a porting
defect, never a newer extract.

`REGISTRY` names each ported computation once: name -> (v5 file it is checked against,
function of a Ctx returning a dict). Each chapter's pull request adds its own lines.

    python scripts/ti_parity.py <v5 run folder> --client 1100 --config <clients_config.json>
"""
import json
import math
from pathlib import Path

from ti.context import Ctx as _Ctx

REL_TOL = 1e-9
ABS_TOL = 1e-9


# The compute context is shared with the real build, so a computation is checked as it runs.
Ctx = _Ctx


def _txn():
    from ti import txn_sections
    return txn_sections


def _bases(c):
    s = c.subsets
    out = {"data_month": c.anchor.iso, "anchor_tag": c.anchor.tag, **s.sizes(),
           "eligibility_funnel": [[f.label, f.count, f.pct_of_total, f.dropoff_pct] for f in s.funnel]}
    if out.get("n_total"):
        out["eligibility_rate"] = round(100 * out["n_eligible"] / out["n_total"], 1)
    return out


# name -> (v5 figures file, compute(ctx) -> dict)
REGISTRY = {
    "bases": ("metrics.json", _bases),
    "portfolio": ("txn_metrics.json", lambda c: _txn().portfolio(c)),
    "financial_services": ("txn_metrics.json", lambda c: _txn().financial_services(c)),
    "merchants": ("txn_metrics.json", lambda c: _txn().merchants(c)),
    "merchant_profiles": ("txn_metrics.json", lambda c: _txn().merchant_profiles(c)),
    "card_behavior": ("txn_metrics.json", lambda c: _txn().card_behavior(c)),
    "interchange": ("txn_metrics.json", lambda c: _txn().interchange(c)),
    # relationship reads the row classification financial services leaves on ctx.shared
    "relationship": ("txn_metrics.json", lambda c: (_txn().financial_services(c), _txn().relationship(c))[1]),
    "family_tables": ("txn_metrics.json", lambda c: _txn().family_tables(c)),
    # competition reads financial services' classification too
    "competition": ("txn_metrics.json", lambda c: (_txn().financial_services(c), _txn().competition(c))[1]),
    # the audit reads all three specs and financial services' providers
    # filed adds to the competition figures, so they are computed first
    "filed": ("txn_metrics.json", lambda c: (lambda fin, comp: _txn().filed(c, {**fin, **comp}))(
        _txn().financial_services(c), _txn().competition(c))),
    "leakage": ("txn_metrics.json", lambda c: (_txn().ensure_competition(c), _txn().leakage(c))[1]),
    "stressors_txn": ("txn_metrics.json", lambda c: (_txn().ensure_competition(c), _txn().stressors_txn(c))[1]),
    "mapping_audit": ("txn_metrics.json", lambda c: (_txn().financial_services(c), _txn().competition(c),
                                                     _txn().merchants(c), _txn().mapping_audit(c))[3]),
}


# the ODD sections register themselves in ti/odd_sections.py
from ti import odd_sections as _odd  # noqa: E402
REGISTRY.update(_odd.PARITY)

def _norm(value):
    """Through JSON, as v5 wrote its figures: tuples become lists, numpy scalars numbers."""
    return json.loads(json.dumps(value, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def _same_number(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def diff(ours, theirs, path=""):
    """The first place two JSON-shaped values differ, as a sentence; None when they agree."""
    if isinstance(ours, bool) or isinstance(theirs, bool):
        same = isinstance(ours, bool) and isinstance(theirs, bool) and ours == theirs
        return None if same else f"{path}: {ours!r} != {theirs!r}"
    if isinstance(ours, (int, float)) and isinstance(theirs, (int, float)):
        return None if _same_number(float(ours), float(theirs)) else f"{path}: {ours!r} != {theirs!r}"
    if isinstance(ours, dict) and isinstance(theirs, dict):
        if set(ours) != set(theirs):
            return (f"{path}: keys differ (only ours: {sorted(set(ours) - set(theirs))[:5]}, "
                    f"only v5: {sorted(set(theirs) - set(ours))[:5]})")
        for k in ours:
            d = diff(ours[k], theirs[k], f"{path}.{k}" if path else str(k))
            if d:
                return d
        return None
    if isinstance(ours, list) and isinstance(theirs, list):
        if len(ours) != len(theirs):
            return f"{path}: {len(ours)} items != {len(theirs)}"
        for i, (a, b) in enumerate(zip(ours, theirs)):
            d = diff(a, b, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if ours == theirs else f"{path}: {ours!r} != {theirs!r}"


def compare(ours: dict, theirs: dict):
    """[(key, 'match' | 'differs' | 'missing in v5', detail)] for every key `ours` returns."""
    ours = _norm(ours)
    rows = []
    for k in sorted(ours):
        if k not in theirs:
            rows.append((k, "missing in v5", ""))
            continue
        d = diff(ours[k], theirs[k], k)
        rows.append((k, "differs" if d else "match", d or ""))
    return rows


def context(v5_dir, config: dict):
    """The Ctx for one v5 run folder: its frame, its data month, the bases on the given config."""
    import pandas as pd
    from ti.core.periods import Month
    from ti.core.subsets import build_subsets
    v5_dir = Path(v5_dir)
    frame = pd.read_parquet(v5_dir / "enriched.parquet")
    metrics = json.loads((v5_dir / "metrics.json").read_text(encoding="utf-8"))
    anchor = Month.from_tag(metrics["anchor_tag"])
    return Ctx(frame, config, anchor, build_subsets(frame, config, anchor), v5_dir)


def v5_txn_frame(v5_dir, client_id):
    """The transaction rows v5's run read, rebuilt from v5's own parquet cache
    (`03-Output/_cache/txn/<id>/`, the files `txn_metrics.json` names as loaded), finished as
    v5's loader.load finishes them. Same rows, so a difference is the port's, not the data's."""
    import glob
    import pandas as pd
    v5_dir = Path(v5_dir)
    tm = json.loads((v5_dir / "txn_metrics.json").read_text(encoding="utf-8"))
    cache = v5_dir.parents[1] / "_cache" / "txn" / str(client_id)
    frames = []
    for name in tm["txn_files_loaded"]:
        hits = sorted(glob.glob(str(cache / (glob.escape(Path(name).stem) + ".*.v6.parquet"))))
        if not hits:
            raise SystemExit(f"v5's cache has no parquet for {name} under {cache}")
        frames.append(pd.read_parquet(hits[-1]))
    df = pd.concat(frames, ignore_index=True)
    for col in ("transaction_type", "mcc_code", "merchant_id", "card_present", "source_file", "merchant_key"):
        df[col] = df[col].astype("category")
    return df[df["transaction_date"].notna()], tm


def with_txn(ctx, client_id):
    """Attach v5's transaction rows, window end and lenses to a parity Ctx."""
    import pandas as pd
    from ti.core.periods import Month
    from ti.transaction_intelligence import lens as txn_lens
    ctx.txn, tm = v5_txn_frame(ctx.source_dir, client_id)
    m = Month.parse(tm["txn_anchor"])
    ctx.anchor_ts = pd.Timestamp(m.year, m.month, 1) + pd.offsets.MonthEnd(0)
    ctx.lenses = txn_lens.build(ctx.frame, ctx.anchor_ts, ctx.warn,
                                branch_map=ctx.config.get("BranchMapping"))
    ctx.client_id = str(client_id)
    return ctx


def run(v5_dir, config: dict, names=None, client_id=None):
    """{name: rows} for each registered computation (or only `names`)."""
    ctx = context(v5_dir, config)
    wanted = [n for n in REGISTRY if not names or n in names]
    if client_id and any(REGISTRY[n][0] == "txn_metrics.json" for n in wanted):
        with_txn(ctx, client_id)
    out = {}
    for name in wanted:
        source, fn = REGISTRY[name]
        if source == "txn_metrics.json" and ctx.txn is None:
            continue
        theirs = json.loads((Path(v5_dir) / source).read_text(encoding="utf-8"))
        out[name] = compare(fn(ctx), theirs)
    return out
