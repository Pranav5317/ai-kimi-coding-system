import unittest
import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from state.project_state import (
    ProjectStateManager,
    PROJECT_STATE_TOOLS,
    DEFAULT_PROJECT_STATE_TEMPLATE,
    CANONICAL_SECTIONS
)
from tools.filesystem import WorkspaceSandbox
from tools.server_manager import DevServerManager
from diary.code_diary import CodeDiary
from agents.workspace_agent import WorkspaceAgent, ALL_WORKSPACE_TOOLS
from orchestration import (
    MessageType,
    AgentMessage,
    Orchestrator
)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for ProjectStateManager and LLM tool calling tests.
    """

    def __init__(self, fixed_response: str = "State reasoning complete.") -> None:
        self.fixed_response = fixed_response
        self.received_messages: List[List[Dict[str, Any]]] = []
        self.tool_calls_sequence: List[Optional[List[Dict[str, Any]]]] = []

    def set_tool_calls_sequence(self, sequence: List[Optional[List[Dict[str, Any]]]]) -> None:
        self.tool_calls_sequence = list(sequence)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        self.received_messages.append(messages)
        if self.tool_calls_sequence:
            calls = self.tool_calls_sequence.pop(0)
            if calls:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": calls
                }
        return {
            "role": "assistant",
            "content": self.fixed_response,
            "tool_calls": None
        }

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        yield self.fixed_response

    def health_check(self) -> Tuple[bool, str]:
        return True, "Mock LLM is ready."


class TestProjectState(unittest.TestCase):
    """
    Deterministic unit tests for ProjectStateManager, PROJECT_STATE.md persistence,
    and LLM tool-calling integration in Agent 5.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="project_state_test_")
        self.workspace_root = Path(self.test_dir) / "workspace"
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.diary_file = Path(self.test_dir) / "CODE_DIARY.md"

        self.diary = CodeDiary(self.diary_file)
        self.sandbox = WorkspaceSandbox(self.workspace_root, diary=self.diary)
        self.server_manager = DevServerManager(workspace_root=self.workspace_root, diary=self.diary)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)
        self.orchestrator = Orchestrator()
        self.mock_llm = MockLLMProvider("State operation finished.")

        self.agent5 = WorkspaceAgent(
            llm_provider=self.mock_llm,
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            server_manager=self.server_manager,
            state_manager=self.state_manager,
            orchestrator=self.orchestrator
        )

        self.orchestrator.register_agent(
            agent_id=self.agent5.agent_id,
            role=self.agent5.role,
            capabilities=self.agent5.capabilities,
            handler=self.agent5.handle_agent_message
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Initialization Test
    def test_01_initialize_project_state(self):
        state_file = self.workspace_root / "PROJECT_STATE.md"
        self.assertTrue(state_file.exists())
        content = state_file.read_text(encoding="utf-8")
        self.assertIn("# Project State", content)
        for section in CANONICAL_SECTIONS:
            self.assertIn(f"## {section}", content)

    # 2. Read State (Full and Section-Specific)
    def test_02_read_project_state(self):
        # Read full state
        full_state = self.state_manager.read_state()
        self.assertIn("# Project State", full_state)
        self.assertIn("## Technology Stack", full_state)

        # Read specific section
        sec = self.state_manager.read_state("User Requirements")
        self.assertIn("## User Requirements", sec)
        self.assertIn("No user requirements recorded yet", sec)

        # Read section via alias / normalized key
        tech_sec = self.state_manager.read_state("tech_stack")
        self.assertIn("## Technology Stack", tech_sec)

    # 3. Update State Preserving Existing Sections
    def test_03_update_project_state_preserves_other_sections(self):
        res = self.state_manager.update_state(
            tech_stack="Python 3.11, Flask, SQLite",
            user_requirements="1. User authentication\n2. Product catalog"
        )
        self.assertIn("Project state successfully updated", res)

        state_content = (self.workspace_root / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("Python 3.11, Flask, SQLite", state_content)
        self.assertIn("1. User authentication", state_content)
        # Verify untouched section remains intact
        self.assertIn("## Architecture", state_content)
        self.assertIn("No architecture defined yet", state_content)

    # 4. Context Compaction State Recovery
    def test_04_state_recovery_after_context_compaction(self):
        # Initial turn: writes state
        self.state_manager.update_state(
            project_overview="E-commerce shopping application",
            tech_stack="FastAPI + React + PostgreSQL",
            important_decisions="Use JWT for authentication"
        )

        # Simulate context compaction: wipe in-memory conversation history
        self.agent5.clear_history()
        self.assertEqual(len(self.agent5.get_history()), 0)

        # Agent reads state from disk and reconstructs project knowledge
        state_read = self.state_manager.read_state()
        self.assertIn("E-commerce shopping application", state_read)
        self.assertIn("FastAPI + React + PostgreSQL", state_read)
        self.assertIn("Use JWT for authentication", state_read)

    # 5. Missing / Invalid Section Lookup Handled Gracefully
    def test_05_missing_section_handled_gracefully(self):
        res = self.state_manager.read_state("NonExistentSection")
        self.assertIn("not found in PROJECT_STATE.md", res)

    # 6. Sandbox Traversal Protection
    def test_06_sandbox_traversal_protection(self):
        # Attempting to read outside workspace fails
        with self.assertRaises(PermissionError):
            self.sandbox.validate_and_resolve("../PROJECT_STATE.md")

    # 7. LLM Tool Definitions Expose State Tools
    def test_07_llm_tools_include_state_tools(self):
        tool_names = [t["function"]["name"] for t in ALL_WORKSPACE_TOOLS]
        self.assertIn("read_project_state", tool_names)
        self.assertIn("update_project_state", tool_names)
        self.assertIn("delegate_task", tool_names)
        self.assertIn("create_file", tool_names)

    # 8. LLM Tool Call: read_project_state
    def test_08_llm_tool_call_read_project_state(self):
        self.state_manager.update_state(tech_stack="Flask + SQLite")

        self.mock_llm.set_tool_calls_sequence([
            [
                {
                    "id": "read_state_call",
                    "function": {
                        "name": "read_project_state",
                        "arguments": {"section": "Technology Stack"}
                    }
                }
            ],
            None  # Second turn produces final answer
        ])

        executed = []
        def tool_cb(name, args, res):
            executed.append((name, args, res))

        resp = self.agent5.process_request("What tech stack are we using?", on_tool_call=tool_cb)
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0][0], "read_project_state")
        self.assertIn("Flask + SQLite", executed[0][2])

    # 9. LLM Tool Call: update_project_state
    def test_09_llm_tool_call_update_project_state(self):
        self.mock_llm.set_tool_calls_sequence([
            [
                {
                    "id": "update_state_call",
                    "function": {
                        "name": "update_project_state",
                        "arguments": {
                            "project_overview": "Real-time analytics dashboard",
                            "current_tasks": "Implement WebSocket stream"
                        }
                    }
                }
            ],
            None
        ])

        executed = []
        def tool_cb(name, args, res):
            executed.append((name, args, res))

        resp = self.agent5.process_request("Update project state with overview and tasks", on_tool_call=tool_cb)
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0][0], "update_project_state")

        # Verify persisted on disk
        saved = (self.workspace_root / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("Real-time analytics dashboard", saved)
        self.assertIn("Implement WebSocket stream", saved)

    # 10. Multi-Step Full Flow: read_state -> delegate_task -> receive result -> update_state
    def test_10_multi_step_state_read_delegate_update_flow(self):
        # 1. Register Agent 3 (Data Manager)
        def a3_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("CREATE TABLE products (id INT PRIMARY KEY, name VARCHAR(100), price DECIMAL(10,2));")

        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema", "migrations"},
            handler=a3_handler
        )

        # 2. Set initial project state
        self.state_manager.update_state(
            project_overview="Online Store",
            tech_stack="Python/Flask + SQLite",
            current_tasks="1. Create database schema for products"
        )

        # 3. Simulate multi-step LLM tool sequence:
        # Step 1: read_project_state
        # Step 2: delegate_task to agent3 for product schema
        # Step 3: create_file database/schema.sql
        # Step 4: update_project_state with completed tasks
        # Step 5: final response
        self.mock_llm.set_tool_calls_sequence([
            [
                {
                    "id": "step1_read_state",
                    "function": {
                        "name": "read_project_state",
                        "arguments": {"section": "current_tasks"}
                    }
                }
            ],
            [
                {
                    "id": "step2_delegate",
                    "function": {
                        "name": "delegate_task",
                        "arguments": {
                            "target_agent": "agent3",
                            "task": "Create product table schema"
                        }
                    }
                }
            ],
            [
                {
                    "id": "step3_create_file",
                    "function": {
                        "name": "create_file",
                        "arguments": {
                            "path": "database/schema.sql",
                            "content": "CREATE TABLE products (id INT PRIMARY KEY, name VARCHAR(100), price DECIMAL(10,2));"
                        }
                    }
                }
            ],
            [
                {
                    "id": "step4_update_state",
                    "function": {
                        "name": "update_project_state",
                        "arguments": {
                            "completed_tasks": "1. Products database schema designed and saved",
                            "current_tasks": "2. Build backend API endpoints"
                        }
                    }
                }
            ],
            None  # Final text turn
        ])

        tool_log = []
        def tool_cb(name, args, res):
            tool_log.append(name)

        final_response = self.agent5.process_request("Continue development based on current tasks", on_tool_call=tool_cb)

        # Assert full tool execution sequence
        self.assertEqual(tool_log, [
            "read_project_state",
            "delegate_task",
            "create_file",
            "update_project_state"
        ])

        # Assert database/schema.sql was created in sandbox
        schema_file = self.workspace_root / "database" / "schema.sql"
        self.assertTrue(schema_file.exists())
        self.assertIn("CREATE TABLE products", schema_file.read_text(encoding="utf-8"))

        # Assert PROJECT_STATE.md reflects updated tasks
        state_content = (self.workspace_root / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("1. Products database schema designed and saved", state_content)
        self.assertIn("2. Build backend API endpoints", state_content)


if __name__ == "__main__":
    unittest.main()

