"""
Everything a build run can be told to do.

PROVENANCE: the analysis team's `config.py`. What changed for the RPE build:
  * no template path, rebrand, stale-data or cover-notice options: the deck is built from blank
    RPE slides (see template.py), so there is no previous client's content to rewrite or purge;
  * no section anchors: sections are appended in registry order, each behind its own divider;
  * new sections replace the slides the analysis team pastes in from R / Power BI / Excel each
    cycle (`client_data` group, see `client_slides.py`);
  * inputs are the client's extract files named by `rpe_env`-resolved paths, never typed in.

`BuildConfig` holds the inputs and the per-client knobs; `SECTIONS` is the registry of deck
sections — each one toggleable and reorderable, with the inputs it needs.

Sections degrade rather than fail. A section whose inputs are missing (no ztrend, no matrix
export, an empty Deposit_Score column) is skipped and the reason is recorded on the Data Notes
slide, so a partial run still produces a usable deck.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    needs: tuple          # which inputs must be present: zaccounts, ztrend, matrix, dbic, declines, refunds, score
    description: str
    group: str = ""       # divider the section sits under (sections of one group share a divider)


SECTIONS = {
    s.key: s for s in (
        # ── the analysis team's generated sections (ported) ───────────────────────────
        Section("branch_personal", "Branch deposit behaviour — Personal", ("zaccounts",),
                "Deposit intensity, engagement, volatility, overdraft activity and account growth "
                "by branch, for personal accounts.", "drivers"),
        Section("branch_business", "Branch deposit behaviour — Business", ("zaccounts",),
                "The same branch view scoped to business accounts.", "branch"),
        Section("deposit_score", "Deposit Score output analysis", ("zaccounts", "score"),
                "Distribution of the 0–5 Deposit Score, risk categorisation, and how the score "
                "aligns to the variables that drive it.", "deposit_score"),
        Section("ds_logic", "Deposit Score rule logic", ("matrix",),
                "The actual CALC logic each active Deposit Score matrix uses.", "deposit_score"),
        Section("dbic", "Program health (DBIC)", ("dbic",),
                "Nightly calculation health, data-feed integrity, Reg E opt-in and eligibility, fee "
                "collection, channel mix and override effectiveness, from the Daily Batch Integrity "
                "Check export.", "program"),
        Section("matrix", "ILS matrix: parameters and overrides", ("matrix",),
                "One slide per account type: limits, scoring factors, overrides and trend On / Off, from the matrix validation extract.", "matrix"),
        Section("comm_strategies", "Communication Strategies", ("matrix",),
                "Active member-outreach strategies and their cadence.", "matrix"),
        # ── the slides the analysis team pastes in each cycle, now computed here ──────
        Section("kpi_rollup", "365-day KPI rollup", ("zaccounts",),
                "Business and personal 365-day KPIs: fees, charge-offs, refunds, accounts and users.",
                "standing"),
        Section("fee_trends", "Collected fee trending and repayment", ("ztrend", "zaccounts"),
                "Daily collected fees with a 30-day moving average, monthly fee table, paid versus "
                "returned items, and the share of items not repaid, personal and business.",
                "standing"),
        Section("exception_items", "Exception items by channel", ("ztrend",),
                "Item volume and median item amount by channel (ACH, POS, check, ...).",
                "drivers"),
        Section("eligibility", "Eligibility drilldown", ("zaccounts",),
                "Accounts by OD status code and user segment, personal and business.", "drivers"),
        Section("branch_summary", "Branch summary", ("zaccounts",),
                "Items per user against eligibility and Reg E opt-in by branch, with top-ten "
                "tables.", "client_data"),
        Section("reg_e", "Reg E drilldown", ("zaccounts",),
                "Opt-in by election, by account-opening year, and items and declines by election.",
                "drivers"),
        Section("debit_declines", "Debit declines", ("zaccounts", "declines"),
                "Debit declines by annual decline segment and by deposit score band.",
                "client_data"),
        Section("scoring_personal", "ILS Scoring Summary — Personal", ("zaccounts", "ztrend"),
                "Predictor validation: score distribution, matrix-position heat maps and default "
                "rate by predictor band.", "scoring"),
        Section("scoring_business", "ILS Scoring Summary — Business", ("zaccounts", "ztrend"),
                "The predictor validation set scoped to business accounts.", "scoring"),
        # ── the narrative spine: calculating -> performing -> pulling back (story_slides.py) ──
        Section("calculating", "Where the limit is calculating", ("zaccounts", "matrix"),
                "Which accounts receive an ILS limit (by overdraft status), how limits are spread, how often they change.", "calc"),
        Section("performing", "Where the limit is performing", ("zaccounts", "ztrend"),
                "Cure rate (negative balance back to $0 within 60 days) by limit, deposits and days on book.", "perform"),
        Section("nsf_share", "NSF share of fee revenue", ("ztrend",),
                "Collected fees on returned items as a share of all collected fees, by month.", "standing"),
        Section("chargeoffs", "Charge-offs against account growth", ("zaccounts",),
                "Accounts charged off and accounts opened by month.", "standing"),
        Section("pullback", "Where the limit pulls back", ("zaccounts",),
                "Accounts whose limit is below their own earlier maximum, against accounts whose limit stayed.", "pullback"),
        Section("peer_data", "Peer fee data (placeholders)", (),
                "Peer NSF / OD fee distributions. The peer data is not in the client extracts, so "
                "these slides are labelled placeholders.", "peer"),
        # ── from the analysis team's delivered decks (Kevin Higginbotham's), generated from the extracts ──
        Section("yoy", "Year-over-year comparison", ("ztrend", "zaccounts"),
                "The last 12 complete months against the 12 before: collected fees, notices, accounts, fees per account.", "standing"),
        Section("usage_segments", "Who generates the fees", ("zaccounts",),
                "Share of accounts and of collected fees by NSF/OD items in 365 days, heavy users (24+) highlighted.", "drivers"),
        Section("peers", "How the client compares", ("zaccounts",),
                "NSF/OD items, collected fees and users per open account against other ILS clients: very large clients against other "
                "very large ones, the rest within their Census region. Client numbers only; five peers at least.", "peers"),
        Section("industry", "Industry update (standard)", (),
                "The cycle's standard consumer-survey and regulatory slides, read from the analysis team's industry_<yyyy-mm>.json.", "industry"),
        Section("data_notes", "Data notes & methodology", ("zaccounts",),
                "Scope, branch classification, and what was skipped and why.", "notes"),
    )
}

# Groups that are on the agenda but get no divider slide, to keep the deck inside MAX_SLIDES: the story's three acts
# (calculating, performing, pulling back) and "Where the Program Stands" keep theirs.
NO_DIVIDER_GROUPS = {"peers", "matrix", "industry", "drivers"}

MAX_SLIDES = 50         # Aaron / coordinator, 2026-11-04: 50 slides at most, cover, agenda, dividers and Contact included

DEFAULT_SECTIONS = [
    # where the program stands -> how it compares -> what drives it -> calculating -> performing -> pulling back
    # -> the matrix -> the industry update; the detail tables are queued for the appendix (`Deck.defer`)
    "kpi_rollup", "fee_trends", "yoy", "nsf_share", "chargeoffs", "peers",
    "exception_items", "usage_segments", "eligibility", "reg_e", "branch_personal",
    "calculating", "performing", "pullback",
    "matrix", "comm_strategies", "industry", "data_notes",
]
# every other section is still in SECTIONS and builds when named (--sections); they are left out of the story
# because each says less than a narrative slide, or uses the 40-day Scoring Summary basis.

GROUP_DIVIDERS = {
    "standing": ("Where the Program Stands", "Fees · Mix · Charge-offs"),
    "drivers": ("What Is Driving It", "Exceptions · Eligibility · Reg E · Branches"),
    "calc": ("Where the Limit Is Calculating", "Who gets a limit · How limits are spread"),
    "perform": ("Where the Limit Is Performing", "Cure rates by limit, deposits and age"),
    "pullback": ("Where the Limit Pulls Back", "Limits lowered · How many · By how much"),
    "matrix": ("ILS Matrix", "Parameters · Overrides · Trends"),
    "client_data": ("Client Analysis", "Fees · Eligibility · Branches · Reg E · Debit Declines"),
    "branch": ("Branch Overdraft and Deposit Behavior", "Deposit intensity · Engagement · Overdraft activity"),
    "scoring": ("Risk Review", "Score distribution · Predictor validation"),
    "deposit_score": ("Deposit Score", "Output analysis · Rule logic"),
    "program": ("Program Health", "Calculation log · Feeds · Reg E · Fee collection"),
    "peer": ("Peer Comparison", "NSF and OD fees by institution size"),
    "peers": ("How the Client Compares", "Items · Fees · Users per open account"),
    "industry": ("Industry Update", "Consumers · Regulation"),
}


def _codes(value):
    """Parse '40, 52, 44' or [40, 52] into a set of strings."""
    if not value:
        return set()
    if isinstance(value, (set, frozenset, list, tuple)):
        return {str(v).strip() for v in value if str(v).strip()}
    return {p.strip() for p in re.split(r"[,;\s]+", str(value)) if p.strip()}


@dataclass
class BuildConfig:
    # ── required inputs ───────────────────────────────────────────────────
    client_name: str            # the organization being reviewed
    zaccounts_path: str
    client_id: str = ""

    # ── optional inputs ───────────────────────────────────────────────────
    ztrend_path: Optional[str] = None
    matrix_path: Optional[str] = None
    dbic_path: Optional[str] = None         # Daily Batch Integrity Check export
    declines_path: Optional[str] = None     # DebitDecline_<date>.csv
    refunds_path: Optional[str] = None      # RefundHistory_<date>.csv
    logic_image: Optional[str] = None       # Deposit Score decision-tree diagram

    # ── output ────────────────────────────────────────────────────────────
    output_path: Optional[str] = None
    output_dir: Optional[str] = None
    report_date: Optional[str] = None       # label override, e.g. "September 11, 2026"
    shell_path: Optional[str] = None        # RPE shell override (default templates/ars_template.pptx)
    chart_dir: Optional[str] = None         # where chart PNGs and the figure sidecar are written

    # ── what to build ─────────────────────────────────────────────────────
    sections: list = field(default_factory=lambda: list(DEFAULT_SECTIONS))

    # ── branch scoping (blank = inferred from branch names) ───────────────
    exclude_branches: set = field(default_factory=set)
    digital_branches: set = field(default_factory=set)
    retail_branches: set = field(default_factory=set)
    include_digital: bool = True

    # ── analysis knobs ────────────────────────────────────────────────────
    top_n_personal: int = 25
    top_n_business: int = 20
    growth_year: Optional[int] = None       # None -> last full calendar year
    min_periods_for_volatility: int = 8
    default_repayment_days: int = 30
    default_basis: str = "deck"             # Scoring Summary default rule: "deck" (40 days, never-repaid excluded) or "readme"
    predictor_bands: str = "deck"           # "deck" = the hand-built deck's bands, "readme" = the analysis registry
    branch_core_only: bool = True           # branch section: overview + three ranked charts only
    include_not_repaid: bool = False        # the 'fatal notice' slides (40-day basis) are not in the story
    standard_dir: Optional[str] = None      # folder holding industry_<yyyy-mm>.json (default: Build Artifacts/ils_analysis/standard)
    peer_pool: Optional[object] = None      # ready peer rows (tests); None = read them (peers_slides.collect_pool)
    show_all_rows: bool = False             # paginate long tables instead of capping
    relabel_mrpc: bool = False              # show MRPC columns as CashPlease

    def __post_init__(self):
        self.exclude_branches = _codes(self.exclude_branches)
        self.digital_branches = _codes(self.digital_branches)
        self.retail_branches = _codes(self.retail_branches)
        if not self.zaccounts_path or not Path(self.zaccounts_path).exists():
            raise FileNotFoundError(f"zaccounts file not found: {self.zaccounts_path}")
        for label, p in (("ztrend", self.ztrend_path), ("matrix validation", self.matrix_path),
                         ("DBIC", self.dbic_path), ("debit declines", self.declines_path),
                         ("refund history", self.refunds_path), ("logic image", self.logic_image)):
            if p and not Path(p).exists():
                raise FileNotFoundError(f"{label} file not found: {p}")
        unknown = [s for s in self.sections if s not in SECTIONS]
        if unknown:
            raise ValueError(f"Unknown section(s): {', '.join(unknown)}. Valid: {', '.join(SECTIONS)}")
        if not self.client_name or not str(self.client_name).strip():
            raise ValueError("client_name is required (it titles the deck)")
        self.client_name = str(self.client_name).strip()

    # ── derived ───────────────────────────────────────────────────────────
    def resolve_output(self, period_tag):
        """Full output path: `<id>-<yyyy.mm>-ILS-<Client> ILS Analysis.pptx` (the RPE convention)."""
        if self.output_path:
            return str(self.output_path)
        name = f"{self.client_id or 'client'}-{period_tag}-ILS-{self.client_name} ILS Analysis.pptx"
        name = re.sub(r'[<>:"/\\|?*]', "", name)
        folder = self.output_dir or str(Path(self.zaccounts_path).parent)
        Path(folder).mkdir(parents=True, exist_ok=True)
        return str(Path(folder) / name)
