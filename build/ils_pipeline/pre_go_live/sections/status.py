# Ported from v5 02-Scripts/ils/pre_go_live/sections/status.py at 7ba1e63. Logic unchanged; copied whole.
"""Account status overview (notebook A1-A2): the whole file's status mix,
then open accounts by Personal / Business."""

from __future__ import annotations

from . import _cut
from ._cut import DC_AMT, DC_CT, ILS_LIMIT, INIT_LIMIT, cut

NEEDS = ["Account Status Code"]


def compute(df, bases, inputs, warn) -> dict:
    if "Account Status Code" not in df.columns:
        warn("status: no Account Status Code column; section skipped")
        return {}
    m: dict = {}
    rows, names = cut(df, "Account Status Code", extras=[INIT_LIMIT])
    m["pgl_status_rows"] = rows
    m["pgl_status_columns"] = names
    if "open" in bases.masks and "Personal_Business" in df.columns:
        rows, names = cut(df[bases["open"]], "Personal_Business",
                          extras=[INIT_LIMIT, ILS_LIMIT, DC_CT, DC_AMT])
        m["pgl_open_by_type"] = rows
        m["pgl_open_by_type_columns"] = names
    return m
