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


MCHB_KEYS = ("mchb_base_label", "mchb_card_accounts", "mchb_card_spend", "mchb_top", "mchb_by_category")


def merchants(ctx):
    """mch_* on personal card spend, mchb_* (v5's subset) on business; the category spec is
    handed on to the profiles and the mapping audit."""
    from ti.transaction_intelligence import merchants as M
    personal, business, base_label = base_accounts(ctx)
    spec = M.load_categories(dictionaries.folder())
    ctx.shared["mch_spec"] = spec
    out = M.compute(ctx.txn, ctx.lenses, spec, ctx.anchor_ts, ctx.warn,
                    account_filter=personal, key_prefix="mch_", base_label=base_label)
    if business is not None and len(business):
        mb = M.compute(ctx.txn, None, spec, ctx.anchor_ts, lambda _m: None,
                       account_filter=business, key_prefix="mchb_",
                       base_label="transacting business accounts")
        out.update({k: v for k, v in mb.items() if k in MCHB_KEYS})
    return out


def merchant_profiles(ctx):
    """Who spends on the card and how that is shifting: same personal base and category spec."""
    from ti.transaction_intelligence import merchant_profiles as MP
    from ti.transaction_intelligence import merchants as M
    personal, _business, base_label = base_accounts(ctx)
    spec = ctx.shared.get("mch_spec") or M.load_categories(dictionaries.folder())
    return MP.compute(ctx.txn, ctx.lenses, spec, ctx.anchor_ts, ctx.warn, account_filter=personal,
                      key_prefix="mch_", base_label=base_label)


def card_behavior(ctx):
    """Tickets, intensity, recurring payments and when the card is used, on personal accounts."""
    from ti.transaction_intelligence import card_behavior as CB
    personal, _business, base_label = base_accounts(ctx)
    return CB.compute(ctx.txn, ctx.lenses, ctx.anchor_ts, ctx.warn, account_filter=personal,
                      key_prefix="beh_", base_label=base_label)


def interchange(ctx):
    """The PIN / signature mix as the rows record it, unpriced (v5: the ARS value section prices it)."""
    from ti.transaction_intelligence import interchange as IC
    personal, _business, base_label = base_accounts(ctx)
    return IC.compute(ctx.txn, ctx.lenses, ctx.anchor_ts, ctx.warn, account_filter=personal,
                      key_prefix="ic_", base_label=base_label)


def relationship(ctx):
    """Engagement breadth, channels used together, billers and primacy, on personal accounts."""
    from ti.transaction_intelligence import relationship as R
    personal, _business, base_label = base_accounts(ctx)
    return R.compute(ctx.txn, ctx.lenses, ctx.shared.get("fin_rows"), ctx.anchor_ts, ctx.warn,
                     account_filter=personal, key_prefix="rel_", base_label=base_label)


def family_tables(ctx):
    """Transactions by branch, product and swipe tier (v5 run.py's closing block)."""
    from ti.transaction_intelligence import lens as L
    out = {}
    if ctx.lenses is None:
        return out
    for fam in ("branch", "product", "swipe_tier"):
        rows = L.family_table(ctx.txn, ctx.lenses, fam)
        if rows:
            out[f"txn_by_{fam}"] = rows
            out[f"txn_by_{fam}_columns"] = ["value", "accounts", "txns", "dollars"]
        else:
            ctx.warn(f"txn family lens {fam}: ODD column absent; table skipped")
    return out


COMPB_KEYS = ("compb_base_label", "compb_accounts_total", "compb_with_competitor",
              "compb_with_competitor_pct", "compb_competitor_dollars", "compb_institutions",
              "compb_by_tier", "compb_local")


def competition(ctx):
    """comp_* on personal accounts, compb_* (v5's subset) on business. Reads financial services'
    classification; hands on the competition config and the competitor rows later sections read."""
    from ti.transaction_intelligence import competition as C
    personal, business, base_label = base_accounts(ctx)
    spec = C.load_config(dictionaries.folder(), ctx.config)
    ctx.shared["comp_spec"] = spec
    out, _files = C.compute(ctx.txn, ctx.lenses, spec, ctx.shared.get("fin_rows"), ctx.anchor_ts,
                            ctx.shared.get("lists_dir"), ctx.warn, account_filter=personal,
                            key_prefix="comp_", base_label=base_label)
    if business is not None and len(business):
        compb, _ = C.compute(ctx.txn, None, spec, ctx.shared.get("fin_rows"), ctx.anchor_ts, None,
                             lambda _m: None, account_filter=business, key_prefix="compb_",
                             base_label="transacting business accounts")
        out.update({k: v for k, v in compb.items() if k in COMPB_KEYS})
    # v5's run pops these hand-offs before writing; overlay, leakage, stressors read them
    ctx.shared["competitor_accounts"] = out.pop("_competitor_accounts", None)
    ctx.shared["competitor_monthly"] = out.pop("_competitor_monthly", None)
    return out


def mapping_audit(ctx):
    """What the dictionaries do not know yet, on the personal card rows (reports only: no figure
    elsewhere moves). Reads the three specs and financial services' providers, as v5's run does."""
    from ti.transaction_intelligence import mapping_audit as MA
    from ti.transaction_intelligence import merchants as M
    personal, _business, _label = base_accounts(ctx)
    df = ctx.txn
    is_card = df["transaction_type"].astype(str).str.upper().isin(["PIN", "SIG"])
    if personal is not None:
        is_card &= df["primary_account_num"].astype(str).isin(personal)
    card = df[is_card]
    if not len(card):
        return {}
    mspec = ctx.shared.get("mch_spec") or M.load_categories(dictionaries.folder())
    cats, _method, _cov = M._categorize(card, mspec, lambda _m: None)
    rows = ctx.shared.get("fin_rows")
    return MA.compute(card, cats, card["amount"].abs(), ctx.shared.get("fin_spec"),
                      ctx.shared.get("comp_spec"), mspec,
                      rows["provider"] if rows is not None else None, ctx.warn)
