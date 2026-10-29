# Ported from v5 02-Scripts/ils/kickoff_analysis/run.py at 7ba1e63. Logic unchanged; edits: the import of core.layout from kickoff/_v5/, the default output folder and --data-root through ils_pipeline/kickoff_input (rpe_env), and the CLI's run inside kickoff/_v5/compat.legacy_strings().
"""Entry point for the ILS Kickoff pipeline.

    from ils.run import run
    run(client_id="1842", period="2026-09",
        data_root=r"C:\\Users\\james.gilmore\\OneDrive - Computer Services, Inc\\ARS - v5 - 8.26\\01-Data\\ILS",
        output_dir=r"...\\03-Output\\ILS\\2026-09\\1842")

Mirrors the ARS convention: client_id + period (YYYY-MM), generic from
day one. Builds one Excel workbook with a tab per analysis, in the same
order as the notebook's slides.
"""

from __future__ import annotations

from dataclasses import dataclass
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

from .core.io import (OPEN_DATE, CodeConfig, business_open, check_output_dir,
                      default_output_dir, load_client_data, personal_open,
                      item_column_relationships, pay_rate_warnings,
                      rege_warnings, resolve_item_columns,
                      segment_warnings)
from .metrics import (
    account_status, business_split, deposits, nsf_strat, od_status,
    reg_e, od_limit, product_code, day2,
)
from .deck import charts, report, slides
from ._v5.core import layout
from ils_pipeline import kickoff_input


def _unmapped(load_warnings) -> list:
    """The column names the loader kept as-is, pulled back out of its warning
    so the pay-rate guard can name the likeliest real total."""
    import ast
    for w in load_warnings:
        if "Unmapped columns" in w and "[" in w:
            try:
                return ast.literal_eval(w[w.index("["):w.rindex("]") + 1])
            except (ValueError, SyntaxError):
                return []
    return []


@dataclass
class RunResult:
    """What a run produced, for a caller that cannot read stdout.

    run() printed its warnings and its deck path and returned only the
    workbook, so ils_run_kickoff could tell a user to read warnings it had
    no way to show them. A CLI can print; a tool has to return.
    """
    report: Path | None
    deck: Path | None
    warnings: list
    codes: CodeConfig

    def __str__(self) -> str:            # still reads as the workbook path
        return str(self.report)

    def __fspath__(self) -> str:
        return str(self.report)


def _template() -> Path:
    """The shared deck template every product builds on."""
    return layout.TEMPLATE


