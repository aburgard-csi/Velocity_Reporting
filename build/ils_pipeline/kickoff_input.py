"""
kickoff_input.py — where the ILS kickoff extract is read from in RPE.

`Inputs/ILS Kickoff/<id>/`: one folder per client, holding the client's one-time data extract
(`<id>_OneTimeData_<yyyymmdd>.csv` or `.xlsx`, the date in the name). v5 looked under
`01-Data/ILS/{YYYY-MM}/{client}/`; here there is one place per client and no month folder, and v5's
loader (`kickoff/core/io.py`, unchanged) takes the folder from `client_dir` below. The newest
extract by the date in its name still wins, so a corrected extract dropped beside the old one is the
one read. `period` is still passed through: v5 records it on the frame and names its output by it.

The kind is in rpe_env.NOT_SCANNED_KINDS: the extract is member-level, hand-landed, and has no
"newer version" the watcher's copier or pruner understands.

Pandas: v5 runs pandas 2.3, this repo pandas 3. Under pandas 3 `astype(str)` keeps a blank code
blank where v5 wrote "nan", so the field summary stops counting blank codes and the Reg E check
raises on one (`'float' object has no attribute 'lower'`). Every entry point here therefore runs
v5's code inside `kickoff._v5.compat.legacy_strings()`, and so must any caller that computes from
the frame `load` returns: the frame alone does not carry the setting.

Running it, two ways, both v5's:
  * `run_kickoff(id, period)` returns the field summary and computes nothing; called again with the
    client's confirmed codes it writes the workbook (and the deck with `deck=True`). v5's
    `ils_run_kickoff` tool.
  * `cd build; python -m ils_pipeline.kickoff.run <id> <yyyy-mm> [--deck]`: at a terminal it asks
    for the codes; passing any code flag, or `--use-defaults`, skips the prompt. v5's CLI.
Either writes to `Build Artifacts/ils/kickoff/<id>/<period>/` (`output_dir` below), never to Outputs.
"""
from pathlib import Path


def folder(client_id) -> Path:
    """The client's kickoff folder. Not created: a missing folder is a missing extract."""
    import rpe_env
    return rpe_env.input_dir("ILS Kickoff", create=False) / str(client_id)


def client_dir(root, client_id, period) -> Path:
    """v5's `data_root / period / client_id`, on the RPE layout.

    `root` is the ILS Kickoff input folder (v5 passed its data root). `period` does not pick a
    folder here; it is accepted so v5's call is unchanged."""
    return Path(root) / str(client_id)


def find_extract(client_id, period) -> Path:
    """The newest OneTimeData extract in the client's folder (v5's `resolve_data_file`)."""
    import rpe_env
    from ils_pipeline.kickoff.core import io
    root = rpe_env.input_dir("ILS Kickoff", create=False)
    if not (root / str(client_id)).is_dir():
        raise FileNotFoundError(
            f"no ILS kickoff folder for {client_id}: land the client's OneTimeData extract in "
            f"{root / str(client_id)}")
    return io.resolve_data_file(root, str(client_id), period)


def load(client_id, period):
    """v5's `load_client_data` on the client's folder: (canonicalized frame, warnings)."""
    import rpe_env
    from ils_pipeline.kickoff.core import io
    from ils_pipeline.kickoff._v5.compat import legacy_strings
    find_extract(client_id, period)            # the RPE-worded error for a missing folder
    with legacy_strings():
        return io.load_client_data(rpe_env.input_dir("ILS Kickoff", create=False), str(client_id),
                                   period)


def root() -> Path:
    """The ILS Kickoff input folder: what v5's run takes as `data_root`."""
    import rpe_env
    return rpe_env.input_dir("ILS Kickoff", create=False)


def output_dir(client_id, period) -> Path:
    """`Build Artifacts/ils/kickoff/<id>/<period>/`: where a run writes when nobody says otherwise.

    v5 wrote `03-Output/ILS/{period}/{client}/`. The run's files go under Build Artifacts; a finished
    deck run from Sheila is also copied to `Outputs/<CSM>/ILS/` (scripts/ils_job.deliver, James Gilmore,
    2026-10-29: "the decks should be going in the respective output folders"). RPE_DATA_ROOT must be set:
    rpe_env.build_artifacts() would otherwise fall back to a folder inside the checkout."""
    import rpe_env
    rpe_env.data_root()                          # raises when unset, rather than write into the repo
    return rpe_env.build_artifacts() / "ils" / "kickoff" / str(client_id) / str(period)


