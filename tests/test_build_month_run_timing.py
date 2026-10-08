"""build_month.run records how long each step took, without burying a failed step's traceback."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_month as BM  # noqa: E402


def test_a_successful_step_logs_its_time(tmp_path):
    log = tmp_path / "build.log"
    assert BM.run([sys.executable, "-c", "print('ok')"], str(log)) == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[-1].startswith("# step finished in ")
    assert lines[-1].endswith(" s")


def test_a_failed_step_leaves_its_own_last_line(tmp_path):
    """ars_launcher._log_reason reports the last log line; it must stay the failure's."""
    log = tmp_path / "build.log"
    assert BM.run([sys.executable, "-c", "raise SystemExit('the real reason')"], str(log)) != 0
    last = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()][-1]
    assert last == "the real reason"
