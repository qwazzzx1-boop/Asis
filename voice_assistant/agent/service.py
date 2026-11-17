from __future__ import annotations
import asyncio
import json
from typing import Any, Protocol
from voice_assistant.agent.providers import ModelProvider
from voice_assistant.plugins.base import PluginRegistry


class SpeechSynthesizer(Protocol):
    async def speak(self, text: str) -> None: ...


class AssistantService:
    def __init__(self, provider: ModelProvider, tools: PluginRegistry, tts: SpeechSynthesizer | None = None, *, memory_turns: int = 8):
        self.provider, self.tools, self.tts = provider, tools, tts
        self.memory_turns = memory_turns
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": (
            "Ты — голосовой мобильный ассистент на телефоне Android. Общайся на русском языке.\n"
            "ПРАВИЛА:\n"
            "1. Используй инструменты (tools) когда нужно выполнить действие. Никогда не утверждай что действие выполнено без результата от tool.\n"
            "2. Для сложных запросов (несколько действий) выполняй tool calls последовательно, по одному за шаг.\n"
            "3. Пользователь может использовать русские сокращения приложений: тг=Telegram, дс=Discord, ют=YouTube, вк=ВКонтакте, хром=Chrome, стим=Steam, майн=Minecraft, инста=Instagram, тикток=TikTok, спотифай=Spotify, обс=OBS, и т.д.\n"
            "4. Когда пользователь просит открыть/запустить приложение, используй launch_application или open_app с названием или сокращением — система запустит приложение на Android или откроет веб-версию.\n"
            "5. Если задача включает несколько шагов (например 'открой тг и напиши сообщение'), разбей на отдельные tool calls.\n"
            "6. При неоднозначности — уточни у пользователя.\n"
            "7. Отвечай кратко и по делу."
        )}]
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def handle_text(self, text: str) -> str:
        self._stop.clear()
        self.messages.append({"role": "user", "content": text})
        # Сохраняем системное сообщение + последние N обменов (user+assistant пары)
        self.messages = [self.messages[0], *self.messages[-self.memory_turns * 2:]]
        for _ in range(10):  # Увеличен лимит с 5 до 10 для сложных цепочек
            if self._stop.is_set(): raise asyncio.CancelledError("Assistant stopped")
            response = await self.provider.respond(self.messages, self.tools.schemas())
            calls = response.get("tool_calls") or []
            self.messages.append({"role": "assistant", "content": response.get("content", "") or "", **({"tool_calls": calls} if calls else {})})
            if not calls: break
            for call in calls:
                if self._stop.is_set(): raise asyncio.CancelledError("Assistant stopped")
                fn = call.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str): args = json.loads(args)
                result = await self.tools.invoke(fn["name"], args)
                self.messages.append({"role": "tool", "name": fn["name"], "content": str(result)[:4000]})
        else:
            raise RuntimeError("Tool call limit reached")
        answer = self.messages[-1].get("content", "")
        if answer and self.tts: await self.tts.speak(answer)
        return answer

    def clear_memory(self) -> None:
        self.messages = self.messages[:1]
