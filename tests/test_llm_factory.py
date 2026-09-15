import unittest
from llm.factory import get_llm_provider
from llm.ollama_client import OllamaProvider
from llm.openai_client import OpenAIProvider


class TestLLMFactory(unittest.TestCase):

    def test_default_ollama_provider(self):
        provider = get_llm_provider(provider_type="ollama", model_name="qwen3-coder:latest")
        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.model, "qwen3-coder:latest")

    def test_openai_provider(self):
        provider = get_llm_provider(provider_type="openai", api_key="sk-test", model_name="gpt-4o")
        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(provider.model_name, "gpt-4o")
        self.assertEqual(provider.api_key, "sk-test")

    def test_groq_provider(self):
        provider = get_llm_provider(provider_type="groq", api_key="gsk-test", model_name="llama-3.3-70b-versatile")
        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(provider.base_url, "https://api.groq.com/openai/v1")
        self.assertEqual(provider.model_name, "llama-3.3-70b-versatile")


if __name__ == "__main__":
    unittest.main()
