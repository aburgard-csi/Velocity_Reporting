"""ics_local_sheet — an ICS client sheet built from local files when there is no VIP sheet.

1776 CoastHills CU has no VIP ICS sheet and none will be pulled (Aaron, 2026-09-16); the
CSM landed a detailed referral export, a current ICS workbook, a Charts workbook and a
direct-mail list instead. These tests pin what the sheet may and may not claim:

  * counts only, and only for months the referral file covers;
  * anything the files cannot supply is ABSENT (never 0, never a guessed goal);
  * workbook sections only for the deck's own period;
  * the sources are named, so the slide notes do not say VIP;
  * build_month falls back to it ONLY when the VIP sheet is missing.

Every file here is synthetic: invented branch names, "Member N" holders, no client data.
"""
import datetime as dt
import json
import os
import sys

import openpyxl
import pytest

import rpe_env as R
import ics_local_sheet as L

CID, NAME, PERIOD = "9901", "Sample Harbor CU", "2026.09"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(REPO, "validation") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "validation"))


# ------------------------------------------------------------------ synthetic inputs
def _months(first=(2025, 7), last=(2026, 8)):
    y, m, out = first[0], first[1], []
    while (y, m) <= last:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def write_referrals(path, months=None, extra=()):
    """Month i carries i+1 referrals, branches 010/020/030 in turn. Every other date is
    written as TEXT (m/d/yyyy), as the real exports mix both. One undated row and one
    duplicate certificate id are added so both flags are exercised."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Referrer Name", "Issue Date", "Referral Code", "Purchase Manager", "Branch",
               "Account Holder", "MRDB Account Hash", "Cert ID"])
    n = 0
    for i, (y, m) in enumerate(months or _months()):
        for k in range(i + 1):
            n += 1
            d = dt.datetime(y, m, 1 + (k % 27))
            ws.append([f"Member {n}", d if n % 2 else f"{d.month}/{d.day}/{d.year}", f"C{n}",
                       "Staff A", ["010", "020", "030"][k % 3], f"Holder {n}", f"H{n}", f"CERT{n}"])
    for d, br in extra:
        n += 1
        ws.append([f"Member {n}", d, f"C{n}", "Staff A", br, f"Holder {n}", f"H{n}", f"CERT{n}"])
    ws.append(["Member X", None, "CX", "Staff A", "010", "Holder X", "HX", "CERTX"])
    ws.append(["Member 1", dt.datetime(2026, 8, 3), "C1", "Staff A", "010", "Holder 1", "H1", "CERT1"])
    wb.save(path)
    return n


def write_charts(path, total_row=5, tab="Goals"):
    wb = openpyxl.Workbook()
    g = wb.active
    g.title = tab
    g.append([])
    g.append([None, NAME])
    g.append([None, "Branch #", "Branch Name", "Monthly Goal"])
    g.append([None, 10, "Harborview", 2])
    g.append([None, 20, "Hilltop", 3])
    g.append([None, None, "Total", total_row])
    ms = wb.create_sheet("Mystery Shop Results")
    ms.append([None, "Branch"])
    ms.append([10, "Harborview"])
    ms.append([20, "Hilltop"])
    wb.save(path)


def write_direct_mail(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(3):
        ws.append([])
    ws.append([None, None, None, "ICS Direct Mail"])
    ws.append([None, None, None, "Period: PTD"])
    ws.append([None, None, None, "Report Date: 9/9/2026"])
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append([None, "# of Accounts", "Branch Number", None, "Name Line 1", "Account Mask", "Open Date"])
    ws.append([None, 1, 10, None, "Holder A", "****0001", dt.datetime(2026, 7, 2)])
    ws.append([None, 2, 20, None, "Holder B", "****0002", "7/15/2026"])
    ws.append([None, 3, 20, None, "Holder C", "****0003", "8/20/2026"])
    wb.save(path)


def write_workbook(path, months=9, branch_tab=True, generated="9/9/2026 8:00:00 AM"):
    """The minimum `ics_workbook_extract.extract` reads, with invented figures: accounts opened
    10, 11, ... per month from Dec 25; the Cumulative row 10, 20, ... (so it disagrees with the
    monthly sum on purpose); plus the branch tab the workbook-only shape reads."""
    wb = openpyxl.Workbook()
    md = wb.active
    md.title = "Monthly Detail"
    md.cell(6, 2, "August 2026 Data")
    cols = list(range(4, 4 + months))
    first = (2025, 12)
    for j, c in enumerate(cols):
        y, m = first[0] + (first[1] - 1 + j) // 12, (first[1] - 1 + j) % 12 + 1
        md.cell(14, c, dt.datetime(y, m, 1))
    rows = {15: ("Accounts Opened via Invitation Checking System", 10),
            16: ("Cumulative From Invitation Checking System", None),
            17: ("Average Balance per Account", 900),
            18: ("Incremental Revenue", None),
            19: ("Spread on Deposits", 40), 20: ("Interchange Income", 50),
            21: ("NSF/OD Fees", 30), 22: ("Other Fees", 5),
            23: ("Account Profit Contribution", 125),
            25: ("Total Expense", 60), 27: ("Profit Contribution to Date", 65)}
    for r, (label, v) in rows.items():
        md.cell(r, 2, label)
        for j, c in enumerate(cols):
            if label.startswith("Cumulative"):
                md.cell(r, c, 10 * (j + 1))
            elif v is not None:
                md.cell(r, c, v + j)
    va = wb.create_sheet("Value of ICS Accts")
    for i, (label, v) in enumerate([("Actual Annual Profit Contribution", 150.0),
                                    ("ICS Cost per Acquired Account", 250),
                                    ("Average Life of Account In Years", 6.9),
                                    ("Life of ICS Accounts", 8.0),
                                    ("% Added Life of ICS Account", 0.16),
                                    ("Return on Investment", 4.0),
                                    ("Accounts Opened via Invitation", 10 * months)], start=3):
        va.cell(i, 2, label)
        va.cell(i, 3, v)
    lo = wb.create_sheet("Life of Account Data")
    lo.cell(12, 1, "Last 12 Months")
    for j, v in enumerate([400, 40, 0.1, 100, 5, 0.05], start=2):
        lo.cell(12, j, v)
    if branch_tab:
        # The real tab: a banner, an all-DDA table, then the Invitation Checking table the
        # workbook-only shape reads (Month and Year to Date "Accounts Opened" columns), a Total
        # row, and the "Report Generated" stamp.
        bt = wb.create_sheet("DDA Openings by Branch")
        bt.cell(2, 2, "Invitation Checking System"); bt.cell(4, 2, NAME)
        bt.cell(5, 2, "Openings by Branch"); bt.cell(6, 2, "August 2026 Data")
        bt.cell(8, 2, "All DDA Openings\nby Branch"); bt.cell(8, 3, "Month"); bt.cell(8, 8, "Year to Date")
        bt.cell(9, 3, "Accounts Opened"); bt.cell(9, 8, "Accounts Opened"); bt.cell(10, 2, "Branch")
        bt.cell(11, 2, 10); bt.cell(11, 3, 40); bt.cell(11, 8, 300)
        bt.cell(12, 2, 20); bt.cell(12, 3, 30); bt.cell(12, 8, 250)
        bt.cell(13, 2, "Total"); bt.cell(13, 3, 70); bt.cell(13, 8, 550)
        bt.cell(16, 2, "Invitation Checking\nDDA Openings\nby Branch"); bt.cell(16, 3, "Month"); bt.cell(16, 8, "Year to Date")
        for c in (3, 8):
            bt.cell(17, c, "Accounts Opened")
        bt.cell(17, 4, "% of Total Opened"); bt.cell(17, 9, "% of Total Opened"); bt.cell(18, 2, "Branch")
        bt.cell(19, 3, 0); bt.cell(19, 8, 0)                 # the blank-branch zero row the real tabs carry
        bt.cell(20, 2, 10); bt.cell(20, 3, 10); bt.cell(20, 8, 60)
        bt.cell(21, 2, 20); bt.cell(21, 3, 8); bt.cell(21, 8, 56)
        bt.cell(22, 2, "Total"); bt.cell(22, 3, 18); bt.cell(22, 8, 116)
        bt.cell(24, 2, f"Report Generated: {generated}")
    wb.save(path)


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A data root with no VIP store and the kind folders the local sheet reads."""
    inputs = tmp_path / "Inputs"
    for kind in (L.REFERRAL_KIND, L.DIRECT_MAIL_KIND, L.CHARTS_KIND, "ICS workbook"):
        (inputs / R.INPUT_KIND_DIRS[kind]).mkdir(parents=True)
    arts = tmp_path / "Build Artifacts"
    arts.mkdir()
    monkeypatch.setattr(R, "inputs", lambda: inputs)
    monkeypatch.setattr(R, "data_root", lambda: tmp_path)
    monkeypatch.setattr(R, "build_artifacts", lambda: arts)
    monkeypatch.setattr(R, "client_csm", lambda cid: "Some Other CSM")
    # The Contact Us card is looked up for every ICS deck (rpe_env.csm_contact): a synthetic row.
    (tmp_path / R.CSM_CONTACTS_NAME).write_text(
        "csm,title,company,address,office,cell,email,source\n"
        "Some Other CSM,Client Service Manager,CSI,,,,Some.Other@example.com,test\n"
        f"{R.ICS_PROGRAM_CONTACT},ICS Program Manager,CSI,,,,program.contact@example.com,test\n", encoding="utf-8")
    monkeypatch.delenv("RPE_CSM_CONTACTS", raising=False)

    def no_vip(arg, program):
        raise SystemExit("no VIP sheet in this test")
    monkeypatch.setattr(R, "resolve_client_json", no_vip)
    return inputs


