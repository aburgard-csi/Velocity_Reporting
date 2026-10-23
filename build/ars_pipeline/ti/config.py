"""
config.py — the client config the ported v5 analyses read (eligibility codes, Reg E codes,
branch names, rates, competitor names).

v5 reads one hand-curated `clients_config.json`. Its eligibility lists are curated, so they
are NOT the same as the ARS database's code tables: on 2026-10-23 the status codes matched
the tables' `active` flag for 18 of 57 ARS clients and the product codes matched
`actively_offered_product` for 8. Which definition the cut ships with is an open decision,
so this module does not pick one silently:

  1. A v5-shaped config file — `TI_CLIENT_CONFIG`, else
     `Inputs/ARS Settings/ti_clients_config.json` — is used when it carries the client.
     This is what the parity check runs on, so ported figures can be compared with v5's.
  2. Otherwise the config is DERIVED from `Inputs/ARS Settings/ars_code_tables.json` (status
     `active`, product `actively_offered_product`, Reg E `optinstatus`) and the branch-name
     dataset, and `warn` says so. Rates and competitor names are left out: every section that
     needs them declines with its own sentence, as in v5.

The entry is returned as v5 stores it (some lists are string-encoded); the ported analyses
parse what they read.
"""
import json
import os
from pathlib import Path

CONFIG_NAME = "ti_clients_config.json"
CODE_TABLES_NAME = "ars_code_tables.json"


def config_path() -> Path:
    if os.environ.get("TI_CLIENT_CONFIG"):
        return Path(os.environ["TI_CLIENT_CONFIG"])
    import rpe_env
    return rpe_env.input_dir("ARS codes", create=False) / CONFIG_NAME


def _code_tables() -> dict:
    import rpe_env
    p = rpe_env.input_dir("ARS codes", create=False) / CODE_TABLES_NAME
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def derived(client_id) -> dict:
    """A v5-shaped entry built from the ARS database code tables and the branch names."""
    cid = str(client_id)
    t = _code_tables()
    status = (t.get("status_codes") or {}).get(cid) or {}
    product = (t.get("product_codes") or {}).get(cid) or {}
    rege = (t.get("rege_codes") or {}).get(cid) or {}
    entry = {"ClientID": cid, "_source": "derived from ars_code_tables.json"}
    if status:
        entry["EligibleStatusCodes"] = sorted(k for k, r in status.items() if r.get("active") == "1")
        entry["IneligibleStatusCodes"] = sorted(k for k, r in status.items() if r.get("active") != "1")
    if product:
        entry["EligibleProductCodes"] = sorted(k for k, r in product.items()
                                               if r.get("actively_offered_product") == "1")
    if rege:
        entry["RegEOptInCode"] = sorted(k for k, r in rege.items() if r.get("optinstatus") == "1")
        entry["RegEOptOutCode"] = sorted(k for k, r in rege.items() if r.get("optinstatus") in ("0", "2"))
    try:
        import branch_names
        names = branch_names.client_map(cid)
        if names:
            entry["BranchMapping"] = dict(names)
    except Exception:
        pass
    return entry


def client_config(client_id, warn=print) -> dict:
    """The client's config entry: the v5-shaped file when it carries the client, else derived."""
    cid = str(client_id)
    p = config_path()
    if p.is_file():
        entry = json.loads(p.read_text(encoding="utf-8-sig")).get(cid)
        if entry:
            if entry.get("exclude"):
                raise SystemExit(f"client {cid} is excluded in {p.name}: "
                                 f"{entry.get('exclude_reason', 'no reason given')}")
            return dict(entry, _source=p.name)
    warn(f"client {cid}: no entry in {p.name}; eligibility and Reg E codes are derived from "
         f"{CODE_TABLES_NAME}, and rates and competitor names are absent")
    return derived(cid)
