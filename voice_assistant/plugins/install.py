from __future__ import annotations
from pathlib import Path
from voice_assistant.config import Settings
from voice_assistant.plugins.base import PluginRegistry, ToolSpec
from voice_assistant.plugins.system import SystemTools
from voice_assistant.plugins.messaging import MessagingTools
from voice_assistant.security.audit import AuditLog
from voice_assistant.security.policy import ApprovalGate, RiskLevel
from voice_assistant.security.credentials import CredentialStore


def install_builtin_tools(settings: Settings, gate: ApprovalGate, audit: AuditLog, data_dir: Path) -> PluginRegistry:
    registry = PluginRegistry(gate, audit)
    system = SystemTools(gate)
    messaging = MessagingTools(CredentialStore(), gate, settings.telegram_credential, settings.discord_credential)

    registry.register(ToolSpec(
        "open_website",
        "Открыть сайт в браузере по URL",
        {"type": "object", "properties": {"url": {"type": "string", "description": "URL сайта (https://...)"}}, "required": ["url"]},
        RiskLevel.SAFE,
        system.open_website,
    ))

    registry.register(ToolSpec(
        "launch_application",
        "Запустить приложение по названию или русскому сокращению (тг, дс, ют, хром, стим, вк, майн, обс, спотифай, инста и др.)",
        {"type": "object", "properties": {
            "executable": {"type": "string", "description": "Название приложения или сокращение (тг, дс, ют, хром, стим, вк, майн...)"},
            "args": {"type": "array", "items": {"type": "string"}, "description": "Аргументы запуска (обычно пусто)"},
        }, "required": ["executable"]},
        RiskLevel.SAFE,
        system.launch,
    ))

    registry.register(ToolSpec(
        "open_app",
        "Универсальный запуск: пробует открыть приложение по сокращению, если нет — открывает веб-версию. Поддерживает: тг, дс, ют, вк, спотифай, инста, тикток, гитхаб, твич, чатгпт и др.",
        {"type": "object", "properties": {"name": {"type": "string", "description": "Название или сокращение (тг, дс, ют, вк, стим, хром, спотифай...)"}}, "required": ["name"]},
        RiskLevel.SAFE,
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
        "Отправить сообщение в Telegram через бота (нужен chat_id)",
        {"type": "object", "properties": {
            "chat_id": {"type": "string", "description": "ID чата Telegram"},
            "message": {"type": "string", "description": "Текст сообщения"},
        }, "required": ["chat_id", "message"]},
        RiskLevel.SAFE,
        messaging.send_telegram,
    ))

    registry.register(ToolSpec(
        "discord_send",
        "Отправить сообщение в Discord через бота (нужен channel_id)",
        {"type": "object", "properties": {
            "channel_id": {"type": "string", "description": "ID канала Discord"},
            "message": {"type": "string", "description": "Текст сообщения"},
        }, "required": ["channel_id", "message"]},
        RiskLevel.SAFE,
        messaging.send_discord,
    ))

    return registry