def kind_dir(inputs, kind):
    return inputs / R.INPUT_KIND_DIRS[kind]


def referral_file(inputs):
    return kind_dir(inputs, L.REFERRAL_KIND) / f"{CID}_ics_detailed referral_v9.xlsx"


def workbook_file(inputs, period):
    return kind_dir(inputs, "ICS workbook") / f"{CID}-{period}-{NAME}-Invitation Checking Workbook v1.7.1.xlsx"


def charts_file(inputs):
    return kind_dir(inputs, L.CHARTS_KIND) / f"{NAME} ICS Charts 2026.xlsx"


def dm_file(inputs):
    return kind_dir(inputs, L.DIRECT_MAIL_KIND) / f"{CID}-2026.08-ICS-{NAME}-Direct Mail New Accounts Opened PTD.xlsx"


# ------------------------------------------------------------------ available()
def test_the_local_kinds_are_never_scanned_by_the_watcher():
    """Hand-landed member-level files: the copier/pruner must not touch them."""
    for kind in (L.REFERRAL_KIND, L.DIRECT_MAIL_KIND):
        assert kind in R.INPUT_KIND_DIRS and kind in R.NOT_SCANNED_KINDS


def test_nothing_on_file_cannot_build(root):
    av = L.available(CID, PERIOD, NAME)
    assert av["ok"] is False and av["vip"] is False and av["shape"] is None
    assert av["referrals"] is None and av["reason"]


