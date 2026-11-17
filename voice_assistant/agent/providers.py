from __future__ import annotations
import asyncio
import json
from typing import Any, Protocol
from urllib.request import Request, urlopen


class ModelProvider(Protocol):
    async def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]: ...


class OllamaProvider:
    def __init__(self, base_url: str, model: str): self.base_url, self.model = base_url.rstrip("/"), model

    def _request(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps({"model": self.model, "messages": messages, "tools": tools or None, "stream": False}).encode()
        request = Request(self.base_url + "/api/chat", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=120) as response: return json.loads(response.read(4_000_000))

    async def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        data = await asyncio.to_thread(self._request, messages, tools)
        return data.get("message", {})


class AnthropicProvider:
    """Optional cloud adapter. Prompt content is sent to Anthropic when selected."""
    def __init__(self, api_key: str, model: str): self.api_key, self.model = api_key, model

    async def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        try: import anthropic
        except ImportError as exc: raise RuntimeError("Install anthropic to enable the Claude provider") from exc
        system = (
            "Ты — голосовой мобильный ассистент на телефоне Android. Общайся на русском. "
            "Используй tools для действий. Не утверждай что действие выполнено без результата от tool. "
            "Пользователь может использовать русские сокращения: тг=Telegram, дс=Discord, ют=YouTube, вк=ВКонтакте, инста=Instagram, спотифай=Spotify и т.д. "
            "Для сложных запросов выполняй tool calls последовательно."
        )
        converted = []
        last_tool_ids: dict[str, str] = {}
        for index, message in enumerate(messages):
            role = message.get("role")
            if role == "system":
                continue
            if role == "assistant" and message.get("tool_calls"):
                blocks = []
                if message.get("content"): blocks.append({"type": "text", "text": message["content"]})
                for call_index, call in enumerate(message["tool_calls"]):
                    fn = call.get("function", {})
                    call_id = f"toolu_{index}_{call_index}"
                    last_tool_ids[fn.get("name", "")] = call_id
                    args = fn.get("arguments", {})
                    if isinstance(args, str): args = json.loads(args)
                    blocks.append({"type": "tool_use", "id": call_id, "name": fn["name"], "input": args})
                converted.append({"role": "assistant", "content": blocks})
            elif role == "tool":
                call_id = last_tool_ids.get(message.get("name", ""))
                if call_id:
                    converted.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id, "content": str(message.get("content", ""))}]})
            else:
                converted.append({"role": role, "content": message.get("content", "")})
        api_tools = [{"name": t["function"]["name"], "description": t["function"]["description"], "input_schema": t["function"]["parameters"]} for t in tools]
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        result = await client.messages.create(model=self.model, max_tokens=4096, system=system, messages=converted, tools=api_tools)
        calls = [{"function": {"name": block.name, "arguments": block.input}} for block in result.content if block.type == "tool_use"]
        text = "\n".join(block.text for block in result.content if block.type == "text")
        return {"role": "assistant", "content": text, "tool_calls": calls}


class OpenRouterProvider:
    """OpenRouter adapter using its OpenAI-compatible Chat Completions API."""
    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _request(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        # The shared service stores tool results by function name (Ollama-style).
        # OpenAI-compatible APIs additionally require tool_call_id on each result.
        api_messages: list[dict[str, Any]] = []
        pending_ids: dict[str, list[str]] = {}
        for message in messages:
            item = dict(message)
            if item.get("role") == "assistant" and item.get("tool_calls"):
                normalized_calls = []
                for index, call in enumerate(item["tool_calls"]):
                    call = dict(call)
                    fn = call.get("function", {})
                    call_id = call.get("id") or f"call_{len(api_messages)}_{index}"
                    call["id"] = call_id
                    call["type"] = "function"
                    pending_ids.setdefault(fn.get("name", ""), []).append(call_id)
                    normalized_calls.append(call)
                item["tool_calls"] = normalized_calls
            elif item.get("role") == "tool":
                ids = pending_ids.get(item.get("name", ""), [])
                if ids:
                    item["tool_call_id"] = ids.pop(0)
                else:
                    # A malformed history should fail clearly rather than send an invalid request.
                    raise RuntimeError(f"Не найден tool_call_id для инструмента {item.get('name', '')}")
            api_messages.append(item)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/voice-assistant-android",
                "X-Title": "Voice Assistant Android",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                data = json.loads(response.read(4_000_000))
        except Exception as exc:
            # Include the provider's useful HTTP response without exposing the API key.
            if hasattr(exc, "read"):
                try:
                    detail = exc.read(4000).decode("utf-8", errors="replace")
                    raise RuntimeError(f"Ошибка OpenRouter: {detail}") from exc
                except RuntimeError:
                    raise
                except Exception:
                    pass
            raise
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenRouter вернул пустой ответ: {data.get('error', data)}")
        return choices[0].get("message") or {}

    async def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, messages, tools)
