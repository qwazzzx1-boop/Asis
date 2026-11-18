from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

from voice_assistant.agent.providers import ModelProvider
from voice_assistant.plugins.base import PluginRegistry


class SpeechSynthesizer(Protocol):
    async def speak(self, text: str) -> None: ...


class AssistantService:
    def __init__(
        self,
        provider: ModelProvider,
        tools: PluginRegistry,
        tts: SpeechSynthesizer | None = None,
        *,
        memory_turns: int = 8,
        max_tool_rounds: int = 10,
    ):
        self.provider, self.tools, self.tts = provider, tools, tts
        self.memory_turns = max(1, memory_turns)
        self.max_tool_rounds = max(1, max_tool_rounds)
        self.messages: list[dict[str, Any]] = [{
            "role": "system",
            "content": (
                "Ты — голосовой мобильный ассистент на телефоне Android. Общайся на русском языке.\n"
                "ПРАВИЛА:\n"
                "1. Используй инструменты, когда нужно выполнить действие. Не утверждай, что действие выполнено без результата инструмента.\n"
                "2. Выполняй цепочки действий последовательно.\n"
                "3. Русские сокращения: тг=Telegram, дс=Discord, ют=YouTube, вк=ВКонтакте, "
                "хром=Chrome, стим=Steam, майн=Minecraft, инста=Instagram, тикток=TikTok, спотифай=Spotify.\n"
                "4. Для запуска приложения используй launch_application или open_app.\n"
                "5. При неоднозначности уточни запрос.\n"
                "6. Не пытайся обходить подтверждения инструментов.\n"
                "7. Отвечай кратко и по делу."
            ),
        }]
        self._stop = asyncio.Event()
        self._request_lock = asyncio.Lock()
        self._request_number = 0

    def stop(self) -> None:
        self._stop.set()

    def _trim_history(self) -> None:
        """Keep complete user turns, including their assistant/tool-call exchanges."""
        if len(self.messages) <= 1:
            return
        turns: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        for message in self.messages[1:]:
            if message.get("role") == "user" and current:
                turns.append(current)
                current = [message]
            else:
                current.append(message)
        if current:
            turns.append(current)
        self.messages = self.messages[:1] + [
            item for turn in turns[-self.memory_turns:] for item in turn
        ]

    async def handle_text(self, text: str) -> str:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Пустое сообщение")

        # A conversation has one writer. Without this lock, parallel UI submits
        # could interleave assistant tool calls and their results.
        async with self._request_lock:
            self._stop.clear()
            self._request_number += 1
            request_id = self._request_number
            self._trim_history()
            self.messages.append({"role": "user", "content": clean_text})
            answer = ""

            try:
                for round_index in range(self.max_tool_rounds):
                    if self._stop.is_set():
                        raise asyncio.CancelledError("Запрос остановлен")

                    response = await self.provider.respond(
                        list(self.messages),
                        self.tools.schemas(),
                    )
                    if not isinstance(response, dict):
                        raise RuntimeError("Провайдер вернул ответ неверного формата")

                    calls = response.get("tool_calls") or []
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.get("content", "") or "",
                    }
                    if calls:
                        normalized_calls = []
                        for index, call in enumerate(calls):
                            if not isinstance(call, dict):
                                raise ValueError("Некорректный вызов инструмента")
                            fn = call.get("function")
                            if not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
                                raise ValueError("Вызов инструмента не содержит имени")
                            call_id = call.get("id") or f"echo_{request_id}_{round_index}_{index}"
                            normalized_calls.append({
                                "id": str(call_id),
                                "type": "function",
                                "function": {
                                    "name": fn["name"],
                                    "arguments": fn.get("arguments", {}),
                                },
                            })
                        assistant_message["tool_calls"] = normalized_calls

                    self.messages.append(assistant_message)
                    if not calls:
                        answer = str(assistant_message["content"])
                        break

                    for call_index, call in enumerate(assistant_message["tool_calls"]):
                        fn = call["function"]
                        if self._stop.is_set():
                            for pending in assistant_message["tool_calls"][call_index:]:
                                self.messages.append({
                                    "role": "tool",
                                    "name": pending["function"]["name"],
                                    "tool_call_id": pending["id"],
                                    "content": "Действие отменено пользователем.",
                                })
                            self.messages.append({
                                "role": "assistant",
                                "content": "Выполнение остановлено пользователем.",
                            })
                            raise asyncio.CancelledError("Запрос остановлен")

                        raw_args = fn.get("arguments", {})
                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                            result = await self.tools.invoke(fn["name"], args)
                            tool_content = str(result)[:4000]
                        except Exception as exc:
                            # Always close the tool-call/result pair. This lets the
                            # provider explain a rejected or failed action cleanly.
                            tool_content = f"Ошибка инструмента: {str(exc)[:1200]}"

                        self.messages.append({
                            "role": "tool",
                            "name": fn["name"],
                            "tool_call_id": call["id"],
                            "content": tool_content,
                        })
                else:
                    raise RuntimeError("Превышен лимит последовательных вызовов инструментов")

                if answer and self.tts:
                    await self.tts.speak(answer)
                return answer

            except asyncio.CancelledError:
                # Remove only a bare user message. If tool calls have started,
                # keep their completed results so external actions aren't forgotten.
                if self.messages and self.messages[-1].get("role") == "user":
                    self.messages.pop()
                raise
            except Exception:
                # A provider failure before its first response leaves only a user
                # message. Remove that dangling turn; preserve completed tool work.
                if self.messages and self.messages[-1].get("role") == "user":
                    self.messages.pop()
                raise

    def clear_memory(self) -> None:
        if self._request_lock.locked():
            raise RuntimeError("Нельзя очистить историю во время активного запроса")
        self.messages = self.messages[:1]
