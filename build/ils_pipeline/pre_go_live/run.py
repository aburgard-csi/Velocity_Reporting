# Ported from v5 02-Scripts/ils/pre_go_live/run.py at 7ba1e63. One RPE change (2026-10-28, CHANGELOG): an extract with no header row stops the run and says so; imports read ils_pipeline.core, and the default data, output and config folders come from ils_pipeline/pgl_input.py (Inputs/ILS PGL, Build Artifacts/ils, ils_pipeline/config).
"""ILS pre-go-live -- entry point.

    from ils.pre_go_live import run
    result = run("1737")                       # -> needs_codes + field summary
    result = run("1737", codes={"open_status": "O", "od_eligible": ["003"],
                                "rege_opt_in": "Y"})

Standalone and one-time: no ODD, no period, never paired with ARS or TXN.
The run is keyed by client + the extract date in the filename; outputs land
under 03-Output/PGL/{client}/{YYYYMMDD}/. The codes used are recorded in the
metrics as provenance -- there is no client config for ILS.
"""

from __future__ import annotations

import json
from pathlib import Path

from ils_pipeline import pgl_input
from ils_pipeline.core.result import AnalysisResult, Timer

from . import bases as bases_mod
from . import codes as codes_mod
from . import field_summary, loader, sections, system_view

ANALYSIS = "ils_pre_go_live"

# Each section: compute(df, bases, inputs, warn) -> dict with pgl_* keys.
SECTIONS = sections.ALL


def run(client_id: str, codes=None, data_root=None, output_root=None,
        config_dir=None, fee=None, tiers=None, include_deleted=False) -> AnalysisResult:
    data_root = Path(data_root) if data_root else pgl_input.root()
    output_root = Path(output_root) if output_root else pgl_input.output_root()
    config_dir = Path(config_dir) if config_dir else pgl_input.config_dir()
    result = AnalysisResult(analysis=ANALYSIS, client_id=str(client_id), period="pre-go-live")

    with Timer(result):
        from ils_pipeline.core.env import check_environment
        check_environment(result.fail)
        if not result.ok:
            return result
        try:
            found = loader.find_extract(data_root, client_id)
        except FileNotFoundError as exc:
            result.fail(str(exc))
            return result
        result.outputs["source"] = str(found.path)
        result.data_month = found.date.strftime("%Y-%m-%d")
        st = found.path.stat()
        result.outputs["source_size"] = st.st_size
        for p in found.others:
            try:
                sz = p.stat().st_size
            except OSError:
                sz = 0
            result.warn(f"another extract in the folder NOT used: {p.name} "
                        f"({sz:,} bytes vs {st.st_size:,} used) -- delete the "
                        f"stale one so there is no doubt which file this report reads")

        df, load_warns = loader.load(found.path)
        for w in load_warns:
            result.warn(w)
        result.rows_in = len(df)
        if df.empty:
            result.fail("extract has no rows")
            return result
        # RPE, 2026-10-28: 1737 TNB's 2026-10 extract came with no header row, so its first account
        # record was read as the column names and the field summary came back empty without a word.
        if not set(df.columns) & set(loader.COLUMNS_1737):
            result.fail(f"{found.path.name} has no header row: its first line is an account record "
                        f"({', '.join(list(df.columns)[:4])}, ...), so none of the extract's "
                        f"{loader.EXPECTED_COLUMNS} named columns is there. Ask for it to be "
                        f"exported again with its header row.")
            return result

        metrics: dict = {"pgl_extract": found.path.name,
                         "pgl_extract_date": found.date.strftime("%Y-%m-%d")}
        metrics.update(field_summary.compute(df, result.warn))
        # The ILS system's own view (matrix + integrity dumps), when the
        # vendor's exports sit next to the extract. Always attached -- the
        # needs_codes reply already shows what the system says it holds.
        sysm = system_view.load(found.path.parent, result.warn)
        metrics.update(sysm)

        # ---- no codes: return the field summary, ask for the reading -------
        c = codes_mod.Codes.from_any(codes) if codes is not None else codes_mod.Codes()
        if not c.complete():
            result.metrics = metrics
            result.status = "needs_codes"
            missing = [k for k in ("open_status", "od_eligible", "rege_opt_in")
                       if not getattr(c, k)]
            result.warnings.append(
                f"codes needed before analysis: {missing}. Read pgl_code_values "
                f"(and pgl_suggested_codes) and run again with the confirmed codes.")
            return result
        problems = codes_mod.validate(c, df)
        if problems:
            for p in problems:
                result.fail(p)
            return result
        metrics["pgl_codes_used"] = c.as_dict()

        deleted_rows = int(df["Deleted"].notna().sum()) if "Deleted" in df.columns else 0
        if include_deleted:
            result.warn("deleted-flagged rows INCLUDED in every base on request "
                        "(include_deleted)")
        else:
            df = bases_mod.drop_deleted(df, result.warn)
        b = bases_mod.build(df, c, result.warn)
        metrics["pgl_bases"] = b.counts()

        inputs = {"codes": c, "fee": fee, "tiers": tiers,
                  "config_dir": config_dir, "extract_date": found.date,
                  "system": sysm, "deleted_rows": deleted_rows}
        for section in SECTIONS:
            try:
                metrics.update(section.compute(df, b, inputs, result.warn))
            except Exception as exc:
                result.warn(f"{section.__name__.rsplit('.', 1)[-1]} failed: "
                            f"{type(exc).__name__}: {exc}")

        out_dir = output_root / "PGL" / str(client_id) / found.date.strftime("%Y%m%d")
        out_dir.mkdir(parents=True, exist_ok=True)
        from ils_pipeline.core.env import write_text_atomic
        mj = out_dir / "pgl_metrics.json"
        write_text_atomic(mj, json.dumps(metrics, indent=1, default=str))
        result.outputs["metrics"] = str(mj)
        result.metrics = metrics
        result.outputs["_manifest_dir"] = str(out_dir)

    manifest_dir = result.outputs.pop("_manifest_dir", None)
    if manifest_dir:
        result.outputs["manifest"] = str(result.write_manifest(manifest_dir))
    return result
