import unittest
import sys
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from agents.frontend_agent import FrontendAgent, DEFAULT_FRONTEND_CAPABILITIES
from orchestration import (
    MessageType,
    AgentMessage,
    Orchestrator
)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for unit testing without local/cloud models.
    """

    def __init__(self, fixed_response: str = "Mock frontend response") -> None:
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


class TestFrontendAgent(unittest.TestCase):
    """
    Deterministic unit tests for Agent 1 (Frontend Developer).
    Ensures zero dependency on external Ollama or live LLMs.
    """

    def setUp(self):
        self.mock_llm = MockLLMProvider("export const Button = () => <button>Click</button>;")
        self.orchestrator = Orchestrator()

        # Create FrontendAgent with injected mock LLM and Orchestrator
        self.agent1 = FrontendAgent(
            llm_provider=self.mock_llm,
            agent_id="agent1",
            orchestrator=self.orchestrator
        )

        # Register Agent 1 with the orchestrator
        self.orchestrator.register_agent(
            agent_id=self.agent1.agent_id,
            role=self.agent1.role,
            capabilities=self.agent1.capabilities,
            handler=self.agent1.handle_agent_message
        )

    # 1. Instantiation Test
    def test_01_agent_instantiation(self):
        self.assertIsNotNone(self.agent1)
        self.assertIsInstance(self.agent1, FrontendAgent)

    # 2. Identity and Role Test
    def test_02_identity_and_role(self):
        self.assertEqual(self.agent1.agent_id, "agent1")
        self.assertEqual(self.agent1.name, "Frontend Developer")
        self.assertEqual(self.agent1.role, "frontend_developer")
        self.assertIn("Frontend Developer", self.agent1.system_prompt)

    # 3. Correct Capabilities Test
    def test_03_capabilities(self):
        expected_caps = {"frontend_code", "frontend_files", "ui_components", "frontend_architecture"}
        self.assertEqual(self.agent1.capabilities, expected_caps)
        self.assertTrue(self.agent1.has_capability("frontend_code"))
        self.assertTrue(self.agent1.has_capability("ui_components"))
        self.assertTrue(self.agent1.has_capability("frontend_files"))
        self.assertTrue(self.agent1.has_capability("frontend_architecture"))

    # 4. Request Processing via Mock LLM Test
    def test_04_process_request(self):
        prompt = "Create a Button component."
        response = self.agent1.process_request(prompt)
        
        self.assertEqual(response, "export const Button = () => <button>Click</button>;")
        self.assertEqual(len(self.mock_llm.received_messages), 1)
        
        # Verify system prompt and user prompt were passed to LLM
        sent_messages = self.mock_llm.received_messages[0]
        self.assertEqual(sent_messages[0]["role"], "system")
        self.assertIn("Frontend Developer", sent_messages[0]["content"])
        self.assertEqual(sent_messages[1]["role"], "user")
        self.assertEqual(sent_messages[1]["content"], prompt)

    # 5. Conversation History Update Test
    def test_05_conversation_history(self):
        self.agent1.clear_history()
        self.assertEqual(len(self.agent1.get_history()), 0)

        self.agent1.process_request("First request")
        self.agent1.process_request("Second request")

        history = self.agent1.get_history()
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "First request")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[2]["role"], "user")
        self.assertEqual(history[2]["content"], "Second request")
        self.assertEqual(history[3]["role"], "assistant")

    # 6. Send AgentMessage Through Orchestration Layer Test
    def test_06_send_agent_message_through_orchestrator(self):
        # Register a mock recipient (agent2)
        def mock_agent2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("API endpoint is /api/v1/auth/login")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"api", "backend_code"},
            handler=mock_agent2_handler
        )

        response = self.agent1.send_agent_message(
            recipient="agent2",
            content="I need the login API route."
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent2")
        self.assertEqual(response.recipient, "agent1")
        self.assertEqual(response.content, "API endpoint is /api/v1/auth/login")

    # 7. Communicate with Mocked Agent 2 (Backend Developer) Test
    def test_07_communicate_with_mocked_agent2(self):
        def agent2_handler(msg: AgentMessage) -> AgentMessage:
            if "login form" in msg.content:
                return msg.create_response("POST /api/login expects { email, password }")
            return msg.create_response("Generic backend response")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"api", "backend_code", "backend_files"},
            handler=agent2_handler
        )

        resp = self.agent1.send_agent_message(
            recipient="agent2",
            content="I need the API contract for the login form."
        )
        self.assertEqual(resp.content, "POST /api/login expects { email, password }")

    # 8. Communicate with Mocked Agent 5 (Workspace Manager) Test
    def test_08_communicate_with_mocked_agent5(self):
        def agent5_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Workspace action: File frontend/src/App.jsx created successfully")

        self.orchestrator.register_agent(
            agent_id="agent5",
            role="workspace_manager",
            capabilities={"filesystem", "workspace", "diary"},
            handler=agent5_handler
        )

        resp = self.agent1.send_agent_message(
            recipient="agent5",
            content="I need frontend/src/App.jsx created with Button component.",
            required_capability="filesystem"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.sender, "agent5")
        self.assertIn("File frontend/src/App.jsx created", resp.content)

    # 9. Inability to Claim Backend/DB/Supervisor Capabilities Test
    def test_09_cannot_claim_backend_or_db_capabilities(self):
        # Frontend agent must not have backend/db/supervisor capabilities
        disallowed_capabilities = [
            "backend_code",
            "backend_files",
            "api",
            "database_schema",
            "migrations",
            "crud",
            "monitoring",
            "scope_validation",
            "escalation",
            "permission_handling",
            "filesystem",
            "workspace"
        ]

        for cap in disallowed_capabilities:
            self.assertFalse(
                self.agent1.has_capability(cap),
                f"Agent 1 should not possess capability '{cap}'"
            )
            self.assertFalse(
                self.orchestrator.registry.has_capability("agent1", cap),
                f"Registry should not report Agent 1 having capability '{cap}'"
            )

    # 10. Direct Incoming Message Handling Test
    def test_10_incoming_message_handling(self):
        incoming_msg = AgentMessage(
            sender="agent2",
            recipient="agent1",
            message_type=MessageType.REQUEST,
            content="Please generate the frontend UserProfile component."
        )
        response = self.agent1.handle_agent_message(incoming_msg)
        
        self.assertEqual(response.sender, "agent1")
        self.assertEqual(response.recipient, "agent2")
        self.assertEqual(response.correlation_id, incoming_msg.message_id)
        self.assertEqual(response.content, "export const Button = () => <button>Click</button>;")


if __name__ == "__main__":
    unittest.main()