def test_the_periods_workbook_alone_builds_the_workbook_only_shape(root):
    """Aaron, 2026-10-13 (1195 KEMBA CU): "Add a workbook-only ICS shape that draws the opening
    counts from Monthly Detail and the branch tab, labelled as accounts opened"."""
    write_workbook(workbook_file(root, PERIOD))
    av = L.available(CID, PERIOD, NAME)
    assert av["ok"] is True and av["shape"] == L.WORKBOOK_ONLY and av["workbook_period"] == PERIOD
    assert av["referrals"] is None and av["vip"] is False
    assert "accounts opened" in av["reason"] and "not as referrals" in av["reason"]


def test_an_older_workbook_alone_cannot_build(root):
    """Stale financials and no referral figures to fall back to: nothing to show."""
    write_workbook(workbook_file(root, "2026.08"))
    av = L.available(CID, PERIOD, NAME)
    assert av["ok"] is False and av["shape"] is None and av["workbook_period"] == "2026.08"
    assert f"only a {PERIOD} workbook" in av["reason"]


def test_referrals_without_a_workbook_are_referrals_only(root):
    write_referrals(referral_file(root))
    av = L.available(CID, PERIOD, NAME)
    assert av["ok"] and av["shape"] == "referrals-only" and av["workbook"] is None
    assert av["referrals"].endswith("referral_v9.xlsx")


def test_an_older_workbook_is_referrals_only(root):
    write_referrals(referral_file(root))
    write_workbook(workbook_file(root, "2026.08"))
    av = L.available(CID, PERIOD, NAME)
    assert av["shape"] == "referrals-only" and av["workbook_period"] == "2026.08"


def test_a_current_workbook_is_full(root):
    write_referrals(referral_file(root))
    write_workbook(workbook_file(root, "2026.08"))
    write_workbook(workbook_file(root, PERIOD))
    write_charts(charts_file(root))
    write_direct_mail(dm_file(root))
    av = L.available(CID, PERIOD, NAME)
    assert av["shape"] == "full" and av["workbook_period"] == PERIOD
    assert av["charts"] and av["direct_mail"]


def test_vip_counts_as_available(root, monkeypatch):
    monkeypatch.setattr(R, "resolve_client_json", lambda a, p: root / "vip.json")
    av = L.available(CID, PERIOD, NAME)
    assert av["ok"] and av["vip"] and av["referrals"] is None


def test_client_id_prefix_is_exact(root):
    write_referrals(kind_dir(root, L.REFERRAL_KIND) / f"{CID}0_ics_detailed referral_v9.xlsx")
    assert L.available(CID, PERIOD, NAME)["referrals"] is None


# ------------------------------------------------------------------ the sheet
def _sheet(root, tmp_path):
    out = tmp_path / "stage" / CID / "ics_local_sheet.json"
    L.build_sheet(CID, NAME, PERIOD, str(out), today=dt.date(2026, 9, 16))
    return json.load(open(out, encoding="utf-8"))


