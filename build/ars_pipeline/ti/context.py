"""
context.py — what every ported computation is handed: the frame, the client config, the data
month, the account bases, and a warn that collects sentences rather than printing them.

The same object drives a real build (`ti_build.py`) and the parity check against v5
(`ti/parity.py`), so a computation is checked exactly as it runs.
"""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Ctx:
    frame: object
    config: dict
    anchor: object
    subsets: object
    source_dir: Path = None
    client_id: str = None
    warnings: list = field(default_factory=list)
    # the transaction side, when the client has a transaction window: the rows (v5's loader
    # frame), the window end, the account lenses keyed on the ODD's account ids, the loader's
    # report, and the section outputs later sections read (v5 run.py passes them along)
    txn: object = None
    anchor_ts: object = None
    lenses: object = None
    txn_report: object = None
    txn_window: dict = None          # ti/window.py describe(): the last N completed months
    shared: dict = field(default_factory=dict)

    def warn(self, message):
        self.warnings.append(message)
