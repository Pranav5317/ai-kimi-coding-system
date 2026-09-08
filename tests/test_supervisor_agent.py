import unittest
import sys
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from agents.supervisor_agent import SupervisorAgent, DEFAULT_SUPERVISOR_CAPABILITIES
from orchestration import (
    MessageType,
    AgentMessage,
    Orchestrator
)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for supervisor unit testing.
    """

    def __init__(self, fixed_response: str = "Supervisor assessment: In scope.") -> None:
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


class TestSupervisorAgent(unittest.TestCase):
    """
    Deterministic unit tests for Agent 4 (Supervisor / Monitor / Spectator).
    Ensures zero dependency on external Ollama or live LLMs.
    """

    def setUp(self):
        self.mock_llm = MockLLMProvider("Supervisor evaluation: Task is aligned with project goals.")
        self.orchestrator = Orchestrator()

        # Create SupervisorAgent with injected mock LLM, Orchestrator, and scope
        self.agent4 = SupervisorAgent(
            llm_provider=self.mock_llm,
            agent_id="agent4",
            orchestrator=self.orchestrator,
            project_scope="Build an e-commerce shopping cart web application"
        )

        # Register Agent 4 as an agent handler and as a non-intrusive observer on the bus
        self.orchestrator.register_agent(
            agent_id=self.agent4.agent_id,
            role=self.agent4.role,
            capabilities=self.agent4.capabilities,
            handler=self.agent4.handle_agent_message
        )
        self.orchestrator.register_observer(self.agent4.observe_message)

    # 1. Instantiation Test
    def test_01_agent_instantiation(self):
        self.assertIsNotNone(self.agent4)
        self.assertIsInstance(self.agent4, SupervisorAgent)

    # 2. Identity and Role Test
    def test_02_identity_and_role(self):
        self.assertEqual(self.agent4.agent_id, "agent4")
        self.assertEqual(self.agent4.name, "Supervisor")
        self.assertEqual(self.agent4.role, "supervisor")
        self.assertIn("Supervisor", self.agent4.system_prompt)

    # 3. Supervisor Capabilities Test
    def test_03_capabilities(self):
        expected_caps = {
            "monitoring",
            "scope_validation",
            "escalation",
            "permission_handling",
            "logistics_monitoring"
        }
        self.assertEqual(self.agent4.capabilities, expected_caps)
        self.assertTrue(self.agent4.has_capability("monitoring"))
        self.assertTrue(self.agent4.has_capability("scope_validation"))
        self.assertTrue(self.agent4.has_capability("escalation"))
        self.assertTrue(self.agent4.has_capability("permission_handling"))
        self.assertTrue(self.agent4.has_capability("logistics_monitoring"))

    # 4. Monitoring Request Processing via Mock LLM
    def test_04_process_monitoring_request(self):
        prompt = "Assess current project milestone logistics."
        response = self.agent4.process_request(prompt)

        self.assertEqual(response, "Supervisor evaluation: Task is aligned with project goals.")
        self.assertEqual(len(self.mock_llm.received_messages), 1)

        sent_messages = self.mock_llm.received_messages[0]
        self.assertEqual(sent_messages[0]["role"], "system")
        self.assertIn("Supervisor", sent_messages[0]["content"])
        self.assertEqual(sent_messages[1]["role"], "user")
        self.assertEqual(sent_messages[1]["content"], prompt)

    # 5 & 7 & 8. Observation of normal A1 -> A2 message with Direct Delivery
    def test_05_observe_a1_to_a2_message_direct_delivery(self):
        a2_received = []

        def mock_a2_handler(msg: AgentMessage) -> AgentMessage:
            a2_received.append(msg)
            return msg.create_response("Backend received frontend contract request")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code"}
        )
        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"api", "backend_code"},
            handler=mock_a2_handler
        )

        msg = AgentMessage(
            sender="agent1",
            recipient="agent2",
            message_type=MessageType.REQUEST,
            content="I need the cart items endpoint schema"
        )
        response = self.orchestrator.send_message(msg)

        # 7. Verify message reached A2 directly
        self.assertEqual(len(a2_received), 1)
        self.assertEqual(a2_received[0].content, "I need the cart items endpoint schema")
        self.assertEqual(response.content, "Backend received frontend contract request")

        # 5 & 8. Verify A4 observed the message without blocking or replacing A2
        obs_history = self.agent4.get_observation_history()
        self.assertTrue(any(m.content == "I need the cart items endpoint schema" for m in obs_history))

    # 6. Observation of normal A2 -> A3 message
    def test_06_observe_a2_to_a3_message(self):
        def mock_a3_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Data Manager provided Cart schema")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"}
        )
        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema"},
            handler=mock_a3_handler
        )

        msg = AgentMessage(
            sender="agent2",
            recipient="agent3",
            message_type=MessageType.REQUEST,
            content="Need database schema for Cart table"
        )
        self.orchestrator.send_message(msg)

        obs_history = self.agent4.get_observation_history()
        self.assertTrue(any("Cart table" in m.content for m in obs_history))

    # 9. Receive ESCALATION
    def test_09_receive_escalation(self):
        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"}
        )

        esc_msg = AgentMessage(
            sender="agent2",
            recipient="agent4",
            message_type=MessageType.ESCALATION,
            content="User requested bitcoin payment processing, which exceeds defined e-commerce cart scope."
        )
        response = self.orchestrator.send_message(esc_msg, required_capability="escalation")

        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent4")
        self.assertEqual(response.recipient, "agent2")
        self.assertIn("logged escalation", response.content)

        # Check recorded escalations
        escalations = self.agent4.get_escalations()
        self.assertEqual(len(escalations), 1)
        self.assertEqual(escalations[0]["sender"], "agent2")
        self.assertIn("bitcoin payment", escalations[0]["content"])

    # 10 & 11 & 12. Receive PERMISSION_REQUEST & Structured Pending State
    def test_10_permission_request_pending_state(self):
        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"migrations"}
        )

        perm_msg = AgentMessage(
            sender="agent3",
            recipient="agent4",
            message_type=MessageType.PERMISSION_REQUEST,
            content="Drop legacy order_items table column"
        )
        response = self.orchestrator.send_message(perm_msg, required_capability="permission_handling")

        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent4")
        self.assertEqual(response.recipient, "agent3")
        self.assertIn("PENDING_USER_APPROVAL", response.content)

        # 11. Check structured pending approval state
        pending_list = self.agent4.get_pending_permissions()
        self.assertEqual(len(pending_list), 1)
        pending = pending_list[0]
        self.assertEqual(pending["status"], "PENDING_USER_APPROVAL")
        self.assertEqual(pending["requesting_agent"], "agent3")
        self.assertEqual(pending["action"], "Drop legacy order_items table column")

        # 12. Verify permission was NOT automatically granted
        self.assertNotEqual(pending["status"], "GRANTED")
        self.assertNotEqual(pending["status"], "APPROVED")

    # 13. Communicate with Mocked A1 (Frontend Developer)
    def test_13_communicate_with_mocked_a1(self):
        def a1_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 1 acknowledged supervisor guidance on UI state")

        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code"},
            handler=a1_handler
        )

        resp = self.agent4.send_agent_message(
            recipient="agent1",
            content="Please ensure shopping cart UI matches the approved mockups."
        )
        self.assertEqual(resp.content, "Agent 1 acknowledged supervisor guidance on UI state")

    # 14. Communicate with Mocked A2 (Backend Developer)
    def test_14_communicate_with_mocked_a2(self):
        def a2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 2 acknowledged API rate-limiting scope guidance")

        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code"},
            handler=a2_handler
        )

        resp = self.agent4.send_agent_message(
            recipient="agent2",
            content="Please implement rate limiting on checkout endpoints."
        )
        self.assertEqual(resp.content, "Agent 2 acknowledged API rate-limiting scope guidance")

    # 15. Communicate with Mocked A3 (Data Manager)
    def test_15_communicate_with_mocked_a3(self):
        def a3_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 3 confirmed schema review completed")

        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema"},
            handler=a3_handler
        )

        resp = self.agent4.send_agent_message(
            recipient="agent3",
            content="Please confirm cart session migration safety."
        )
        self.assertEqual(resp.content, "Agent 3 confirmed schema review completed")

    # 16. Communicate with Mocked A5 (Workspace Manager)
    def test_16_communicate_with_mocked_a5(self):
        def a5_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response("Agent 5 reported dev server running on port 3000")

        self.orchestrator.register_agent(
            agent_id="agent5",
            role="workspace_manager",
            capabilities={"workspace", "dev_server"},
            handler=a5_handler
        )

        resp = self.agent4.send_agent_message(
            recipient="agent5",
            content="Querying application runtime status",
            required_capability="workspace"
        )
        self.assertIn("dev server running on port 3000", resp.content)

    # 17. Inability to Claim Development / Filesystem Capabilities
    def test_17_cannot_claim_disallowed_capabilities(self):
        disallowed = [
            "frontend_code",
            "frontend_files",
            "ui_components",
            "frontend_architecture",
            "backend_code",
            "backend_files",
            "api",
            "backend_architecture",
            "database_schema",
            "migrations",
            "crud",
            "data_models",
            "filesystem",
            "workspace",
            "dev_server"
        ]

        for cap in disallowed:
            self.assertFalse(
                self.agent4.has_capability(cap),
                f"Agent 4 should not possess capability '{cap}'"
            )
            self.assertFalse(
                self.orchestrator.registry.has_capability("agent4", cap),
                f"Registry should not report Agent 4 having capability '{cap}'"
            )

    # 18. Scope Context Availability
    def test_18_scope_context_availability(self):
        self.assertEqual(self.agent4.project_scope, "Build an e-commerce shopping cart web application")
        scope_eval = self.agent4.check_scope("Add checkout payment step")
        self.assertTrue(scope_eval["in_scope"])
        self.assertEqual(scope_eval["project_scope"], "Build an e-commerce shopping cart web application")

    # 19. Observation History is Separate from CodeDiary
    def test_19_observation_history_separation(self):
        self.agent4.clear_observation_history()
        self.assertEqual(len(self.agent4.get_observation_history()), 0)

        test_msg = AgentMessage(
            sender="agent1",
            recipient="agent2",
            message_type=MessageType.INFORMATION,
            content="UI theme loaded"
        )
        self.agent4.observe_message(test_msg)

        obs = self.agent4.get_observation_history()
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].content, "UI theme loaded")


if __name__ == "__main__":
    unittest.main()