def test_referral_counts(root, tmp_path):
    n = write_referrals(referral_file(root))
    write_charts(charts_file(root))
    d = _sheet(root, tmp_path)
    rf = d["referrals"]
    assert rf["program_to_date"] == n == sum(range(1, 15))
    # 2026 is months 7..14 of the fixture (Jan..Aug 26): 7+8+...+14
    assert rf["year_to_date"] == sum(range(7, 15))
    assert rf["previous_month"] == {"label": "August", "value": 14}
    assert rf["trend"]["months"][0] == "Aug 25" and rf["trend"]["months"][-1] == "Aug 26"
    assert len(rf["trend"]["months"]) == L.TREND_MONTHS
    assert rf["trend"]["referrals"] == list(range(2, 15))
    assert rf["trend"]["partial_last"] is False and rf["latest_data_month"] == "2026-08"
    assert rf["monthly_goal"] == 5 and rf["prev_month_vs_goal_pct"] == round(14 / 5 * 100)
    br = {b["number"]: b for b in rf["by_branch"]["branches"]}
    assert br["10"]["name"] == "Harborview" and br["10"]["goal"] == 24     # monthly 2 x 12
    assert "goal" not in br["30"] and br["30"]["name"] == "Branch 30"
    assert sum(b["referrals"] for b in br.values()) == rf["year_to_date"]
    flags = " ".join(d["_flags"])
    assert "30" in flags and "no readable Issue Date" in flags and "duplicate" in flags


def test_absent_sections_are_omitted_not_zeroed(root, tmp_path):
    write_referrals(referral_file(root))                 # no charts, no workbook
    d = _sheet(root, tmp_path)
    rf = d["referrals"]
    for k in ("monthly_goal", "prev_month_vs_goal_pct", "month_to_date"):
        assert k not in rf
    assert all("goal" not in b for b in rf["by_branch"]["branches"])
    for k in ("performance", "revenue", "financial_summary", "monthly_detail", "benchmark",
              "contacts", "mystery_shop", "referred_by_product"):
        assert k not in d
    om = d["_provenance"]["omitted"]
    assert "goals" in om and "mystery_shop" in om and "referrals.month_to_date" in om
    assert "workbook" not in d["meta"]


def test_a_month_in_progress_is_partial(root, tmp_path):
    write_referrals(referral_file(root), extra=[(dt.datetime(2026, 9, 4), "010"),
                                                (dt.datetime(2026, 9, 9), "020"),
                                                (dt.datetime(2026, 10, 1), "010")])
    d = _sheet(root, tmp_path)
    rf = d["referrals"]
    assert rf["month_to_date"] == {"label": "September", "value": 2, "partial": True}
    assert rf["trend"]["partial_last"] is True and rf["trend"]["months"][-1] == "Sep 26"
    assert rf["previous_month"]["value"] == 14 and rf["latest_data_month"] == "2026-09"
    assert d["meta"]["data_through"] == "2026-09-09"          # the October row is left out
    assert any("after 2026.09" in f for f in d["_flags"])


def test_stale_referrals_stop(root, tmp_path):
    write_referrals(referral_file(root), months=_months(last=(2026, 6)))
    with pytest.raises(SystemExit, match="before 2026-08"):
        _sheet(root, tmp_path)


def test_goal_total_row_disagreement_is_flagged(root, tmp_path):
    write_referrals(referral_file(root))
    write_charts(charts_file(root), total_row=4)
    d = _sheet(root, tmp_path)
    assert d["referrals"]["monthly_goal"] == 5
    assert any("Total row says 4" in f for f in d["_flags"])


def test_full_shape_and_provenance(root, tmp_path, monkeypatch):
    write_referrals(referral_file(root))
    write_charts(charts_file(root))
    write_direct_mail(dm_file(root))
    write_workbook(workbook_file(root, PERIOD))
    d = _sheet(root, tmp_path)
    for k in ("performance", "revenue", "financial_summary", "monthly_detail", "benchmark"):
        assert d[k]
    m = d["meta"]
    assert m["source_kind"] == "local" and m["period"] == PERIOD and m["client_id"] == CID
    assert m["workbook"] == workbook_file(root, PERIOD).name and m["workbook_month"] == "August 2026"
    assert m["program_start"] == "2025-12" and m["data_through"] == "2026-08-14"
    assert referral_file(root).name in m["referral_source"] and "not VIP" in m["referral_source"]
    assert charts_file(root).name in m["referral_source"]
    assert "vip_source" not in m
    prov = d["_provenance"]
    assert prov["vip"] is False and prov["shape"] == "full"
    roles = {f["role"]: f for f in prov["files"]}
    assert roles["referrals"]["sheet"] and roles["referrals"]["file_date"]
    assert roles["workbook"]["workbook_period"] == PERIOD
    # direct mail is recorded, never added to referrals
    dm = d["direct_mail"]
    assert dm["accounts_opened_ptd"] == 3 and "_rendered" not in dm
    assert dm["source_file"] == dm_file(root).name and dm["source_folder"]
    assert dm["report_date"] == "2026-09-09"
    assert d["referrals"]["program_to_date"] == sum(range(1, 15))
    # no contact card in the sheet: build_ics_gen looks up the managing CSM itself
    assert "contacts" not in d and "contacts" not in prov["omitted"]


