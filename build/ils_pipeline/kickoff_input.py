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
    find_extract(client_id, period)            # the RPE-worded error for a missing folder
    return io.load_client_data(rpe_env.input_dir("ILS Kickoff", create=False), str(client_id), period)
