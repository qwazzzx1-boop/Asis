import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from voice_assistant.config import Settings
from voice_assistant.agent.providers import OpenRouterProvider


class MobileDefaultsTests(unittest.TestCase):
    def test_new_install_defaults_to_openrouter(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings.load(Path(directory) / "missing.json")
        self.assertEqual(settings.provider, "openrouter")
        self.assertEqual(settings.model, "openai/gpt-4o-mini")

    def test_untouched_legacy_ollama_defaults_are_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({
                "provider": "ollama",
                "model": "qwen2.5:7b",
                "ollama_url": "http://192.168.0.100:11434",
            }), encoding="utf-8")
            settings = Settings.load(path)
        self.assertEqual(settings.provider, "openrouter")
        self.assertEqual(settings.model, "openai/gpt-4o-mini")

    def test_explicit_custom_ollama_settings_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({
                "provider": "ollama",
                "model": "llama3",
                "ollama_url": "http://10.0.0.5:11434",
            }), encoding="utf-8")
            settings = Settings.load(path)
        self.assertEqual(settings.provider, "ollama")
        self.assertEqual(settings.model, "llama3")


class OpenRouterTlsTests(unittest.TestCase):
    @patch("voice_assistant.agent.providers.urlopen")
    def test_openrouter_uses_verified_certifi_context_and_official_endpoint(self, mocked_urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}]
        }).encode("utf-8")
        mocked_urlopen.return_value = response

        provider = OpenRouterProvider("test-key", "openai/gpt-4o-mini")
        result = provider._request([{"role": "user", "content": "hello"}], [])

        self.assertEqual(result["content"], "ok")
        args, kwargs = mocked_urlopen.call_args
        self.assertEqual(args[0].full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertIsNotNone(kwargs.get("context"))
        self.assertEqual(args[0].get_header("Authorization"), "Bearer test-key")


if __name__ == "__main__":
    unittest.main()
