"""
pgl_input.py — where the ILS pre-go-live extract is read from in RPE.

`Inputs/ILS PGL/<id>/`: one folder per client, holding the PGL account extract
(`<id>_<Client>_PreGL_<yyyymmdd>.csv` or `.xlsx`, the date in the name) and, when the vendor
supplies them, its two system dumps (`..._MatrixValidation.txt`, `..._IntegrityCheck.txt`), which v5
reads from the same folder as the extract. v5 looked under `01-Data/ILS/{month}/{client}` and four
legacy spellings; here there is one place, and v5's loader (`pre_go_live/loader.py`, unchanged)
takes the folder from `ils_dirs` below.

The kind is in rpe_env.NOT_SCANNED_KINDS: the extract is member-level, hand-landed, and has no
"newer version" the watcher's copier or pruner understands.

A delivery may also land as one zip in the kind's own folder, `Inputs/ILS PGL/<id>_<anything>.zip`,
holding the extract and its dumps (the 2026-10 deliveries for 1737 TNB and 1759 First Central came so).
The zip is never changed or unpacked in Inputs: `ils_dirs` unpacks a copy into
`Build Artifacts/ils/PGL/<id>/_landed/<zip name>/`, again only when the zip changes, and offers that
folder beside `<id>/`, so the newest extract across both still wins and the dumps are read from beside
the extract they came with.
"""
import json
import os
import re
import time
import zipfile
from pathlib import Path


def folder(client_id) -> Path:
    """The client's PGL folder. Not created: a missing folder is a missing extract."""
    import rpe_env
    return rpe_env.input_dir("ILS PGL", create=False) / str(client_id)


def ils_dirs(root, client_id) -> list:
    """v5's `core.datapaths.ils_dirs` shape: the folders that may hold the client's extracts.

    `root` is the ILS PGL input folder (v5 passed its data root): the client's folder when it exists,
    then the unpacked copy of each zip landed for the client."""
    d = Path(root) / str(client_id)
    return ([d] if d.is_dir() else []) + [unpack(z, client_id) for z in landed_zips(root, client_id)]


def landed_zips(root, client_id) -> list:
    """`<root>/<id>_*.zip` (or `<id> *.zip`): a delivery landed zipped. 1737's never matches 17370's."""
    rx = re.compile(rf"^{re.escape(str(client_id))}(?!\d).*\.zip$", re.I)
    try:
        return sorted(p for p in Path(root).iterdir() if p.is_file() and rx.match(p.name))
    except OSError:
        return []


def unpack(zip_path, client_id) -> Path:
    """The zip's files, flat, in `Build Artifacts/ils/PGL/<id>/_landed/<zip stem>/`, with the archive's own
    timestamps. Done once per version of the zip: a `.source.json` beside them records its size and time."""
    import rpe_env
    zip_path = Path(zip_path)
    dest = rpe_env.build_artifacts() / "ils" / "PGL" / str(client_id) / "_landed" / zip_path.stem
    st = zip_path.stat()
    stamp = {"zip": zip_path.name, "size": st.st_size, "mtime": int(st.st_mtime)}
    marker = dest / ".source.json"
    try:
        if json.loads(marker.read_text(encoding="utf-8")) == stamp:
            return dest
    except (OSError, ValueError):
        pass
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name           # flat, and never outside dest
            if info.is_dir() or not name or name.startswith("."):
                continue
            out = dest / name
            out.write_bytes(zf.read(info))
            t = time.mktime(info.date_time + (0, 0, -1))
            os.utime(out, (t, t))
    marker.write_text(json.dumps(stamp), encoding="utf-8")
    return dest


def find_extract(client_id):
    """The newest extract in the client's folder or landed zip, the others listed (v5's `find_extract`)."""
    import rpe_env
    from ils_pipeline.pre_go_live import loader
    root = rpe_env.input_dir("ILS PGL", create=False)
    if not ils_dirs(root, client_id):
        raise FileNotFoundError(
            f"no ILS pre-go-live folder for {client_id}: land the client's PGL extract in "
            f"{root / str(client_id)} (or its zip, {client_id}_<Client>_PGL_<yyyymmdd>.zip, in {root})")
    return loader.find_extract(root, client_id)


def root() -> Path:
    """v5's `data_root` for this engine: the ILS PGL input folder, which `loader.find_extract` takes
    first (it reads `<root>/<id>/` through `ils_dirs` above). Not created."""
    import rpe_env
    return rpe_env.input_dir("ILS PGL", create=False)


def output_root() -> Path:
    """v5's `output_root` (`03-Output`): `Build Artifacts/ils/`, under which v5's run adds
    `PGL/<id>/<yyyymmdd>/`. Never `Outputs/`: a PGL run is not a cycle deliverable."""
    import rpe_env
    return rpe_env.build_artifacts() / "ils"


def config_dir() -> Path:
    """v5's `config_dir` (`0_Config`): `ils_pipeline/config/`, which holds only `ils_fee_tiers.json`,
    v5's universal tier scenarios (not client config; arrives with the fees section)."""
    return Path(__file__).resolve().parent / "config"
