from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os


def _app_dir() -> Path:
    """Return a writable app-private directory on any platform."""
    try:
        # Android: use the app files directory
        from android.storage import app_storage_path  # type: ignore[import]
        return Path(app_storage_path())
    except ImportError:
        pass
    # Desktop fallback
    base = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "VoiceAssistant"
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class Settings:
    language: str = "ru"
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    ollama_url: str = "http://192.168.0.100:11434"  # LAN IP — Ollama на ПК
    confirmation_messages: bool = True
    allowed_roots: list[str] = field(default_factory=list)
    telegram_credential: str = "voice-assistant.telegram-bot"
    discord_credential: str = "voice-assistant.discord-bot"
    games: list[dict[str, object]] = field(default_factory=list)

    # --- Android-specific ---
    ollama_remote: bool = True  # Use remote Ollama over LAN

    def save(self, path: Path | None = None) -> Path:
        if path is None:
            path = _app_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "language": self.language,
            "provider": self.provider,
            "model": self.model,
            "ollama_url": self.ollama_url,
            "confirmation_messages": self.confirmation_messages,
            "allowed_roots": self.allowed_roots,
            "telegram_credential": self.telegram_credential,
            "discord_credential": self.discord_credential,
            "games": self.games,
            "ollama_remote": self.ollama_remote,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        if path is None:
            path = _app_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(
            language=data.get("language", "ru"),
            provider=data.get("provider", "ollama"),
            model=data.get("model", "qwen2.5:7b"),
            ollama_url=data.get("ollama_url", "http://192.168.0.100:11434"),
            confirmation_messages=data.get("confirmation_messages", True),
            allowed_roots=data.get("allowed_roots", []),
            telegram_credential=data.get("telegram_credential", "voice-assistant.telegram-bot"),
            discord_credential=data.get("discord_credential", "voice-assistant.discord-bot"),
            games=data.get("games", []),
            ollama_remote=data.get("ollama_remote", True),
        )
