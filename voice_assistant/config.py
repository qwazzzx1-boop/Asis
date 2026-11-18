from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os


def _app_dir() -> Path:
    """Return a writable app-private directory on any platform."""
    try:
        from android.storage import app_storage_path  # type: ignore[import]
        return Path(app_storage_path())
    except ImportError:
        pass
    base = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "VoiceAssistant"
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class Settings:
    language: str = "ru"
    # OpenRouter is the sensible mobile default: it does not require a PC/LAN Ollama host.
    provider: str = "openrouter"
    model: str = "openai/gpt-4o-mini"
    ollama_url: str = "http://192.168.0.100:11434"
    confirmation_messages: bool = True
    allowed_roots: list[str] = field(default_factory=list)
    telegram_credential: str = "voice-assistant.telegram-bot"
    discord_credential: str = "voice-assistant.discord-bot"
    games: list[dict[str, object]] = field(default_factory=list)
    ollama_remote: bool = True

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
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary_path, path)
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

        provider = data.get("provider", "openrouter")
        model = data.get("model", "openai/gpt-4o-mini")
        # Migrate the app's old untouched defaults, which silently sent Android
        # requests to a made-up LAN Ollama address instead of the configured API.
        if (
            provider == "ollama"
            and model == "qwen2.5:7b"
            and data.get("ollama_url", "http://192.168.0.100:11434") == "http://192.168.0.100:11434"
        ):
            provider, model = "openrouter", "openai/gpt-4o-mini"

        return cls(
            language=data.get("language", "ru"),
            provider=provider,
            model=model,
            ollama_url=data.get("ollama_url", "http://192.168.0.100:11434"),
            confirmation_messages=data.get("confirmation_messages", True),
            allowed_roots=data.get("allowed_roots", []),
            telegram_credential=data.get("telegram_credential", "voice-assistant.telegram-bot"),
            discord_credential=data.get("discord_credential", "voice-assistant.discord-bot"),
            games=data.get("games", []),
            ollama_remote=data.get("ollama_remote", True),
        )
