from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, Awaitable, Callable

from voice_assistant.security.policy import ApprovalGate, RiskLevel
from voice_assistant.security.audit import AuditLog


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    risk: RiskLevel
    handler: Callable[..., Awaitable[Any]]


class PluginRegistry:
    def __init__(self, gate: ApprovalGate, audit: AuditLog):
        self.gate, self.audit = gate, audit
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or spec.name in self._tools:
            raise ValueError(f"Duplicate or empty tool name: {spec.name!r}")
        if not isinstance(spec.parameters, dict) or spec.parameters.get("type") != "object":
            raise ValueError(f"Tool {spec.name} must use an object JSON schema")
        self._tools[spec.name] = spec

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {"type": "function", "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }}
            for t in self._tools.values()
        ]

    @staticmethod
    def _validate_arguments(tool: ToolSpec, arguments: Any) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError("Аргументы инструмента должны быть JSON-объектом")

        schema = tool.parameters
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if not isinstance(properties, dict) or not isinstance(required, list):
            raise ValueError(f"Некорректная JSON Schema у инструмента {tool.name}")

        missing = [key for key in required if key not in arguments]
        if missing:
            raise ValueError("Не хватает обязательных аргументов: " + ", ".join(missing))

        unknown = set(arguments) - set(properties)
        if unknown:
            raise ValueError("Неизвестные аргументы: " + ", ".join(sorted(unknown)))

        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for key, value in arguments.items():
            definition = properties.get(key, {})
            expected = definition.get("type") if isinstance(definition, dict) else None
            py_type = type_map.get(expected)
            if py_type is not None:
                # bool is a subclass of int in Python; do not accept it as a number.
                if expected in ("integer", "number") and isinstance(value, bool):
                    raise ValueError(f"Аргумент {key!r} имеет неверный тип")
                if not isinstance(value, py_type):
                    raise ValueError(f"Аргумент {key!r} должен иметь тип {expected}")
            if expected == "string":
                if "maxLength" in definition and len(value) > definition["maxLength"]:
                    raise ValueError(f"Аргумент {key!r} слишком длинный")
                if "minLength" in definition and len(value) < definition["minLength"]:
                    raise ValueError(f"Аргумент {key!r} слишком короткий")
        return arguments

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        confirmed: bool = False,
    ) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Неизвестный инструмент: {name}")

        try:
            safe_arguments = self._validate_arguments(tool, arguments)
            summary = f"{name}: " + ", ".join(
                f"{k}={str(v)[:180]}" for k, v in safe_arguments.items()
            )
            await self.gate.check(summary[:700], tool.risk, confirmed=confirmed)

            result = tool.handler(**safe_arguments)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            self.audit.record(name, "failed", detail=type(exc).__name__)
            raise

        self.audit.record(name, "completed")
        return result
