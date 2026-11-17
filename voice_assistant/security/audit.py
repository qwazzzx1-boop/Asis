from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class AuditLog:
    """Append-only JSONL audit with allowlisted fields to avoid logging secrets/content."""
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, action: str, outcome: str, *, detail: str = "") -> None:
        row = {"at": datetime.now(timezone.utc).isoformat(), "action": action[:80], "outcome": outcome[:40], "detail": detail[:240]}
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
