# Ported from v5 02-Scripts/ils/pre_go_live/codes.py at 7ba1e63. Logic unchanged; copied whole.
"""Per-run client codes. There is no config file for ILS: the codes are
chosen off the field summary each run, validated against the file's actual
values, and recorded in the run's own output as provenance."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

FIELD_FOR = {"open_status": "Account Status Code",
             "od_eligible": "OD Status Code (from Core)",
             "rege_opt_in": "Reg-E Opt-In Value",
             "rege_opt_out": "Reg-E Opt-In Value"}


def _listify(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return [str(x).strip().upper() for x in v]
    return [str(v).strip().upper()]


@dataclass
class Codes:
    open_status: list = field(default_factory=list)
    od_eligible: list = field(default_factory=list)
    rege_opt_in: list = field(default_factory=list)
    rege_opt_out: list = field(default_factory=list)

    def __post_init__(self):
        for name in ("open_status", "od_eligible", "rege_opt_in", "rege_opt_out"):
            setattr(self, name, _listify(getattr(self, name)))

    @classmethod
    def from_any(cls, obj) -> "Codes":
        if isinstance(obj, cls):
            return obj
        return cls(**{k: v for k, v in dict(obj).items() if k in FIELD_FOR})

    def complete(self) -> bool:
        # RPE, 2026-11-11 (James): a client with no Reg E yet has nothing to opt in; Reg E codes are optional
        return bool(self.open_status and self.od_eligible)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in FIELD_FOR if getattr(self, k)}


def all_values(df: pd.DataFrame, name: str) -> list[str]:
    """Every non-blank value of the code's column, most common first (the od_eligible = ALL reading)."""
    col = FIELD_FOR[name]
    if col not in df.columns:
        return []
    s = df[col].dropna().astype(str)
    return [v for v in s[s.str.strip() != ""].value_counts().index]


def validate(codes: Codes, df: pd.DataFrame, soft: list | None = None) -> list[str]:
    """Every code must be a value the file actually carries.

    RPE, 2026-11-11 (James): a Reg E code the file does not carry (a client with no Reg E yet, whose column
    holds only D) is not a stop; when `soft` is given it goes there as a warning and the Reg E counts are 0."""
    problems = []
    for name in ("open_status", "od_eligible", "rege_opt_in", "rege_opt_out"):
        wanted = getattr(codes, name)
        if not wanted:
            continue
        col = FIELD_FOR[name]
        if col not in df.columns:
            problems.append(f"{name}: column {col!r} not in the file")
            continue
        actual = set(df[col].dropna().unique())
        missing = [w for w in wanted if w not in actual]
        if missing:
            if soft is not None and name.startswith("rege_"):
                soft.append(f"{name}: {missing} not among {col!r} values {sorted(actual)[:12]}; counted as none")
                continue
            problems.append(f"{name}: {missing} not among {col!r} values "
                            f"{sorted(actual)[:12]}")
    return problems