def _split(v):
    if not v:
        return None
    return [s.strip() for s in str(v).split(",") if s.strip()]


def run_kickoff(client_id: str, period: str, personal_code: str = "", business_code: str = "",
                open_code: str = "", eligible_stat_codes: str = "", rege_opt_in: str = "",
                rege_opt_out: str = "", deck: bool = False, output_dir=None,
                items_from_calc: bool = False) -> str:
    """The non-interactive kickoff, in two steps: v5's `ils_run_kickoff` tool
    (v5 tools/products/ils.py at 7ba1e63), on the RPE folders.

    Called with only client_id and period it loads the newest extract and returns the FIELD SUMMARY
    (the distinct values of Business Flag, Account Status, Stat Code, Product Code and Reg E Flag,
    with counts) and computes nothing. Which values mean personal, business, open and OD-eligible,
    and which Reg E Flag means opted in, are the client's answers: ask, never choose. Called again
    with any code it runs: the workbook, and the deck when `deck` is set. Returns text either way,
    the run's warnings included, so a caller that cannot read stdout still sees them.
    """
    from ils_pipeline.kickoff._v5.compat import legacy_strings

    confirmed = any([personal_code, business_code, open_code, eligible_stat_codes, rege_opt_in,
                     rege_opt_out])
    try:
        with legacy_strings():
            from ils_pipeline.kickoff.core.io import CodeConfig, summarise_fields
            if not confirmed:
                frame, warnings = load(client_id, period)
                head = (f"{client_id} {period} -- kickoff, step 1 of 2. "
                        f"No codes given, so nothing has been computed.\n\n")
                tail = ("\n\nWarnings from the load:\n  "
                        + "\n  ".join(warnings)) if warnings else ""
                return head + summarise_fields(frame) + tail

            defaults = CodeConfig()
            codes = CodeConfig(
                personal_code=personal_code or defaults.personal_code,
                business_code=business_code or defaults.business_code,
                open_status_code=open_code or defaults.open_status_code,
                eligible_stat_codes=(_split(eligible_stat_codes)
                                     or defaults.eligible_stat_codes),
                rege_opt_in=_split(rege_opt_in) or [],
                rege_opt_out=_split(rege_opt_out) or [])
            from ils_pipeline.kickoff.run import run as _run
            find_extract(client_id, period)            # the RPE-worded error for a missing folder
            try:
                result = _run(client_id, period, root(), output_dir, codes=codes, deck=deck,
                              items_from_calc=items_from_calc)
            except Exception as exc:
                if not deck:
                    raise
                # A deck failure must not cost the workbook. Retry without it
                # and say so, rather than returning nothing for both.
                result = _run(client_id, period, root(), output_dir, codes=codes, deck=False,
                              items_from_calc=items_from_calc)
                result.warnings.append(
                    f"The deck failed to build ({type(exc).__name__}: {exc}). "
                    f"The workbook above is complete and unaffected.")
    except FileNotFoundError as exc:
        return (f"No kickoff extract for {client_id} {period}: {exc}. "
                f"Expected Inputs/ILS Kickoff/{client_id}/"
                f"{client_id}_OneTimeData_*.csv or .xlsx")
    except Exception as exc:
        return (f"Kickoff run failed for {client_id} {period}: "
                f"{type(exc).__name__}: {exc}")
    lines = [f"{client_id} {period} kickoff complete.",
             f"  codes: personal={codes.personal_code!r} "
             f"business={codes.business_code!r} "
             f"open={codes.open_status_code!r} "
             f"od-eligible={codes.eligible_stat_codes}",
             f"  reg-e opt-in={codes.rege_opt_in or 'NOT CONFIRMED'} "
             f"opt-out={codes.rege_opt_out or 'NOT CONFIRMED'}",
             f"  workbook: {result.report}"]
    if result.deck:
        lines.append(f"  deck: {result.deck}")
    elif deck:
        lines.append("  deck: NOT built -- the run declined it")

    # The warnings come back with the result. Telling a caller to read
    # warnings while returning none is worse than returning nothing.
    if result.warnings:
        lines.append("")
        lines.append(f"WARNINGS ({len(result.warnings)}) -- read these "
                     f"before quoting any number:")
        lines += [f"  - {w}" for w in result.warnings]
    else:
        lines.append("")
        lines.append("No warnings: the run accounted for its input.")
    return "\n".join(lines)
