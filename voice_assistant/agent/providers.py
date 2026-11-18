from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any, Protocol
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - packaging error is reported at request time
    certifi = None


class ModelProvider(Protocol):
    async def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]: ...


class OllamaProvider:
    def __init__(self, base_url: str, model: str):
        self.base_url, self.model = base_url.rstrip("/"), model

    def _request(self, messages, tools):
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": tools or None,
            "stream": False,
        }, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url + "/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read(4_000_000))

    async def respond(self, messages, tools):
        data = await asyncio.to_thread(self._request, messages, tools)
        message = data.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama вернул ответ неверного формата")
        return message


class AnthropicProvider:
    """Anthropic adapter preserving IDs and grouping tool results correctly."""
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    async def respond(self, messages, tools):
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("Для Claude требуется пакет anthropic") from exc

        system = (
            "Ты — голосовой мобильный ассистент на Android. Общайся на русском. "
            "Используй инструменты для действий и не заявляй об успехе без их результата. "
            "Не обходи подтверждения инструментов."
        )
        converted = []
        index = 0
        while index < len(messages):
            message = messages[index]
            role = message.get("role")
            if role == "system":
                index += 1
                continue

            if role == "assistant" and message.get("tool_calls"):
                blocks = []
                if message.get("content"):
                    blocks.append({"type": "text", "text": str(message["content"])})
                for call in message["tool_calls"]:
                    fn = call.get("function", {})
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        args = json.loads(args)
                    blocks.append({
                        "type": "tool_use",
                        "id": str(call.get("id") or ""),
                        "name": fn["name"],
                        "input": args,
                    })
                converted.append({"role": "assistant", "content": blocks})
                index += 1

                results = []
                while index < len(messages) and messages[index].get("role") == "tool":
                    tool_message = messages[index]
                    tool_id = tool_message.get("tool_call_id")
                    if not tool_id:
                        raise RuntimeError("В истории Anthropic отсутствует tool_call_id")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": str(tool_id),
                        "content": str(tool_message.get("content", "")),
                    })
                    index += 1
                if results:
                    converted.append({"role": "user", "content": results})
                continue

            converted.append({"role": role, "content": message.get("content", "")})
            index += 1

        api_tools = [{
            "name": item["function"]["name"],
            "description": item["function"]["description"],
            "input_schema": item["function"]["parameters"],
        } for item in tools]
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        result = await client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=converted,
            tools=api_tools,
        )
        calls = [{
            "id": block.id,
            "function": {"name": block.name, "arguments": block.input},
        } for block in result.content if block.type == "tool_use"]
        answer = "\n".join(block.text for block in result.content if block.type == "text")
        return {"role": "assistant", "content": answer, "tool_calls": calls}


class OpenRouterProvider:
    """OpenRouter adapter using the OpenAI-compatible Chat Completions API."""
    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key, self.model = api_key, model
        self.base_url = base_url.rstrip("/")

    def _request(self, messages, tools):
        api_messages = []
        pending_ids: dict[str, list[str]] = {}
        for message in messages:
            item = dict(message)
            if item.get("role") == "assistant" and item.get("tool_calls"):
                normalized = []
                for index, original in enumerate(item["tool_calls"]):
                    call = dict(original)
                    fn = dict(call.get("function") or {})
                    call_id = str(call.get("id") or f"echo_call_{len(api_messages)}_{index}")
                    call["id"] = call_id
                    call["type"] = "function"
                    args = fn.get("arguments", {})
                    if not isinstance(args, str):
                        fn["arguments"] = json.dumps(args, ensure_ascii=False)
                    call["function"] = fn
                    pending_ids.setdefault(fn.get("name", ""), []).append(call_id)
                    normalized.append(call)
                item["tool_calls"] = normalized
            elif item.get("role") == "tool":
                tool_id = item.get("tool_call_id")
                if not tool_id:
                    ids = pending_ids.get(item.get("name", ""), [])
                    if ids:
                        tool_id = ids.pop(0)
                if not tool_id:
                    raise RuntimeError(f"Не найден tool_call_id для инструмента {item.get('name', '')}")
                item["tool_call_id"] = str(tool_id)
            api_messages.append(item)

        payload = {"model": self.model, "messages": api_messages, "stream": False}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        request = Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/voice-assistant-android",
                "X-Title": "Voice Assistant Android",
            },
            method="POST",
        )
        if certifi is None:
            raise RuntimeError("В APK отсутствует пакет certifi с корневыми сертификатами. Пересоберите приложение.")
        # Android Python builds do not consistently expose the system CA store to
        # urllib. certifi provides the public root CAs while TLS verification stays on.
        tls_context = ssl.create_default_context(cafile=certifi.where())
        try:
            with urlopen(request, timeout=120, context=tls_context) as response:
                data = json.loads(response.read(4_000_000))
        except Exception as exc:
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
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise RuntimeError("OpenRouter вернул ответ неверного формата")
        return message

    async def respond(self, messages, tools):
        return await asyncio.to_thread(self._request, messages, tools)
