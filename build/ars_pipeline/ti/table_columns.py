"""
table_columns.py — column names for the cut's tables that v5 never named, so that
`ti/monthly_analysis/tables.py` can write them as CSVs.

v5's tables layer writes a tabular figure only when it declares `<key>_columns` (or sits in its
LEGACY_COLUMNS). On the cut's real Sep26 packs that left 30 tables unwritten for 1761 and 68 for
1776, so those figures could not be checked row by row. The names live here, beside the ported
code and not in it: no ported file changes, no figure in `ti_pack.json` moves, and `with_columns`
is applied only on the way into `tables.write`.

Every name below is read from the line that builds the row (cited per entry), never from sample
values. Where the code already declares the names under another key, `ALIASES` points at that key
instead of repeating it, so the two can never drift:

  - the business-side tables (`finb_`, `compb_`, `mchb_`) are computed by the same functions as
    the personal side, which declare their columns; `txn_sections.py`'s business allow-lists
    (FINB_KEYS, COMPB_KEYS, MCHB_KEYS) keep the tables but not those declarations;
  - card_behavior.py declares `beh_routing_by_merchant`'s names as `beh_routing_columns`.

An alias whose key is absent leaves the table unwritten and named in the build's warnings, exactly
as an undeclared table is: a header is never invented.

Not here on purpose (they stay in `ti_pack.json`, and the build's warning names them):
  - `tier_migration_matrix`: a 9 x 9 matrix of account counts whose rows carry no label (the row is
    the tier over the prior three months, the column the tier over the latest three: No card,
    Non-user, 1-5, 6-10, 11-15, 16-20, 21-25, 26-40, 41+, profile.py:115); a CSV of it cannot be
    read without this note;
  - `tier_migration_windows`: the two windows' month tags, not a table.
"""

TI = "build/ars_pipeline/ti/"

# key -> the declared columns key it shares a row shape with
ALIASES = {
    "finb_by_category": "fin_by_category_columns",          # financial_services.py:450
    "compb_institutions": "comp_institutions_columns",      # competition.py:278
    "compb_by_tier": "comp_by_tier_columns",                # competition.py:287
    "mchb_top": "mch_top_columns",                          # merchants.py:141
    "mchb_by_category": "mch_by_category_columns",          # merchants.py:157
    "beh_routing_by_merchant": "beh_routing_columns",       # card_behavior.py:167
}

LIFE = ["offset_months", "accounts"]    # lifecycle.curve: [offset, n, mean, total, pct_active] (lifecycle.py:146)
RISK = ["accounts", "at_risk_pct", "at_risk_spend_annualized"]   # retention.risk_row (retention.py:273)

