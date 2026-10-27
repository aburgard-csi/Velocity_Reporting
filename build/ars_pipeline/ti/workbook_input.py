"""
workbook_input.py — the client's ARS Workbook for the cut, found the way the ARS build finds it.

v5 looked in its own `01-Data/<period>/<client>/` (`ti/workbook.find_workbook`). Here the workbook
comes from RPE's inputs: `<id>-<yyyy.mm>-*Workbook*.xlsx` across `rpe_env.report_dirs()`, never the
Invitation Checking workbook, the same rule as `build_month.ars_workbook` (which lives in `scripts/`,
so it is restated here rather than imported).

`attach` reads it with v5's reader (`ti/workbook.read`, logic unchanged) and does what v5's run did
next: when the client config leaves `ICRate` or `NSF_OD_Fee` blank, the workbook's current values
fill them (value, interchange and cohort price with them); when both are set and disagree beyond
rounding, config wins and the run says so.
"""
import glob
import os
from pathlib import Path


def find(client_id, period):
    """The client's ARS workbook for `period` (yyyy.mm), or None."""
    import rpe_env
    hits = []
    for d in rpe_env.report_dirs():
        hits += [f for f in glob.glob(os.path.join(str(d), f"{client_id}-{period}-*Workbook*.xlsx"))
                 if "invitation checking" not in os.path.basename(f).lower()
                 and not os.path.basename(f).startswith("~$")]
    return Path(sorted(hits)[-1]) if hits else None      # v5's reader takes a Path


def attach(config, client_id, period, warn):
    """(config with ICRate / NSF_OD_Fee backfilled, the wb_* figures). Never raises."""
    from ti import workbook
    try:
        path = find(client_id, period)
        if path is None:
            warn(f"no ARS Workbook in Inputs for {client_id} {period}; the economics slides are stated")
            return config, {}
        wb = workbook.read(path, warn)
        wb["wb_found"] = os.path.basename(path)
        for cfg_key, wb_key in (("ICRate", "wb_ic_rate"), ("NSF_OD_Fee", "wb_nsf_fee")):
            cfg_val = str(config.get(cfg_key, "")).strip()
            wb_val = wb.get(wb_key)
            if wb_val is None:
                continue
            if not cfg_val:
                config = {**config, cfg_key: str(wb_val)}
                warn(f"{cfg_key} not in the client config; using the workbook's current value {wb_val}")
            elif not workbook.rates_agree(cfg_val, wb_val):
                warn(f"{cfg_key} mismatch: config says {cfg_val}, the workbook's current value is "
                     f"{wb_val}; config wins")
        return config, wb
    except Exception as exc:                          # the workbook never takes the cut down
        warn(f"workbook read failed: {type(exc).__name__}: {exc}")
        return config, {}
