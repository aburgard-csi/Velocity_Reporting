"""
The build pipeline: load once, build each enabled section, save.

PROVENANCE: the analysis team's `build.py`. Same shape — load the extracts once, build each section
inside its own try/except, collect every skip reason and print it on a Data Notes slide — with the
template machinery removed (there is no template to purge, rebrand or anchor into; see template.py)
and the new sections added for what the team pastes in by hand each cycle (client_slides.py).

Order of operations:

  1. Open the RPE shell with its demo slides detached.
  2. Load the extracts once (60-190 MB each) and derive what several sections share: the account /
     notice frame (`r_common.Frame`), the per-account volatility table, the 66-day notice counts.
  3. Draw the cover, then build each enabled section in registry order. A section's slides get a
     divider in front of them the first time their group appears.
  4. Write the Data Notes slide(s) from the accumulated skip reasons, the closing slide, slide
     numbers and logos, the figure sidecars, and save.

Every section is wrapped: a section that raises is reported on the notes slide and the rest of the deck
still builds. A half-finished deck plus an explicit note beats no deck at all when a client's export has
something unexpected in it.
"""
from __future__ import annotations

import json
import os
import traceback
from datetime import datetime

from . import theme as T                       # first: it puts build/ on sys.path for the modules below
from . import analysis_slides
from . import branch_metrics as BM
from . import branch_slides
from . import peers_slides
from . import standard_slides
from . import client_slides as CS
from . import dbic
from . import dbic_slides
from . import ds_analysis as DS
from . import ds_logic
from . import ds_slides
from . import ils_data
from . import matrix_data as MD
from . import matrix_report
from . import matrix_prep_slides
from . import matrix_slides
from . import r_common
from . import scoring_summary
from . import story_slides
from . import theme as T
from .config import (APPENDIX_KEYS, GROUP_DIVIDERS, MAX_SLIDES, NO_DIVIDER_GROUPS, PART_APPENDIX, PART_OF,
                     SECTIONS, BuildConfig)
from .ils_data import count
from .template import Shell

import brand                                                   # noqa: E402  (build/ is on sys.path via theme)
import cover_divider                                           # noqa: E402
import rpe_env                                                 # noqa: E402
import shapes                                                  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN                # noqa: E402
from pptx.util import Pt                                       # noqa: E402

PRODUCT = "Intelligent Limit System®"
DECK_KIND = "ILS Program Analysis"


class _Run:
    """Mutable state for one build."""

    def __init__(self, cfg, shell, deck, loaded, frame, S):
        self.cfg = cfg
        self.shell = shell
        self.dk = deck
        self.loaded = loaded
        self.fr = frame
        self.S = S
        self.notes = []
        self.errors = []
        self.slides_by_section = {}
        self.section_counts = {}
        self.settings = {}
        self.build_log = []
        self.say = lambda m: None
        self.cv = None                 # shared per-account volatility table
        self.notice66 = None           # shared 66-day notice counts

    def shared_cv(self):
        if self.cv is None and self.loaded.has_trend:
            self.cv = BM.account_level_cv(self.loaded.ztrend, self.cfg.min_periods_for_volatility)
        return self.cv

    def shared_notice66(self):
        if self.notice66 is None and self.loaded.has_trend:
            self.notice66 = DS.notice_counts_66(self.loaded.ztrend, self.loaded.snapshot)
        return self.notice66


# ── section builders ────────────────────────────────────────────────────────
def _sec_branch(run, accttype, key):
    return branch_slides.add_branch_section(
        run.dk, run.cfg, run.loaded, accttype, section=key, cv=run.shared_cv(), divider=False, progress=run.say)


def _sec_scoring(run, accttype, key):
    notes = []
    if accttype == "Personal":
        notes += CS.add_scoring_figures(run.dk, run.cfg, run.fr, section=key, progress=run.say)
    notes += scoring_summary.add_scoring_section(run.dk, run.cfg, run.loaded, accttype, section=key,
                                                 divider=False, progress=run.say, frame=run.fr)
    return notes


