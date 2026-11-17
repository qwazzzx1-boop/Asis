from __future__ import annotations
import json
from pathlib import Path
from voice_assistant.config import _app_dir


class CredentialStore:
    """JSON-based credential store for Android (keyring не работает на Android)."""

    def __init__(self, path: Path | None = None):
        self._path = path or (_app_dir() / "credentials.json")

    def _load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def get(self, name: str) -> str | None:
        return self._load().get(name)

    def set(self, name: str, value: str) -> None:
        data = self._load()
        data[name] = value
        self._save(data)

    def delete(self, name: str) -> None:
        data = self._load()
        data.pop(name, None)
        self._save(data)
