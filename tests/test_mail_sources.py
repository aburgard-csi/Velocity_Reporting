"""The email-sourced inputs: MRPC/CashPlease from Bradford, ICS from Matt.

Outlook is not available in CI or on a machine with it closed, so `scan` takes an
injected message list and every rule below is exercised without COM.
"""
import datetime as _dt
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "scripts"))

import mail_sources as M                                     # noqa: E402

BRAD = "bradford.sanders@csiweb.com"
MATT = "matt.milliman@csiweb.com"


class Att:
    def __init__(self, name, size=1000):
        self.FileName, self.Size = name, size
        self.saved_to = None

    def SaveAsFile(self, path):
        with open(path, "wb") as fh:
            fh.write(b"x" * self.Size)
        self.saved_to = path


class Msg:
    def __init__(self, smtp, atts, subject="report", received=None):
        self.smtp = smtp
        self.Attachments = atts
        self.Subject = subject
        self.ReceivedTime = received or _dt.datetime(2026, 9, 9, 8, 0, 0)


# ------------------------------------------------------------------ classify
@pytest.mark.parametrize("name,kind,client,period", [
    ("1218-2026.09-MRPC-Ideal Credit Union-MRPCPM_Analysis_v10.xlsx",
     M.MRPCPM, "1218", "2026.09"),
    ("1676-2026.09-True Sky CU-Invitation Checking Workbook v1.7.1-DM.xlsx",
     M.ICS_WB, "1676", "2026.09"),
    ("260906_044753-MRPCEnrollmentSummary_v3_13.xlsx", M.WEEKLY, None, None),
    ("CashPleaseSummaryV1_260906_063545.xlsx", M.WEEKLY, None, None),
    ("Q3 numbers.xlsx", M.OTHER, None, None),
])
def test_attachment_classification(name, kind, client, period):
    assert M.classify_attachment(name) == (kind, client, period)


# ------------------------------------------------------------------ senders
def test_only_the_named_senders_are_read():
    """A display name is spoofable; the SMTP address is the only admission."""
    good = Msg(BRAD, [Att("1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx")])
    imposter = Msg("attacker@example.com",
                   [Att("1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx")])
    assert len(M.scan(messages=[good, imposter])) == 1


def test_sender_address_is_matched_case_insensitively():
    m = Msg(BRAD.upper(), [Att("1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx")])
    assert len(M.scan(messages=[m])) == 1


def test_a_sender_may_only_supply_their_own_kinds():
    """An ICS workbook from the MRPC sender is reported, never filed — otherwise
    SENDERS is decorative."""
    m = Msg(BRAD, [Att("1676-2026.09-X-Invitation Checking Workbook v1.7.1.xlsx")])
    rec = M.scan(messages=[m])[0]
    assert "not expected from" in rec["skip"]


def test_matt_supplies_ics_workbooks():
    m = Msg(MATT, [Att("1676-2026.09-X-Invitation Checking Workbook v1.7.1.xlsx")])
    rec = M.scan(messages=[m])[0]
    assert rec["kind"] == M.ICS_WB and "skip" not in rec


# ------------------------------------------------------------------ filtering
@pytest.mark.parametrize("name", ["notes.pdf", "chart.png", "~$book.xlsx"])
def test_non_workbook_attachments_are_ignored(name):
    assert M.scan(messages=[Msg(BRAD, [Att(name)])]) == []


def test_an_unrecognised_name_is_parked_not_dropped(tmp_path):
    rec = M.scan(messages=[Msg(BRAD, [Att("Q3 numbers.xlsx")])])[0]
    assert "convention" in rec["skip"]
    dest = M.destination(rec, str(tmp_path))
    assert dest.endswith(os.path.join("ARS & MRPC Reports", "Q3 numbers.xlsx"))


def test_the_same_attachment_twice_is_taken_once():
    a = Msg(BRAD, [Att("1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx")])
    b = Msg(BRAD, [Att("1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx")])
    assert len(M.scan(messages=[a, b])) == 1


# ------------------------------------------------------------------ destinations
def test_each_kind_lands_in_its_own_folder(tmp_path):
    msgs = [Msg(BRAD, [Att("1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx"),
                       Att("260906_044753-MRPCEnrollmentSummary_v3_13.xlsx")]),
            Msg(MATT, [Att("1676-2026.09-X-Invitation Checking Workbook v1.7.1.xlsx")])]
    dests = {r["name"]: d for r, d, _ in M.plan(M.scan(messages=msgs), str(tmp_path))}
    assert dests["1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx"].endswith(
        os.path.join("MRPC Analyses", "1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx"))
    assert dests["260906_044753-MRPCEnrollmentSummary_v3_13.xlsx"].endswith(
        os.path.join("Weekly Summaries", "260906_044753-MRPCEnrollmentSummary_v3_13.xlsx"))
    assert dests["1676-2026.09-X-Invitation Checking Workbook v1.7.1.xlsx"].endswith(
        os.path.join("ICS Workbooks",
                     "1676-2026.09-X-Invitation Checking Workbook v1.7.1.xlsx"))