def test_legacy_xls_is_read_from_a_converted_copy(root, tmp_path, monkeypatch):
    """No xlrd in the .venv: the .xls is converted as a COPY in Build Artifacts."""
    src = kind_dir(root, L.REFERRAL_KIND) / f"{CID}_ics_detailed referral_v9.xls"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy placeholder")
    before = src.read_bytes()
    conv = R.build_artifacts() / L.WORK_DIRNAME / CID / "converted.xlsx"
    conv.parent.mkdir(parents=True)
    write_referrals(conv)
    seen = []
    monkeypatch.setitem(sys.modules, "xlrd", None)          # import xlrd -> ImportError
    monkeypatch.setattr(L, "_convert_xls_with_excel", lambda p, cid: seen.append(p) or str(conv))
    d = _sheet(root, tmp_path)
    assert seen and seen[0].endswith(".xls")
    assert "Build Artifacts/" in d["_provenance"]["files"][0]["read_via"]
    assert d["referrals"]["program_to_date"] == sum(range(1, 15))
    assert src.read_bytes() == before


# ------------------------------------------------------------------ build_month fallback
@pytest.fixture
def bm(root, tmp_path, monkeypatch):
    import build_month as BM
    calls = []
    monkeypatch.setattr(R, "sweep_temp", lambda *a, **k: (0, 0))
    monkeypatch.setattr(BM, "run", lambda cmd, log, stdout_to=None: calls.append([str(c) for c in cmd]) or 0)
    built = []

    def fake_build(cid, name, period, out):
        built.append(out)
        json.dump({"meta": {}, "_flags": ["a flag"]}, open(out, "w", encoding="utf-8"))
        return out
    monkeypatch.setattr(BM.LOCAL_ICS, "build_sheet", fake_build)
    return BM, calls, built, str(tmp_path / "stage")


def _av(ok=True, shape="referrals-only"):
    return {"ok": ok, "vip": False, "workbook": None, "workbook_period": None,
            "referrals": "x_referral.xls" if ok else None, "direct_mail": None,
            "shape": shape if ok else None, "reason": "reason sentence"}


def test_vip_sheet_is_used_first(bm, root, monkeypatch):
    BM, calls, built, stage = bm
    vip = root / "vip_ics.json"
    monkeypatch.setattr(R, "resolve_client_json", lambda a, p: vip)
    monkeypatch.setattr(BM.LOCAL_ICS, "available", lambda *a, **k: pytest.fail("local path consulted"))
    err, made = BM.build_client(CID, NAME, "MM", ["ICS"], PERIOD, stage)
    assert err is None and not built
    assert str(vip) in calls[-1] and "--referrals-only" not in calls[-1]


def test_missing_vip_falls_back_to_local_files(bm, monkeypatch):
    BM, calls, built, stage = bm
    monkeypatch.setattr(BM.LOCAL_ICS, "available", lambda *a, **k: _av(shape="referrals-only"))
    err, made = BM.build_client(CID, NAME, "MM", ["ICS"], PERIOD, stage)
    assert err is None and made["ICS"]
    assert built == [os.path.join(stage, CID, "ics_local_sheet.json")]
    assert built[0] in calls[-1] and "--referrals-only" in calls[-1]
    log = open(os.path.join(stage, CID, "build.log"), encoding="utf-8").read()
    assert "LOCAL files, not VIP" in log and "a flag" in log


def test_full_local_shape_is_not_referrals_only(bm, monkeypatch):
    BM, calls, built, stage = bm
    monkeypatch.setattr(BM.LOCAL_ICS, "available", lambda *a, **k: dict(_av(shape="full"), workbook="w.xlsx"))
    err, _ = BM.build_client(CID, NAME, "MM", ["ICS"], PERIOD, stage)
    assert err is None and "--referrals-only" not in calls[-1]


def test_no_vip_and_no_local_files_stops(bm, monkeypatch):
    BM, calls, built, stage = bm
    monkeypatch.setattr(BM.LOCAL_ICS, "available", lambda *a, **k: _av(ok=False))
    err, made = BM.build_client(CID, NAME, "MM", ["ICS"], PERIOD, stage)
    assert err.startswith("no ICS sheet") and not built and not calls


def test_mrpc_has_no_local_fallback(bm, monkeypatch):
    BM, calls, built, stage = bm
    monkeypatch.setattr(BM.LOCAL_ICS, "available", lambda *a, **k: pytest.fail("local path consulted"))
    err, _ = BM.build_client(CID, NAME, None, ["MRPC"], PERIOD, stage)
    assert err.startswith("no MRPC sheet") and not built


