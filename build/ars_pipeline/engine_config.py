#!/usr/bin/env python3
"""
engine_config.py — the analysis engine's per-client record, built from what the pipeline has.

The engine (build/ars_pipeline/engine) expects the record v5 kept in clients_config.json:
eligible status and product codes, the Reg E code sets, the mail flag, the interchange rate
and the NSF fee. Nothing in this pipeline is written in that shape, but everything it needs
is here already:

    Inputs/ARS Settings/ars_code_tables.json   the ARS database's code tables per client
                                                (scripts/ars_code_tables.py): product codes with
                                                is_business / eligible_for_debit_card /
                                                actively_offered_product, Reg E codes with their
                                                opt-in status, status codes with active
    the client's ARS workbook                   Key Assumptions on `Actuals MM`: Interchange
                                                Rate and NSF Fee (engine.workbook.read)
    clients.md                                  the delivery name (scripts/build_month.read_roster)

Precedence is v5's: an explicit override wins, the workbook fills the blanks, and a client
with no code-table entry gets a record whose funnel stages are SKIPPED with a warning, never
zeros (core/subsets.build_subsets says so for each missing set). A missing NSF fee is left
absent: the sections that price NSF decline with their own warning rather than read zero.

Reg E code sets are derived from the code table's wording through odd_rows.rege_label, so
the engine's code reading and the deck's wording reading cannot disagree by construction.
The record is a plain mutable dict: the engine injects `_txn` into it.
"""
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir), os.path.join(HERE, os.pardir, os.pardir, "scripts")):
    if _p not in sys.path:
        sys.path.append(_p)

from odd_rows import rege_label, REGE_IN, REGE_OUT, REGE_DEFAULT      # noqa: E402

DEFAULT_RATE = 0.0060      # 60 bp, the same default build_lift_matrix uses when a workbook carries none
_TRUE = {"1", "true", "yes", "y", "t"}


def _truthy(v):
    return str(v if v is not None else "").strip().lower() in _TRUE


def _client_tables(tables, client_id):
    """(product_codes, rege_codes, status_codes) for one client, each {code: {col: val}}."""
    cid = str(client_id)
    out = []
    for key in ("product_codes", "rege_codes", "status_codes"):
        table = (tables or {}).get(key) or {}
        out.append(table.get(cid) or table.get(int(cid) if cid.isdigit() else cid) or {})
    return tuple(out)


def rege_code_sets(rege_codes, warn=None):
    """{RegEOptInCode, RegEOptOutCode, RegEDefaultCode} from a client's Reg E code table,
    reading each code's opt-in status wording (then its description) through
    odd_rows.rege_label. A code whose wording no rule covers is reported, never guessed."""
    sets = {"RegEOptInCode": [], "RegEOptOutCode": [], "RegEDefaultCode": []}
    field = {REGE_IN: "RegEOptInCode", REGE_OUT: "RegEOptOutCode", REGE_DEFAULT: "RegEDefaultCode"}
    unmapped = []
    for code, row in sorted((rege_codes or {}).items()):
        label = rege_label((row or {}).get("optinstatus"))
        if not label:
            label = rege_label((row or {}).get("description"))
        if label in field:
            sets[field[label]].append(str(code))
        elif label is None:
            unmapped.append(f"{code} ({(row or {}).get('optinstatus') or (row or {}).get('description')})")
    if unmapped and warn:
        warn(f"Reg E codes with wording no mapping covers, left out of every set: {', '.join(unmapped)}")
    return sets


PROFILES = Path(__file__).resolve().parent / "engine" / "config" / "client_profiles.json"
PROFILE_KEYS = ("LocalCompetitors", "RegionalCompetitors", "SelfNames", "BranchMapping", "Profile")


def client_profile(client_id, warn=None, path=None):
    """The per-client keys above for `client_id`, or {} with a warning when the client has none."""
    import json
    warn = warn or (lambda m: None)
    p = Path(path) if path else PROFILES
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        warn(f"client profiles file missing ({p.name}); competitor lists and branch names unavailable")
        return {}
    rec = doc.get(str(client_id)) or {}
    out = {k: rec[k] for k in PROFILE_KEYS if k in rec}
    if "LocalCompetitors" not in out:
        warn(f"client {client_id}: no LocalCompetitors in {p.name}; only national and regional "
             "competitors are ranked")
    return out


def record_for(client_id, tables=None, workbook=None, name=None, overrides=None, warn=None):
    """The engine's client record.

    tables    the ars_code_tables.json document (scripts/ars_code_tables.load()), or None
    workbook  engine.workbook.read()'s dict for the client's ARS workbook, or None
    name      the delivery name from clients.md, or None
    overrides explicit values that win over everything (v5: "config wins when set")
    """
    warn = warn or (lambda m: None)
    cid = str(client_id)
    products, rege, statuses = _client_tables(tables, cid)
    rec = {"ClientID": cid, "ClientName": name, "Products": ["ARS"], "EligibleMailCode": "Yes"}
    # James's per-client analysis inputs (engine/config/client_profiles.json, from v5): local
    # and regional competitor lists, self-names, branch display names, profile. Aaron's code
    # tables have no equivalent, so these are the reading of record (2026-09-30: without them
    # "Which competitors to work first" drew empty for every client).
    rec.update(client_profile(cid, warn))

    if statuses:
        rec["EligibleStatusCodes"] = sorted(c for c, r in statuses.items() if _truthy((r or {}).get("active")))
    else:
        warn(f"no status code table for {cid}; the status funnel stage is skipped")
    if products:
        rec["EligibleProductCodes"] = sorted(
            c for c, r in products.items() if _truthy((r or {}).get("actively_offered_product")))
        rec["BusinessProductCodes"] = sorted(c for c, r in products.items() if _truthy((r or {}).get("is_business")))
    else:
        warn(f"no product code table for {cid}; the product funnel stage is skipped")
    if rege:
        rec.update(rege_code_sets(rege, warn))
    else:
        warn(f"no Reg E code table for {cid}; Reg E is read from the extract's wording only")

    wb = workbook or {}
    if wb.get("wb_ic_rate") is not None:
        rec["ICRate"] = float(wb["wb_ic_rate"])
    else:
        rec["ICRate"] = DEFAULT_RATE
        warn(f"no interchange rate in the workbook for {cid}; using the {DEFAULT_RATE:.2%} default")
    if wb.get("wb_nsf_fee") is not None:
        rec["NSF_OD_Fee"] = float(wb["wb_nsf_fee"])
    else:
        warn(f"no NSF fee in the workbook for {cid}; NSF pricing declines rather than reads zero")

    for k, v in (overrides or {}).items():
        if v not in (None, "", []):
            rec[k] = v
    rec["_config_source"] = {
        "code_tables": ((tables or {}).get("_source") or {}).get("extracted"),
        "workbook": wb.get("wb_found") or wb.get("wb_file"),
        "rate_source": "workbook" if wb.get("wb_ic_rate") is not None else "default",
    }
    return rec


def load_tables(path=None):
    """The extracted code tables from Inputs/ARS Settings/, or None when none have been extracted."""
    from ars_code_tables import load
    return load(path)
