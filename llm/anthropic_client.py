import json
import urllib.request
import urllib.error
from typing import Generator, List, Dict, Any, Tuple, Optional
from llm.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """
    Native Anthropic Claude 3.5 Sonnet LLM Provider using Anthropic Messages API.
    Provides elite multi-file software engineering performance for cloud users.
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com/v1",
        timeout: int = 300
    ):
        self.api_key = api_key
        self.model_name = model_name or "claude-3-5-sonnet-20241022"
        self.base_url = base_url.rstrip("/") if base_url else "https://api.anthropic.com/v1"
        self.timeout = timeout

    def _convert_tools_to_anthropic(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        anthropic_tools = []
        for t in tools:
            fn = t.get("function", t)
            anthropic_tools.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}})
            })
        return anthropic_tools

    def _convert_messages_to_anthropic(self, messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        system_prompt = ""
        formatted_msgs: List[Dict[str, Any]] = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")

            if role == "system":
                system_prompt += f"{content}\n"
            elif role in ("user", "assistant"):
                formatted_msgs.append({
                    "role": role,
                    "content": content or "Proceeding with task."
                })
            elif role == "tool":
                # Convert tool output into assistant/user message for Claude
                tool_name = m.get("name", "tool")
                formatted_msgs.append({
                    "role": "user",
                    "content": f"[Tool Output - {tool_name}]: {content}"
                })

        return system_prompt.strip(), formatted_msgs

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Sends messages to Anthropic Messages endpoint.
        """
        url = f"{self.base_url}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        system_prompt, ant_messages = self._convert_messages_to_anthropic(messages)
        ant_tools = self._convert_tools_to_anthropic(tools)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": ant_messages
        }

        if system_prompt:
            payload["system"] = system_prompt
        if ant_tools:
            payload["tools"] = ant_tools

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                blocks = res_json.get("content", [])

                text_parts = []
                tool_calls = []

                for block in blocks:
                    b_type = block.get("type")
                    if b_type == "text":
                        text_parts.append(block.get("text", ""))
                    elif b_type == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "function": {
                                "name": block.get("name"),
                                "arguments": block.get("input", {})
                            }
                        })

                res_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": "\n".join(text_parts)
                }
                if tool_calls:
                    res_msg["tool_calls"] = tool_calls

                return res_msg

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            return {
                "role": "assistant",
                "content": f"⚠️ Anthropic API Error ({e.code}): {err_body}"
            }
        except Exception as e:
            return {
                "role": "assistant",
                "content": f"⚠️ Connection error to Anthropic Claude: {str(e)}"
            }

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        """
        Simple text fallback generator for Anthropic streaming.
        """
        res = self.chat(messages, **kwargs)
        yield res.get("content", "")

    def health_check(self) -> Tuple[bool, str]:
        """
        Checks if Anthropic API key is valid.
        """
        if not self.api_key:
            return False, "Anthropic API Key missing. Set OPENAI_API_KEY / multiAgent.apiKey in settings."

        res = self.chat([{"role": "user", "content": "Hi"}], max_tokens=10)
        content = res.get("content", "")
        if "⚠️ Anthropic API Error" in content:
            return False, content
        return True, f"Connected to Anthropic Claude ({self.model_name})"

