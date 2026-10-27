"""
deferred_input.py — the client's 2:1 guarantee deferral tracker for the cut, from `Inputs/Deferred Billing`.

v5 looked in its own `01-Data/ARS/<period>/<client>/` (`ti/guarantee.find_tracker`). Here the trackers sit
in one folder (`rpe_env` kind "Deferred Billing"), one per client, named "<id> <Client> ... Deferred expense
tracking.xlsx"; some names lead with a revision date ("020525 Revised 1453 Connex ..."), so the client id
is matched as a whole number anywhere in the name, never as a prefix of another id.

`attach` reads the tracker with v5's reader (`ti/guarantee.read`, logic unchanged); `review` then says
what v5's run said after reading it (`ars/monthly_analysis/run.py` at a491b5c): a tracker more than a
month behind the data, whether the guarantee is clear or deferring, and any month where the tracker's
revenue and the workbook's differ by more than 10%. Nothing here is ever silent.
"""
import re


def find(client_id):
    """The client's tracker in Inputs/Deferred Billing (the newest if several), or None."""
    import rpe_env
    folder = rpe_env.input_dir("Deferred Billing", create=False)
    if not folder.is_dir():
        return None
    own = re.compile(rf"(?<!\d){re.escape(str(client_id))}(?!\d)")
    hits = [p for p in folder.glob("*Deferred*.xls*")
            if not p.name.startswith("~$") and own.search(p.name)]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def attach(client_id, warn):
    """The gt_* figures, or {} with the reason said. Never raises."""
    from ti import guarantee
    try:
        path = find(client_id)
        if path is None:
            warn(f"no 2:1 guarantee deferral tracker in Inputs/Deferred Billing for {client_id}; "
                 f"guarantee math is skipped and the workbook's billed figures stand in its place")
            return {}
        return guarantee.read(path, warn)
    except Exception as exc:
        warn(f"deferral tracker read failed: {type(exc).__name__}: {exc}")
        return {}


def review(gt, wb, data_month, warn):
    """v5's run-level checks on a loaded tracker, as sentences (run.py at a491b5c)."""
    if not gt:
        return
    dm, lm = str(data_month or ""), str(gt.get("gt_latest_month") or "")
    if len(dm) == 7 and len(lm) == 7:
        lag = (int(dm[:4]) - int(lm[:4])) * 12 + int(dm[5:7]) - int(lm[5:7])
        if lag > 1:
            warn(f"deferral tracker is {lag} months behind the data (tracker through {lm}, data through "
                 f"{dm}): either the client exited the 2:1 and the sheet stopped, or it needs updating; "
                 f"its figures are as of {lm}")
    if gt.get("gt_state") == "clear":
        warn(f"Deferral tracker loaded ({gt['gt_source']}): the guarantee is clear (no balance deferred); "
             f"billed economics apply")
    else:
        warn(f"Deferral tracker loaded ({gt['gt_source']}): ${gt['gt_deferred_balance']:,.0f} deferred "
             f"through {gt['gt_latest_month']} ({gt['gt_state']}); client economics use the guarantee "
             f"math, not billed fees")
    wb_by_month = {r[0]: r[1] for r in (wb.get("wb_monthly") or []) if r[1] is not None}
    for mth, rev, *_rest in gt.get("gt_months", []):
        wb_rev = wb_by_month.get(mth)
        if wb_rev and rev and abs(rev - wb_rev) > 0.1 * max(wb_rev, 1):
            warn(f"guarantee reconciliation: {mth} tracker revenue ${rev:,.0f} vs workbook ${wb_rev:,.0f}: "
                 f"differs >10%, confirm which sheet is current")