def _sec_deposit_score(run, key):
    za = run.loaded.zaccounts
    ok, reason = DS.is_available(za)
    if not ok:
        return [reason]
    has_rules = ds_logic.has_rules(run.S) if run.S else False
    variables = ds_logic.rule_variables(run.S) if has_rules else None
    label = MD.deposit_score_label(run.S) if run.S else ""
    notes = []
    types = DS.scored_types(za) or [None]
    for t in types:
        run.say(f"Analysing Deposit Score output — {t or 'all accounts'}…")
        A = DS.analyze(za, run.loaded.ztrend, run.loaded.snapshot, scope_type=t, variables=variables,
                       has_rules=has_rules, notice66=run.shared_notice66(), active_rules_label=label)
        notes.extend(ds_slides.add_ds_section(run.dk, A, section=key, divider=False, progress=run.say))
    return notes


def _sec_ds_logic(run, key):
    if not run.S:
        return ["No matrix validation export was supplied, so the Deposit Score rule-logic slides were skipped."]
    _, notes = ds_logic.add_ds_logic_slides(run.dk, run.S, section=key, logic_image=run.cfg.logic_image,
                                            show_all=run.cfg.show_all_rows)
    return notes


def _sec_dbic(run, key):
    if not run.cfg.dbic_path:
        return ["No DBIC export was supplied, so the program-health slides (calculation log, feed integrity, Reg E "
                "opt-in, fee collection) were skipped."]
    run.say("Parsing DBIC export…")
    d = dbic.load(run.cfg.dbic_path)
    if not d.available:
        return [f"The DBIC export {os.path.basename(str(run.cfg.dbic_path))} contained no recognised sections, so the "
                f"program-health slides were skipped."]
    run.say(f"  {len(d.secs)} section(s) recognised.")
    return dbic_slides.add_dbic_section(run.dk, d, section=key, divider=False, progress=run.say)


def _sec_matrix(run, key):
    if not run.S:
        return ["No matrix validation export was supplied, so the matrix slides (parameters and overrides) were skipped."]
    return matrix_prep_slides.add_matrix_prep_slides(run.dk, run.cfg, run.S, run.settings, section=key, fr=run.fr)


def _sec_comm(run, key):
    if not run.S:
        return []
    if not MD.has_comm_strategies(run.S):
        return ["No Communication Strategies were found in the matrix export."]
    run.dk.source = CS._src(run.cfg, run.fr, "mx", extra="Strategies with ACTIVE = 1 only; inactive strategies are not shown.")
    matrix_slides.slides_comm_strategies(run.dk, run.S, section=key, show_all=run.cfg.show_all_rows)
    return []


def _client(fn):
    return lambda run, key: fn(run.dk, run.cfg, run.fr, section=key, progress=run.say)