def test_a_client_with_no_ars_assembles_without_the_ars_flag(bm, root, monkeypatch):
    """1439 Horizon Bank NA is ICS (referrals-only) + MRPC with no ARS (Aaron, 2026-10-07).
    The driver always passed `--ars made["ARS"]` to assemble_combined and would have raised
    KeyError before the assembler ever ran; the assembler itself has not needed --ars since
    2026-09-01 (the first program present supplies the shell)."""
    BM, calls, built, stage = bm
    vip = root / "vip.json"
    monkeypatch.setattr(R, "resolve_client_json", lambda a, p: vip)
    err, made = BM.build_client(CID, NAME, None, ["ICS-REFERRALS", "MRPC"], PERIOD, stage)
    assert err is None and set(made) == {"ICS", "MRPC", "DELIVERABLE"}
    assemble = calls[-1]
    assert assemble[1].endswith("assemble_combined.py")
    assert "--ars" not in assemble and "--ics" in assemble and "--mrpc" in assemble
    assert assemble[assemble.index("--ics") + 1] == made["ICS"]
    assert os.path.basename(made["DELIVERABLE"]) == f"{CID}-{PERIOD}-ICS-MRPC-{NAME} Results.pptx"
    assert "--referrals-only" in calls[0]            # the ICS section is the referrals-only shape


# ------------------------------------------------------------------ the deck
def test_local_sheet_deck_names_its_files_and_opens(root, tmp_path):
    """A FULL local build: the case that wrote slide27.xml twice (the Summit slide took a
    static slide's partname) when it had no Contact slide. Every ICS deck has one now, naming
    the managing CSM. Notes must name the local files, not VIP."""
    import build_ics_gen as G
    from validate_deck import package_findings
    write_referrals(referral_file(root))
    write_charts(charts_file(root))
    write_workbook(workbook_file(root, PERIOD))
    d = _sheet(root, tmp_path)
    out = str(tmp_path / "deck" / f"{CID}-{PERIOD}-ICS-{NAME} ICS Results.pptx")
    os.makedirs(os.path.dirname(out))
    G.build(d, os.path.join(REPO, "templates", "ics_template.pptx"), out)
    assert package_findings(out) == []
    from pptx import Presentation
    prs = Presentation(out)
    notes = [s.notes_slide.notes_text_frame.text for s in prs.slides]
    data_notes = [n for n in notes if n.startswith("Source — ICS detailed referral file")]
    assert data_notes and all(referral_file(root).name in n and f"({CID})" in n for n in data_notes)
    joined = " ".join(notes).replace("not VIP", "")
    assert "VIP ICS Referral" not in joined and "pulled" not in joined
    text = " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    assert "PTD · August 14, 2026" in text and "Contact Us" in text and "Some Other CSM" in text
    assert "Direct Mail New Accounts" not in text              # no direct-mail file, no slide


def test_referrals_only_deck_without_goals_shows_no_goal(root, tmp_path):
    import build_ics_gen as G
    from validate_deck import package_findings
    write_referrals(referral_file(root))
    d = _sheet(root, tmp_path)
    out = str(tmp_path / "deck" / f"{CID}-{PERIOD}-ICS-{NAME} ICS Results.pptx")
    os.makedirs(os.path.dirname(out))
    G.build(d, os.path.join(REPO, "templates", "ics_template.pptx"), out, referrals_only=True)
    assert package_findings(out) == []
    from pptx import Presentation
    prs = Presentation(out)
    text = " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    cells = " ".join(c.text for s in prs.slides for sh in s.shapes if sh.has_table
                     for r in sh.table.rows for c in r.cells)
    assert "vs Goal" not in text and "% of Goal" not in text and "Goal" not in cells
    assert "0%" not in text


# ------------------------------------------------------------------ the workbook-only shape
# 1195 KEMBA CU (Aaron, 2026-10-13): the period's ICS workbook and nothing else. Counts are
# ACCOUNTS OPENED via the Invitation Checking System and every slide says so; they are not
# referrals (on 1776, the one client with both, the workbook runs above the referral file).
def _wb_only_sheet(root, tmp_path, charts=True):
    write_workbook(workbook_file(root, PERIOD))
    if charts:
        write_charts(charts_file(root))
    return _sheet(root, tmp_path)