COLUMNS = {
    # ---- monthly_analysis/profile.py ---------------------------------------------------------
    "swipe_tier": ["tier", "accounts", "monthly_spend", "monthly_swipes", "monthly_nsf_od_items"],  # :75
    "ticket_by_tier": ["tier", "accounts", "avg_ticket"],                                       # :77
    "spend_swipe_series": ["month", "spend", "swipes"],                                         # :142
    "nsf_series": ["month", "nsf_items", "accounts_with_items"],                                # :162
    # accounts = every eligible account in the band; the rate is responders over the band's MAILED
    # accounts, a count the row does not carry (so responded / accounts is not the rate)
    "age": ["age_band", "accounts", "responded", "response_rate_of_mailed_pct"],                # :190
    "balance_profile": ["balance_band", "accounts", "responded", "response_rate_of_mailed_pct"],  # :207
    "new_products": ["product", "accounts_opened"],                                             # :241
    "new_swipe_seg": ["tier", "accounts", "pct_of_new_cardholders"],                            # :305
    "openings": ["month", "opened", "closed", "net_cumulative"],                                # :324
    "survival": ["horizon", "survival_pct"],                                                    # :342
    # ---- monthly_analysis/balance.py ---------------------------------------------------------
    "balance_bands": ["band", "accounts", "pct_of_accounts", "balance", "pct_of_balance"],      # :128
    "pfi_tiers": ["tier", "accounts", "pct_of_accounts", "balance", "pct_of_balance", "debit_pct"],  # :210
    "rege_by_balance_band": ["band", "reg_e_base_accounts"],                                    # :252
    # ---- monthly_analysis/retention.py -------------------------------------------------------
    "retention_health": ["status", "accounts", "pct_of_accounts", "recent_mean_spend",
                         "prior_mean_spend", "debit_pct"],                                      # :184
    "retention_by_age": ["age_band"] + RISK,                                                    # :283
    "retention_by_tenure": ["tenure_band"] + RISK,                                              # :297
    "retention_by_balance": ["balance_band"] + RISK,                                            # :301
    "retention_by_product": ["product"] + RISK,                                                 # :320
    "retention_by_swipe_tier": ["swipe_tier"] + RISK,                                           # :333
    "retention_by_response": ["response_group"] + RISK,                                         # :349
    "dormancy_progression": ["months_silent", "accounts", "pct_of_carded"],                     # :342
    # ---- monthly_analysis/attrition.py -------------------------------------------------------
    "attrition_velocity": ["month", "opened", "closed"],                                        # :236
    "attrition_life_dist": ["tenure_band", "closed"],                                           # :292
    "attrition_by_product": ["product", "at_risk", "closed", "rate_pct"],                       # :468
    # ---- monthly_analysis/ics.py -------------------------------------------------------------
    "ics_cmp_activation_cum": ["months_since_open", "ics_activated_pct", "non_ics_activated_pct"],  # :266
    "ics_cmp_openings_monthly": ["open_month", "ics_opened"],                                   # :278
    "ics_cmp_closure_duration": ["months_to_close", "ics_closed"],                              # :317
    "ics_cmp_branch": ["branch", "ics_accounts", "activated_m1_pct", "survival_12mo_pct"],      # :525
    # ---- lifecycle curves (lifecycle.curve) --------------------------------------------------
    "life_control": LIFE + ["mean_spend", "total_spend", "pct_active"],           # lifecycle_report.py:212
    "life_ramp_swipes": LIFE + ["mean_swipes", "total_swipes", "pct_active"],     # lifecycle_report.py:167
    "life_decline_swipes": LIFE + ["mean_swipes", "total_swipes", "pct_active"],  # lifecycle_report.py:197
    "life_deposit_decline": LIFE + ["mean_deposits", "total_deposits", "pct_with_deposit"],  # lifecycle_report.py:108
    "life_deposit_control": LIFE + ["mean_deposits", "total_deposits", "pct_with_deposit"],  # lifecycle_report.py:120
    "life_ramp_non": LIFE + ["mean_spend", "total_spend", "pct_active"],          # lifecycle_ics.py:68
    "life_decline_non": LIFE + ["mean_spend", "total_spend", "pct_active"],       # lifecycle_ics.py:75
    "life_ramp_ics_lift_pct": ["offset_months", "ics_lift_pct"],                  # lifecycle_ics.py:87
    "leak_control": LIFE + ["mean_competitor_dollars", "total_competitor_dollars",
                            "pct_with_any"],                                      # leakage.py:110
    # ---- transaction_intelligence/card_behavior.py -------------------------------------------
    "beh_intensity_bands": ["band", "accounts", "pct_of_card_accounts"],                        # :41
    "beh_ticket_bands": ["band", "transactions", "pct_of_transactions"],                        # :41
    "beh_active_accounts_monthly": ["month", "card_accounts"],                                  # :79
    "beh_card_dollars_monthly": ["month", "card_dollars"],                                      # :81
    # ---- transaction_intelligence/competition.py ---------------------------------------------
    "comp_competitors_per_account": ["competitors", "accounts"],                                # :295
    "comp_ecosystems": ["ecosystem", "accounts", "pct_of_accounts", "dollars"],                 # :367
    "comp_review_queue": ["descriptor", "txns", "dollars"],                                     # :498
    # account x competitor pairs, not accounts
    "comp_recency_bands": ["band", "pairs", "pct_of_pairs"],                                    # :615
    # ---- transaction_intelligence/financial_services.py --------------------------------------
    "fin_provider_concentration": ["category", "providers", "top3_dollar_pct"],                 # :473
    "finb_provider_concentration": ["category", "providers", "top3_dollar_pct"],                # :473
    # account x category relationships, not accounts
    "fin_recency": ["category", "active", "cooling", "dormant", "lapsed"],                      # :481
    "fin_new_recurring_stopped": ["category", "new_90d", "recurring", "stopped"],               # :482
    "fin_multi_category": ["categories", "accounts"],                                           # :489
    "fin_by_lens_category": ["lens", "category", "accounts", "pct_of_lens_accounts"],           # :524
    "fin_review_queue": ["descriptor", "txns", "dollars"],                                      # :628
    # ---- transaction_intelligence/merchants.py -----------------------------------------------
    "mch_new": ["merchant", "dollars", "accounts"],                                             # :185
    "mch_faded": ["merchant", "dollars", "accounts"],                                           # :187
    # ---- transaction_intelligence/portfolio.py -----------------------------------------------
    "txn_by_channel": ["channel", "txns", "pct_of_txns", "dollars", "avg_ticket"],              # :56
    "txn_field9_values": ["merchant_id_value", "rows"],                                         # :85
    "txn_field11_values": ["card_present_value", "rows"],                                       # :85
    "txn_top_merchants": ["merchant", "card_txns", "pct_of_card_txns"],                         # :122
    # txns / accounts / dollars over every rail; card_txns PIN + SIG only
    "txn_monthly": ["month", "txns", "accounts", "dollars", "card_txns"],                       # :142
    # ---- transaction_intelligence/relationship.py --------------------------------------------
    "rel_by_channel": ["channel", "accounts", "pct_of_accounts"],                               # :106
    "rel_billers_bands": ["band", "accounts", "pct_of_accounts"],                               # :141
}


def with_columns(metrics: dict) -> dict:
    """`metrics` plus a `<key>_columns` for each table here that is present and undeclared.

    A copy: the pack's figures are never touched. A key that already declares its columns keeps
    its own."""
    out = dict(metrics)
    for key, alias in ALIASES.items():
        if key in metrics and f"{key}_columns" not in metrics and metrics.get(alias):
            out[f"{key}_columns"] = list(metrics[alias])
    for key, columns in COLUMNS.items():
        if key in metrics and f"{key}_columns" not in metrics:
            out[f"{key}_columns"] = list(columns)
    return out
