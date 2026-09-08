from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Any, Tuple, Optional


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM backends (Ollama, Kimi K2, OpenAI API, etc.).
    
    This ensures agents interact with language models through a standard contract,
    supporting function/tool calling and zero-code-change provider swapping.
    """

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Send a list of chat messages to the model (with optional tools) and return
        the model's response message dictionary containing 'content' and optional 'tool_calls'.
        
        Args:
            messages: List of message dictionaries ('role', 'content', etc.)
            tools: Optional list of tool/function schema definitions
            **kwargs: Provider-specific inference parameters.
        
        Returns:
            Dict containing at least {'role': 'assistant', 'content': '...', 'tool_calls': [...]}
        """
        pass

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        """
        Send a list of chat messages and stream text chunks as they arrive (when no tools are needed).
        """
        pass

    @abstractmethod
    def health_check(self) -> Tuple[bool, str]:
        """
        Check if the LLM backend is accessible and the configured model is available.
        
        Returns:
            Tuple of (is_healthy: bool, message: str).
        """
        pass
