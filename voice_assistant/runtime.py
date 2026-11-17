from __future__ import annotations
import os
from pathlib import Path
from voice_assistant.agent.providers import OllamaProvider, OpenRouterProvider
from voice_assistant.agent.service import AssistantService
from voice_assistant.config import Settings, _app_dir
from voice_assistant.plugins.install import install_builtin_tools
from voice_assistant.security.audit import AuditLog
from voice_assistant.security.credentials import CredentialStore
from voice_assistant.security.policy import ApprovalGate


def data_directory() -> Path:
    root = _app_dir() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_service(settings: Settings, approve) -> AssistantService:
    if settings.provider == "ollama":
        provider = OllamaProvider(settings.ollama_url, settings.model)
    elif settings.provider == "anthropic":
        credential = CredentialStore().get("anthropic-api-key")
        if not credential:
            raise RuntimeError("Сохраните API ключ Anthropic в настройках")
        from voice_assistant.agent.providers import AnthropicProvider
        provider = AnthropicProvider(credential, settings.model)
    elif settings.provider == "openrouter":
        credential = CredentialStore().get("openrouter-api-key")
        if not credential:
            raise RuntimeError("Сохраните API ключ OpenRouter в настройках")
        provider = OpenRouterProvider(credential, settings.model)
    else:
        raise ValueError(f"Неизвестный провайдер: {settings.provider}")
    gate = ApprovalGate(approve)
    audit = AuditLog(data_directory() / "actions.jsonl")
    registry = install_builtin_tools(settings, gate, audit, data_directory())
    return AssistantService(provider, registry, tts=None)
