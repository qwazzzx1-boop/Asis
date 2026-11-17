from __future__ import annotations
import asyncio
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from voice_assistant.security.policy import ApprovalGate, RiskLevel
from voice_assistant.security.credentials import CredentialStore


def _post(url: str, body: dict, headers: dict[str, str] | None = None) -> dict:
    req = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urlopen(req, timeout=15) as response:
            data = response.read(1_000_000)
        return json.loads(data or b"{}")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("Messaging request failed") from exc


class MessagingTools:
    """Bot-only adapters. Chat identifiers must be supplied explicitly; no contact scraping."""
    def __init__(self, credentials: CredentialStore, gate: ApprovalGate, telegram_key: str, discord_key: str):
        self.credentials, self.gate = credentials, gate
        self.telegram_key, self.discord_key = telegram_key, discord_key

    async def send_telegram(self, chat_id: str, message: str) -> str:
        await self.gate.check(f"Telegram destination {chat_id}; message: {message}", RiskLevel.DANGEROUS)
        token = self.credentials.get(self.telegram_key)
        if not token: raise RuntimeError("Telegram bot credential is not configured in the OS credential store")
        if len(message) > 4096: raise ValueError("Telegram message is too long")
        result = await asyncio.to_thread(_post, f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat_id, "text": message})
        if not result.get("ok"): raise RuntimeError("Telegram rejected the message")
        return "Telegram message sent"

    async def send_discord(self, channel_id: str, message: str) -> str:
        await self.gate.check(f"Discord destination {channel_id}; message: {message}", RiskLevel.DANGEROUS)
        token = self.credentials.get(self.discord_key)
        if not token: raise RuntimeError("Discord bot credential is not configured in the OS credential store")
        if len(message) > 2000: raise ValueError("Discord message is too long")
        result = await asyncio.to_thread(_post, f"https://discord.com/api/v10/channels/{channel_id}/messages", {"content": message}, {"Authorization": f"Bot {token}"})
        if not result.get("id"): raise RuntimeError("Discord rejected the message")
        return "Discord message sent"
