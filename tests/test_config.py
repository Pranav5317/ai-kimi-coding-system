import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import AppConfig
from llm.ollama_client import OllamaProvider


class TestConfigAndModelSelection(unittest.TestCase):
    """
    Tests for AppConfig model selection and OllamaProvider model handling.
    """

    def test_01_default_model_is_qwen3_coder(self):
        # When no env vars are set
        with patch.dict(os.environ, {}, clear=True):
            cfg = AppConfig()
            self.assertEqual(cfg.default_model, "qwen3-coder:latest")

    def test_02_model_override_via_llm_model_env(self):
        with patch.dict(os.environ, {"LLM_MODEL": "custom-model:latest"}, clear=True):
            cfg = AppConfig()
            self.assertEqual(cfg.default_model, "custom-model:latest")

    def test_03_model_override_via_model_name_env(self):
        with patch.dict(os.environ, {"MODEL_NAME": "qwen2.5-coder:7b"}, clear=True):
            cfg = AppConfig()
            self.assertEqual(cfg.default_model, "qwen2.5-coder:7b")

    def test_04_ollama_provider_default_model(self):
        provider = OllamaProvider()
        self.assertEqual(provider.model, "qwen3-coder:latest")

    def test_05_ollama_provider_explicit_model(self):
        provider = OllamaProvider(model="custom-qwen:8b")
        self.assertEqual(provider.model, "custom-qwen:8b")

    @patch("requests.post")
    def test_06_ollama_provider_sends_configured_model(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Test response",
                "tool_calls": None
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        provider = OllamaProvider(model="qwen3:8b")
        messages = [{"role": "user", "content": "Hello"}]
        res = provider.chat(messages)

        self.assertEqual(res["content"], "Test response")
        # Verify the payload sent to Ollama API contained model="qwen3:8b"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertIn("json", kwargs)
        self.assertEqual(kwargs["json"]["model"], "qwen3:8b")


if __name__ == "__main__":
    unittest.main()

