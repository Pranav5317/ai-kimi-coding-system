import unittest
from typing import List, Dict, Any, Optional, Generator
from llm.router import LLMRouter
from llm.base import BaseLLMProvider


class DummyProvider(BaseLLMProvider):
    def __init__(self, provider_name: str, model_name: str):
        self._provider_name = provider_name
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, **kwargs: Any) -> Dict[str, Any]:
        return {"role": "assistant", "content": f"Response from {self._provider_name}:{self.model_name}"}

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        yield f"Response from {self._provider_name}:{self.model_name}"

    def health_check(self):
        return True, "OK"


class TestLLMRouter(unittest.TestCase):
    def test_llm_router_fallback(self):
        default_p = DummyProvider("ollama", "qwen3-coder:latest")
        router = LLMRouter(default_provider=default_p)

        provider = router.get_agent_llm("agent1")
        self.assertEqual(provider.provider_name, "ollama")
        self.assertEqual(provider.model_name, "qwen3-coder:latest")

        p_name, m_name = router.get_agent_model_info("agent1")
        self.assertEqual(p_name, "ollama")
        self.assertEqual(m_name, "qwen3-coder:latest")

    def test_llm_router_custom_agent_override(self):
        default_p = DummyProvider("ollama", "qwen3-coder:latest")
        router = LLMRouter(default_provider=default_p)

        agent2_provider = DummyProvider("anthropic", "claude-3-5-sonnet-20241022")
        router._agent_providers["agent2"] = agent2_provider
        router._agent_configs["agent2"] = ("anthropic", "claude-3-5-sonnet-20241022")

        # Agent 1 still uses fallback
        p1 = router.get_agent_llm("agent1")
        self.assertEqual(p1.provider_name, "ollama")

        # Agent 2 uses custom model
        p2 = router.get_agent_llm("agent2")
        self.assertEqual(p2.provider_name, "anthropic")
        self.assertEqual(p2.model_name, "claude-3-5-sonnet-20241022")


