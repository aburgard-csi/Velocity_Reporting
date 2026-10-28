"""The ILS kickoff run and its CLI (build/ils_pipeline/kickoff/run.py, kickoff_input.run_kickoff).

v5's run tests (v5 tests/test_ils_kickoff.py at 7ba1e63, the two held back from the loader stage),
with the import rewritten, plus the RPE side: the two-step path computes nothing without codes, the
workbook lands in Build Artifacts and never in Outputs, and the CLI still asks at a terminal.

Every test runs under kickoff/_v5/compat.legacy_strings(), as the entry points do.
"""
import runpy
import sys

import pytest
from openpyxl import load_workbook

from ils_pipeline import kickoff_input
from ils_pipeline.kickoff.core import io


@pytest.fixture(autouse=True)
def _v5_pandas():
    """v5's code under the pandas 2 string semantics it was written for (kickoff/_v5/compat.py)."""
    from ils_pipeline.kickoff._v5.compat import legacy_strings
    with legacy_strings():
        yield


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    return tmp_path


# ---- v5's tests -----------------------------------------------------------

# ---- 7. a run that only prints cannot be called by a tool ---------------
#
# ils_run_kickoff returned the workbook path and the sentence "Read the run's
# WARNINGS before quoting any number from it" -- while returning no warnings,
# because run() printed them. A tool that withholds the warnings it tells you
# to read is worse than one that says nothing. It also lost the deck path.

def test_the_run_returns_what_it_prints(tmp_path, monkeypatch):
    from ils_pipeline.kickoff import run as runner
    import inspect
    src = inspect.getsource(runner.run)
    assert "return " in src
    sig = inspect.signature(runner.run)
    assert "deck" in sig.parameters


def test_the_result_carries_paths_warnings_and_codes():
    from ils_pipeline.kickoff.run import RunResult
    r = RunResult(report=None, deck=None, warnings=["a"], codes=io.CodeConfig())
    assert r.warnings == ["a"] and r.codes.personal_code == "P"
    # still usable where a path was expected before
    assert str(r) == "None"


# ---- RPE side ---------------------------------------------------------------

TABS = ["Account Status Analysis", "Product Code Distribution", "Account Type Analysis",
        "Personal Deposit Analysis", "Business Deposit Analysis", "NSF Stratification",
        "NSF Stratification (Business)", "NSF Pay Ratio", "NSF Pay Ratio (Business)",
        "NSF Strat w Deposits", "NSF Strat w Deposits (Biz)", "OD Status Stratification",
        "OD Status Stratification (Biz)", "Reg E Summary", "Reg E by OD Eligibility",
        "Reg E by OD Eligibility (Biz)", "Historical Reg E", "OD Limit Stratification",
        "OD Limit Stratification (Biz)"]


def _extract(root, client_id="1842", name="1842_OneTimeData_20261001.csv"):
    """Twenty accounts: personal and business, open and closed, every code column filled."""
    rows = ["AcctNo,Account Status,Business Flag,Stat Code,Product Code,Reg E Flag,Total Items,"
            "Paid Items,Returned Items,OD Limit,Deposit Count,Deposit Amount,Swipes"]
    for i in range(20):
        rows.append(",".join(str(v) for v in [
            1000 + i, "C" if i % 7 == 6 else "O", "B" if i % 4 == 3 else "P",
            "ODP Account" if i % 3 else "No OD", f"0{i % 3}", "Y" if i % 2 else "N",
            i * 3, i * 2, i, 500 * (1 + i % 3), i % 9, 125.0 * i, i * 4]))
    d = root / "Inputs" / "ILS Kickoff" / client_id
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("\n".join(rows) + "\n", encoding="utf-8")
    return d / name


def _files(path):
    return sorted(p for p in path.rglob("*") if p.is_file())


def test_without_codes_the_run_returns_the_field_summary_and_writes_nothing(root):
    _extract(root)
    text = kickoff_input.run_kickoff("1842", "2026-10")
    assert "step 1 of 2" in text and "nothing has been computed" in text
    assert "Business Flag: 'P' (15), 'B' (5)" in text
    assert _files(root / "Build Artifacts") == [] and _files(root / "Outputs") == []


