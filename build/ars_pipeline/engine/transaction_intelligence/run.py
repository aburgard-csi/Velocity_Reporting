"""Transaction Intelligence — entry point.

    from ars.transaction_intelligence import run
    result = run("1615", "2026-08")

Same contract as monthly_analysis: run(client_id, period, **options) ->
AnalysisResult. Locates the client's transaction files, loads the trailing
window through the local parquet cache, joins against the ODD enrichment the
ARS run already wrote (if present), computes the portfolio block, and writes
txn_metrics.json + a manifest next to the ARS outputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import sys

from ..core.periods import Month
from ..core.result import AnalysisResult, Timer


def _step(msg: str) -> None:
    """Progress to stderr: minutes of silent number-crunching on a 5M-row
    file reads as a hang and gets Ctrl+C'd. Never on stdout (the Desktop
    tools own stdout)."""
    print(f"  [txn] {msg}", file=sys.stderr, flush=True)
from .txn_common import odd_account_key
from . import (card_behavior, competition, competition_report, financial_services,
               hotspots, lens, loader, mapping_audit, merchants, overlay,
               portfolio, relationship, sections_report, stressors_txn)
from . import leakage

ANALYSIS = "transaction_intelligence"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MONTHS = 12


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"    # the dictionaries ship with the engine


def run(client_id: str, period: str, data_root=None, output_root=None,
        config_dir=None, months: int = DEFAULT_MONTHS, *,
        txn_dirs=None, cache_dir=None, out_dir=None, odd=None, client_cfg=None) -> AnalysisResult:
    """In the pipeline the caller (build/ars_pipeline/run_analysis.py) names everything:
    `txn_dirs` (rpe_env's Inputs/Txn Files/<id>/), `cache_dir` and `out_dir` under
    Build Artifacts/, the enriched ODD frame `odd` it already holds, and the client
    record `client_cfg` from engine_config. The v5 root arguments remain for the tests."""
    data_root = Path(data_root) if data_root else PROJECT_ROOT / "01-Data"
    output_root = Path(output_root) if output_root else PROJECT_ROOT / "03-Output"
    config_dir = Path(config_dir) if config_dir else CONFIG_DIR
    parsed = Month.parse(period)
    result = AnalysisResult(analysis=ANALYSIS, client_id=str(client_id),
                            period=parsed.iso if parsed else str(period))

    with Timer(result):
        if parsed is None:
            result.fail(f"could not parse period {period!r}; expected YYYY-MM")
            return result
        from ..core.env import check_environment
        check_environment(result.fail)
        if not result.ok:
            return result

        txn_dir = [Path(d) for d in txn_dirs] if txn_dirs else loader.find_txn_dirs(data_root, client_id)
        if not txn_dir:
            result.fail(f"no transaction folder for {client_id}; looked under "
                        f"{data_root} for Inputs/Txn Files/{client_id}")
            return result
        result.outputs["source"] = "; ".join(str(d) for d in txn_dir)

        # The ARS run's data month is the anchor; the ODD carries one month of
        # lag on the file period, and we want the same window end.
        data_month = parsed.shift(-1)
        anchor_ts = pd.Timestamp(data_month.year, data_month.month, 1) + pd.offsets.MonthEnd(0)
        cache_dir = Path(cache_dir) if cache_dir else output_root / "_cache" / "txn" / str(client_id)
        _step("loading transaction files (cached files read fast; new ones re-read in chunks)...")
        df, rpt = loader.load(txn_dir, cache_dir, months=months, anchor=anchor_ts)
        _step(f"{rpt.rows:,} rows loaded ({rpt.cached} cached, {rpt.read} read)")
        for w in rpt.warnings:
            result.warn(w)
        result.rows_in = rpt.rows
        result.outputs["cache"] = str(cache_dir)
        if df.empty:
            result.fail("no transactions loaded")
            return result

        # How the transaction months line up with the ODD data month.
        last_txn_month = Month(df["transaction_date"].max().year,
                               df["transaction_date"].max().month)
        result.data_month = last_txn_month.iso
        lag = (data_month.year - last_txn_month.year) * 12 + (data_month.month - last_txn_month.month)
        if lag > 0:
            result.warn(f"transaction data ends {last_txn_month.iso}, {lag} month(s) "
                        f"before the ODD data month {data_month.iso}")
        elif lag < 0:
            result.warn(f"transaction data runs {-lag} month(s) past the ODD data "
                        f"month {data_month.iso}")

        enriched = output_root / parsed.iso / str(client_id) / "enriched.parquet"
        if odd is not None:
            result.outputs["odd"] = "enriched frame from the ODD run"
        elif enriched.exists():
            try:
                odd = pd.read_parquet(enriched, columns=None)
                result.outputs["odd"] = str(enriched)
            except Exception as exc:
                result.warn(f"could not read ODD enrichment for the join "
                            f"({type(exc).__name__}); join rate not measured")
        else:
            result.warn("no ARS enrichment for this period (run monthly_analysis "
                        "first); ODD join rate not measured")

        metrics: dict = {
            "txn_files_loaded": rpt.files,
            "txn_files_skipped_n": len(rpt.skipped),
            "txn_files_cached": rpt.cached,
            "txn_files_read": rpt.read,
            "txn_files_short": list(rpt.short),
            "txn_columns_found": rpt.columns_found,
            "txn_window_months": months,
            "txn_anchor": data_month.iso,
        }
        # ONE choice of the ODD id column for every chapter (txn_common.odd_account_key).
        acct_key = (odd_account_key(odd, df["primary_account_num"].unique(), result.warn)[0]
                    if odd is not None else None)
        metrics.update(portfolio.compute(df, odd, result.warn, acct_key=acct_key))

        out_dir = Path(out_dir) if out_dir else output_root / parsed.iso / str(client_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ---- lenses from the ODD, then the sections ---------------------------
        # The client record is read HERE rather than below: the branch family
        # needs BranchMapping to group by display name, and the lens attrs are
        # built once. In the pipeline it arrives from engine_config.
        if client_cfg is None:
            client_cfg = {}
            cfg_path = config_dir / "clients_config.json"
            if cfg_path.exists():
                client_cfg = json.loads(
                    cfg_path.read_text(encoding="utf-8-sig")).get(str(client_id), {}) or {}
        lenses = (lens.build(odd, anchor_ts, result.warn,
                             branch_map=client_cfg.get("BranchMapping"), acct_key=acct_key)
                  if odd is not None else None)
        if lenses is not None:
            metrics["lenses"] = [[n, lenses.label(n), int(lenses.masks[n].sum())] for n in lenses.names()]
        personal = business = fin_rows = None
        # the txn file only contains accounts that transacted, so every
        # headline rate in this chapter has a TRANSACTING denominator --
        # the base label says so (issue #30)
        base_label = "transacting accounts"
        try:
            spec = financial_services.load_patterns(config_dir, client_cfg)
            personal = business = None
            if lenses is not None and "personal" in lenses.masks:
                personal, business = lenses.ids("personal"), lenses.ids("business")
            base_label = ("transacting personal accounts"
                          if personal is not None else "transacting accounts")
            # One classification of the rows, shared by both sections.
            _step(f"classifying {len(df):,} descriptions against the dictionaries "
                  f"(the long quiet step -- about 1-3 minutes on a 5M-row book; "
                  f"do NOT interrupt)...")
            fin_rows = financial_services.classify_rows(df, spec)
            _step("classification done; computing sections...")
            # Headline base = personal accounts; business reported separately so
            # floor plans and SBA loans never inflate the retail story.
            fin, fin_out = financial_services.compute(
                df, lenses, spec, anchor_ts, out_dir / "lists", result.warn,
                account_filter=personal, key_prefix="fin_", base_label=base_label,
                classification=fin_rows)
            metrics.update(fin)
            result.outputs.update(fin_out)
            if business is not None and len(business):
                finb, _ = financial_services.compute(
                    df, None, spec, anchor_ts, None, lambda _m: None,
                    account_filter=business, key_prefix="finb_", base_label="transacting business accounts",
                    classification=fin_rows)
                metrics.update({k: v for k, v in finb.items()
                                if k in ("finb_base_label", "finb_accounts_total", "finb_leaking_accounts",
                                         "finb_leaking_pct", "finb_leakage_dollars", "finb_addressable_dollars",
                                         "finb_by_category", "finb_top_providers", "finb_provider_concentration",
                                         "finb_p2p")})
        except FileNotFoundError as exc:
            result.warn(f"financial services skipped: {exc}")
            fin_rows = None
        except Exception as exc:
            result.warn(f"financial services failed: {type(exc).__name__}: {exc}")
            fin_rows = None
        try:
            cspec = competition.load_config(config_dir, client_cfg)
            comp, comp_out = competition.compute(
                df, lenses, cspec, fin_rows, anchor_ts, out_dir / "lists", result.warn,
                account_filter=personal, key_prefix="comp_", base_label=base_label)
            metrics.update(comp)
            result.outputs.update(comp_out)
            if business is not None and len(business):
                compb, _ = competition.compute(
                    df, None, cspec, fin_rows, anchor_ts, None, lambda _m: None,
                    account_filter=business, key_prefix="compb_", base_label="transacting business accounts")
                metrics.update({k: v for k, v in compb.items()
                                if k in ("compb_base_label", "compb_accounts_total", "compb_with_competitor",
                                         "compb_with_competitor_pct", "compb_competitor_dollars",
                                         "compb_institutions", "compb_by_tier", "compb_local")})
        except FileNotFoundError as exc:
            result.warn(f"competition skipped: {exc}")
        except Exception as exc:
            result.warn(f"competition failed: {type(exc).__name__}: {exc}")
        try:
            mspec = merchants.load_categories(config_dir)
            metrics.update(merchants.compute(df, lenses, mspec, anchor_ts, result.warn,
                                             account_filter=personal, key_prefix="mch_",
                                             base_label=base_label))
            if business is not None and len(business):
                mb = merchants.compute(df, None, mspec, anchor_ts, lambda _m: None,
                                       account_filter=business, key_prefix="mchb_",
                                       base_label="transacting business accounts")
                metrics.update({k: v for k, v in mb.items()
                                if k in ("mchb_base_label", "mchb_card_accounts", "mchb_card_spend",
                                         "mchb_top", "mchb_by_category")})
        except FileNotFoundError as exc:
            result.warn(f"merchants skipped: {exc}")
        except Exception as exc:
            result.warn(f"merchants failed: {type(exc).__name__}: {exc}")
        try:
            # what the dictionaries do not know yet -- reports only, no number
            # here moves. Runs on the same personal card base merchants used.
            is_card = df["transaction_type"].astype(str).str.upper() \
                .isin(["PIN", "SIG"])
            if personal is not None:
                is_card &= df["primary_account_num"].astype(str).isin(personal)
            card = df[is_card]
            if len(card):
                cats, _method, _cov = merchants._categorize(
                    card, mspec, lambda _m: None)
                metrics.update(mapping_audit.compute(
                    card, cats, card["amount"].abs(), spec, cspec, mspec,
                    fin_rows["provider"] if fin_rows is not None else None,
                    result.warn))
        except Exception as exc:
            result.warn(f"mapping audit failed: {type(exc).__name__}: {exc}")
        try:
            metrics.update(card_behavior.compute(df, lenses, anchor_ts, result.warn,
                                                 account_filter=personal, key_prefix="beh_",
                                                 base_label=base_label))
        except Exception as exc:
            result.warn(f"card_behavior failed: {type(exc).__name__}: {exc}")
        try:
            metrics.update(relationship.compute(df, lenses, fin_rows, anchor_ts, result.warn,
                                                account_filter=personal, key_prefix="rel_",
                                                base_label=base_label))
        except Exception as exc:
            result.warn(f"relationship failed: {type(exc).__name__}: {exc}")
        # Popped outside the try: three sections downstream read these, and a
        # failure inside overlay must not leave them undefined.
        comp_rows = metrics.pop("_competitor_accounts", None)
        comp_monthly = metrics.pop("_competitor_monthly", None)
        addr_rows = metrics.pop("_addressable_accounts", None)
        try:
            ovl, ovl_out = overlay.compute(lenses, comp_rows, addr_rows,
                                           out_dir / "lists", result.warn)
            metrics.update(ovl)
            result.outputs.update(ovl_out)
        except Exception as exc:
            result.warn(f"overlay failed: {type(exc).__name__}: {exc}")
        try:
            # Does competitor spend climb before an account closes? Same
            # event-time alignment as the ODD's lifecycle curve, on the one
            # series only the transaction file can see.
            metrics.update(leakage.compute(odd, comp_monthly, data_month,
                                           result.warn, acct_key=acct_key))
        except Exception as exc:
            result.warn(f"leakage failed: {type(exc).__name__}: {exc}")
        try:
            # The stressor count, across both sources. The ODD run reports
            # "Banking elsewhere" as a condition it could not build; this is
            # where it can be.
            stx, stx_out = stressors_txn.compute(
                odd, comp_rows, data_month, client_cfg,
                out_dir / "lists", result.warn)
            metrics.update(stx)
            result.outputs.update(stx_out)
        except Exception as exc:
            result.warn(f"stressors_txn failed: {type(exc).__name__}: {exc}")
        try:
            # attrition x competition, per branch. Joins the two chapters'
            # own figures; recomputes neither.
            hot = hotspots.compute(odd, metrics.get("comp_by_branch"),
                                   data_month, client_cfg.get("BranchMapping"),
                                   result.warn)
            metrics.update(hot)
        except Exception as exc:
            result.warn(f"hotspots failed: {type(exc).__name__}: {exc}")
        if lenses is not None:
            for fam in ("branch", "product", "swipe_tier"):
                rows = lens.family_table(df, lenses, fam)
                if rows:
                    metrics[f"txn_by_{fam}"] = rows
                    metrics[f"txn_by_{fam}_columns"] = ["value", "accounts", "txns", "dollars"]
                else:
                    result.warn(f"txn family lens {fam}: ODD column absent; table skipped")
        _step("sections done; writing metrics...")
        result.metrics = metrics
        from ..core.env import write_text_atomic
        mj = out_dir / "txn_metrics.json"
        write_text_atomic(mj, json.dumps(metrics, indent=1, default=str))
        result.outputs["metrics"] = str(mj)
        result.outputs["_manifest_dir"] = str(out_dir)

    manifest_dir = result.outputs.pop("_manifest_dir", None)
    if manifest_dir:
        result.outputs["manifest"] = str(result.write_manifest(manifest_dir))
    return result


def report(result: AnalysisResult) -> str:
    m = result.metrics or {}
    L: list[str] = []
    A = L.append
    A("=" * 60)
    A(f"{result.client_id}  transaction intelligence   period {result.period}   "
      f"data through {result.data_month}   ({result.duration_s or 0:.0f}s)")
    A("=" * 60)
    if not m:
        A("no metrics")
    else:
        A(f"  files: {len(m.get('txn_files_loaded', []))} loaded "
          f"({m.get('txn_files_cached', 0)} from cache), {m.get('txn_files_skipped_n', 0)} "
          f"outside the {m.get('txn_window_months')}-month window; "
          f"{m.get('txn_columns_found')} columns")
        short = m.get("txn_files_short") or []
        if short:
            # Said here, at the top, not only in a warning 400 lines down:
            # nine short files on 1100 went unread for weeks (#256).
            A(f"  READ SHORT on {len(short)} file(s): every figure below is "
              f"understated -- {', '.join(short)}")
        A(f"  rows {m.get('txn_rows', 0):,}   {m.get('txn_first_date')} -> {m.get('txn_last_date')}   "
          f"{m.get('txn_months_covered')} months")
        A(f"  accounts {m.get('txn_accounts', 0):,}   txns/acct {m.get('txn_per_account')}   "
          f"hashed account rows {m.get('txn_account_hashed_pct')}%")
        A(f"  MCC populated on {m.get('txn_mcc_coverage_pct')}% of card rows   "
          f"field 9 distinct {m.get('txn_field9_distinct')} {m.get('txn_field9_values', [])[:4]}   "
          f"field 11 distinct {m.get('txn_field11_distinct')} {m.get('txn_field11_values', [])[:4]}")
        if m.get("txn_odd_match_pct") is not None:
            A(f"  ODD join on {m.get('txn_odd_join_key')}: {m.get('txn_odd_accounts_matched', 0):,} "
              f"accounts matched ({m.get('txn_odd_match_pct')}%)")
        A("")
        A(f"    {'channel':<8}{'txns':>12}{'share':>8}{'amount':>16}{'avg':>9}")
        for ch, c, pct, a, avg in m.get("txn_by_channel", []):
            A(f"    {ch:<8}{c:>12,}{pct:>7.1f}%{a:>16,}{avg:>9,.2f}")
        A(f"  card spend {m.get('txn_card_spend', 0):,}   SIG share of card $ {m.get('txn_sig_share_pct')}%   "
          f"negative amounts {m.get('txn_negative_amount_pct')}%")
        A("")
        A(f"    {'month':<10}{'txns':>12}{'accounts':>10}{'amount':>16}{'card txns':>11}")
        for per, c, accts, a, cardc in m.get("txn_monthly", []):
            A(f"    {per:<10}{c:>12,}{accts:>10,}{a:>16,}{cardc:>11,}")
        A("")
        A(f"  top merchants by card transactions   ({m.get('txn_merchants_distinct', 0):,} distinct; "
          f"top 15 = {m.get('txn_top15_share_pct')}%, {m.get('txn_merchants_for_80pct', 0):,} merchants = 80%)")
        for name, c, pct in m.get("txn_top_merchants", []):
            A(f"    {str(name)[:40]:<42}{c:>10,}{pct:>7.1f}%")
        if m.get("txn_top_ach_chk"):
            A("")
            A("  top ACH / check counterparties")
            for name, c, a in m.get("txn_top_ach_chk", []):
                A(f"    {str(name)[:40]:<42}{c:>10,}{a:>16,}")
        if m.get("fin_by_category"):
            A("")
            A("=" * 60)
            A(f"FINANCIAL SERVICES   base: {m.get('fin_base_label')}   {m.get('fin_categories_n')} categories, "
              f"{m.get('fin_patterns_n'):,} names; matched {m.get('fin_matched_rows', 0):,} rows ({m.get('fin_matched_rows_pct')}%)")
            A("-" * 60)
            A(f"  leakage  {m.get('fin_leaking_accounts', 0):,} accounts ({m.get('fin_leaking_pct')}%)   "
              f"${m.get('fin_leakage_dollars', 0):,}  = {m.get('fin_leakage_pct_of_transfer_dollars')}% of ACH+check $")
            A(f"  addressable  {m.get('fin_addressable_accounts', 0):,} accounts ({m.get('fin_addressable_pct')}%), "
              f"{m.get('fin_addressable_active_accounts', 0):,} active/cooling   ${m.get('fin_addressable_dollars', 0):,}")
            A(f"  adjacency (P2P + fintech)  ${m.get('fin_adjacency_dollars', 0):,}   "
              f"multi-category leakers {m.get('fin_multi_category_pct')}%")
            sf = m.get("fin_self")
            if sf:
                A(f"  INTERNAL (SelfNames)  {sf['accounts']:,} accounts   {sf['txns']:,} txns   "
                  f"${sf['dollars']:,}  = {sf['pct_of_transfer_dollars']}% of ACH+check $   "
                  f"(whole book; excluded from every table)")
                for n, accts, txns, d in sf.get("by_name", [])[:5]:
                    A(f"    {n[:40]:<42}{accts:>8,}{txns:>10,}{d:>14,}")
            A("")
            A(f"    {'category':<26}{'accts':>8}{'% accts':>8}{'$':>15}{'$/acct':>9}{'wallet%':>8}{'card%':>7}  kind")
            for r in m["fin_by_category"]:
                ws = f"{r[8]:>7.1f}%" if r[8] is not None else f"{'-':>8}"
                A(f"    {r[0][:25]:<26}{r[1]:>8,}{r[2]:>7.1f}%{r[4]:>15,}{r[5]:>9,}{ws}{r[9]:>6.0f}%  "
                  f"{r[6]}{'' if r[7] else ' (non-addressable)'}")
            conc = m.get("fin_provider_concentration") or []
            if conc:
                A("")
                A("  who they pay   (top 3 providers' share of category $; distinct providers)")
                for name, n_prov, top3 in conc[:10]:
                    provs = m.get("fin_top_providers", {}).get(name, [])[:3]
                    A(f"    {name[:25]:<26}{top3:>5.0f}%  of {n_prov:>4}   " +
                      "  ".join(f"{p[0][:18]} ${p[2]:,}" for p in provs))
            rec = m.get("fin_recency") or []
            if rec:
                A("")
                A(f"    {'recency':<26}{'active':>8}{'cooling':>9}{'dormant':>9}{'lapsed':>8}    {'new':>6}{'recur':>7}{'stopped':>8}")
                dyn = {r[0]: r for r in (m.get("fin_new_recurring_stopped") or [])}
                for r in rec:
                    d = dyn.get(r[0], [r[0], 0, 0, 0])
                    A(f"    {r[0][:25]:<26}{r[1]:>8,}{r[2]:>9,}{r[3]:>9,}{r[4]:>8,}    {d[1]:>6,}{d[2]:>7,}{d[3]:>8,}")
            bl = m.get("fin_by_lens") or []
            if bl:
                A("")
                A(f"    {'by lens':<24}{'accts':>9}{'addressbl':>10}{'%':>7}{'$/acct':>10}{'P2P/fintech':>12}{'%':>7}")
                A(f"    (addressable categories only; base = lens accounts that transacted)")
                for ln, label, n, lk, pct, dpl, adjn, adjp in bl:
                    A(f"    {label[:23]:<24}{n:>9,}{lk:>9,}{pct:>6.1f}%{dpl:>10,}{adjn:>12,}{adjp:>6.1f}%")
                if m.get("fin_responder_leak_gap_pp") is not None:
                    A(f"  responders minus mailed non-responders: {m['fin_responder_leak_gap_pp']:+.1f} pts addressable (raw)")
                if m.get("fin_responder_leak_gap_conditioned_pp") is not None:
                    A(f"  conditioned on a transfer habit: {m['fin_responder_leak_gap_conditioned_pp']:+.1f} pts "
                      f"-- {m.get('fin_responder_leak_gap_note', '')}")
            for key, label in (("fin_at_risk_leaking", "recently inactive AND leaking"),
                               ("fin_new_accounts_leaking", "opened last 12 mo AND already leaking")):
                v = m.get(key)
                if v and v.get("accounts"):
                    A(f"  {label:<40}{v['leaking']:>8,} of {v['accounts']:,}  ({v['pct']}%)")
            prof = m.get("fin_leakers_profile") or []
            if prof:
                A("")
                A(f"    {'leakers hold with us':<26}{'accts':>8}{'median bal':>12}{'total bal':>16}{'tenure':>8}{'resp%':>7}")
                for name, n, mb, tb, ten, rp in prof:
                    A(f"    {name[:25]:<26}{n:>8,}{(mb if mb is not None else 0):>12,}{(tb if tb is not None else 0):>16,}"
                      f"{(ten if ten is not None else 0):>8}{(rp if rp is not None else 0):>6.1f}%")
            for key, label in (("fin_p2p", "P2P TRANSFERS"), ("fin_fintech", "FINTECH / NEOBANKS")):
                v = m.get(key)
                if v:
                    A("")
                    A(f"  {label}   {v['accounts']:,} accounts ({v['pct_of_accounts']}%)   {v['txns']:,} txns   "
                      f"${v['dollars']:,}   ${v['dollars_per_acct']:,}/acct   (adjacency, not leakage, not debit spend)")
                    A("    " + "   ".join(f"{p[0][:16]} {p[1]:,} accts ${p[2]:,}" for p in v.get("providers", [])[:5]))
                    if v.get("by_lens"):
                        A("    by lens: " + "  ".join(f"{ln} {pct}%" for ln, n_, pct in v["by_lens"]))
            ut = m.get("fin_unmatched_top") or []
            if ut:
                A("")
                A("  LARGEST UNMATCHED TRANSFER COUNTERPARTIES   (any kind; is a lender/bank hiding here?)")
                for k, c, d in ut[:12]:
                    A(f"    {k[:40]:<42}{c:>8,}{d:>14,}")
            rq = m.get("fin_review_queue") or []
            if rq:
                A("")
                A(f"  REVIEW QUEUE   finserv-looking descriptions the dictionary missed   ${m.get('fin_review_queue_dollars', 0):,}")
                for s_, c, d in rq[:12]:
                    A(f"    {s_[:48]:<50}{c:>8,}{d:>14,}")
            if m.get("finb_by_category"):
                A("")
                A(f"  BUSINESS ACCOUNTS (separate)   {m.get('finb_accounts_total', 0):,} transacting; "
                  f"{m.get('finb_leaking_accounts', 0):,} leaking ({m.get('finb_leaking_pct')}%)   "
                  f"${m.get('finb_leakage_dollars', 0):,} leakage")
                for r in m["finb_by_category"][:8]:
                    provs = m.get("finb_top_providers", {}).get(r[0], [])[:2]
                    A(f"    {r[0][:25]:<26}{r[1]:>7,}{r[4]:>15,}  " + "  ".join(f"{p[0][:18]} ${p[2]:,}" for p in provs))
            if result.outputs.get("finserv_lists"):
                A("")
                A(f"  action lists: {len(result.outputs['finserv_lists'])} CSVs under "
                  f"{Path(next(iter(result.outputs['finserv_lists'].values()))).parent}")
        L.extend(competition_report.lines(m, result.outputs))
        L.extend(sections_report.lines(m))
    if result.warnings:
        A("")
        A(f"WARNINGS ({len(result.warnings)})")
        for w in result.warnings:
            A(f"  - {w}")
    return "\n".join(L)
