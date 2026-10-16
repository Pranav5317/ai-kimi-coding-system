import unittest
from agents.workspace_agent import WorkspaceAgent
from llm.base import BaseLLMProvider


class MockLLM(BaseLLMProvider):
    def __init__(self):
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def chat(self, messages, tools=None, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            # First turn: returns a teaser promising action but no tool call
            return {"role": "assistant", "content": "Let me update the JavaScript file:"}
        elif self.call_count == 2:
            # Second turn: returns the actual tool execution call
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "create_file",
                            "arguments": {"path": "frontend/script.js", "content": "console.log('Fixed');"}
                        }
                    }
                ]
            }
        else:
            # Third turn: final text answer
            return {"role": "assistant", "content": "Successfully updated frontend/script.js."}

    def chat_stream(self, messages, **kwargs):
        yield "mock"

    def health_check(self):
        return True, "OK"


class TestUnfulfilledPromise(unittest.TestCase):
    def test_auto_continuation_on_unfulfilled_promise(self):
        mock_llm = MockLLM()
        agent = WorkspaceAgent(llm_provider=mock_llm)

        res = agent.process_request("Fix the frontend script")

        # Verify that the agent auto-continued past the teaser and executed the tool call
        self.assertEqual(mock_llm.call_count, 3)
        self.assertTrue((agent.sandbox.workspace_root / "frontend/script.js").exists())


if __name__ == "__main__":
    unittest.main()
