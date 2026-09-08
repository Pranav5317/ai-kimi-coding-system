import unittest
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from agents.workspace_agent import WorkspaceAgent
from tools.filesystem import WorkspaceSandbox
from state import ProjectStateManager


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, fixed_response: str = "Test response") -> None:
        self.fixed_response = fixed_response
        self.tool_calls_sequence: List[Optional[List[Dict[str, Any]]]] = []

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if self.tool_calls_sequence:
            next_calls = self.tool_calls_sequence.pop(0)
            if next_calls:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": next_calls
                }
        return {
            "role": "assistant",
            "content": self.fixed_response,
            "tool_calls": None
        }

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any):
        yield self.fixed_response

    def health_check(self) -> Tuple[bool, str]:
        return True, "Mock LLM is ready."


class TestChatPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.temp_dir)
        self.sandbox = WorkspaceSandbox(workspace_root=self.workspace_root)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)
        self.llm = MockLLMProvider(fixed_response="I will inspect the codebase for you.")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_history_saved_on_message(self) -> None:
        agent = WorkspaceAgent(
            llm_provider=self.llm,
            sandbox=self.sandbox,
            state_manager=self.state_manager
        )
        agent.add_message("user", "Hello agent!")

        history_file = self.workspace_root / ".agent_chat_history.json"
        self.assertTrue(history_file.exists(), "History JSON file should be created on disk.")

        data = json.loads(history_file.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["role"], "user")
        self.assertEqual(data[0]["content"], "Hello agent!")

    def test_history_reloaded_on_init(self) -> None:
        history_file = self.workspace_root / ".agent_chat_history.json"
        pre_saved = [
            {"role": "user", "content": "What is the architecture?"},
            {"role": "assistant", "content": "The architecture is FastAPI backend with HTML frontend."}
        ]
        history_file.write_text(json.dumps(pre_saved), encoding="utf-8")

        agent = WorkspaceAgent(
            llm_provider=self.llm,
            sandbox=self.sandbox,
            state_manager=self.state_manager
        )

        self.assertEqual(len(agent.history), 2)
        self.assertEqual(agent.history[0]["content"], "What is the architecture?")
        self.assertEqual(agent.history[1]["content"], "The architecture is FastAPI backend with HTML frontend.")

    def test_history_persists_tool_executions(self) -> None:
        self.llm.tool_calls_sequence = [
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "list_files",
                        "arguments": {"path": "."}
                    }
                }
            ]
        ]

        agent = WorkspaceAgent(
            llm_provider=self.llm,
            sandbox=self.sandbox,
            state_manager=self.state_manager
        )

        res = agent.process_request("show me the files in this workspace")
        self.assertEqual(res, "I will inspect the codebase for you.")

        history_file = self.workspace_root / ".agent_chat_history.json"
        self.assertTrue(history_file.exists())
        data = json.loads(history_file.read_text(encoding="utf-8"))

        roles = [item["role"] for item in data]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)
        self.assertIn("tool", roles)

    def test_clear_history_persists_empty_list(self) -> None:
        agent = WorkspaceAgent(
            llm_provider=self.llm,
            sandbox=self.sandbox,
            state_manager=self.state_manager
        )
        agent.add_message("user", "Temporary message")
        history_file = self.workspace_root / ".agent_chat_history.json"
        self.assertTrue(history_file.exists())

        agent.clear_history()
        data = json.loads(history_file.read_text(encoding="utf-8"))
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
