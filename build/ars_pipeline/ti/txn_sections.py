"""
txn_sections.py — v5's transaction run (`ars/transaction_intelligence/run.py`), one section at a time.

Each function takes the shared context (`ti/context.py`) and returns the figures v5's run merged
into `txn_metrics.json` for that section, in v5's order and with v5's arguments. What a later
section reads from an earlier one (the row classification, the personal and business accounts,
the competitor rows) is left on `ctx.shared`, as v5's run passes it along in local variables.

The same functions drive a real build (the chapters' `compute`) and the parity check against v5,
so a section is checked exactly as it runs. Each chapter's pull request adds its sections here.

Lists v5 writes beside its outputs (`lists/*.csv`) go to `ctx.shared["lists_dir"]` when the build
sets one, and nowhere when it does not (the parity check).
"""
from ti import dictionaries


def base_accounts(ctx):
    """The personal / business account ids and the headline base label (v5 run.py)."""
    if "personal" not in ctx.shared:
        personal = business = None
        if ctx.lenses is not None and "personal" in ctx.lenses.masks:
            personal, business = ctx.lenses.ids("personal"), ctx.lenses.ids("business")
        ctx.shared.update(personal=personal, business=business,
                          base_label=("transacting personal accounts" if personal is not None
                                      else "transacting accounts"))
    return ctx.shared["personal"], ctx.shared["business"], ctx.shared["base_label"]


def portfolio(ctx):
    from ti.transaction_intelligence import portfolio as P
    return P.compute(ctx.txn, ctx.frame, ctx.warn)


FINB_KEYS = ("finb_base_label", "finb_accounts_total", "finb_leaking_accounts",
             "finb_leaking_pct", "finb_leakage_dollars", "finb_addressable_dollars",
             "finb_by_category", "finb_top_providers", "finb_provider_concentration", "finb_p2p")


def financial_services(ctx):
    """fin_* on personal accounts, finb_* (v5's subset of keys) on business accounts."""
    from ti.transaction_intelligence import financial_services as F
    personal, business, base_label = base_accounts(ctx)
    spec = F.load_patterns(dictionaries.folder(), ctx.config)
    rows = F.classify_rows(ctx.txn, spec)
    ctx.shared.update(fin_spec=spec, fin_rows=rows)
    out, _files = F.compute(ctx.txn, ctx.lenses, spec, ctx.anchor_ts, ctx.shared.get("lists_dir"),
                            ctx.warn, account_filter=personal, key_prefix="fin_",
                            base_label=base_label, classification=rows)
    if business is not None and len(business):
        finb, _ = F.compute(ctx.txn, None, spec, ctx.anchor_ts, None, lambda _m: None,
                            account_filter=business, key_prefix="finb_",
                            base_label="transacting business accounts", classification=rows)
        out.update({k: v for k, v in finb.items() if k in FINB_KEYS})
    # v5's run pops this hand-off before writing and gives it to the overlay section
    ctx.shared["addressable_accounts"] = out.pop("_addressable_accounts", None)
    return out