def test_with_codes_the_workbook_lands_in_build_artifacts_never_outputs(root):
    _extract(root)
    text = kickoff_input.run_kickoff("1842", "2026-10", personal_code="P", business_code="B",
                                     open_code="O", eligible_stat_codes="ODP Account",
                                     rege_opt_in="Y")
    assert "kickoff complete" in text, text
    written = _files(root / "Build Artifacts")
    assert len(written) == 1
    assert written[0].parent == root / "Build Artifacts" / "ils" / "kickoff" / "1842" / "2026-10"
    assert written[0].name.startswith("1842 - ILS Kickoff Report Data-")
    assert _files(root / "Outputs") == []
    assert load_workbook(written[0]).sheetnames == ["Report Info"] + TABS


def test_the_default_output_folder_needs_the_data_root(monkeypatch):
    monkeypatch.delenv("RPE_DATA_ROOT", raising=False)
    import rpe_env
    monkeypatch.setattr(rpe_env, "_load_dotenv", lambda: {})
    with pytest.raises(SystemExit):
        kickoff_input.output_dir("1842", "2026-10")


def test_a_missing_extract_is_named_in_the_rpe_folder(root):
    text = kickoff_input.run_kickoff("9999", "2026-10", personal_code="P")
    assert "No kickoff extract for 9999" in text and "Inputs/ILS Kickoff/9999/" in text


def _cli(monkeypatch, *argv, tty=False, answers=()):
    monkeypatch.setattr(sys, "argv", ["run", *argv])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: tty, raising=False)
    asked = []
    replies = iter(answers)

    def fake_input(prompt=""):
        asked.append(prompt)
        return next(replies, "")
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.delitem(sys.modules, "ils_pipeline.kickoff.run", raising=False)   # as `python -m` finds it
    runpy.run_module("ils_pipeline.kickoff.run", run_name="__main__")
    return asked


def test_at_a_terminal_the_cli_asks_for_the_codes(root, monkeypatch, capsys):
    _extract(root)
    asked = _cli(monkeypatch, "1842", "2026-10", tty=True, answers=["P", "B", "O", "ODP Account", "Y"])
    assert any("Personal account code" in q for q in asked)
    assert any("Reg E Flag value(s) meaning OPTED IN" in q for q in asked)
    assert "reg-e opt-in=['Y']" in capsys.readouterr().out
    assert len(_files(root / "Build Artifacts" / "ils" / "kickoff" / "1842" / "2026-10")) == 1


def test_a_code_flag_skips_the_prompt(root, monkeypatch):
    _extract(root)
    asked = _cli(monkeypatch, "1842", "2026-10", "--personal-code", "P", tty=True)
    assert asked == []
    assert _files(root / "Outputs") == []
    assert len(_files(root / "Build Artifacts" / "ils" / "kickoff" / "1842" / "2026-10")) == 1


def test_the_run_file_is_v5_s_and_names_its_source():
    import pathlib
    from ils_pipeline.kickoff import run as runner
    first = pathlib.Path(runner.__file__).read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("# Ported from v5 02-Scripts/ils/kickoff_analysis/run.py at 7ba1e63.")
    src = pathlib.Path(runner.__file__).read_text(encoding="utf-8")
    assert "ars_pipeline" not in src and "from ti" not in src and "import ti" not in src


def test_with_the_deck_both_files_land_in_build_artifacts(root):
    _extract(root)
    text = kickoff_input.run_kickoff("1842", "2026-10", personal_code="P", business_code="B",
                                     open_code="O", eligible_stat_codes="ODP Account",
                                     rege_opt_in="Y", deck=True)
    assert "  deck: " in text and "NOT built" not in text, text
    out = root / "Build Artifacts" / "ils" / "kickoff" / "1842" / "2026-10"
    names = sorted(p.name for p in _files(root / "Build Artifacts"))
    assert len(names) == 2 and "1842 - ILS Kickoff 2026-10.pptx" in names
    assert (out / "1842 - ILS Kickoff 2026-10.pptx").is_file()
    assert _files(root / "Outputs") == []


def test_the_template_carries_the_layout_the_deck_asks_for():
    """The kickoff deck adds every slide on layout index LAYOUT_BLANK (deckkit.open_template, build._divider):
    in v5's template that is BLANK, and RPE's templates/ars_template.pptx, read only, must say the same."""
    from pptx import Presentation
    from ils_pipeline.kickoff._v5 import deckkit as dk
    from ils_pipeline.kickoff._v5.core import layout
    import rpe_env
    assert layout.TEMPLATE == rpe_env.REPO_ROOT / "templates" / "ars_template.pptx"
    assert layout.LOGO.is_file()
    names = [lay.name for lay in Presentation(str(layout.TEMPLATE)).slide_layouts]
    assert names[dk.LAYOUT_BLANK] == "BLANK"
