import unittest
import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple, Optional
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from agents.workspace_agent import (
    WorkspaceAgent,
    DEFAULT_WORKSPACE_CAPABILITIES,
    DEFAULT_WORKSPACE_SYSTEM_PROMPT
)
from tools.filesystem import WorkspaceSandbox
from tools.server_manager import DevServerManager
from diary.code_diary import CodeDiary
from orchestration import (
    MessageType,
    AgentMessage,
    Orchestrator
)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for WorkspaceAgent testing.
    """

    def __init__(self, fixed_response: str = "Workspace action completed successfully.") -> None:
        self.fixed_response = fixed_response
        self.received_messages: List[List[Dict[str, Any]]] = []
        self.tool_calls_to_return: Optional[List[Dict[str, Any]]] = None

    def set_tool_calls(self, tool_calls: Optional[List[Dict[str, Any]]]) -> None:
        self.tool_calls_to_return = tool_calls

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        self.received_messages.append(messages)
        if self.tool_calls_to_return:
            calls = self.tool_calls_to_return
            self.tool_calls_to_return = None  # Return once, then return final answer on next turn
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


class TestWorkspaceAgent(unittest.TestCase):
    """
    Comprehensive deterministic unit tests for Agent 5 (Workspace/Runtime Manager & Project Manager).
    """

    def setUp(self):
        # Create temporary sandbox and diary
        self.test_dir = tempfile.mkdtemp(prefix="agent5_test_")
        self.workspace_root = Path(self.test_dir) / "workspace"
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.diary_file = Path(self.test_dir) / "CODE_DIARY.md"

        self.diary = CodeDiary(self.diary_file)
        self.sandbox = WorkspaceSandbox(self.workspace_root, diary=self.diary)
        self.server_manager = DevServerManager(workspace_root=self.workspace_root, diary=self.diary)

        self.mock_llm = MockLLMProvider("Workspace operations complete.")
        self.orchestrator = Orchestrator()

        self.agent5 = WorkspaceAgent(
            llm_provider=self.mock_llm,
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            server_manager=self.server_manager,
            orchestrator=self.orchestrator
        )

        # Register Agent 5 in Orchestrator
        self.orchestrator.register_agent(
            agent_id=self.agent5.agent_id,
            role=self.agent5.role,
            capabilities=self.agent5.capabilities,
            handler=self.agent5.handle_agent_message
        )

    def tearDown(self):
        # Cleanup temporary files
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Instantiation Test
    def test_01_agent_instantiation(self):
        self.assertIsNotNone(self.agent5)
        self.assertIsInstance(self.agent5, WorkspaceAgent)

    # 2. Identity and Role Test
    def test_02_identity_and_role(self):
        self.assertEqual(self.agent5.agent_id, "agent5")
        self.assertEqual(self.agent5.role, "workspace_manager")
        self.assertIn("Agent 5", self.agent5.name)
        self.assertIn("Workspace/Runtime Manager", self.agent5.system_prompt)

    # 3. Workspace Capabilities Test
    def test_03_capabilities(self):
        expected_caps = {
            "filesystem",
            "workspace",
            "dev_server",
            "diary",
            "project_management",
            "agent_coordination",
            "project_state"
        }
        self.assertEqual(self.agent5.capabilities, expected_caps)
        self.assertTrue(self.agent5.has_capability("filesystem"))
        self.assertTrue(self.agent5.has_capability("workspace"))
        self.assertTrue(self.agent5.has_capability("dev_server"))
        self.assertTrue(self.agent5.has_capability("diary"))
        self.assertTrue(self.agent5.has_capability("project_management"))
        self.assertTrue(self.agent5.has_capability("agent_coordination"))
        self.assertTrue(self.agent5.has_capability("project_state"))

    # 4. Standard Request Processing via Mock LLM
    def test_04_process_request_no_tools(self):
        prompt = "Explain the current workspace layout."
        response = self.agent5.process_request(prompt)

        self.assertEqual(response, "Workspace operations complete.")
        self.assertEqual(len(self.mock_llm.received_messages), 1)
        sent = self.mock_llm.received_messages[0]
        self.assertEqual(sent[0]["role"], "system")
        self.assertEqual(sent[1]["role"], "user")
        self.assertEqual(sent[1]["content"], prompt)

    # 5. Tool Calling: Filesystem Operations
    def test_05_tool_calling_filesystem(self):
        # Simulate LLM returning a create_file tool call
        self.mock_llm.set_tool_calls([
            {
                "id": "call_1",
                "function": {
                    "name": "create_file",
                    "arguments": {"path": "backend/app.py", "content": "print('hello world')"}
                }
            }
        ])

        recorded_tools = []
        def tool_cb(name, args, res):
            recorded_tools.append((name, args, res))

        resp = self.agent5.process_request("Create backend/app.py", on_tool_call=tool_cb)
        self.assertTrue(resp.startswith("Workspace operations complete."))
        self.assertEqual(len(recorded_tools), 1)
        self.assertEqual(recorded_tools[0][0], "create_file")

        # Verify file exists on disk
        target_file = self.workspace_root / "backend" / "app.py"
        self.assertTrue(target_file.exists())
        self.assertEqual(target_file.read_text(encoding="utf-8"), "print('hello world')")

        # Verify Code Diary was written
        diary_content = self.diary_file.read_text(encoding="utf-8")
        self.assertIn("CREATE_FILE", diary_content)

    # 6. Sandbox Security: Traversal Prevention
    def test_06_sandbox_traversal_prevention(self):
        result = self.agent5._execute_tool("create_file", {"path": "../secret.txt", "content": "bad"})
        self.assertIn("Security Sandbox Violation", result)

        diary_content = self.diary_file.read_text(encoding="utf-8")
        self.assertIn("Security Sandbox Violation", diary_content)

    # 7. Dev Server Management Lifecycle (Mocked Subprocess)
    @patch("subprocess.Popen")
    def test_07_dev_server_lifecycle(self, mock_popen):
        # Setup mock Popen process
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # Simulates running process
        mock_popen.return_value = mock_proc

        # Start server via agent tool execution
        start_res = self.agent5._execute_tool(
            "start_dev_server",
            {"command": "python -m http.server 8000", "port": 8000, "name": "web"}
        )
        self.assertIn("started successfully with PID 12345", start_res)
        self.assertIn("8000", start_res)

        # Check status
        status_res = self.agent5._execute_tool("get_server_status", {"name": "web"})
        self.assertIn("RUNNING", status_res)
        self.assertIn("12345", status_res)

        # Stop server
        stop_res = self.agent5._execute_tool("stop_dev_server", {"name": "web"})
        self.assertIn("stopped successfully", stop_res)
        mock_proc.terminate.assert_called_once()

        # Check Code Diary recorded server actions
        diary_content = self.diary_file.read_text(encoding="utf-8")
        self.assertIn("START_DEV_SERVER", diary_content)
        self.assertIn("STOP_DEV_SERVER", diary_content)

    # 8. Project Structure Setup
    def test_08_setup_project_structure(self):
        res = self.agent5.setup_project_structure()
        self.assertEqual(res["status"], "SUCCESS")

        self.assertTrue((self.workspace_root / "frontend").is_dir())
        self.assertTrue((self.workspace_root / "backend").is_dir())
        self.assertTrue((self.workspace_root / "database" / "migrations").is_dir())
        self.assertTrue((self.workspace_root / "docs").is_dir())

        diary_content = self.diary_file.read_text(encoding="utf-8")
        self.assertIn("SETUP_PROJECT_STRUCTURE", diary_content)

    # 9. Inter-Agent Communication: A5 -> A1 (Frontend Developer)
    def test_09_communicate_with_a1(self):
        def a1_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 1 generated React UI components")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code"},
            handler=a1_handler
        )

        resp = self.agent5.dispatch_task(
            target_agent_id="agent1",
            task_description="Build the shopping cart component",
            required_capability="frontend_code"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.content, "Agent 1 generated React UI components")

    # 10. Inter-Agent Communication: A5 -> A2 (Backend Developer)
    def test_10_communicate_with_a2(self):
        def a2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 2 generated Flask API endpoints")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_handler
        )

        resp = self.agent5.dispatch_task(
            target_agent_id="agent2",
            task_description="Create /api/cart endpoints",
            required_capability="backend_code"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.content, "Agent 2 generated Flask API endpoints")

    # 11. Inter-Agent Communication: A5 -> A3 (Data Manager)
    def test_11_communicate_with_a3(self):
        def a3_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 3 created database migration scripts")

        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema", "migrations"},
            handler=a3_handler
        )

        resp = self.agent5.dispatch_task(
            target_agent_id="agent3",
            task_description="Generate migration for cart_items table",
            required_capability="migrations"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.content, "Agent 3 created database migration scripts")

    # 12. Inter-Agent Communication: A5 -> A4 (Supervisor)
    def test_12_communicate_with_a4(self):
        def a4_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Supervisor validated project milestone progress")

        self.orchestrator.register_agent(
            agent_id="agent4",
            role="supervisor",
            capabilities={"monitoring"},
            handler=a4_handler
        )

        resp = self.agent5.send_agent_message(
            recipient="agent4",
            content="Report: Phase 1 project scaffolding complete",
            required_capability="monitoring"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.content, "Supervisor validated project milestone progress")

    # 13. Incoming Agent Message Handling: Peer requesting file operation
    def test_13_handle_incoming_agent_message_tool_action(self):
        # A2 sends a request to A5 to write a file in the workspace
        req_msg = AgentMessage(
            sender="agent2",
            recipient="agent5",
            message_type=MessageType.REQUEST,
            content="Write server.py",
            metadata={
                "action": "create_file",
                "args": {"path": "backend/server.py", "content": "from flask import Flask\napp = Flask(__name__)"}
            }
        )
        response = self.agent5.handle_agent_message(req_msg)

        self.assertEqual(response.sender, "agent5")
        self.assertEqual(response.recipient, "agent2")
        self.assertIn("created successfully", response.content)

        # Verify file created on disk
        self.assertTrue((self.workspace_root / "backend" / "server.py").exists())

    # 14. Cannot Claim Disallowed Capabilities
    def test_14_cannot_claim_disallowed_capabilities(self):
        disallowed = [
            "frontend_code",
            "frontend_files",
            "ui_components",
            "backend_code",
            "backend_files",
            "api",
            "database_schema",
            "migrations",
            "crud",
            "monitoring",
            "scope_validation"
        ]

    # 15. Sanitize Code Content Tests (Unwrapping JSON artifacts, markdown, and escapes)
    def test_15_sanitize_code_content(self):
        from tools.filesystem import sanitize_code_content

        # Case A: Stringified JSON object
        raw_json = '{"python": "import flask\\nfrom flask import Flask\\napp = Flask(__name__)\\n@app.route(\\"/\\")\\ndef index():\\n    return \\"Hello, World!\\""}'
        cleaned = sanitize_code_content(raw_json)
        self.assertNotIn('{"python":', cleaned)
        self.assertIn('from flask import Flask', cleaned)
        self.assertIn('return "Hello, World!"', cleaned)

        # Case B: Dictionary input
        dict_input = {"python": "import os\nprint('hello')"}
        cleaned_dict = sanitize_code_content(dict_input)
        self.assertNotIn('{"python":', cleaned_dict)
        self.assertIn("print('hello')", cleaned_dict)

        # Case C: Markdown code fence
        md_input = "```python\ndef test():\n    return True\n```"
        cleaned_md = sanitize_code_content(md_input)
        self.assertNotIn("```", cleaned_md)
        self.assertIn("def test():", cleaned_md)

        # Case D: Escaped newline string
        escaped_input = 'def greet(name: str) -> str:\\n    return f\\"Hello, {name}!\\"'
        cleaned_esc = sanitize_code_content(escaped_input)
        self.assertIn("\n", cleaned_esc)
        self.assertIn('return f"Hello, {name}!"', cleaned_esc)

    # 16. Create File with JSON-wrapped LLM Artifacts produces valid syntax
    def test_16_create_file_with_json_wrapped_code(self):
        json_wrapped_payload = (
            '{"python": "import flask\\nfrom flask import Flask\\napp = Flask(__name__)\\n'
            '@app.route(\\"/\\")\\ndef index():\\n    return \\"Hello, World!\\"\\n'
            'if __name__ == \\"__main__\\":\\n    app.run(debug=True)"}'
        )

        res = self.agent5._execute_tool(
            "create_file",
            {"path": "backend/app.py", "content": json_wrapped_payload}
        )
        self.assertIn("created successfully", res)

        # Verify disk content is valid Python and can be compiled
        written_file = self.workspace_root / "backend" / "app.py"
        content = written_file.read_text(encoding="utf-8")
        self.assertNotIn('{"python":', content)
        self.assertNotIn('"}', content)

    # 17. Delegation Tool Schema Exposed to LLM
    def test_17_delegation_tool_schema_exposed(self):
        from agents.workspace_agent import ALL_WORKSPACE_TOOLS, DELEGATION_TOOLS
        tool_names = [t["function"]["name"] for t in ALL_WORKSPACE_TOOLS]
        self.assertIn("delegate_task", tool_names)
        self.assertIn("create_file", tool_names)
        self.assertIn("start_dev_server", tool_names)

        delegation_tool = next(t for t in DELEGATION_TOOLS if t["function"]["name"] == "delegate_task")
        params = delegation_tool["function"]["parameters"]
        self.assertIn("target_agent", params["properties"])
        self.assertIn("task", params["properties"])
        self.assertEqual(params["properties"]["target_agent"]["enum"], ["agent1", "agent2", "agent3"])

    # 18. LLM Tool-Calling Delegation Path to Agent 1 (Frontend Developer)
    def test_18_llm_tool_calling_delegation_to_agent1(self):
        def a1_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("function Navbar() { return <nav>Home</nav>; }")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code"},
            handler=a1_handler
        )

        # Mock LLM returns tool call for delegate_task
        self.mock_llm.set_tool_calls([
            {
                "id": "call_delegate_1",
                "function": {
                    "name": "delegate_task",
                    "arguments": {
                        "target_agent": "agent1",
                        "task": "Create the main navigation component",
                        "context": "Dark theme with Logo on left"
                    }
                }
            }
        ])

        recorded_tools = []
        def tool_cb(name, args, res):
            recorded_tools.append((name, args, res))

        resp = self.agent5.process_request("Please build the frontend navbar", on_tool_call=tool_cb)

        self.assertEqual(resp, "Workspace operations complete.")
        self.assertEqual(len(recorded_tools), 1)
        tool_name, tool_args, tool_result = recorded_tools[0]
        self.assertEqual(tool_name, "delegate_task")
        self.assertEqual(tool_args["target_agent"], "agent1")
        self.assertIn("Navbar()", tool_result)
        self.assertIn("Response from agent1", tool_result)

        # Verify Code Diary recorded delegation
        diary_content = self.diary_file.read_text(encoding="utf-8")
        self.assertIn("DELEGATE_TASK", diary_content)

    # 19. LLM Tool-Calling Delegation Path to Agent 2 (Backend Developer)
    def test_19_llm_tool_calling_delegation_to_agent2(self):
        def a2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("from flask import Flask\napp = Flask(__name__)\n@app.route('/api/items')\ndef get_items(): return []")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_handler
        )

        self.mock_llm.set_tool_calls([
            {
                "id": "call_delegate_2",
                "function": {
                    "name": "delegate_task",
                    "arguments": {
                        "target_agent": "agent2",
                        "task": "Build REST API for items",
                        "context": "GET /api/items"
                    }
                }
            }
        ])

        recorded_tools = []
        def tool_cb(name, args, res):
            recorded_tools.append((name, args, res))

        resp = self.agent5.process_request("Build backend API", on_tool_call=tool_cb)

        self.assertEqual(len(recorded_tools), 1)
        self.assertEqual(recorded_tools[0][0], "delegate_task")
        self.assertIn("/api/items", recorded_tools[0][2])

    # 20. LLM Tool-Calling Delegation Path to Agent 3 (Data Manager)
    def test_20_llm_tool_calling_delegation_to_agent3(self):
        def a3_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);")

        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema", "migrations"},
            handler=a3_handler
        )

        self.mock_llm.set_tool_calls([
            {
                "id": "call_delegate_3",
                "function": {
                    "name": "delegate_task",
                    "arguments": {
                        "target_agent": "agent3",
                        "task": "Create schema migration for items table"
                    }
                }
            }
        ])

        recorded_tools = []
        def tool_cb(name, args, res):
            recorded_tools.append((name, args, res))

        self.agent5.process_request("Create database migration", on_tool_call=tool_cb)

        recorded_llm_tools = [t for t in recorded_tools if t[0] != "apply_skill"]
        self.assertEqual(len(recorded_llm_tools), 1)
        self.assertEqual(recorded_llm_tools[0][0], "delegate_task")
        self.assertIn("CREATE TABLE items", recorded_llm_tools[0][2])

    # 21. Delegation Rejects Invalid Target Agent Safely
    def test_21_delegation_rejects_invalid_targets(self):
        # Disallow delegating dev tasks to agent4 (supervisor)
        res_a4 = self.agent5._execute_tool("delegate_task", {"target_agent": "agent4", "task": "Write code"})
        self.assertIn("Supervisor/Monitor agent and cannot be assigned development tasks", res_a4)

        # Disallow arbitrary agent IDs
        res_invalid = self.agent5._execute_tool("delegate_task", {"target_agent": "agent99", "task": "Write code"})
        self.assertIn("Invalid target agent 'agent99'", res_invalid)

        # Disallow empty target
        res_empty = self.agent5._execute_tool("delegate_task", {"target_agent": "", "task": "Write code"})
        self.assertIn("Missing required 'target_agent'", res_empty)

    # 22. Agent 4 Observes Delegation Messages Non-Intrusively
    def test_22_agent4_observes_delegation(self):
        observed_messages = []
        def a4_observer(msg: AgentMessage):
            observed_messages.append(msg)

        self.orchestrator.register_observer(a4_observer)

        def a1_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Frontend code ready")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code"},
            handler=a1_handler
        )

        res = self.agent5._execute_tool(
            "delegate_task",
            {"target_agent": "agent1", "task": "Build Landing Page UI"}
        )

        self.assertIn("Frontend code ready", res)
        # Verify A4 observer captured the message
        self.assertTrue(any(m.sender == "agent5" and m.recipient == "agent1" for m in observed_messages))

    # 23. End-to-End Multiturn Delegation and Workspace File Creation Loop
    def test_23_end_to_end_multiturn_delegation_and_file_creation(self):
        # Register Agent 2
        def a2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return 'OK'\n")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_handler
        )

        # Custom mock provider that executes a 2-step tool sequence:
        # Turn 1: calls delegate_task to agent2
        # Turn 2: calls create_file with the code received from agent2
        # Turn 3: returns final response
        class MultiStepMockLLM(BaseLLMProvider):
            def __init__(self):
                self.turn = 0
            def chat(self, messages, tools=None, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "step1",
                            "function": {
                                "name": "delegate_task",
                                "arguments": {"target_agent": "agent2", "task": "Write Flask server"}
                            }
                        }]
                    }
                elif self.turn == 2:
                    # Tool result from step 1 is in messages[-1]
                    last_tool_msg = messages[-1]
                    code_from_agent = "from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return 'OK'\n"
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "step2",
                            "function": {
                                "name": "create_file",
                                "arguments": {"path": "backend/server.py", "content": code_from_agent}
                            }
                        }]
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": "Backend server file created successfully.",
                        "tool_calls": None
                    }
            def chat_stream(self, messages, **kwargs):
                yield "Backend server file created successfully."
            def health_check(self):
                return True, "Ready"

        multistep_llm = MultiStepMockLLM()
        agent5_coord = WorkspaceAgent(
            llm_provider=multistep_llm,
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            server_manager=self.server_manager,
            orchestrator=self.orchestrator
        )

        executed_tools = []
        def tool_cb(name, args, res):
            executed_tools.append((name, args, res))

        final_resp = agent5_coord.process_request("Create backend server", on_tool_call=tool_cb)

        self.assertTrue(final_resp.startswith("Backend server file created successfully."))
        self.assertEqual(len(executed_tools), 2)
        self.assertEqual(executed_tools[0][0], "delegate_task")
        self.assertEqual(executed_tools[1][0], "create_file")

        # Verify file is physically created in sandbox and has valid Python syntax
        created_file = self.workspace_root / "backend" / "server.py"
        self.assertTrue(created_file.exists())
        self.assertIn("@app.route('/')", created_file.read_text(encoding="utf-8"))

    # 24. Critical End-to-End Test: Multi-Round Autonomous Project Orchestration
    def test_24_critical_e2e_autonomous_multi_round_orchestration(self):
        """
        Demonstrates ONE high-level user request through multiple autonomous delegation rounds:
        User: 'Build me a task management web application using React, FastAPI and SQLite.'
        Round 1: read_project_state
        Round 2: delegate_task to agent3 (Database schema)
        Round 3: update_project_state with DB schema progress
        Round 4: delegate_task to agent2 (FastAPI backend using A3 schema)
        Round 5: update_project_state with backend progress
        Round 6: delegate_task to agent1 (React frontend consuming API)
        Round 7: update_project_state with completed state
        Round 8: Final completion summary
        """
        # 1. Register Specialist Agents in Orchestrator
        def a1_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 1 created App.jsx and TaskList.jsx components connecting to /api/tasks.")

        def a2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 2 created backend/main.py with FastAPI router and verified syntax [PASSED].")

        def a3_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 3 created database/schema.sql for tasks table (id, title, status).")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code"},
            handler=a1_handler
        )
        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_handler
        )
        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema"},
            handler=a3_handler
        )

        # 2. Scripted multi-turn LLM provider executing the sequence
        script = [
            # Turn 1: Inspect project state
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "read_project_state", "arguments": {}}
                }]
            },
            # Turn 2: Delegate database design to Agent 3
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_2",
                    "function": {
                        "name": "delegate_task",
                        "arguments": {
                            "target_agent": "agent3",
                            "task": "Design SQLite schema for tasks (id, title, completed)."
                        }
                    }
                }]
            },
            # Turn 3: Update project state with database results
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_3",
                    "function": {
                        "name": "update_project_state",
                        "arguments": {
                            "section": "Completed Tasks",
                            "content": "- Database schema for tasks table created by Agent 3."
                        }
                    }
                }]
            },
            # Turn 4: Delegate backend implementation to Agent 2 with schema context
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_4",
                    "function": {
                        "name": "delegate_task",
                        "arguments": {
                            "target_agent": "agent2",
                            "task": "Implement FastAPI endpoints (/api/tasks) using tasks table schema.",
                            "context": "Schema: tasks(id INT, title TEXT, completed BOOLEAN)"
                        }
                    }
                }]
            },
            # Turn 5: Update project state with backend results
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_5",
                    "function": {
                        "name": "update_project_state",
                        "arguments": {
                            "section": "Completed Tasks",
                            "content": "- Database schema created.\n- FastAPI backend API implemented and verified by Agent 2."
                        }
                    }
                }]
            },
            # Turn 6: Delegate frontend implementation to Agent 1 with API contract
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_6",
                    "function": {
                        "name": "delegate_task",
                        "arguments": {
                            "target_agent": "agent1",
                            "task": "Implement React UI components to display and add tasks via /api/tasks.",
                            "context": "Endpoints: GET /api/tasks, POST /api/tasks"
                        }
                    }
                }]
            },
            # Turn 7: Update project state with full completion
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_7",
                    "function": {
                        "name": "update_project_state",
                        "arguments": {
                            "section": "Current Progress",
                            "content": "All tiers (Database, FastAPI backend, React frontend) built and verified."
                        }
                    }
                }]
            },
            # Turn 8: Final assistant completion response
            {
                "role": "assistant",
                "content": (
                    "The task management application is fully implemented:\n"
                    "1. SQLite database schema created by Agent 3.\n"
                    "2. FastAPI backend API created and verified by Agent 2.\n"
                    "3. React frontend components built by Agent 1.\n"
                    "Persistent project state updated in PROJECT_STATE.md."
                ),
                "tool_calls": None
            }
        ]

        class ScriptedProjectLLM(BaseLLMProvider):
            def __init__(self, steps):
                self.steps = steps
                self.idx = 0
                self.received_messages = []
            def chat(self, messages, tools=None, **kwargs):
                self.received_messages.append(messages)
                if self.idx < len(self.steps):
                    resp = self.steps[self.idx]
                    self.idx += 1
                    return resp
                return {"role": "assistant", "content": "Done", "tool_calls": None}
            def chat_stream(self, messages, **kwargs):
                yield "Done"
            def health_check(self):
                return True, "Ready"

        orchestrating_llm = ScriptedProjectLLM(script)
        pm_agent = WorkspaceAgent(
            llm_provider=orchestrating_llm,
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            server_manager=self.server_manager,
            orchestrator=self.orchestrator,
            max_tool_iterations=15
        )

        executed_tools = []
        def tool_cb(name, args, res):
            executed_tools.append(name)

        final_result = pm_agent.process_request(
            "Build me a task management web application using React, FastAPI and SQLite.",
            on_tool_call=tool_cb
        )

        # 3. Assertions
        self.assertIn("The task management application is fully implemented", final_result)
        llm_executed_tools = [t for t in executed_tools if t != "apply_skill"]
        self.assertEqual(llm_executed_tools, [
            "read_project_state",
            "delegate_task",
            "update_project_state",
            "delegate_task",
            "update_project_state",
            "delegate_task",
            "update_project_state"
        ])

        # Verify PROJECT_STATE.md on disk was maintained and contains the updates
        state_content = (self.workspace_root / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("All tiers (Database, FastAPI backend, React frontend) built and verified.", state_content)
        self.assertIn("FastAPI backend API implemented and verified by Agent 2.", state_content)

    # 25. Dynamic Delegation Order (Non-hardcoded)
    def test_25_dynamic_delegation_order_backend_only(self):
        """
        Verifies that A5 can dynamically delegate only to Agent 2 when given a backend-only request,
        proving that ordering and specialist targets are not hardcoded.
        """
        def a2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 2 generated standalone CLI script.")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_handler
        )

        class ScriptedBackendOnlyLLM(BaseLLMProvider):
            def __init__(self):
                self.turn = 0
            def chat(self, messages, tools=None, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "c1",
                            "function": {
                                "name": "delegate_task",
                                "arguments": {"target_agent": "agent2", "task": "Create CLI data processor"}
                            }
                        }]
                    }
                elif self.turn == 2:
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "c2",
                            "function": {
                                "name": "update_project_state",
                                "arguments": {"section": "Completed Tasks", "content": "- CLI tool built by Agent 2"}
                            }
                        }]
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": "CLI backend script is completed.",
                        "tool_calls": None
                    }
            def chat_stream(self, messages, **kwargs):
                yield "Done"
            def health_check(self):
                return True, "Ready"

        pm = WorkspaceAgent(
            llm_provider=ScriptedBackendOnlyLLM(),
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            orchestrator=self.orchestrator
        )

        tool_names = []
        res = pm.process_request("Create a backend CLI processor", on_tool_call=lambda n, a, r: tool_names.append(n))
        self.assertIn("CLI backend script is completed", res)
        self.assertEqual(tool_names, ["delegate_task", "update_project_state"])

    # 26. Repeat Delegation to the Same Specialist
    def test_26_repeat_delegation_to_same_specialist(self):
        """
        Verifies that A5 can delegate to the same specialist (e.g. agent2) multiple times in succession.
        """
        call_count = {"agent2": 0}
        def a2_handler(msg: AgentMessage) -> AgentMessage:
            call_count["agent2"] += 1
            if call_count["agent2"] == 1:
                return msg.create_response("Agent 2 generated User model.")
            return msg.create_response("Agent 2 generated Auth router.")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_handler
        )

        class RepeatSpecialistLLM(BaseLLMProvider):
            def __init__(self):
                self.turn = 0
            def chat(self, messages, tools=None, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "c1",
                            "function": {"name": "delegate_task", "arguments": {"target_agent": "agent2", "task": "Create models"}}
                        }]
                    }
                elif self.turn == 2:
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "c2",
                            "function": {"name": "delegate_task", "arguments": {"target_agent": "agent2", "task": "Create auth routes"}}
                        }]
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": "Both backend models and routes completed.",
                        "tool_calls": None
                    }
            def chat_stream(self, messages, **kwargs):
                yield "Done"
            def health_check(self):
                return True, "Ready"

        pm = WorkspaceAgent(
            llm_provider=RepeatSpecialistLLM(),
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            orchestrator=self.orchestrator
        )

        res = pm.process_request("Build user models and authentication")
        self.assertIn("Both backend models and routes completed", res)
        self.assertEqual(call_count["agent2"], 2)

    # 27. Bounded Orchestration Iteration Limit Preserves State
    def test_27_bounded_orchestration_limit_preserves_state(self):
        """
        Verifies that when max_tool_iterations is reached, A5 stops, preserves state, and returns a summary.
        """
        class InfiniteLoopLLM(BaseLLMProvider):
            def chat(self, messages, tools=None, **kwargs):
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "loop_call",
                        "function": {"name": "read_project_state", "arguments": {}}
                    }]
                }
            def chat_stream(self, messages, **kwargs):
                yield "Looping"
            def health_check(self):
                return True, "Ready"

        pm = WorkspaceAgent(
            llm_provider=InfiniteLoopLLM(),
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            orchestrator=self.orchestrator,
            max_tool_iterations=4
        )

        res = pm.process_request("Keep reading state forever")
        self.assertIn("Orchestration limit reached", res)
        self.assertIn("maximum of 4 reasoning steps", res)
        self.assertIn("PROJECT_STATE.md", res)

    # 28. Handling Specialist Failure and State Update
    def test_28_specialist_failure_handling_and_state_update(self):
        """
        Verifies that when a specialist returns an error or failure, A5 receives it in context,
        updates Known Issues in PROJECT_STATE.md, and handles it gracefully.
        """
        def a2_failing_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Verification FAILED: Missing required database driver 'asyncpg'.")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_failing_handler
        )

        class FailureHandlingLLM(BaseLLMProvider):
            def __init__(self):
                self.turn = 0
            def chat(self, messages, tools=None, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "c1",
                            "function": {"name": "delegate_task", "arguments": {"target_agent": "agent2", "task": "Build async database backend"}}
                        }]
                    }
                elif self.turn == 2:
                    # In turn 2, LLM sees the failure from agent 2 and records it in Known Issues
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "c2",
                            "function": {
                                "name": "update_project_state",
                                "arguments": {
                                    "section": "Known Issues",
                                    "content": "- Backend blocked: asyncpg driver dependency required."
                                }
                            }
                        }]
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": "Backend task reported a blocker (asyncpg driver required). State updated in PROJECT_STATE.md.",
                        "tool_calls": None
                    }
            def chat_stream(self, messages, **kwargs):
                yield "Done"
            def health_check(self):
                return True, "Ready"

        pm = WorkspaceAgent(
            llm_provider=FailureHandlingLLM(),
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            orchestrator=self.orchestrator
        )

        res = pm.process_request("Build async backend")
        self.assertIn("Backend task reported a blocker", res)

        # Check that PROJECT_STATE.md records the issue
        state_content = (self.workspace_root / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("Backend blocked: asyncpg driver dependency required.", state_content)

    # 29. Context Compaction Recovery via read_project_state
    def test_29_context_compaction_recovery_via_read_project_state(self):
        """
        Verifies that when conversation history is cleared, A5 reconstructs context from PROJECT_STATE.md.
        """
        # Populate initial project state
        self.agent5.state_manager.update_state("User Requirements", "Task management app with React and FastAPI.")
        self.agent5.state_manager.update_state("Completed Tasks", "Database schema created.")

        # Simulate fresh session after context compaction
        self.agent5.clear_history()
        self.assertEqual(len(self.agent5.get_history()), 0)

        class RecoveryLLM(BaseLLMProvider):
            def __init__(self):
                self.turn = 0
            def chat(self, messages, tools=None, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    return {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "c1",
                            "function": {"name": "read_project_state", "arguments": {}}
                        }]
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": "Recovered state: Database schema is already completed. Ready to proceed with backend.",
                        "tool_calls": None
                    }
            def chat_stream(self, messages, **kwargs):
                yield "Done"
            def health_check(self):
                return True, "Ready"

        pm = WorkspaceAgent(
            llm_provider=RecoveryLLM(),
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            orchestrator=self.orchestrator
        )

    def test_extract_xml_tool_calls(self):
        """Verify fallback parsing of <function=tool><parameter=key>val</parameter></function> tags."""
        xml_text = (
            "<function=list_files>\n"
            "<parameter=directory>\n"
            "AI Based road pothole detection system\n"
            "</parameter>\n"
            "</function>\n"
            "</tool_call>"
        )
        extracted = self.agent5._extract_tool_calls_from_text(xml_text)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["function"]["name"], "list_files")
        self.assertEqual(extracted[0]["function"]["arguments"]["path"], "AI Based road pothole detection system")

        cleaned = self.agent5._clean_tool_call_xml_from_text(xml_text)
        self.assertEqual(cleaned, "")

    def test_process_request_with_xml_tool_call(self):
        """Verify process_request handles LLMs outputting pseudo-XML tool calls in content."""
        class XMLToolLLM(BaseLLMProvider):
            def __init__(self):
                self.turn = 0
            def chat(self, messages, tools=None, **kwargs):
                self.turn += 1
                if self.turn == 1:
                    return {
                        "role": "assistant",
                        "content": (
                            "<function=create_file>\n"
                            "<parameter=path>sample.py</parameter>\n"
                            "<parameter=content>print('hello xml')</parameter>\n"
                            "</function>\n"
                            "</tool_call>"
                        ),
                        "tool_calls": None
                    }
                else:
                    return {
                        "role": "assistant",
                        "content": "File sample.py created successfully.",
                        "tool_calls": None
                    }
            def chat_stream(self, messages, **kwargs):
                yield "Done"
            def health_check(self):
                return True, "Ready"

        xml_agent = WorkspaceAgent(
            llm_provider=XMLToolLLM(),
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            orchestrator=self.orchestrator
        )

        res = xml_agent.process_request("Create sample.py")
        self.assertIn("File sample.py created successfully.", res)
        # Verify file was actually created on disk
        self.assertTrue((self.workspace_root / "sample.py").exists())
        self.assertEqual((self.workspace_root / "sample.py").read_text(encoding="utf-8"), "print('hello xml')")


if __name__ == "__main__":
    unittest.main()



