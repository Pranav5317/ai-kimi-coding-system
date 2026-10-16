import os
from typing import Dict, Optional, Tuple
from config import config
from llm.base import BaseLLMProvider
from llm.factory import get_llm_provider


class LLMRouter:
    """
    Multi-Model LLM Router managing per-agent model assignments and provider caching.
    Supports assigning distinct providers and models (e.g. Anthropic, OpenAI, DeepSeek, Groq, Ollama)
    to individual specialized agents (Agent 1 through Agent 5).
    """

    def __init__(self, default_provider: Optional[BaseLLMProvider] = None) -> None:
        self._default_provider = default_provider or get_llm_provider()
        self._agent_providers: Dict[str, BaseLLMProvider] = {}
        self._agent_configs: Dict[str, Tuple[str, str]] = {}

    def register_agent_llm(
        self,
        agent_id: str,
        provider_type: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> BaseLLMProvider:
        """
        Explicitly registers or overrides a custom LLM provider for a specific agent ID.
        """
        clean_id = agent_id.strip().lower()
        p_type = provider_type or getattr(config, f"{clean_id}_llm_provider", None) or config.llm_provider
        m_name = model_name or getattr(config, f"{clean_id}_llm_model", None) or config.default_model

        provider_instance = get_llm_provider(
            provider_type=p_type,
            model_name=m_name,
            api_key=api_key,
            base_url=base_url
        )
        self._agent_providers[clean_id] = provider_instance
        self._agent_configs[clean_id] = (provider_instance.provider_name, provider_instance.model_name)
        return provider_instance

    def get_agent_llm(self, agent_id: str) -> BaseLLMProvider:
        """
        Retrieves the configured LLM provider for the given agent ID.
        If no custom provider is configured, checks environment overrides, then falls back to default.
        """
        clean_id = agent_id.strip().lower()
        if clean_id in self._agent_providers:
            return self._agent_providers[clean_id]

        # Check environment or AppConfig overrides for this agent
        env_provider = os.getenv(f"{clean_id.upper()}_LLM_PROVIDER") or getattr(config, f"{clean_id}_llm_provider", None)
        env_model = os.getenv(f"{clean_id.upper()}_LLM_MODEL") or getattr(config, f"{clean_id}_llm_model", None)

        if env_provider or env_model:
            return self.register_agent_llm(
                agent_id=clean_id,
                provider_type=env_provider,
                model_name=env_model
            )

        return self._default_provider

    def get_agent_model_info(self, agent_id: str) -> Tuple[str, str]:
        """
        Returns (provider_name, model_name) for a given agent ID.
        """
        clean_id = agent_id.strip().lower()
        if clean_id in self._agent_configs:
            return self._agent_configs[clean_id]
        
        provider = self.get_agent_llm(clean_id)
        p_name = getattr(provider, "provider_name", getattr(provider, "name", "ollama"))
        m_name = getattr(provider, "model_name", getattr(provider, "model", config.default_model or "qwen3-coder:latest"))
        return str(p_name), str(m_name)

