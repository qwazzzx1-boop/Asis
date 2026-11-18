import asyncio
import unittest

from voice_assistant.agent.service import AssistantService


class FakeTools:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def schemas(self):
        return []

    async def invoke(self, name, arguments):
        self.calls.append((name, arguments))
        if self.fail:
            raise ValueError("test rejection")
        return "tool result"


class SerialProvider:
    def __init__(self):
        self.active = 0
        self.max_active = 0

    async def respond(self, messages, tools):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return {"content": "ok"}


class ToolProvider:
    def __init__(self):
        self.calls = 0
        self.seen_tool_results = []

    async def respond(self, messages, tools):
        self.calls += 1
        self.seen_tool_results = [m for m in messages if m.get("role") == "tool"]
        if self.calls == 1:
            return {
                "content": "",
                "tool_calls": [{
                    "function": {"name": "echo", "arguments": {"value": "x"}}
                }],
            }
        return {"content": "done"}


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_requests_are_serialized(self):
        provider = SerialProvider()
        service = AssistantService(provider, FakeTools())
        results = await asyncio.gather(
            service.handle_text("first"),
            service.handle_text("second"),
        )
        self.assertEqual(results, ["ok", "ok"])
        self.assertEqual(provider.max_active, 1)

    async def test_tool_result_keeps_call_id(self):
        provider = ToolProvider()
        tools = FakeTools()
        service = AssistantService(provider, tools)
        self.assertEqual(await service.handle_text("run tool"), "done")
        tool_messages = [m for m in service.messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertTrue(tool_messages[0].get("tool_call_id"))
        self.assertEqual(tool_messages[0]["content"], "tool result")

    async def test_tool_error_is_returned_to_provider(self):
        provider = ToolProvider()
        service = AssistantService(provider, FakeTools(fail=True))
        self.assertEqual(await service.handle_text("run failing tool"), "done")
        tool_messages = [m for m in service.messages if m.get("role") == "tool"]
        self.assertIn("Ошибка инструмента", tool_messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