BUILDERS = {
    "branch_personal": lambda r, k: _sec_branch(r, "Personal", k),
    "branch_business": lambda r, k: _sec_branch(r, "Business", k),
    "scoring_personal": lambda r, k: _sec_scoring(r, "Personal", k),
    "scoring_business": lambda r, k: _sec_scoring(r, "Business", k),
    "deposit_score": _sec_deposit_score,
    "ds_logic": _sec_ds_logic,
    "dbic": _sec_dbic,
    "matrix": _sec_matrix,
    "comm_strategies": _sec_comm,
    "kpi_rollup": _client(CS.add_kpi_rollup),
    "fee_trends": _client(CS.add_fee_trends),
    "exception_items": _client(CS.add_exception_items),
    "eligibility": _client(CS.add_eligibility),
    "branch_summary": _client(CS.add_branch_summary),
    "reg_e": _client(CS.add_reg_e),
    "debit_declines": _client(CS.add_debit_declines),
    "peer_data": _client(CS.add_peer_data),
    "calculating": lambda r, k: story_slides.add_calculating(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "performing": lambda r, k: story_slides.add_performing(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "nsf_share": lambda r, k: story_slides.add_nsf_share(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "chargeoffs": lambda r, k: story_slides.add_chargeoffs(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "pullback": lambda r, k: story_slides.add_pullback(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "yoy": lambda r, k: analysis_slides.add_yoy(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "usage_segments": lambda r, k: analysis_slides.add_usage_segments(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "peers": lambda r, k: peers_slides.add_peers(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
    "industry": lambda r, k: standard_slides.add_industry(r.dk, r.cfg, r.fr, r.S, section=k, progress=r.say),
}


# ── cover, dividers, closing ─────────────────────────────────────────────────
def _draw_cover(slide, client, month, logo=None):
    """The cover in the brand template's style (cover_divider.draw_cover), with the deck's own line.

    `cover_divider.draw_cover` stamps "Executive Review", which is the RPE deck's name; this deck is the
    ILS Program Analysis, so the line under the client name is "ILS Program Analysis  •  <month>"."""
    import brand_art
    from pptx.util import Inches
    cover_divider._clear(slide)
    cover_divider._rect(slide, 0, 0, cover_divider.SLIDE_W, cover_divider.SLIDE_H, brand.WHITE,
                        name=cover_divider.TAG_COVER)
    brand_art.add_freeform(slide, "title_band.xml")
    brand_art.add_freeform(slide, "title_wedge.xml")
    brand_art.add_logo(slide, "dark", 0.21, 0.01, 2.35)
    cover_divider._chips(slide, [PRODUCT])
    box = cover_divider._text(slide, cover_divider.COVER_X, 2.0, cover_divider.COVER_W, 2.55,
                              [(client, cover_divider._cover_pt(client), cover_divider.KICK, brand.WHITE, True),
                               (f"{DECK_KIND}  •  {month}", 24, cover_divider.KICK, brand.WHITE, False)],
                              anchor=MSO_ANCHOR.BOTTOM)
    box.text_frame.paragraphs[1].space_before = Pt(10)
    if logo and os.path.exists(logo):
        fit = rpe_env.fit_box(logo, 2.5, 0.7)
        if fit:
            lw, lh = fit
            x = cover_divider.SLIDE_W - 0.9 - 2.9
            cover_divider._rect(slide, x, 1.0, 2.9, 1.0, brand.WHITE, radius=0.1)
            slide.shapes.add_picture(logo, Inches(x + (2.9 - lw) / 2), Inches(1.0 + (1.0 - lh) / 2), width=Inches(lw))
    return slide


def _move_before(prs, slide, ref):
    lst = prs.slides._sldIdLst
    src, tgt = shapes.sldid_of(prs, slide), shapes.sldid_of(prs, ref)
    if src is None or tgt is None:
        return False
    lst.remove(src)
    tgt.addprevious(src)
    return True


# ── the data-notes slide ─────────────────────────────────────────────────────
def _slide_data_notes(run, key):
    """ONE appendix page: scope on the left, methods and limits on the right. Everything that was skipped, noted or
    compared with the hand-built decks is in the speaker notes (and figures_index.json), not on the slide."""
    cfg, loaded, fr = run.cfg, run.loaded, run.fr
    br = loaded.branches
    dk = run.dk
    scope = []
    za = loaded.zaccounts
    n_open = int((za["acctstatus"].astype(str).str.upper() == "O").sum())
    pull = f"; the extract was pulled {loaded.file_date:%Y-%m-%d}" if loaded.file_date is not None else ""
    scope.append(f"{count(len(za))} accounts in the extract, {count(n_open)} open, as of {str(fr.asof)[:10]}{pull}.")
    kept = "retail branches and digital channels" if cfg.include_digital else "retail branches"
    scope.append(f"Branch views cover the {kept}; back-office codes are held out ({br.summary()}).")
    scope.append("Open active accounts have a deposit in the last 240 days or an NSF/OD item in the last 365; a user has at least one NSF/OD item in 365 days.")
    scope.append("Comparisons use complete months only; movement within 2% is called almost flat.")
    scope.append("Peers are other ILS clients, shown by client number only; very large clients are compared with other very large ones, "
                 "the rest within their Census region, with five peers at least.")
    method = [
        f"Cure (the performing slides): a negative balance reaches $0 or more within {story_slides.CURE_DAYS} days of the notice. The Scoring "
        f"Summary uses a separate {fr.default_days}-day default and never shares a slide with a cure rate.",
        "NSF is collected fees on returned items and OD is collected fees on paid items; neither is netted for refunds.",
        "Pulled back means the current limit is below the account's own earlier maximum. The extracts have no daily limit history, so when "
        "and why are not shown, and no savings are claimed.",
        "Year over year compares the last 12 complete months with the 12 before. The hand-built decks' windows cannot be reproduced "
        "from the extract; the changes agree to within about two points and the levels differ.",
        "Trends are On or Off only, communication strategies are listed only when active, and strategic refunds are not shown.",
    ]
    extras = [m for m in (list(loaded.notes) + list(run.notes) + list(run.errors)) if m]
    full = ["Scope"] + scope + ["Methods"] + method + (["Notes, skips and comparisons"] + extras if extras else [])
    slide = dk.content("Appendix: data notes and methodology",
                       f"Scope, definitions and limits for the analysis in this deck  ·  data as of {str(fr.asof)[:10]}",
                       section=key, source=CS._src(cfg, fr, "za", "zt", "dd", "rf", "mx", "dbic"))
    colw = 6.0
    T.band_real(slide, 0.50, 1.75, colw, "SCOPE AND DEFINITIONS")
    T.bullets_real(slide, 0.50, 2.25, colw, 4.35, scope, size=13, min_size=10)
    T.band_real(slide, 0.50 + colw + 0.33, 1.75, colw, "METHODS AND LIMITS")
    T.bullets_real(slide, 0.50 + colw + 0.33, 2.25, colw, 4.35, method, size=13, min_size=10)
    note = slide.notes_slide.notes_text_frame.text
    slide.notes_slide.notes_text_frame.text = ("Say first: this page is for reference; it says what the figures cover and what they do not.\n" + note +
                                               "\n" + "\n".join(full))
    return slide


# ── slide furniture ──────────────────────────────────────────────────────────
def _finish(run):
    """Slide numbers and the client's logo on every content slide (STYLE.md section 4), in order."""
    prs = run.dk.prs
    assets = rpe_env.temp_dir("ars_assets_")
    lockup = os.path.join(os.path.dirname(os.path.abspath(brand.__file__)), "assets", "logo.png")
    numbered = {id(s) for s in run.dk.numbered}
    for n, slide in enumerate(prs.slides, 1):
        if id(slide) not in numbered:
            continue
        shapes.textbox(slide, 0.45, 7.05, 0.70, 0.30, str(n), 10, brand.NAVY_RGB, True, PP_ALIGN.LEFT, brand.BODY,
                       MSO_ANCHOR.MIDDLE, name="Slide number")
        shapes.data_logo(slide, run.cfg.client_id or None, assets_dir=assets, lockup=lockup)


def _period_tag(cfg, loaded):
    """yyyy.mm — the REPORTING month, from the data pull's file stamp, never the clock (STYLE.md section 5)."""
    d = loaded.file_date or loaded.snapshot
    return f"{d.year}.{d.month:02d}", f"{d:%B %Y}"


# ── driver ──────────────────────────────────────────────────────────────────
def build_review(cfg: BuildConfig, progress=None):
    """Build the analysis deck. Returns the output path."""
    say = progress or (lambda m: None)
    say("Opening the RPE shell…")
    shell = Shell(cfg.shell_path)
    loaded = ils_data.load(
        cfg.zaccounts_path, cfg.ztrend_path, exclude_branches=cfg.exclude_branches,
        digital_branches=cfg.digital_branches, retail_branches=cfg.retail_branches,
        include_digital=cfg.include_digital, progress=say,
        declines_path=cfg.declines_path, refunds_path=cfg.refunds_path)
    fr = r_common.Frame(loaded)

    S, types, codes, settings = None, [], {}, {}
    if cfg.matrix_path:
        say("Parsing matrix validation export…")
        S = matrix_report.parse(cfg.matrix_path)
        types, codes, settings = MD.detect_types(S)
        if not types:
            say("  Warning: no account types found in the matrix export — matrix sections will be skipped.")
            S = None
        else:
            say(f"  {len(S)} sections, {len(types)} account type(s): {', '.join(types)}.")
    period, month = _period_tag(cfg, loaded)
    if not types:
        types = ils_data.account_types(loaded.zaccounts)
        codes = {t: "" for t in types}
    footer_types = "  ·  ".join(f"{t} ({codes.get(t, '')})".replace(" ()", "") for t in types)

    date_label = cfg.report_date or loaded.date_label
    dk = T.Deck(shell, cfg.client_name, date_label, client_id=cfg.client_id, footer_label=DECK_KIND,
                footer_extra=footer_types, types=types, codes=codes, colors=T.assign_type_colors(types))
    dk.relabel_mrpc = cfg.relabel_mrpc
    dk.pill_text = f"As of {loaded.snapshot:%b} {loaded.snapshot.day}, {loaded.snapshot.year}"
    chart_dir = cfg.chart_dir or os.path.join(str(rpe_env.build_artifacts()), "ils_analysis", "out",
                                              f"{cfg.client_id or 'client'}-{period}-charts")
    os.makedirs(chart_dir, exist_ok=True)
    dk.chart_dir = chart_dir
    ref_path = os.path.join(chart_dir, "parity_reference.json")
    if os.path.isfile(ref_path):
        dk.ref = json.load(open(ref_path, encoding="utf-8"))
        say(f"  parity reference figures: {len(dk.ref)} from {ref_path}")
    dk.source = CS._src(cfg, fr, "za", "zt")
    run = _Run(cfg, shell, dk, loaded, fr, S)
    run.settings = settings
    run.say = say

    # ── cover ──────────────────────────────────────────────────────────────
    cover = shell.add_slide()
    dk.generated.append(cover)
    logo = None
    try:
        assets = rpe_env.temp_dir("ars_assets_")
        lp = rpe_env.client_logo(cfg.client_id) if cfg.client_id else None
        logo = str(rpe_env.trim_logo(lp, assets)) if lp else None
    except Exception as exc:                                  # a logo problem never fails a build
        say(f"  logo not used: {type(exc).__name__}: {exc}")
    _draw_cover(cover, cfg.client_name, month, logo)
    dk.set_notes(cover, "Source: cover slide, no data.", extra=T.CONFIDENTIALITY_NOTICE)

    # ── sections ───────────────────────────────────────────────────────────
    done_groups = set()
    done_parts = set()
    agenda_rows = []

    def _part_divider(part, first_slide, key):
        """The part's divider, with no description line (Aaron, 2026-11-05), before its first slide; once per part."""
        if part in done_parts:
            return
        done_parts.add(part)
        agenda_rows.append((part, ""))
        div = dk.divider(part, section=key, source=f"Source: section divider for {cfg.client_name} (no data).")
        _move_before(dk.prs, div, first_slide)

    def _do_section(key):
        if key == "data_notes":
            return                         # always built last, below
        sec = SECTIONS[key]
        missing = []
        if "matrix" in sec.needs and not S:
            missing.append("matrix validation export")
        if "dbic" in sec.needs and not cfg.dbic_path:
            missing.append("DBIC export")
        if "ztrend" in sec.needs and not cfg.ztrend_path:
            missing.append("ZTrend")
        if "declines" in sec.needs and not cfg.declines_path:
            missing.append("DebitDecline file")
        if missing:
            run.notes.append(f"{sec.label}: skipped — no {' or '.join(missing)} supplied.")
            return
        say(f"Building section: {sec.label}…")
        before = len(dk.generated)
        try:
            run.notes.extend(n for n in (BUILDERS[key](run, key) or []) if n)
        except Exception as exc:
            detail = traceback.format_exc(limit=3).strip().splitlines()[-1]
            run.errors.append(f"{sec.label}: failed to build — {type(exc).__name__}: {exc}. ({detail})")
            say(f"  ! {sec.label} failed: {exc}")
            if os.environ.get("ILS_REVIEW_DEBUG"):
                traceback.print_exc()
        added = dk.generated[before:]
        run.slides_by_section[key] = added
        run.section_counts[key] = len(added)
        if added and key in PART_OF:
            _part_divider(PART_OF[key], added[0], key)
        elif added and sec.group in GROUP_DIVIDERS and sec.group not in done_groups:
            done_groups.add(sec.group)
            title, benefits = GROUP_DIVIDERS[sec.group]
            agenda_rows.append((title, ""))
            if sec.group not in NO_DIVIDER_GROUPS:
                div = dk.divider(title, blurb=benefits, section=key,
                                 source=f"Source: section divider for {cfg.client_name} (no data).")
                _move_before(dk.prs, div, added[0])
        if added:
            say(f"  {len(added)} slide(s).")

    for key in cfg.sections:
        if key not in APPENDIX_KEYS:
            _do_section(key)

    closing = shell.add_slide()
    dk.generated.append(closing)
    cover_divider.draw_closing(closing, f"{cfg.client_name}  •  {month}", title="Thank You")
    dk.set_notes(closing, "Source: closing slide, no data.")
    # Contact Us: the client's managing CSM (rpe_env.csm_contact, drawn by shapes.draw_contact_slide, the same
    # card every RPE deck carries), then the ILS consultant when one is passed (--consultant; Aaron, 2026-11-05).
    try:
        contact = rpe_env.csm_contact(cfg.client_id)
    except SystemExit as exc:
        contact = None
        run.build_log.append(f"Contact Us slide not added: {exc}")
    if contact:
        cs = shell.add_slide()
        dk.generated.append(cs)
        cards = [contact] + ([cfg.consultant] if cfg.consultant else [])
        shapes.draw_contact_slide(cs, cards)
        note = shapes.contact_card_note(contact)
        if cfg.consultant:
            note += (f" ILS consultant {cfg.consultant['name']}: details as given by the CSM from the Outlook "
                     "directory, passed to the build with --consultant.")
        cs.notes_slide.notes_text_frame.text = note
        run.build_log.append("Contact Us carries the CSM"
                             + (f" and ILS consultant {cfg.consultant['name']}." if cfg.consultant
                                else " only: no consultant details were passed (--consultant)."))

    # ── the appendix: the matrix first, then the detail tables the story slides point to, then the data notes ─────
    for key in cfg.sections:
        if key in APPENDIX_KEYS:
            _do_section(key)
    n_before_deferred = len(dk.generated)
    for fn in list(dk.deferred):
        try:
            for n in (fn() or []):
                if isinstance(n, str) and n and n not in run.notes:
                    run.notes.append(n)
        except Exception as exc:
            detail = traceback.format_exc(limit=3).strip().splitlines()[-1]
            run.errors.append(f"Appendix slide failed to build — {type(exc).__name__}: {exc}. ({detail})")
            if os.environ.get("ILS_REVIEW_DEBUG"):
                traceback.print_exc()
    n_appendix = len(dk.deferred)
    _slide_data_notes(run, "data_notes")
    if PART_APPENDIX not in done_parts and len(dk.generated) > n_before_deferred:
        _part_divider(PART_APPENDIX, dk.generated[n_before_deferred], "appendix")
    if PART_APPENDIX not in done_parts:
        agenda_rows.append((PART_APPENDIX, ""))
    # ── the agenda goes right after the cover ───────────────────────────────
    ref = dk.prs.slides[1] if len(dk.prs.slides) > 1 else None
    ag = standard_slides.add_agenda(dk, agenda_rows)
    if ref is not None:
        _move_before(dk.prs, ag, ref)

    _finish(run)
    if len(shell.prs.slides) > MAX_SLIDES:
        msg = f"The deck has {len(shell.prs.slides)} slides, over the {MAX_SLIDES}-slide limit; name fewer sections (--sections) or shorten the appendix."
        run.build_log.append(msg)
        run.errors.append(msg)
        say("  ! " + msg)
    out_path = cfg.resolve_output(period)
    say("Saving…")
    shell.save(out_path)
    index = {"client_id": cfg.client_id, "client": cfg.client_name, "period": period, "data_as_of": str(fr.asof)[:10],
             "deck": os.path.basename(out_path), "figures": dk.sidecars,
             "skipped_or_noted": run.notes + run.errors, "build_log": run.build_log}
    with open(os.path.join(chart_dir, "figures_index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1, ensure_ascii=False, default=str)
    say(f"Saved: {out_path}")
    total = sum(run.section_counts.values())
    say(f"Done — {total} generated slide(s) in a {len(shell.prs.slides)}-slide deck.")
    if run.errors:
        say(f"{len(run.errors)} section(s) reported an error; see the Data Notes slide.")
    return out_path


def summarize(cfg: BuildConfig):
    """A dry-run description of what a build would produce."""
    lines = []
    for key in cfg.sections:
        sec = SECTIONS[key]
        have = {"zaccounts": bool(cfg.zaccounts_path), "ztrend": bool(cfg.ztrend_path), "matrix": bool(cfg.matrix_path),
                "dbic": bool(cfg.dbic_path), "declines": bool(cfg.declines_path), "refunds": bool(cfg.refunds_path),
                "score": True}
        missing = [n for n in sec.needs if not have.get(n, True)]
        status = "will build" if not missing else f"needs {', '.join(missing)}"
        lines.append(f"{sec.label} — {status}")
    return lines
