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
from dataclasses import dataclass, field
from pathlib import Path

REL_TOL = 1e-9
ABS_TOL = 1e-9


@dataclass
class Ctx:
    frame: object
    config: dict
    anchor: object
    subsets: object
    v5_dir: Path
    warnings: list = field(default_factory=list)

    def warn(self, message):
        self.warnings.append(message)


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
}


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


def run(v5_dir, config: dict, names=None):
    """{name: rows} for each registered computation (or only `names`)."""
    ctx = context(v5_dir, config)
    out = {}
    for name, (source, fn) in REGISTRY.items():
        if names and name not in names:
            continue
        theirs = json.loads((Path(v5_dir) / source).read_text(encoding="utf-8"))
        out[name] = compare(fn(ctx), theirs)
    return out
