"""Two small tools the merge and roster skills lean on (Aaron, 2026-10-28)."""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "build"))
import changelog_merge as CM  # noqa: E402
import roster_candidate as RC  # noqa: E402

CONFLICT = (
    "# Change log\n\nintro\n\n"
    "<<<<<<< HEAD\n### 2026-10-28 — Ours\n\nSummary: ours.\n\nbody\n"
    "=======\n### 2026-10-27 — Theirs\n\nSummary: theirs.\n\nbody\n"
    ">>>>>>> origin/main\n"
    "### 2026-10-26 — Older\n\nSummary: older.\n")


def test_a_changelog_conflict_keeps_both_entries_with_a_blank_line_between():
    out = CM.resolve(CONFLICT)
    assert "<<<<<<<" not in out and "=======" not in out and ">>>>>>>" not in out
    heads = [h for h, _ in CM.entries(out)]
    assert heads == ["2026-10-28 — Ours", "2026-10-27 — Theirs", "2026-10-26 — Older"]
    for m in re.finditer(r"(?m)^### ", out):
        before = out[:m.start()]
        assert before.endswith("\n\n"), out[max(0, m.start() - 20):m.start() + 10]   # a blank line before every heading


def test_crlf_files_keep_their_line_endings():
    out = CM.resolve(CONFLICT.replace("\n", "\r\n"))
    assert "\r\n" in out and "\n" not in out.replace("\r\n", "")
    assert "\r\r\n" not in out and "\n\n\n" not in out.replace("\r\n", "\n").replace("\n\n\n\n", "")


def test_a_file_with_no_conflict_or_a_broken_one_is_refused():
    import pytest
    with pytest.raises(ValueError):
        CM.resolve("### 2026-10-28 — Clean\n\nSummary: x.\n")
    with pytest.raises(ValueError):
        CM.resolve("<<<<<<< HEAD\nours\n=======\ntheirs\n")


def test_an_entry_without_a_summary_line_is_reported():
    assert CM.entries("### a\n\nno summary here\n\n### b\n\nSummary: ok\n") == [("a", False), ("b", True)]


def test_the_tool_edits_the_file_in_place(tmp_path, capsys):
    f = tmp_path / "CHANGELOG.md"
    f.write_text(CONFLICT, encoding="utf-8", newline="")
    assert CM.main([str(f)]) == 0
    assert "<<<<<<<" not in f.read_text(encoding="utf-8")
    assert CM.main([str(f)]) == 1                         # now there is nothing to resolve: refused, unchanged


def test_programs_read_the_csm_list_words_in_section_order():
    row = {"rpe_programs": "CashPlease; ARS", "products": "ARS; CashPlease; ILS; Professional Services"}
    assert RC.programs(row) == ["ARS", "CP"]
    assert RC.programs({"products": "ICS; ILS"}) == ["ICS"]
    assert RC.programs({}) == []


def test_the_main_row_leaves_cashplease_to_its_own_table():
    assert RC.main_row("1585", "First Community Bank of the Heartland", "MM", ["ARS", "CP"]) == \
        "| 1585 | First Community Bank of the Heartland | MM | yes | — | — | ARS |"
    assert RC.main_row("1075", "Austin Bank", "SM", ["ARS", "ICS", "MRPC"]).endswith("| yes | yes | yes | ARS-ICS-MRPC |")


def test_the_cashplease_row_says_how_the_slides_ship():
    assert RC.cp_row("1585", "X", "James Gilmore", 1324, ["ARS", "CP"]) == \
        "| 1585 | X | James Gilmore | yes | 1324 | **ARS-CP** section |  |"
    assert "standalone deck" in RC.cp_row("1131", "Y", "Aaron Burgard", 10540, ["CP"])
    assert RC.cp_row("1038", "Z", "Aaron Burgard", None, ["ARS"]) is None
    assert "| ? |" in RC.cp_row("1828", "W", "Aaron Burgard", None, ["ARS", "CP"])


def test_the_tools_reject_bad_input(capsys):
    assert RC.main(["12x"]) == 2 and RC.main([]) == 2


def test_the_two_skills_name_tools_that_exist_and_keep_their_guards():
    for name, must in (("merge-and-release", ("Never rebase", "changelog_merge.py", "release_launcher.ps1", "empty")),
                       ("add-client-to-roster", ("roster_candidate.py", "ILS is not tracked", "release"))):
        text = open(os.path.join(REPO, ".claude", "skills", name, "SKILL.md"), encoding="utf-8").read()
        head = re.match(r"---\nname: ([\w-]+)\ndescription: (.+)\n---\n", text)
        assert head and head.group(1) == name
        for path in re.findall(r"scripts/\w+\.(?:py|ps1)", text):
            assert os.path.isfile(os.path.join(REPO, path)), (name, path)
        for phrase in must:
            assert phrase in text, (name, phrase)

