from __future__ import annotations

from pathlib import Path

from voice_assistant.config import Settings
from voice_assistant.plugins.base import PluginRegistry, ToolSpec
from voice_assistant.plugins.system import SystemTools
from voice_assistant.plugins.messaging import MessagingTools
from voice_assistant.security.audit import AuditLog
from voice_assistant.security.policy import ApprovalGate, RiskLevel
from voice_assistant.security.credentials import CredentialStore


def install_builtin_tools(
    settings: Settings,
    gate: ApprovalGate,
    audit: AuditLog,
    data_dir: Path,
) -> PluginRegistry:
    registry = PluginRegistry(gate, audit)
    system = SystemTools(gate)
    messaging = MessagingTools(
        CredentialStore(),
        gate,
        settings.telegram_credential,
        settings.discord_credential,
    )

    registry.register(ToolSpec(
        "open_website",
        "Открыть сайт в браузере по HTTP(S) URL",
        {
            "type": "object",
            "properties": {"url": {"type": "string", "minLength": 8, "maxLength": 2048}},
            "required": ["url"],
        },
        RiskLevel.SAFE,
        system.open_website,
    ))

    registry.register(ToolSpec(
        "launch_application",
        "Запустить приложение по названию или русскому сокращению",
        {
            "type": "object",
            "properties": {
                "executable": {"type": "string", "minLength": 1, "maxLength": 100},
                "args": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["executable"],
        },
        RiskLevel.CONFIRM,
        system.launch,
    ))

    registry.register(ToolSpec(
        "open_app",
        "Открыть приложение по названию или его веб-версию",
        {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 100}},
            "required": ["name"],
        },
        RiskLevel.CONFIRM,
        system.open_app_or_website,
    ))

    registry.register(ToolSpec(
        "list_apps",
        "Показать список поддерживаемых сокращений приложений",
        {"type": "object", "properties": {}, "required": []},
        RiskLevel.SAFE,
        system.list_available_apps,
    ))

    registry.register(ToolSpec(
        "telegram_send",
        "Отправить сообщение в Telegram через настроенного бота",
        {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "minLength": 1, "maxLength": 64},
                "message": {"type": "string", "minLength": 1, "maxLength": 4096},
            },
            "required": ["chat_id", "message"],
        },
        RiskLevel.DANGEROUS,
        messaging.send_telegram,
    ))

    registry.register(ToolSpec(
        "discord_send",
        "Отправить сообщение в Discord через настроенного бота",
        {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "minLength": 1, "maxLength": 64},
                "message": {"type": "string", "minLength": 1, "maxLength": 2000},
            },
            "required": ["channel_id", "message"],
        },
        RiskLevel.DANGEROUS,
        messaging.send_discord,
    ))

    return registry
