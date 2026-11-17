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
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool: {spec.name}")
        self._tools[spec.name] = spec

    def schemas(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in self._tools.values()]

    async def invoke(self, name: str, arguments: dict[str, Any], *, confirmed: bool = False) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        try:
            summary = f"{name}: " + ", ".join(f"{k}={str(v)[:300]}" for k, v in arguments.items())
            await self.gate.check(summary[:700], tool.risk, confirmed=confirmed)
            result = tool.handler(**arguments)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            self.audit.record(name, "failed", detail=type(exc).__name__)
            raise
        self.audit.record(name, "completed")
        return result
