"""The run's codes as the ILS system itself holds them: read from the vendor's two dumps (RPE, 2026-10-28).

James Gilmore, 2026-10-28: "you can get codes from the matrix validation and database integrity check in
the zip" (Tim Barrett's ILS Matrix Validation Deck Builder reads the same matrix tables). Each code comes
with the evidence it rests on, so the CSM confirming it sees why:

  od_eligible   the matrix's OD STATUS CODE MAPPING: the status codes with CAN_OVERDRAFT = 1
  open_status   the extract's Account Status value whose live count (deleted rows out) equals the
                integrity check's open/active accounts, summed over account types
  rege_opt_in   the Reg-E value whose live count equals the integrity check's opt-in count, summed;
  rege_opt_out  then the one other value, when there is exactly one

A code is offered only when the evidence is exact: no count match, no suggestion, and the reason is said.
Nothing here runs the analysis: the CSM confirms the codes (the client confirms nothing) and the run uses
what was confirmed. Keys: pgl_dump_codes.
"""
from __future__ import annotations

BLANKS = {"", "NULL", "BLANK", "NONE"}


def _live(df):
    return df[df["Deleted"].isna()] if "Deleted" in df.columns else df


def _counts(df, col):
    if col not in df.columns:
        return {}
    return {str(k): int(v) for k, v in _live(df)[col].dropna().astype(str).str.strip().value_counts().items()}


def _match(counts, want):
    """The one value whose count is exactly `want`, or None."""
    hits = [v for v, n in counts.items() if n == want]
    return hits[0] if len(hits) == 1 else None


def derive(df, sysv: dict) -> dict:
    out: dict = {}

    smap = sysv.get("sysv_matrix_status_map") or []
    if smap:
        can = [str(r[0]) for r in smap if r and r[2] == 1]
        real = [c for c in can if c.upper() not in BLANKS]
        if real:
            seen = _counts(df, "OD Status Code (from Core)")
            note = ("the ILS matrix marks " + ", ".join(real) + " as able to overdraft (CAN_OVERDRAFT = 1); "
                    + ", ".join(f"{c}: {seen.get(c, 0):,} live accounts in the extract" for c in real))
            if len(real) < len(can):
                note += "; the matrix also lets a blank status overdraft, which no code can name"
            out["od_eligible"] = {"codes": real, "basis": note}
        else:
            out["od_eligible"] = {"codes": [], "basis": "no status code in the ILS matrix has CAN_OVERDRAFT = 1"}

    acc = sysv.get("sysv_accounts") or []
    cols = sysv.get("sysv_accounts_columns") or []
    if acc and cols:
        def total(name):
            i = cols.index(name) if name in cols else None
            return sum(int(r[i] or 0) for r in acc) if i is not None else None

        sys_open, sys_rege = total("open"), total("rege_optin")
        if sys_open is not None:
            counts = _counts(df, "Account Status Code")
            v = _match(counts, sys_open)
            out["open_status"] = ({"codes": [v], "basis": f"{v}: {counts[v]:,} live accounts = the ILS "
                                                          f"system's {sys_open:,} open/active"}
                                  if v else {"codes": [], "basis": f"no Account Status value has exactly the "
                                             f"system's {sys_open:,} open/active accounts ({counts})"})
        if sys_rege is not None:
            counts = _counts(df, "Reg-E Opt-In Value")
            v = _match(counts, sys_rege)
            if v:
                out["rege_opt_in"] = {"codes": [v], "basis": f"{v}: {counts[v]:,} live accounts = the ILS "
                                                              f"system's {sys_rege:,} Reg E opt-ins"}
                rest = [k for k in counts if k != v and k.upper() not in BLANKS]
                if len(rest) == 1:
                    out["rege_opt_out"] = {"codes": rest, "basis": f"the one other Reg E value ({rest[0]}: "
                                                                   f"{counts[rest[0]]:,})"}
            else:
                out["rege_opt_in"] = {"codes": [], "basis": f"no Reg E value has exactly the system's "
                                      f"{sys_rege:,} opt-ins ({counts})"}
    return {"pgl_dump_codes": out}
