from typing import Optional
from config import config
from llm.base import BaseLLMProvider
from llm.ollama_client import OllamaProvider
from llm.openai_client import OpenAIProvider


def get_llm_provider(
    provider_type: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> BaseLLMProvider:
    """
    Factory method to instantiate the requested LLM provider.
    Supports 'ollama', 'openai', 'groq', 'deepseek', and 'anthropic'.
    """
    p_type = (provider_type or config.llm_provider or "ollama").lower()
    m_name = model_name or config.default_model or "qwen3-coder:latest"
    key = api_key if api_key is not None else config.api_key
    url = base_url if base_url is not None else config.api_base_url

    if p_type in ["openai", "groq", "deepseek", "anthropic"]:
        default_url = "https://api.openai.com/v1"
        if p_type == "groq":
            default_url = "https://api.groq.com/openai/v1"
        elif p_type == "deepseek":
            default_url = "https://api.deepseek.com"

        target_url = url if url else default_url
        target_model = m_name
        if p_type == "openai" and m_name.startswith("qwen"):
            target_model = "gpt-4o"
        elif p_type == "groq" and m_name.startswith("qwen"):
            target_model = "llama-3.3-70b-versatile"

        return OpenAIProvider(
            api_key=key or "",
            model_name=target_model,
            base_url=target_url,
            timeout=config.llm_timeout or 300
        )
    else:
        # Default to OllamaProvider
        return OllamaProvider(
            base_url=config.ollama_base_url or "http://localhost:11434",
            model=m_name,
            default_temperature=config.temperature or 0.0,
            num_ctx=config.num_ctx or 8192,
            timeout=config.llm_timeout or 300
        )
