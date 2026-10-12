"""rpe_env.extract_odd_csv unzips a given ODD zip once per process, and again if the zip changes."""
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "build"))
import rpe_env  # noqa: E402


def _zip(path, body):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("1-ODD_V2_1.csv", body)


def test_the_same_zip_is_extracted_once(tmp_path, monkeypatch):
    monkeypatch.setattr(rpe_env, "_odd_csv_cache", {})
    z = tmp_path / "1_ODDD.zip"
    _zip(z, "a,b\n1,2\n")
    first = rpe_env.extract_odd_csv(str(z))
    assert open(first, encoding="utf-8").read() == "a,b\n1,2\n"
    second = rpe_env.extract_odd_csv(str(z), prefix="other_")
    assert second == first


def test_a_changed_zip_or_a_missing_file_is_extracted_again(tmp_path, monkeypatch):
    monkeypatch.setattr(rpe_env, "_odd_csv_cache", {})
    z = tmp_path / "1_ODDD.zip"
    _zip(z, "a,b\n1,2\n")
    first = rpe_env.extract_odd_csv(str(z))
    os.remove(first)                                   # scratch swept away: do not hand back a dead path
    again = rpe_env.extract_odd_csv(str(z))
    assert os.path.isfile(again)
    _zip(z, "a,b\n3,4\n5,6\n")                         # a new landing of the same name
    changed = rpe_env.extract_odd_csv(str(z))
    assert open(changed, encoding="utf-8").read() == "a,b\n3,4\n5,6\n"
