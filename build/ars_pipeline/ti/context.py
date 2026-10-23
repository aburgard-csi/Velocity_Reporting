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

    def warn(self, message):
        self.warnings.append(message)