def run(client_id: str, period: str, data_root: str | Path,
        output_dir: str | Path | None = None,
        codes: CodeConfig | None = None, deck: bool = False,
        items_from_calc: bool = False) -> "RunResult":
    """
    codes: personal/business/open-status codes and OD eligibility rule (Stat Code).
    Defaults to CodeConfig() (P/B/O, eligible stat code "ODP Account") if
    not given -- pass your own CodeConfig(...) for a client whose file
    uses different values, rather than editing this file.
    """
    codes = codes or CodeConfig()
    warnings: list[str] = []
    data_root = Path(data_root)
    if output_dir is None:
        output_dir = kickoff_input.output_dir(client_id, period)
    # Before a single file is written: does this folder belong to this client?
    output_dir = check_output_dir(client_id, Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    deck_out = output_dir / f"{client_id} - ILS Kickoff {period}.pptx"

    # Say the codes out loud. They decide who counts as personal, who as
    # open, and which Stat Code means OD-eligible; a run that applies defaults silently
    # produces a confident number about the wrong population.
    print(f"Client {client_id}, period {period}")
    print(f"  codes: personal={codes.personal_code!r} "
          f"business={codes.business_code!r} open={codes.open_status_code!r} "
          f"OD-eligible Stat Code(s)={codes.eligible_stat_codes}")
    print(f"  reg-e opt-in={codes.rege_opt_in or 'NOT CONFIRMED'} "
          f"opt-out={codes.rege_opt_out or 'NOT CONFIRMED'}")
    print(f"  output: {output_dir}")

    df, load_warnings = load_client_data(data_root, client_id, period)
    warnings.extend(load_warnings)
    # Blank item counts refuse the run; the '# Calc' estimates only on request.
    estimated = resolve_item_columns(df, items_from_calc)
    if estimated:
        # The load's "blank, and here is the flag" note is answered by the flag.
        warnings = [w for w in warnings if not w.startswith("Item counts are blank")]
        warnings.extend(estimated)

    # Before anything is computed from them: did the two segments account for
    # the open book? Every table below is per-segment, so an account in
    # neither is missing from all of them and from nothing that says so.
    warnings.extend(segment_warnings(df, codes))
    # Reg E opt-in is a separate question from OD eligibility, and one the
    # run used to never ask. Unconfirmed is reported, never guessed.
    warnings.extend(rege_warnings(df, codes))
    # A 100% pay rate on every band is a column-mapping symptom, not a book
    # with no returns. Caught before any table is computed from it.
    warnings.extend(pay_rate_warnings(df, _unmapped(load_warnings)))
    warnings.extend(item_column_relationships(df))

    df_personal = personal_open(df, codes)
    df_business = business_open(df, codes)

    # Every analysis is kept as it is emitted, keyed by the sheet name. The
    # deck renders from this, so the workbook and the deck cannot drift: a
    # sheet with no slide and a slide with no sheet are both test failures.
    analyses: dict = {}
    chart_files: dict = {}
    built_deck = None

    def emit(path, sheet_name, data_df, charts=None, slide=True):
        """One analysis. `slide=False` keeps it in the workbook but off the
        deck -- for a table the run has already said is not meaningful."""
        report.add_analysis_to_report(path, sheet_name, data_df, charts=charts)
        if slide:
            analyses[sheet_name] = data_df
            chart_files[sheet_name] = list(charts or [])

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        report_path = report.create_report(
            client_id=client_id,
            output_dir=output_dir,
            total_accounts=len(df),
            source_file_name=df.attrs.get("source_path", ""),
        )

        # ---- Slide 1: Account Status Summary ----
        t1 = account_status.compute(df)
        plot1 = t1[t1.iloc[:, 0] != "Grand Total"]
        c1a = charts.bar_with_line(
            plot1.iloc[:, 0], plot1["# of Accounts"], plot1["Pay Ratio"] * 100,
            "# of Accounts", "Pay Ratio (%)",
            "Account Summary: Number of Accounts and Pay Ratio by Status",
            str(tmp_path / "account_status_analysis.png"),
        )
        returned = plot1["# of Items"] - plot1["# of Items Paid"]
        pct_paid = (plot1["# of Items Paid"] / plot1["# of Items"].replace(0, 1) * 100).round(1)
        c1b = charts.stacked_percentage_bar(
            plot1.iloc[:, 0], pct_paid, 100 - pct_paid, "Paid Items %", "Returned Items %",
            "Item Disposition by Account Status\n(Paid vs Returned)", "Percentage of Items",
            str(tmp_path / "item_disposition_by_status.png"),
        )
        c1c = charts.horizontal_share(
            list(plot1.iloc[:, 0]), list(plot1["% of Items"]), list(plot1["# of Items"]),
            "Distribution of Items by Account Status\n(Sorted by Share)", "Percentage of Total Items",
            str(tmp_path / "item_share_by_status.png"),
        )
        emit(report_path, "Account Status Analysis", t1, charts=[
            (c1a, "Chart 1: Accounts and Pay Ratio by Status"),
            (c1b, "Chart 2: Item Disposition (Paid vs Returned)"),
            (c1c, "Chart 3: Item Share Distribution"),
        ])

        # ---- Product Code Distribution (not an eligibility signal in ILS,
        # just a useful breakdown for the kickoff conversation) ----
        from .core.io import PRODUCT_CODE
        if PRODUCT_CODE in df.columns:
            t_product = product_code.compute(df)
            emit(report_path, "Product Code Distribution", t_product)
        else:
            warnings.append(f"'{PRODUCT_CODE}' column not found -- skipped Product Code Distribution tab.")

        # ---- Slide 2: Business vs Personal (Open Accounts) ----
        t2 = business_split.compute(df, codes)
        plot2 = t2[t2.iloc[:, 0] != "Grand Total"]
        c2 = charts.grouped_bar(
            list(plot2.iloc[:, 0]), list(plot2["% of Accounts"]), list(plot2["% of Items"]),
            "% of Accounts", "% of Items",
            "Account Distribution: % of Accounts vs % of Items by Business Type\n(Open Accounts Only)",
            "Business Flag", "Percentage",
            str(tmp_path / "business_type_distribution.png"),
        )
        emit(report_path, "Account Type Analysis", t2, charts=[
            (c2, "% of Accounts vs % of Items by Business Flag"),
        ])

        # ---- Slide 3 & 4: Deposit Distribution (personal / business) ----
        t3 = deposits.compute(df_personal)
        plot3 = t3[t3.iloc[:, 0] != "Grand Total"]
        c3 = charts.distribution_bar(
            list(plot3["Deposit Bin"]), list(plot3["% of Accounts"]), list(plot3["Accounts"]),
            df_personal["Deposit Count"].mean() if "Deposit Count" in df_personal.columns else 0,
            "Mean deposits/month",
            "Personal Account Distribution by Monthly Deposit Frequency\n(Open Accounts Only)",
            "Number of Deposits per Month",
            str(tmp_path / "personal_deposit_distribution.png"),
        )
        emit(report_path, "Personal Deposit Analysis", t3, charts=[
            (c3, "Personal Account Distribution by Deposit Frequency"),
        ])

        t4 = deposits.compute(df_business)
        plot4 = t4[t4.iloc[:, 0] != "Grand Total"]
        c4 = charts.distribution_bar(
            list(plot4["Deposit Bin"]), list(plot4["% of Accounts"]), list(plot4["Accounts"]),
            df_business["Deposit Count"].mean() if "Deposit Count" in df_business.columns else 0,
            "Mean deposits/month",
            "Business Account Distribution by Monthly Deposit Frequency\n(Open Accounts Only)",
            "Number of Deposits per Month",
            str(tmp_path / "business_deposit_distribution.png"),
        )
        emit(report_path, "Business Deposit Analysis", t4, charts=[
            (c4, "Business Account Distribution by Deposit Frequency"),
        ])

        # ---- Slides 5 & 6: NSF Stratification, basic ----
        t5 = nsf_strat.compute(df_personal, level="basic")
        t6 = nsf_strat.compute(df_business, level="basic")
        emit(report_path, "NSF Stratification", t5)
        emit(report_path, "NSF Stratification (Business)", t6)

        # ---- Slides 7 & 8: NSF Stratification + Pay Ratio ----
        t7 = nsf_strat.compute(df_personal, level="pay_ratio")
        t8 = nsf_strat.compute(df_business, level="pay_ratio")
        emit(report_path, "NSF Pay Ratio", t7)
        emit(report_path, "NSF Pay Ratio (Business)", t8)

        # ---- Slides 9 & 10: NSF Stratification, full detail ----
        # Slide 10 (business) was empty in the source notebook -- filled in
        # by mirroring Slide 9's personal logic, per instruction.
        t9 = nsf_strat.compute(df_personal, level="full")
        t10 = nsf_strat.compute(df_business, level="full")
        emit(report_path, "NSF Strat w Deposits", t9)
        emit(report_path, "NSF Strat w Deposits (Biz)", t10)

        # ---- Slide 11: OD/NSF Summary by Stat Code ----
        t11p = od_status.compute(df_personal)
        t11b = od_status.compute(df_business)
        emit(report_path, "OD Status Stratification", t11p)
        emit(report_path, "OD Status Stratification (Biz)", t11b)

        # ---- Reg E ----
        t_rege_simple = reg_e.simple(df_personal)
        t_rege_elig_p, elig_warning_p = reg_e.with_eligibility(df_personal, codes)
        t_rege_elig_b, elig_warning_b = reg_e.with_eligibility(df_business, codes)
        if elig_warning_p:
            warnings.append(f"Reg E opt-in by OD eligibility (Personal): {elig_warning_p}")
        if elig_warning_b:
            warnings.append(f"Reg E opt-in by OD eligibility (Business): {elig_warning_b}")
        t_rege_annual = reg_e.annual(df_personal)
        emit(report_path, "Reg E Summary", t_rege_simple)
        # A split the run has just called not meaningful does not go on a
        # slide. It stays in the workbook, where someone can look at why.
        emit(report_path, "Reg E by OD Eligibility", t_rege_elig_p,
             slide=not elig_warning_p)
        emit(report_path, "Reg E by OD Eligibility (Biz)", t_rege_elig_b,
             slide=not elig_warning_b)
        emit(report_path, "Historical Reg E", t_rege_annual)

        # ---- OD Limit Stratification ----
        t_odlimit_p = od_limit.compute(df_personal)
        t_odlimit_b = od_limit.compute(df_business)
        emit(report_path, "OD Limit Stratification", t_odlimit_p)
        emit(report_path, "OD Limit Stratification (Biz)", t_odlimit_b)

        # ---- Day 2 (from the ILS Kickoff Day 2 app) ----
        # Workbook tab and deck slide alike, under the deck's "Day 2 read-out"
        # section. A tab the run skips is absent from both.
        emit(report_path, "Day 2 Highlights", pd.concat([
            day2.highlights(df_personal, codes, "Personal"),
            day2.highlights(df_business, codes, "Business"),
        ], ignore_index=True))
        for label, seg, sheet in (("Personal", df_personal, "Day 2 OD Status Reg E In"),
                                  ("Business", df_business, "Day 2 OD Status Reg E In (Biz)")):
            t = day2.od_status_rege(seg, codes)
            if t is None:
                warnings.append(f"Day 2: {label} OD status for Reg E opt-ins skipped -- the Reg E "
                                f"opt-in value is not confirmed or matched no open {label.lower()} account.")
            else:
                emit(report_path, sheet, t)
        if OPEN_DATE in df.columns:
            for code, sheet in ((codes.personal_code, "Day 2 Year Opened"),
                                (codes.business_code, "Day 2 Year Opened (Biz)")):
                t = day2.year_opened(df, codes, code)
                if t is not None:
                    emit(report_path, sheet, t)
            t = day2.rege_by_year(df_personal, codes)
            if t is not None:
                emit(report_path, "Day 2 Reg E by Year Opened", t)
        else:
            warnings.append(f"'{OPEN_DATE}' column not found -- skipped the Day 2 year-opened tabs.")

        # The deck is built inside the temp directory because the chart PNGs
        # live there; pptx embeds them, so they only have to survive the save.
        if deck:
            stranded = slides.unslided(analyses)
            if stranded:
                warnings.append(
                    f"{len(stranded)} analysis/analyses reached the workbook but "
                    f"no slide: {stranded}. Add a Slide() to SLIDE_MANIFEST or "
                    f"decide deliberately that they are workbook-only.")
            deck_path = slides.build(
                client_id=client_id, period=period, analyses=analyses,
                chart_files=chart_files, template=_template(), out=deck_out,
                warnings=warnings, charts_dir=tmp_path,
                codes=codes, source=df.attrs.get("source_path", ""))
            print(f"Deck written to:   {deck_path}")
            built_deck = deck_path

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")

    print(f"\nReport written to: {report_path}")
    return RunResult(report=report_path, deck=built_deck, warnings=warnings,
                     codes=codes)


def prompt_for_codes(defaults: CodeConfig | None = None) -> CodeConfig:
    """
    Ask the user for the personal/business/open-status codes and Reg E
    eligibility rule at the start of a run, instead of hardcoding them.
    Press Enter on any prompt to keep the default shown.
    """
    d = defaults or CodeConfig()
    print("Account codes for this client's file (press Enter to keep default):")

    personal = input(f"  Personal account code [{d.personal_code}]: ").strip() or d.personal_code
    business = input(f"  Business account code [{d.business_code}]: ").strip() or d.business_code
    open_code = input(f"  Open status code [{d.open_status_code}]: ").strip() or d.open_status_code
    eligible_raw = input(
        f"  OD-eligible Stat Code(s), comma-separated "
        f"[{', '.join(d.eligible_stat_codes)}]: "
    ).strip()
    eligible = [s.strip() for s in eligible_raw.split(",")] if eligible_raw else d.eligible_stat_codes
    # Only opt-in is asked. Everything else is opted out by definition, and
    # asking for the complement made the operator enumerate a list they do
    # not think in (James, 2026-09-09).
    print("  Reg E opt-in is a DIFFERENT question from OD eligibility:")
    opt_in_raw = input(
        f"  Reg E Flag value(s) meaning OPTED IN, comma-separated "
        f"(everything else counts as opted out) "
        f"[{', '.join(d.rege_opt_in) or 'none set'}]: ").strip()
    opt_in = [s.strip() for s in opt_in_raw.split(",")] if opt_in_raw else d.rege_opt_in
    opt_out = d.rege_opt_out

    return CodeConfig(
        personal_code=personal,
        business_code=business,
        open_status_code=open_code,
        eligible_stat_codes=eligible,
        rege_opt_in=opt_in,
        rege_opt_out=opt_out,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the ILS Kickoff analysis for one client/period.")
    parser.add_argument("client_id")
    parser.add_argument("period", help="YYYY-MM")
    parser.add_argument("--data-root", default=None,
                        help="default: Inputs/ILS Kickoff/ under RPE_DATA_ROOT")
    parser.add_argument("--output-dir", default=None,
                        help="default: Build Artifacts/ils/kickoff/{client_id}/{period}/ under RPE_DATA_ROOT. "
                             "A folder naming a different client is refused.")
    parser.add_argument("--personal-code")
    parser.add_argument("--business-code")
    parser.add_argument("--open-code")
    parser.add_argument("--eligible-stat-codes", help="comma-separated")
    parser.add_argument("--rege-opt-in", help="comma-separated Reg E Flag "
                        "value(s) meaning the member opted in")
    parser.add_argument("--rege-opt-out", help="comma-separated")
    parser.add_argument(
        "--deck", action="store_true",
        help="also build the kickoff deck beside the workbook.",
    )
    parser.add_argument(
        "--items-from-calc", action="store_true",
        help="when the item columns are blank, use the file's 'Paid/Returned Items # Calc' "
             "estimates, labelled as estimates on the warnings slide.",
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="Prompt for account codes (the default at a terminal).",
    )
    parser.add_argument(
        "--use-defaults", action="store_true",
        help="Skip the prompt and accept the default codes. Say so on "
             "purpose: the defaults decide who counts as personal, who as "
             "open, and which Stat Code means OD-eligible.",
    )
    args = parser.parse_args()

    # Prompting is the default at a terminal. The codes are the client's
    # answer, not ours -- on 1840 the Reg-E rule matched 0 of 4,559 accounts
    # because nobody was asked, and the run said so only after the workbook
    # had been written.
    flagged = any([args.personal_code, args.business_code, args.open_code,
                   args.eligible_stat_codes, args.rege_opt_in,
                   args.rege_opt_out])
    interactive = args.interactive or (
        not flagged and not args.use_defaults and sys.stdin.isatty())

    if interactive:
        codes = prompt_for_codes()
    else:
        defaults = CodeConfig()
        codes = CodeConfig(
            personal_code=args.personal_code or defaults.personal_code,
            business_code=args.business_code or defaults.business_code,
            open_status_code=args.open_code or defaults.open_status_code,
            rege_opt_in=([s.strip() for s in args.rege_opt_in.split(",")]
                         if args.rege_opt_in else defaults.rege_opt_in),
            rege_opt_out=([s.strip() for s in args.rege_opt_out.split(",")]
                          if args.rege_opt_out else defaults.rege_opt_out),
            eligible_stat_codes=(
                [s.strip() for s in args.eligible_stat_codes.split(",")]
                if args.eligible_stat_codes else defaults.eligible_stat_codes
            ),
        )

    from ._v5.compat import legacy_strings
    with legacy_strings():
        run(args.client_id, args.period, args.data_root or kickoff_input.root(),
            args.output_dir, codes=codes, deck=args.deck, items_from_calc=args.items_from_calc)
