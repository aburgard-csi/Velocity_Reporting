"""The contract every analysis module satisfies.

Each analysis package (monthly_analysis, lift_matrix, ...) exposes:

    run(client_id: str, period: str, **options) -> AnalysisResult

Same signature everywhere. The orchestrator, the MCP tool, and the skill
never special-case an individual analysis -- adding one is a new folder,
not a change to the plumbing.
"""

from __future__ import annotations

import json
import platform
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AnalysisResult:
    """What an analysis returns. Compact enough to hand back to Claude.

    Never contains row-level data. Metrics are aggregates; large artifacts
    are referenced by path in `outputs`.
    """

    analysis: str                      # "monthly_analysis"
    client_id: str                     # "1441"
    period: str                        # "2026-08" (file period)
    status: str = "ok"                 # ok | warning | error

    client_name: str | None = None     # "FNB Alaska"
    data_month: str | None = None      # "2026-07" -- lags period by one

    metrics: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)   # label -> path

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    started_at: str | None = None
    duration_s: float | None = None
    rows_in: int | None = None

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        if self.status == "ok":
            self.status = "warning"

    def fail(self, message: str) -> None:
        self.errors.append(message)
        self.status = "error"

    @property
    def ok(self) -> bool:
        return self.status != "error"

    def summary(self) -> str:
        """One screen. What a person reads before trusting the run."""
        head = f"{self.analysis} | {self.client_id}"
        if self.client_name:
            head += f" {self.client_name}"
        head += f" | period {self.period}"
        if self.data_month:
            head += f" | data through {self.data_month}"

        lines = [head, f"status: {self.status.upper()}"]
        if self.rows_in is not None:
            lines.append(f"rows: {self.rows_in:,}")
        if self.duration_s is not None:
            lines.append(f"duration: {self.duration_s:.1f}s")
        for e in self.errors:
            lines.append(f"  ERROR {e}")
        for w in self.warnings:
            lines.append(f"  WARN  {w}")
        for label, path in self.outputs.items():
            lines.append(f"  -> {label}: {path}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_manifest(self, directory: str | Path) -> Path:
        """Persist the result next to the outputs.

        This is also the peer-set store: one manifest per client per period
        means portfolio questions ('median eligibility across my book') are
        answered by reading manifests, not by re-running anything. Cheap to
        write now, impossible to backfill later.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.client_id}_{self.period}_{self.analysis}.json"
        payload = self.to_dict()
        payload["_env"] = {
            "python": platform.python_version(),
            "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        from .env import write_text_atomic
        write_text_atomic(path, json.dumps(payload, indent=2, default=str))
        return path


class Timer:
    """Stamps started_at and duration_s onto a result."""

    def __init__(self, result: AnalysisResult):
        self.result = result

    def __enter__(self):
        self._t0 = time.perf_counter()
        self.result.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self.result

    def __exit__(self, *exc):
        self.result.duration_s = round(time.perf_counter() - self._t0, 2)
        return False
