import unittest
import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from tools.filesystem import WorkspaceSandbox
from agents.workspace_agent import WorkspaceAgent
from state import ProjectStateManager


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, fixed_response: str = "Code files updated successfully.") -> None:
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
        return True, "Mock LLM ready"


class TestChangeTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.temp_dir)
        self.sandbox = WorkspaceSandbox(workspace_root=self.workspace_root)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)
        self.llm = MockLLMProvider()
        self.sandbox.clear_tracked_changes()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_create_file_records_new_change(self) -> None:
        res = self.sandbox.create_file("test_app.py", "print('hello world')\n")
        self.assertIn("created successfully", res)
        self.assertEqual(len(self.sandbox.tracked_changes), 1)

        change = self.sandbox.tracked_changes[0]
        self.assertEqual(change["action"], "NEW")
        self.assertEqual(change["added"], 1)
        self.assertIn("print('hello world')", change["diff"])

    def test_02_edit_file_records_modify_change(self) -> None:
        self.sandbox.create_file("test_app.py", "line 1\nline 2\n")
        self.sandbox.clear_tracked_changes()

        self.sandbox.edit_file("test_app.py", "line 1\nline 2 modified\nline 3\n")
        self.assertEqual(len(self.sandbox.tracked_changes), 1)

        change = self.sandbox.tracked_changes[0]
        self.assertEqual(change["action"], "MODIFY")
        self.assertGreater(change["added"], 0)
        self.assertIn("-line 2", change["diff"])
        self.assertIn("+line 2 modified", change["diff"])

    def test_03_write_changes_log_file(self) -> None:
        self.sandbox.create_file("app.py", "def main(): pass\n")
        log_path = self.sandbox.write_changes_log()

        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        self.assertIn("# Project Code Changes Log", content)
        self.assertIn("🟢 `[NEW]`", content)
        self.assertIn("```diff", content)

    def test_04_agent5_response_appends_changes_summary(self) -> None:
        self.llm.tool_calls_sequence = [
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "create_file",
                        "arguments": {"path": "main.py", "content": "print('start')\n"}
                    }
                }
            ]
        ]

        agent = WorkspaceAgent(
            llm_provider=self.llm,
            sandbox=self.sandbox,
            state_manager=self.state_manager
        )

        response = agent.process_request("Create main.py")
        self.assertIn("Code Changes Summary", response)
        self.assertIn("🟢 `[NEW]`", response)
        self.assertIn("CHANGES_LOG.md", response)

        changes_log = self.workspace_root / "CHANGES_LOG.md"
        self.assertTrue(changes_log.exists())


if __name__ == "__main__":
    unittest.main()
