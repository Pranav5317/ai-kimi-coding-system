import json
from typing import Generator, List, Dict, Any, Tuple, Optional
import requests

from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """
    Ollama LLM Provider implementation using Ollama's HTTP REST API.
    Supports native tool/function calling and real-time streaming.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3-coder:latest",
        default_temperature: float = 0.2,
        num_ctx: int = 8192,
        timeout: int = 300
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.default_temperature = default_temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.chat_endpoint = f"{self.base_url}/api/chat"
        self.tags_endpoint = f"{self.base_url}/api/tags"

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.model

    def health_check(self) -> Tuple[bool, str]:
        """
        Verifies if Ollama is running and whether the specified model is installed.
        """
        try:
            response = requests.get(self.tags_endpoint, timeout=3.0)
            if response.status_code != 200:
                return False, f"Ollama returned HTTP status {response.status_code}."

            data = response.json()
            available_models = [m.get("name", "") for m in data.get("models", [])]
            
            # Check model name match (exact or prefix match e.g. 'llama3.1:latest' or 'llama3.1')
            model_found = any(
                self.model == m or self.model == m.split(":")[0] or m.startswith(self.model)
                for m in available_models
            )

            if not model_found:
                models_str = ", ".join(available_models) if available_models else "None"
                return False, (
                    f"Model '{self.model}' not found in Ollama.\n"
                    f"Installed models: {models_str}\n"
                    f"Run `ollama pull {self.model}` in your terminal to download it."
                )

            return True, f"Connected to Ollama. Model '{self.model}' is ready."

        except requests.exceptions.ConnectionError:
            return False, (
                f"Could not connect to Ollama at {self.base_url}.\n"
                "Please make sure Ollama is running (`ollama serve` or start Ollama app)."
            )
        except requests.exceptions.Timeout:
            return False, f"Connection to Ollama timed out at {self.base_url}."
        except Exception as e:
            return False, f"Unexpected error while checking Ollama health: {str(e)}"

    @staticmethod
    def _sanitize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sanitizes pseudo-XML tags (<parameter...>, </parameter>, <function...>, </function>) in message content
        to prevent Ollama's Go XML tool parser from throwing 500 XML syntax errors.
        """
        sanitized = []
        for msg in messages:
            msg_copy = dict(msg)
            content = msg_copy.get("content")
            if isinstance(content, str) and content:
                content = content.replace("<parameter", "&lt;parameter")
                content = content.replace("</parameter>", "&lt;/parameter&gt;")
                content = content.replace("<function", "&lt;function")
                content = content.replace("</function>", "&lt;/function&gt;")
                msg_copy["content"] = content
            sanitized.append(msg_copy)
        return sanitized

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Sends chat request to Ollama with optional tool definitions and returns the model message object.
        Supports automatic retry if Ollama's local runner is cold-starting or recovering from a 500 error.
        """
        clean_messages = self._sanitize_messages(messages)
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": clean_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.default_temperature),
                "num_ctx": kwargs.get("num_ctx", self.num_ctx)
            }
        }
        if tools:
            payload["tools"] = tools

        req_timeout = kwargs.get("timeout", self.timeout)
        max_retries = kwargs.get("max_retries", 3)

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(self.chat_endpoint, json=payload, timeout=req_timeout)
                response.raise_for_status()
                data = response.json()
                msg = data.get("message", {})
                return {
                    "role": msg.get("role", "assistant"),
                    "content": msg.get("content", ""),
                    "tool_calls": msg.get("tool_calls", None)
                }
            except (requests.exceptions.ReadTimeout, requests.exceptions.Timeout):
                if attempt < max_retries:
                    import time
                    time.sleep(2.0)
                    continue
                raise TimeoutError(
                    f"Local Ollama model '{self.model}' timed out after {req_timeout}s. "
                    "Your local GPU/CPU might be overloaded, un-loading VRAM, or processing a very large prompt context. "
                    "Please retry your query or check your local Ollama status ('ollama ps')."
                )
            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    import time
                    time.sleep(2.0)
                    continue
                raise ConnectionError(f"Failed to reach Ollama at {self.chat_endpoint}. Is Ollama running?")
            except requests.exceptions.HTTPError as e:
                # Handle Ollama 500 internal runner / tokenize cold-start errors automatically
                if e.response.status_code == 500 and attempt < max_retries:
                    import time
                    time.sleep(2.0)
                    continue
                raise RuntimeError(f"Ollama API error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                if attempt < max_retries:
                    import time
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"Failed to generate response: {str(e)}")

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        """
        Streams response tokens directly from Ollama as newline-delimited JSON.
        """
        clean_messages = self._sanitize_messages(messages)
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": clean_messages,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.default_temperature),
                "num_ctx": kwargs.get("num_ctx", self.num_ctx)
            }
        }

        try:
            with requests.post(self.chat_endpoint, json=payload, stream=True, timeout=kwargs.get("timeout", 120)) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line.decode("utf-8"))
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done", False):
                            break
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Failed to reach Ollama at {self.chat_endpoint}. Is Ollama running?")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama API stream error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"Stream error: {str(e)}")