def test_workbook_only_counts_come_from_monthly_detail_and_the_branch_tab(root, tmp_path):
    d = _wb_only_sheet(root, tmp_path)
    rf, m = d["referrals"], d["meta"]
    assert m["count_basis"] == "accounts_opened" and rf["count_basis"] == "accounts_opened"
    assert rf["program_to_date"] == 90                      # the Cumulative row, not the sum (126)
    assert any("Cumulative row says 90" in f and "add to 126" in f for f in d["_flags"])
    assert rf["year_to_date"] == 11 + 12 + 13 + 14 + 15 + 16 + 17 + 18   # Jan..Aug 26
    assert rf["previous_month"] == {"label": "August", "value": 18}
    assert rf["latest_data_month"] == "2026-08"
    assert rf["trend"]["months"][0] == "Dec 25" and rf["trend"]["months"][-1] == "Aug 26"
    assert rf["trend"]["referrals"] == list(range(10, 19)) and rf["trend"]["partial_last"] is False
    assert "month_to_date" not in rf and "monthly_goal" not in rf
    # Branches from the Invitation Checking table's Year to Date column, named from the Goals tab;
    # the all-DDA table above it (300 / 250) is never read.
    assert [(b["name"], b["number"], b["referrals"], b["month"]) for b in rf["by_branch"]["branches"]] == \
        [("Harborview", "10", 60, 10), ("Hilltop", "20", 56, 8)]
    assert not any(b.get("goal") for b in rf["by_branch"]["branches"])
    # Dated by the workbook: the stamp is the pull, the month end is how far the counts run.
    assert m["data_pull"] == "2026-09-09" and m["data_through"] == "2026-08-31"
    assert m["workbook_month"] == "August 2026" and m["source_kind"] == "local"
    assert "NOT referral counts" in m["referral_source"] and "Monthly Detail" in m["referral_source"]
    # The workbook sections ride along: it IS the period's workbook.
    for k in ("performance", "revenue", "financial_summary", "monthly_detail", "benchmark"):
        assert d[k]
    prov = d["_provenance"]
    assert prov["shape"] == L.WORKBOOK_ONLY and prov["vip"] is False
    assert "referrals (as such)" in prov["omitted"] and "goals" in prov["omitted"]
    assert "referrals.month_to_date" in prov["omitted"]
    assert not any("totals" in f for f in d["_flags"])      # branch-tab YTD 116 == Monthly Detail YTD


def test_workbook_only_branch_names_fall_back_to_the_branch_name_dataset(root, tmp_path, monkeypatch):
    import branch_names as BN
    monkeypatch.setattr(BN, "client_map", lambda cid: {"10": "Harbor Dataset", "20": "Hill Dataset"} if cid == CID else {})
    d = _wb_only_sheet(root, tmp_path, charts=False)
    assert [b["name"] for b in d["referrals"]["by_branch"]["branches"]] == ["Harbor Dataset", "Hill Dataset"]


def test_workbook_only_without_a_branch_tab_is_flagged_not_invented(root, tmp_path):
    write_workbook(workbook_file(root, PERIOD), branch_tab=False)
    d = _sheet(root, tmp_path)
    assert d["referrals"]["by_branch"]["branches"] == []
    assert any("no 'DDA Openings by Branch' table" in f for f in d["_flags"])
    assert d["meta"]["data_pull"] == dt.date.fromtimestamp(os.path.getmtime(workbook_file(root, PERIOD))).isoformat()


def test_workbook_only_month_not_ended_at_the_report_date_is_incomplete(root, tmp_path):
    """Generated mid-August: August stays on the chart hatched and July is the previous month."""
    write_workbook(workbook_file(root, PERIOD), generated="8/20/2026 8:00:00 AM")
    d = _sheet(root, tmp_path)
    rf = d["referrals"]
    assert rf["trend"]["partial_last"] is True and rf["trend"]["months"][-1] == "Aug 26"
    assert rf["previous_month"] == {"label": "July", "value": 17}
    assert rf["program_to_date"] == 80 and d["meta"]["data_through"] == "2026-07-31"
    assert any("Aug 26 is incomplete" in f for f in d["_flags"])


def test_workbook_only_deck_is_worded_as_accounts_opened(root, tmp_path):
    from validate_deck import package_findings
    d = _wb_only_sheet(root, tmp_path)
    out, prs = _build_deck(root, tmp_path, d)
    assert package_findings(out) == []
    ts = _titles(prs)
    i = ts.index("Accounts Opened via Invitation Checking")
    assert ts[i + 1] == "Accounts Opened by Month – Last 9 Months"
    assert ts[i + 2] == "Accounts Opened by Branch – Year to Date"
    assert "Performance of ICS Accounts" in " ".join(ts)       # the workbook sections are present
    text = " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    cells = [c.text for s in prs.slides for sh in s.shapes if sh.has_table for r in sh.table.rows for c in r.cells]
    for must in ("Opened Program-to-Date", "ICS accounts opened, program to date", "PTD · August 2026",
                 "has opened 90 checking accounts via the Invitation Checking System",
                 "Branches With Accounts Opened", "Accounts Opened by Month & by Branch"):
        assert must in text, must
    assert "Opened YTD" in cells and "Harborview" in cells
    for never in ("The Power of Referrals", "Referrals Program-to-Date", "Referral Trend", "Results by Branch",
                  "Referrals YTD", "Branches Reporting Referrals", "checking referrals"):
        assert never not in text and never not in cells, never
    # The slide face says what IS counted; "not referrals" is for the notes (Aaron, 2026-10-13:
    # "remove the word 'Not referrals' from Accounts Opened via Invitation checking").
    assert "not referral" not in text.lower()
    notes = [s.notes_slide.notes_text_frame.text for s in prs.slides]
    count_notes = [n for n in notes[i:i + 3]]
    assert all("NOT referral counts" in n and workbook_file(root, PERIOD).name in n and f"({CID})" in n
               for n in count_notes)
    assert "VIP ICS Referral" not in " ".join(notes)


