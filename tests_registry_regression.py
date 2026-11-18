import tempfile
import unittest
from pathlib import Path

from voice_assistant.security.policy import ApprovalGate, RiskLevel, ApprovalRequired
from voice_assistant.plugins.base import PluginRegistry, ToolSpec
from voice_assistant.security.audit import AuditLog


class RegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_forbidden_is_never_approved(self):
        async def approve(_):
            return True

        gate = ApprovalGate(approve)
        with self.assertRaises(ApprovalRequired):
            await gate.check("blocked", RiskLevel.FORBIDDEN)

    async def test_unknown_argument_is_rejected(self):
        async def approve(_):
            return True

        async def handler(value):
            return value

        with tempfile.TemporaryDirectory() as temp:
            gate = ApprovalGate(approve)
            audit = AuditLog(Path(temp) / "audit.jsonl")
            registry = PluginRegistry(gate, audit)
            registry.register(ToolSpec(
                "echo",
                "test",
                {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
                RiskLevel.SAFE,
                handler,
            ))
            with self.assertRaises(ValueError):
                await registry.invoke("echo", {"value": "ok", "extra": "no"})


if __name__ == "__main__":
    unittest.main()
