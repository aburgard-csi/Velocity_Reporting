# Ported from v5 02-Scripts/ils/pre_go_live/run.py at 7ba1e63. Logic unchanged; the needs_codes half only (stage g11-02); imports read ils_pipeline.core, default folders come from ils_pipeline/pgl_input.py.
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

from . import codes as codes_mod
from . import field_summary, loader, system_view

ANALYSIS = "ils_pre_go_live"

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
        # STAGE g11-02 (RPE): v5's run stops here until bases, sections and the metrics file are
        # ported (g11-03..g11-05, where this file becomes v5's run.py whole).
        result.metrics = metrics
        result.fail("ILS PGL port stage g11-02: only the needs_codes half of run is ported")
    return result
