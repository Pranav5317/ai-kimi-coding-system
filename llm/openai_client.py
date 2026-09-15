import json
import urllib.request
import urllib.error
from typing import Generator, List, Dict, Any, Tuple, Optional
from llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI-compatible LLM Provider.
    Works with OpenAI (gpt-4o, gpt-4o-mini), Groq, DeepSeek, and OpenAI-compatible API proxies.
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 300
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        self.timeout = timeout

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Send a list of messages to OpenAI chat completions endpoint.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0)
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                choice = res_json.get("choices", [{}])[0].get("message", {})
                
                content = choice.get("content") or ""
                tool_calls = choice.get("tool_calls", [])

                res_msg = {
                    "role": "assistant",
                    "content": content
                }
                if tool_calls:
                    res_msg["tool_calls"] = tool_calls

                return res_msg

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            return {
                "role": "assistant",
                "content": f"⚠️ OpenAI API Error ({e.code}): {err_body}"
            }
        except Exception as e:
            return {
                "role": "assistant",
                "content": f"⚠️ Connection error to OpenAI provider: {str(e)}"
            }

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        """
        Stream response tokens from OpenAI chat completions API.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "temperature": kwargs.get("temperature", 0.0)
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                for line in response:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_content = line_str[6:].strip()
                        if data_content == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_content)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
        except Exception as e:
            yield f"⚠️ Streaming error: {str(e)}"

    def health_check(self) -> Tuple[bool, str]:
        """
        Verifies API key validity by querying the models endpoint or attempting a test payload.
        """
        if not self.api_key:
            return False, "OpenAI API key is missing. Set OPENAI_API_KEY or multiAgent.apiKey in settings."

        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return True, f"Connected to OpenAI provider ({self.model_name})"
                return False, f"Unexpected response status: {response.status}"
        except urllib.error.HTTPError as e:
            return False, f"OpenAI authentication error ({e.code}): Check your API key."
        except Exception as e:
            return False, f"Unable to reach OpenAI provider: {str(e)}"