# ------------------------------------------------------------------ saving
def test_it_saves_and_reports(tmp_path):
    msgs = [Msg(MATT, [Att("1676-2026.09-X-Invitation Checking Workbook v1.7.1.xlsx")])]
    planned = M.plan(M.scan(messages=msgs), str(tmp_path))
    out = M.save(planned)
    assert out[0][2] == "saved"
    assert os.path.exists(out[0][1]) and not os.path.exists(out[0][1] + ".part")


def test_a_local_copy_written_after_the_mail_is_not_clobbered(tmp_path):
    """The recalculated-workbook guard, same as the share copier: a local file
    modified after the message arrived is a deliberate change."""
    name = "1676-2026.09-X-Invitation Checking Workbook v1.7.1.xlsx"
    dest_dir = tmp_path / "ICS Workbooks"
    dest_dir.mkdir(parents=True)
    (dest_dir / name).write_bytes(b"recalculated in Excel")
    msgs = [Msg(MATT, [Att(name)],
                received=_dt.datetime.now() - _dt.timedelta(days=2))]
    _rec, _dest, why = M.plan(M.scan(messages=msgs), str(tmp_path))[0]
    assert "local copy is newer" in why
    assert (dest_dir / name).read_bytes() == b"recalculated in Excel"


def test_an_identical_file_already_held_is_not_refetched(tmp_path):
    name = "1218-2026.09-MRPC-X-MRPCPM_Analysis_v10.xlsx"
    d = tmp_path / "MRPC Analyses"
    d.mkdir(parents=True)
    (d / name).write_bytes(b"x" * 1000)
    os.utime(d / name, (0, 0))                 # older than the message
    planned = M.plan(M.scan(messages=[Msg(BRAD, [Att(name, size=1000)])]), str(tmp_path))
    assert planned[0][2] == "already held"


def test_skipped_records_are_not_written(tmp_path):
    planned = M.plan(M.scan(messages=[Msg(BRAD, [Att("Q3 numbers.xlsx")])]), str(tmp_path))
    out = M.save(planned)
    assert out[0][2].startswith("skipped")
    assert not os.path.exists(out[0][1])


def test_available_reports_rather_than_raises():
    ok, why = M.available()
    assert isinstance(ok, bool) and isinstance(why, str) and why


# ------------------------------------------------------------------ newest only
def test_only_the_newest_weekly_of_each_family_is_taken():
    """A mailbox holds every weekly ever sent; the pipeline reads one."""
    names = ["260517_082159-MRPCEnrollmentSummary_v3_13.xlsx",
             "260906_044753-MRPCEnrollmentSummary_v3_13.xlsx",
             "CashPleaseSummaryV1_260517_091848.xlsx",
             "CashPleaseSummaryV1_260906_063545.xlsx"]
    got = sorted(r["name"] for r in M.scan(messages=[Msg(BRAD, [Att(n) for n in names])]))
    assert got == ["260906_044753-MRPCEnrollmentSummary_v3_13.xlsx",
                   "CashPleaseSummaryV1_260906_063545.xlsx"]


def test_only_the_newest_period_per_client_is_taken():
    names = ["1676-2026.05-X-Invitation Checking Workbook v1.7.1.xlsx",
             "1676-2026.07-X-Invitation Checking Workbook v1.7.1.xlsx",
             "1539-2026.05-X-Invitation Checking Workbook v1.7.1.xlsx"]
    got = sorted(r["name"] for r in M.scan(messages=[Msg(MATT, [Att(n) for n in names])]))
    assert got == ["1539-2026.05-X-Invitation Checking Workbook v1.7.1.xlsx",
                   "1676-2026.07-X-Invitation Checking Workbook v1.7.1.xlsx"]


def test_an_older_version_than_inputs_already_holds_is_refused(tmp_path):
    """The stale-input failure this pipeline keeps guarding against, on the mail
    path: Archive holds 2026.05 workbooks long after 2026.07 landed."""
    d = tmp_path / "ICS Workbooks"
    d.mkdir(parents=True)
    (d / "1676-2026.07-X-Invitation Checking Workbook v1.7.1.xlsx").write_bytes(b"newer")
    msgs = [Msg(MATT, [Att("1676-2026.05-X-Invitation Checking Workbook v1.7.1.xlsx")])]
    _rec, _dest, why = M.plan(M.scan(messages=msgs), str(tmp_path))[0]
    assert "already holds a newer one (2026.07)" in why


def test_unclassifiable_attachments_are_all_reported_not_deduped():
    msgs = [Msg(BRAD, [Att("Q3 numbers.xlsx"), Att("Q4 numbers.xlsx")])]
    assert len(M.scan(messages=msgs)) == 2
