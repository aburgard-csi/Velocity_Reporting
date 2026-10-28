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
"""
from pathlib import Path


def folder(client_id) -> Path:
    """The client's PGL folder. Not created: a missing folder is a missing extract."""
    import rpe_env
    return rpe_env.input_dir("ILS PGL", create=False) / str(client_id)


def ils_dirs(root, client_id) -> list:
    """v5's `core.datapaths.ils_dirs` shape: the folders that may hold the client's extracts.

    `root` is the ILS PGL input folder (v5 passed its data root); one folder or none."""
    d = Path(root) / str(client_id)
    return [d] if d.is_dir() else []


def find_extract(client_id):
    """The newest extract in the client's folder, the others listed (v5's `find_extract`)."""
    import rpe_env
    from ils_pipeline.pre_go_live import loader
    root = rpe_env.input_dir("ILS PGL", create=False)
    if not (root / str(client_id)).is_dir():
        raise FileNotFoundError(
            f"no ILS pre-go-live folder for {client_id}: land the client's PGL extract in "
            f"{root / str(client_id)}")
    return loader.find_extract(root, client_id)
