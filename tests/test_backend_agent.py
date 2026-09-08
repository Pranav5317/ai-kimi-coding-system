import unittest
import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from agents.backend_agent import BackendAgent, DEFAULT_BACKEND_CAPABILITIES
from tools.filesystem import WorkspaceSandbox
from tools.verifier import BackendVerifier, VerificationResult, VERIFICATION_TOOLS
from diary.code_diary import CodeDiary
from orchestration import (
    MessageType,
    AgentMessage,
    Orchestrator
)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for unit testing without local/cloud models.
    """

    def __init__(self, fixed_response: str = "Mock backend response") -> None:
        self.fixed_response = fixed_response
        self.received_messages: List[List[Dict[str, Any]]] = []

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        self.received_messages.append(messages)
        return {
            "role": "assistant",
            "content": self.fixed_response,
            "tool_calls": None
        }

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        yield self.fixed_response

    def health_check(self) -> Tuple[bool, str]:
        return True, "Mock LLM is ready."


class ScriptedToolMockLLMProvider(BaseLLMProvider):
    """
    Mock LLM provider that plays a predetermined sequence of tool calls and text responses.
    """

    def __init__(self, script: List[Dict[str, Any]]) -> None:
        self.script = list(script)
        self.step = 0
        self.received_messages: List[List[Dict[str, Any]]] = []

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        self.received_messages.append(messages)
        if self.step < len(self.script):
            res = self.script[self.step]
            self.step += 1
            return res
        return {
            "role": "assistant",
            "content": "Finished scripted flow.",
            "tool_calls": None
        }

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        yield "Scripted stream"

    def health_check(self) -> Tuple[bool, str]:
        return True, "Scripted LLM ready."


class TestBackendAgent(unittest.TestCase):
    """
    Deterministic unit tests for Agent 2 (Backend Developer).
    Ensures zero dependency on external Ollama or live LLMs.
    """

    def setUp(self):
        self.mock_llm = MockLLMProvider("from fastapi import FastAPI\napp = FastAPI()")
        self.orchestrator = Orchestrator()

        # Create BackendAgent with injected mock LLM and Orchestrator
        self.agent2 = BackendAgent(
            llm_provider=self.mock_llm,
            agent_id="agent2",
            orchestrator=self.orchestrator
        )

        # Register Agent 2 with the orchestrator
        self.orchestrator.register_agent(
            agent_id=self.agent2.agent_id,
            role=self.agent2.role,
            capabilities=self.agent2.capabilities,
            handler=self.agent2.handle_agent_message
        )

    # 1. Instantiation Test
    def test_01_agent_instantiation(self):
        self.assertIsNotNone(self.agent2)
        self.assertIsInstance(self.agent2, BackendAgent)

    # 2. Identity and Role Test
    def test_02_identity_and_role(self):
        self.assertEqual(self.agent2.agent_id, "agent2")
        self.assertEqual(self.agent2.name, "Backend Developer")
        self.assertEqual(self.agent2.role, "backend_developer")
        self.assertIn("Backend Developer", self.agent2.system_prompt)

    # 3. Correct Capabilities Test
    def test_03_capabilities(self):
        expected_caps = {"backend_code", "backend_files", "api", "backend_architecture"}
        self.assertEqual(self.agent2.capabilities, expected_caps)
        self.assertTrue(self.agent2.has_capability("backend_code"))
        self.assertTrue(self.agent2.has_capability("backend_files"))
        self.assertTrue(self.agent2.has_capability("api"))
        self.assertTrue(self.agent2.has_capability("backend_architecture"))

    # 4. Request Processing via Mock LLM Test
    def test_04_process_request(self):
        prompt = "Create a FastAPI authentication router."
        response = self.agent2.process_request(prompt)

        self.assertEqual(response, "from fastapi import FastAPI\napp = FastAPI()")
        self.assertEqual(len(self.mock_llm.received_messages), 1)

        sent_messages = self.mock_llm.received_messages[0]
        self.assertEqual(sent_messages[0]["role"], "system")
        self.assertIn("Backend Developer", sent_messages[0]["content"])
        self.assertEqual(sent_messages[1]["role"], "user")
        self.assertEqual(sent_messages[1]["content"], prompt)

    # 5. Conversation History Update Test
    def test_05_conversation_history(self):
        self.agent2.clear_history()
        self.assertEqual(len(self.agent2.get_history()), 0)

        self.agent2.process_request("First backend prompt")
        self.agent2.process_request("Second backend prompt")

        history = self.agent2.get_history()
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "First backend prompt")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[2]["role"], "user")
        self.assertEqual(history[2]["content"], "Second backend prompt")
        self.assertEqual(history[3]["role"], "assistant")

    # 6. Send AgentMessage Through Orchestrator Test
    def test_06_send_agent_message_through_orchestrator(self):
        def mock_agent1_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Frontend received API schema")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code", "ui_components"},
            handler=mock_agent1_handler
        )

        response = self.agent2.send_agent_message(
            recipient="agent1",
            content="Here is the user API schema: { id: int, username: str }"
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent1")
        self.assertEqual(response.recipient, "agent2")
        self.assertEqual(response.content, "Frontend received API schema")

    # 7. Communicate with Mocked Agent 1 (Frontend Developer) Test
    def test_07_communicate_with_mocked_agent1(self):
        def agent1_handler(msg: AgentMessage) -> AgentMessage:
            if "login contract" in msg.content:
                return msg.create_response("Agent 1 updated LoginForm to use /api/v1/auth/login")
            return msg.create_response("Agent 1 acknowledged")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code", "frontend_files", "ui_components"},
            handler=agent1_handler
        )

        resp = self.agent2.send_agent_message(
            recipient="agent1",
            content="Here is the login contract: POST /api/v1/auth/login with { email, password }"
        )
        self.assertEqual(resp.content, "Agent 1 updated LoginForm to use /api/v1/auth/login")

    # 8. Communicate with Mocked Agent 3 (Data Manager) Test
    def test_08_communicate_with_mocked_agent3(self):
        def agent3_handler(msg: AgentMessage) -> AgentMessage:
            if "users table" in msg.content:
                return msg.create_response("Schema for users table: id INT, email VARCHAR(255), hashed_password VARCHAR(255)")
            return msg.create_response("Agent 3 DB acknowledgment")

        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema", "migrations", "crud"},
            handler=agent3_handler
        )

        resp = self.agent2.send_agent_message(
            recipient="agent3",
            content="I need the database fields and schema for users table.",
            required_capability="database_schema"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.sender, "agent3")
        self.assertIn("Schema for users table", resp.content)

    # 9. Communicate with Mocked Agent 4 (Supervisor / Escalation) Test
    def test_09_communicate_with_mocked_agent4(self):
        def agent4_handler(msg: AgentMessage) -> AgentMessage:
            if msg.message_type == MessageType.ESCALATION:
                return msg.create_response("Agent 4 supervisor logged escalation: out of scope item")
            elif msg.message_type == MessageType.PERMISSION_REQUEST:
                return msg.create_response("Agent 4 supervisor approved permission")
            return msg.create_response("Agent 4 acknowledged")

        self.orchestrator.register_agent(
            agent_id="agent4",
            role="supervisor",
            capabilities={"monitoring", "scope_validation", "escalation", "permission_handling"},
            handler=agent4_handler
        )

        # Test Escalation
        esc_resp = self.orchestrator.escalate(
            sender="agent2",
            content="Third-party payment integration requested outside current backend scope."
        )
        self.assertIsNotNone(esc_resp)
        self.assertEqual(esc_resp.sender, "agent4")
        self.assertIn("logged escalation", esc_resp.content)

        # Test Permission Request
        perm_resp = self.orchestrator.request_permission(
            sender="agent2",
            content="Request permission to install external cryptography dependency."
        )
        self.assertIsNotNone(perm_resp)
        self.assertEqual(perm_resp.sender, "agent4")
        self.assertIn("approved permission", perm_resp.content)

    # 10. Communicate with Mocked Agent 5 (Workspace Manager) Test
    def test_10_communicate_with_mocked_agent5(self):
        def agent5_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 5 created backend/routers/auth.py successfully")

        self.orchestrator.register_agent(
            agent_id="agent5",
            role="workspace_manager",
            capabilities={"filesystem", "workspace", "dev_server", "diary"},
            handler=agent5_handler
        )

        resp = self.agent2.send_agent_message(
            recipient="agent5",
            content="Create backend/routers/auth.py with FastAPI router code",
            required_capability="filesystem"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.sender, "agent5")
        self.assertIn("created backend/routers/auth.py", resp.content)

    # 11. Inability to Claim Disallowed Capabilities Test
    def test_11_cannot_claim_disallowed_capabilities(self):
        disallowed_capabilities = [
            "frontend_code",
            "frontend_files",
            "ui_components",
            "frontend_architecture",
            "database_schema",
            "migrations",
            "crud",
            "monitoring",
            "scope_validation",
            "escalation",
            "permission_handling",
            "filesystem",
            "workspace",
            "dev_server"
        ]

        for cap in disallowed_capabilities:
            self.assertFalse(
                self.agent2.has_capability(cap),
                f"Agent 2 should not possess capability '{cap}'"
            )
            self.assertFalse(
                self.orchestrator.registry.has_capability("agent2", cap),
                f"Registry should not report Agent 2 having capability '{cap}'"
            )


class TestBackendVerificationAndRepair(unittest.TestCase):
    """
    Unit tests for BackendVerifier and Agent 2 autonomous verification & self-repair loop.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_path = Path(self.temp_dir) / "workspace"
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.diary_path = Path(self.temp_dir) / "CODE_DIARY.md"
        self.diary = CodeDiary(self.diary_path)
        self.sandbox = WorkspaceSandbox(self.workspace_path, diary=self.diary)
        self.verifier = BackendVerifier(sandbox=self.sandbox, diary=self.diary)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 12. BackendVerifier - Valid Python Syntax Check
    def test_12_verifier_valid_python(self):
        self.sandbox.create_file(
            "backend/valid_app.py",
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )
        result = self.verifier.verify_python("backend/valid_app.py")
        self.assertIsInstance(result, VerificationResult)
        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PASSED", result.summary())

    # 13. BackendVerifier - Invalid Python Syntax Check
    def test_13_verifier_invalid_python(self):
        self.sandbox.create_file(
            "backend/invalid_app.py",
            "def broken_syntax(a, b\n    return a + b\n"
        )
        result = self.verifier.verify_python("backend/invalid_app.py")
        self.assertFalse(result.passed)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("FAILED", result.summary())
        self.assertTrue("SyntaxError" in result.stderr or "SyntaxError" in result.stdout or len(result.stderr) > 0)

    # 14. BackendVerifier - Non-existent file
    def test_14_verifier_nonexistent_file(self):
        result = self.verifier.verify_python("backend/does_not_exist.py")
        self.assertFalse(result.passed)
        self.assertIn("does not exist", result.details)

    # 15. BackendVerifier - Security Sandbox Violation
    def test_15_verifier_security_sandbox_violation(self):
        result = self.verifier.verify_python("../../escape.py")
        self.assertFalse(result.passed)
        self.assertIn("Security Sandbox Violation", result.details)

    # 16. BackendVerifier - Passing Unit Test
    def test_16_verifier_run_tests_passing(self):
        self.sandbox.create_file(
            "backend/math_mod.py",
            "def multiply(x, y):\n    return x * y\n"
        )
        self.sandbox.create_file(
            "backend/test_math.py",
            "import unittest\n"
            "from backend.math_mod import multiply\n"
            "class MathTest(unittest.TestCase):\n"
            "    def test_mult(self):\n"
            "        self.assertEqual(multiply(3, 4), 12)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        result = self.verifier.run_tests(test_path="backend/test_math.py")
        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PASSED", result.summary())

    # 17. BackendVerifier - Failing Unit Test
    def test_17_verifier_run_tests_failing(self):
        self.sandbox.create_file(
            "backend/failing_test.py",
            "import unittest\n"
            "class FailTest(unittest.TestCase):\n"
            "    def test_fail(self):\n"
            "        self.assertEqual(1, 2)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        result = self.verifier.run_tests(test_path="backend/failing_test.py")
        self.assertFalse(result.passed)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("FAILED", result.summary())

    # 18. Agent 2 Autonomous Self-Repair Loop (Successful Repair)
    def test_18_backend_agent_autonomous_self_repair_success(self):
        # Scripted LLM tool calls:
        # 1. create_file with syntax bug: def calculate(:\n return 42
        # 2. verify_python_syntax -> fails
        # 3. edit_file with fix: def calculate():\n    return 42
        # 4. verify_python_syntax -> passes
        # 5. Final message: "Backend file calculate.py created and verified successfully."
        script = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "create_file",
                            "arguments": {
                                "path": "backend/calc.py",
                                "content": "def calculate(:\n    return 42\n"
                            }
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "verify_python_syntax",
                            "arguments": {
                                "file_path": "backend/calc.py"
                            }
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "edit_file",
                            "arguments": {
                                "path": "backend/calc.py",
                                "content": "def calculate():\n    return 42\n"
                            }
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "verify_python_syntax",
                            "arguments": {
                                "file_path": "backend/calc.py"
                            }
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": "Backend file calc.py created and verified successfully.",
                "tool_calls": None
            }
        ]

        scripted_llm = ScriptedToolMockLLMProvider(script)
        agent2 = BackendAgent(
            llm_provider=scripted_llm,
            agent_id="agent2",
            sandbox=self.sandbox,
            verifier=self.verifier,
            diary=self.diary,
            max_repair_attempts=3
        )

        tool_logs: List[str] = []
        def on_tool(name: str, args: dict, res: str):
            tool_logs.append(name)

        resp = agent2.process_request("Create calc.py and verify it.", on_tool_call=on_tool)

        self.assertIn("Backend file calc.py created and verified successfully.", resp)
        self.assertIn("create_file", tool_logs)
        self.assertIn("verify_python_syntax", tool_logs)
        self.assertIn("edit_file", tool_logs)

        # Check that file exists on disk with corrected content
        calc_content = self.sandbox.read_file("backend/calc.py")
        self.assertIn("def calculate():", calc_content)

    # 19. Agent 2 Bounded Self-Repair Loop (Exhaustion of Max Attempts)
    def test_19_backend_agent_bounded_self_repair_exhaustion(self):
        # Scripted LLM keeps creating broken syntax and verifying repeatedly > 3 times
        broken_code = "def broken(:\n    pass\n"
        script = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "create_file",
                            "arguments": {"path": "backend/bad.py", "content": broken_code}
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "verify_python_syntax",
                            "arguments": {"file_path": "backend/bad.py"}
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "verify_python_syntax",
                            "arguments": {"file_path": "backend/bad.py"}
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "verify_python_syntax",
                            "arguments": {"file_path": "backend/bad.py"}
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "verify_python_syntax",
                            "arguments": {"file_path": "backend/bad.py"}
                        }
                    }
                ]
            }
        ]

        scripted_llm = ScriptedToolMockLLMProvider(script)
        agent2 = BackendAgent(
            llm_provider=scripted_llm,
            agent_id="agent2",
            sandbox=self.sandbox,
            verifier=self.verifier,
            diary=self.diary,
            max_repair_attempts=3
        )

        resp = agent2.process_request("Create bad.py and verify.")
        self.assertIn("Maximum self-repair attempts (3) exhausted", resp)

    # 20. Code Sanitization in BackendAgent File Operations
    def test_20_backend_agent_code_sanitization(self):
        script = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "create_file",
                            "arguments": {
                                "path": "backend/wrapped.py",
                                "content": "{\"python\": \"from fastapi import FastAPI\\napp = FastAPI()\"}"
                            }
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": "Created wrapped.py without JSON artifacts.",
                "tool_calls": None
            }
        ]
        scripted_llm = ScriptedToolMockLLMProvider(script)
        agent2 = BackendAgent(
            llm_provider=scripted_llm,
            agent_id="agent2",
            sandbox=self.sandbox,
            verifier=self.verifier,
            diary=self.diary
        )

        resp = agent2.process_request("Create wrapped file.")
        content = self.sandbox.read_file("backend/wrapped.py")
        self.assertNotIn('{"python":', content)
        self.assertIn("from fastapi import FastAPI", content)

    # 21. Handle Agent Message with Explicit Action Metadata
    def test_21_handle_message_with_action_metadata(self):
        self.sandbox.create_file("backend/status.py", "STATUS = 'OK'\n")
        agent2 = BackendAgent(
            llm_provider=MockLLMProvider("Fallback"),
            agent_id="agent2",
            sandbox=self.sandbox,
            verifier=self.verifier,
            diary=self.diary
        )

        msg = AgentMessage(
            sender="agent5",
            recipient="agent2",
            message_type=MessageType.REQUEST,
            content="Check syntax of status.py",
            metadata={"action": "verify_python_syntax", "args": {"file_path": "backend/status.py"}}
        )
        response = agent2.handle_agent_message(msg)
        self.assertEqual(response.sender, "agent2")
        self.assertEqual(response.recipient, "agent5")
        self.assertIn("PASSED", response.content)
        self.assertEqual(response.metadata.get("status"), "COMPLETED")

    # 22. Tool Argument Validation Handling
    def test_22_tool_argument_validation(self):
        agent2 = BackendAgent(
            llm_provider=MockLLMProvider("Fallback"),
            agent_id="agent2",
            sandbox=self.sandbox,
            verifier=self.verifier,
            diary=self.diary
        )

        res_no_path = agent2._execute_tool("create_file", {})
        self.assertIn("Argument Error", res_no_path)

        res_no_verify_path = agent2._execute_tool("verify_python_syntax", {})
        self.assertIn("Argument Error", res_no_verify_path)

        res_unknown = agent2._execute_tool("unknown_tool", {})
        self.assertIn("Unknown tool", res_unknown)

    # 23. A5 to A2 Delegation with Backend Verification
    def test_23_a5_to_a2_delegation_flow(self):
        from agents.workspace_agent import WorkspaceAgent

        script = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "create_file",
                            "arguments": {
                                "path": "backend/service.py",
                                "content": "def run_service():\n    return {'status': 'healthy'}\n"
                            }
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "verify_python_syntax",
                            "arguments": {
                                "file_path": "backend/service.py"
                            }
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": "Backend service.py created and verified with passing syntax.",
                "tool_calls": None
            }
        ]
        scripted_llm = ScriptedToolMockLLMProvider(script)

        orchestrator = Orchestrator()
        agent2 = BackendAgent(
            llm_provider=scripted_llm,
            agent_id="agent2",
            sandbox=self.sandbox,
            verifier=self.verifier,
            diary=self.diary,
            orchestrator=orchestrator
        )
        orchestrator.register_agent(
            agent_id=agent2.agent_id,
            role=agent2.role,
            capabilities=agent2.capabilities,
            handler=agent2.handle_agent_message
        )

        agent5_mock = MockLLMProvider("Done")
        agent5 = WorkspaceAgent(
            llm_provider=agent5_mock,
            agent_id="agent5",
            sandbox=self.sandbox,
            diary=self.diary,
            orchestrator=orchestrator
        )
        orchestrator.register_agent(
            agent_id=agent5.agent_id,
            role=agent5.role,
            capabilities=agent5.capabilities,
            handler=agent5.handle_agent_message
        )

        delegation_res = agent5.delegate_task(
            target_agent="agent2",
            task="Implement backend service.py and verify it."
        )

        self.assertIn("Backend service.py created and verified", delegation_res)
        self.assertTrue((self.workspace_path / "backend" / "service.py").exists())

    # 24. Unconfigured Sandbox/Verifier Error Handling
    def test_24_unconfigured_sandbox_handling(self):
        agent_unconfigured = BackendAgent(
            llm_provider=MockLLMProvider("Fallback"),
            agent_id="agent2"
        )
        # Should return error strings gracefully
        err_verify = agent_unconfigured._tool_verify_python("foo.py")
        self.assertIn("Verification Error", err_verify)

        with self.assertRaises(RuntimeError):
            agent_unconfigured._tool_create_file("foo.py", "content")


if __name__ == "__main__":
    unittest.main()

