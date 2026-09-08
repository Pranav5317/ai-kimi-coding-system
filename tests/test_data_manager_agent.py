import unittest
import sys
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from agents.data_manager_agent import DataManagerAgent, DEFAULT_DATA_MANAGER_CAPABILITIES
from orchestration import (
    MessageType,
    AgentMessage,
    Orchestrator
)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for unit testing without local/cloud models.
    """

    def __init__(self, fixed_response: str = "Mock data manager response") -> None:
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


class TestDataManagerAgent(unittest.TestCase):
    """
    Deterministic unit tests for Agent 3 (Data Manager).
    Ensures zero dependency on external Ollama or live LLMs.
    """

    def setUp(self):
        self.mock_llm = MockLLMProvider("CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE);")
        self.orchestrator = Orchestrator()

        # Create DataManagerAgent with injected mock LLM and Orchestrator
        self.agent3 = DataManagerAgent(
            llm_provider=self.mock_llm,
            agent_id="agent3",
            orchestrator=self.orchestrator
        )

        # Register Agent 3 with the orchestrator
        self.orchestrator.register_agent(
            agent_id=self.agent3.agent_id,
            role=self.agent3.role,
            capabilities=self.agent3.capabilities,
            handler=self.agent3.handle_agent_message
        )

    # 1. Instantiation Test
    def test_01_agent_instantiation(self):
        self.assertIsNotNone(self.agent3)
        self.assertIsInstance(self.agent3, DataManagerAgent)

    # 2. Identity and Role Test
    def test_02_identity_and_role(self):
        self.assertEqual(self.agent3.agent_id, "agent3")
        self.assertEqual(self.agent3.name, "Data Manager")
        self.assertEqual(self.agent3.role, "data_manager")
        self.assertIn("Data Manager", self.agent3.system_prompt)

    # 3. Correct Capabilities Test
    def test_03_capabilities(self):
        expected_caps = {"database_schema", "migrations", "crud", "data_models"}
        self.assertEqual(self.agent3.capabilities, expected_caps)
        self.assertTrue(self.agent3.has_capability("database_schema"))
        self.assertTrue(self.agent3.has_capability("migrations"))
        self.assertTrue(self.agent3.has_capability("crud"))
        self.assertTrue(self.agent3.has_capability("data_models"))

    # 4. Request Processing via Mock LLM Test
    def test_04_process_request(self):
        prompt = "Create a PostgreSQL users table schema."
        response = self.agent3.process_request(prompt)

        self.assertEqual(response, "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE);")
        self.assertEqual(len(self.mock_llm.received_messages), 1)

        sent_messages = self.mock_llm.received_messages[0]
        self.assertEqual(sent_messages[0]["role"], "system")
        self.assertIn("Data Manager", sent_messages[0]["content"])
        self.assertEqual(sent_messages[1]["role"], "user")
        self.assertEqual(sent_messages[1]["content"], prompt)

    # 5. Conversation History Update Test
    def test_05_conversation_history(self):
        self.agent3.clear_history()
        self.assertEqual(len(self.agent3.get_history()), 0)

        self.agent3.process_request("Define User data model")
        self.agent3.process_request("Add password_hash field")

        history = self.agent3.get_history()
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Define User data model")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[2]["role"], "user")
        self.assertEqual(history[2]["content"], "Add password_hash field")
        self.assertEqual(history[3]["role"], "assistant")

    # 6. Send AgentMessage Through Orchestrator Test
    def test_06_send_agent_message_through_orchestrator(self):
        def mock_agent2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Backend received schema")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"api", "backend_code"},
            handler=mock_agent2_handler
        )

        response = self.agent3.send_agent_message(
            recipient="agent2",
            content="Here is the user entity definition: { id: int, email: str }"
        )

        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent2")
        self.assertEqual(response.recipient, "agent3")
        self.assertEqual(response.content, "Backend received schema")

    # 7. Communicate with Mocked Agent 1 (Frontend Developer) Test
    def test_07_communicate_with_mocked_agent1(self):
        def agent1_handler(msg: AgentMessage) -> AgentMessage:
            if "user data fields" in msg.content:
                return msg.create_response("Frontend received expected user fields: id, name, email")
            return msg.create_response("Agent 1 acknowledged")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code", "frontend_files", "ui_components"},
            handler=agent1_handler
        )

        resp = self.agent3.send_agent_message(
            recipient="agent1",
            content="Here are the user data fields required by the frontend: { id, name, email, created_at }",
            required_capability="frontend_code"
        )
        self.assertEqual(resp.content, "Frontend received expected user fields: id, name, email")

    # 8. Communicate with Mocked Agent 2 (Backend Developer) Test
    def test_08_communicate_with_mocked_agent2(self):
        def agent2_handler(msg: AgentMessage) -> AgentMessage:
            if "users table" in msg.content:
                return msg.create_response("Backend models updated with users table fields")
            return msg.create_response("Agent 2 acknowledged")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code", "backend_files", "api"},
            handler=agent2_handler
        )

        resp = self.agent3.send_agent_message(
            recipient="agent2",
            content="Here is the required schema and CRUD requirement for users table.",
            required_capability="backend_code"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.sender, "agent2")
        self.assertIn("Backend models updated", resp.content)

    # 9. Send ESCALATION to Mocked Agent 4 (Supervisor) Test
    def test_09_escalation_to_mocked_agent4(self):
        def agent4_handler(msg: AgentMessage) -> AgentMessage:
            if msg.message_type == MessageType.ESCALATION:
                return msg.create_response("Agent 4 supervisor logged scope escalation: database clustering outside scope")
            return msg.create_response("Agent 4 acknowledged")

        self.orchestrator.register_agent(
            agent_id="agent4",
            role="supervisor",
            capabilities={"monitoring", "scope_validation", "escalation", "permission_handling"},
            handler=agent4_handler
        )

        esc_resp = self.orchestrator.escalate(
            sender="agent3",
            content="Database clustering and multi-region replication requested outside current project scope."
        )
        self.assertIsNotNone(esc_resp)
        self.assertEqual(esc_resp.sender, "agent4")
        self.assertIn("logged scope escalation", esc_resp.content)

    # 10. Send PERMISSION_REQUEST to Mocked Agent 4 (Supervisor) Test
    def test_10_permission_request_to_mocked_agent4(self):
        def agent4_handler(msg: AgentMessage) -> AgentMessage:
            if msg.message_type == MessageType.PERMISSION_REQUEST:
                return msg.create_response("Agent 4 routed permission request to user: DROP TABLE permission pending")
            return msg.create_response("Agent 4 acknowledged")

        self.orchestrator.register_agent(
            agent_id="agent4",
            role="supervisor",
            capabilities={"monitoring", "scope_validation", "escalation", "permission_handling"},
            handler=agent4_handler
        )

        perm_resp = self.orchestrator.request_permission(
            sender="agent3",
            content="Changing production schema and dropping legacy column requires user permission."
        )
        self.assertIsNotNone(perm_resp)
        self.assertEqual(perm_resp.sender, "agent4")
        self.assertIn("routed permission request to user", perm_resp.content)

    # 11. Communicate with Mocked Agent 5 (Workspace Manager) Test
    def test_11_communicate_with_mocked_agent5(self):
        def agent5_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 5 created migration file in project workspace")

        self.orchestrator.register_agent(
            agent_id="agent5",
            role="workspace_manager",
            capabilities={"filesystem", "workspace", "dev_server", "diary"},
            handler=agent5_handler
        )

        resp = self.agent3.send_agent_message(
            recipient="agent5",
            content="Create database migration file 001_initial_schema.sql in appropriate project location",
            required_capability="filesystem"
        )
        self.assertIsNotNone(resp)
        self.assertEqual(resp.sender, "agent5")
        self.assertIn("created migration file", resp.content)

    # 12. Inability to Claim Disallowed Capabilities Test
    def test_12_cannot_claim_disallowed_capabilities(self):
        disallowed_capabilities = [
            "frontend_code",
            "frontend_files",
            "ui_components",
            "frontend_architecture",
            "backend_code",
            "backend_files",
            "api",
            "backend_architecture",
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
                self.agent3.has_capability(cap),
                f"Agent 3 should not possess capability '{cap}'"
            )
            self.assertFalse(
                self.orchestrator.registry.has_capability("agent3", cap),
                f"Registry should not report Agent 3 having capability '{cap}'"
            )


if __name__ == "__main__":
    unittest.main()