def test_workbook_only_build_month_logs_the_workbook_and_is_not_referrals_only(bm, monkeypatch):
    BM, calls, built, stage = bm
    monkeypatch.setattr(BM.LOCAL_ICS, "available",
                        lambda *a, **k: dict(_av(shape=L.WORKBOOK_ONLY), referrals=None, workbook="w.xlsx"))
    err, made = BM.build_client(CID, NAME, None, ["ICS"], PERIOD, stage)
    assert err is None and made["ICS"] and "--referrals-only" not in calls[-1]
    log = open(os.path.join(stage, CID, "build.log"), encoding="utf-8").read()
    assert "workbook-only" in log and "accounts opened via ICS from the workbook" in log and "workbook w.xlsx" in log


def test_a_goals_tab_named_with_a_leading_space_is_still_read(root):
    """1195's Charts workbook names the tab ' Goals'."""
    write_charts(charts_file(root), tab=" Goals")
    goals, _, info = L.read_goals(str(charts_file(root)))
    assert goals["10"] == ("Harborview", 2) and info["branches"] == 2


# ------------------------------------------------------------------ direct mail slide
def _titles(prs):
    return [next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()), "") for s in prs.slides]


def _build_deck(root, tmp_path, d, referrals_only=False):
    import build_ics_gen as G
    out = str(tmp_path / "deck" / f"{CID}-{PERIOD}-ICS-{NAME} ICS Results.pptx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    G.build(d, os.path.join(REPO, "templates", "ics_template.pptx"), out, referrals_only=referrals_only)
    from pptx import Presentation
    return out, Presentation(out)


def test_direct_mail_slide_follows_results_by_branch(root, tmp_path):
    """Aaron, 2026-09-16: "Direct mail should get its own slide." Right after the referral
    slides, dated by the last month, its figures stated and never mixed into referrals."""
    from validate_deck import package_findings
    write_referrals(referral_file(root))
    write_charts(charts_file(root))
    write_direct_mail(dm_file(root))
    d = _sheet(root, tmp_path)
    ref_ptd = d["referrals"]["program_to_date"]
    out, prs = _build_deck(root, tmp_path, d, referrals_only=True)
    assert package_findings(out) == []
    ts = _titles(prs)
    i = ts.index("Direct Mail New Accounts")
    assert ts[i - 1].startswith("Results by Branch")
    s = prs.slides[i]
    text = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
    cells = [c.text for sh in s.shapes if sh.has_table for r in sh.table.rows for c in r.cells]
    assert "PTD · August 2026" in text                     # last month, Month YYYY
    assert "Opened Program-to-Date" in text and "Opened in August 2026" in text
    assert "Hilltop" in cells and "All 2 Branches" in cells   # branch 20 named from the Goals tab
    assert "Jul'26 – Aug'26" in text and "peak 2 in Jul'26" in text
    assert any(sh.shape_type == 13 and sh.left < 914400 for sh in s.shapes), "no chart picture"
    n = s.notes_slide.notes_text_frame.text
    assert dm_file(root).name in n and f"({CID})" in n and "NOT referral counts" in n
    assert d["referrals"]["program_to_date"] == ref_ptd      # DM never added to referrals
    agenda = " ".join(sh.text_frame.text for sh in prs.slides[ts.index("Agenda")].shapes if sh.has_text_frame)
    assert "Direct Mail" in agenda


def test_no_direct_mail_block_no_slide(root, tmp_path):
    write_referrals(referral_file(root))
    d = _sheet(root, tmp_path)
    assert "direct_mail" not in d
    _, prs = _build_deck(root, tmp_path, d, referrals_only=True)
    assert "Direct Mail New Accounts" not in _titles(prs)
    d["direct_mail"] = {"accounts_opened_ptd": 0, "last_month": "2026-08",
                        "by_month": {"months": [], "accounts": []}, "by_branch": []}
    _, prs = _build_deck(root, tmp_path, d, referrals_only=True)
    assert "Direct Mail New Accounts" not in _titles(prs)


def test_direct_mail_chart_renders(tmp_path):
    import ics_charts_gen as CH
    from PIL import Image
    d = {"direct_mail": {"accounts_opened_ptd": 30, "report_date": "2026-09-09", "last_month": "2026-09",
                         "by_month": {"months": ["Jul 26", "Aug 26", "Sep 26"], "accounts": [10, 15, 5]},
                         "by_branch": [{"branch": "10", "accounts": 30}]}}
    assert CH.has_direct_mail(d) and CH.dm_partial_last(d["direct_mail"])      # Sep report, Sep month
    out = str(tmp_path / "dm.png")
    CH.c_direct_mail_trend(d, out)
    w, h = Image.open(out).size
    assert (w, h) == CH.DM_CANVAS
    bw, bh = CH.DM_BOX_IN
    assert abs(w / h - bw / bh) < 0.01, "chart aspect must match its picture box"
    d["direct_mail"]["report_date"] = "2026-10-02"
    assert not CH.dm_partial_last(d["direct_mail"])
