from typing import Generator, List, Dict, Optional
from llm.base import BaseLLMProvider


class BaseAgent:
    """
    Core agent abstraction representing a single agent persona in the multi-agent architecture.
    
    Manages its own role, system prompt, conversation history, and interaction with an LLM backend.
    """

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        llm_provider: BaseLLMProvider
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.llm_provider = llm_provider
        self.history: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        """Appends a message to the agent's conversational memory."""
        self.history.append({"role": role, "content": content})

    def get_history(self) -> List[Dict[str, str]]:
        """Returns the current conversation history."""
        return list(self.history)

    def clear_history(self) -> None:
        """Clears conversational memory for this session."""
        self.history = []

    def _prepare_messages(self, user_input: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Prepares the full payload of messages to be sent to the LLM,
        including the system prompt and history.
        """
        messages: List[Dict[str, str]] = []
        
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
            
        messages.extend(self.history)
        
        if user_input is not None:
            messages.append({"role": "user", "content": user_input})
            
        return messages

    def send_message(self, user_input: str) -> str:
        """
        Synchronously sends a user message to the agent, receives the full response,
        updates internal history, and returns the response.
        """
        # Prepare context
        messages = self._prepare_messages(user_input)
        
        # Record user input in history
        self.add_message("user", user_input)
        
        # Call LLM backend
        response_text = self.llm_provider.chat(messages)
        
        # Record assistant response in history
        self.add_message("assistant", response_text)
        
        return response_text

    def stream_message(self, user_input: str) -> Generator[str, None, None]:
        """
        Streams response chunks from the LLM in real-time, accumulating the full
        response and updating internal history upon completion.
        """
        messages = self._prepare_messages(user_input)
        self.add_message("user", user_input)
        
        full_response_chunks = []
        for chunk in self.llm_provider.chat_stream(messages):
            full_response_chunks.append(chunk)
            yield chunk
            
        full_response = "".join(full_response_chunks)
        self.add_message("assistant", full_response)

