import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestration import (
    MessageType,
    AgentMessage,
    AgentRegistry,
    AgentRegistration,
    MessageBus,
    Orchestrator
)


class TestOrchestrationLayer(unittest.TestCase):
    """
    Deterministic unit tests for the multi-agent orchestration/communication layer.
    These tests do not invoke Ollama or any LLM.
    """

    def setUp(self):
        self.orchestrator = Orchestrator()

        # Define standard mock handlers for testing
        def agent1_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response(f"Agent1 received: {msg.content}")

        def agent2_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response(f"Agent2 received: {msg.content}")

        def agent3_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response(f"Agent3 received: {msg.content}")

        def agent4_handler(msg: AgentMessage) -> AgentMessage:
            if msg.message_type == MessageType.PERMISSION_REQUEST:
                return msg.create_response("Permission GRANTED by Agent 4")
            elif msg.message_type == MessageType.ESCALATION:
                return msg.create_response("Escalation ACKNOWLEDGED by Agent 4")
            return msg.create_response(f"Agent4 received: {msg.content}")

        def agent5_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response(f"Agent5 workspace operation queued: {msg.content}")

        # Register standard 5 agents with architectural roles and capabilities
        self.orchestrator.register_agent(
            agent_id="agent1",
            role="frontend_developer",
            capabilities={"frontend_code", "frontend_files"},
            handler=agent1_handler
        )
        self.orchestrator.register_agent(
            agent_id="agent2",
            role="backend_developer",
            capabilities={"backend_code", "backend_files", "api"},
            handler=agent2_handler
        )
        self.orchestrator.register_agent(
            agent_id="agent3",
            role="data_manager",
            capabilities={"database_schema", "migrations", "crud"},
            handler=agent3_handler
        )
        self.orchestrator.register_agent(
            agent_id="agent4",
            role="supervisor",
            capabilities={"monitoring", "scope_validation", "escalation", "permission_handling"},
            handler=agent4_handler
        )
        self.orchestrator.register_agent(
            agent_id="agent5",
            role="workspace_manager",
            capabilities={"filesystem", "workspace", "dev_server", "diary"},
            handler=agent5_handler
        )

    # 1. Agent Registration Test
    def test_01_agent_registration(self):
        reg = self.orchestrator.registry.get_agent("agent1")
        self.assertIsNotNone(reg)
        self.assertEqual(reg.agent_id, "agent1")
        self.assertEqual(reg.role, "frontend_developer")
        self.assertTrue(reg.has_capability("frontend_code"))
        self.assertEqual(len(self.orchestrator.registry.list_agents()), 5)

    # 2. Duplicate Registration Rejection Test
    def test_02_duplicate_agent_registration_rejection(self):
        with self.assertRaises(ValueError) as ctx:
            self.orchestrator.register_agent(
                agent_id="agent1",
                role="duplicate_role",
                capabilities={"some_capability"}
            )
        self.assertIn("already registered", str(ctx.exception))

    # 3. Unknown Recipient Rejection Test
    def test_03_unknown_recipient_rejection(self):
        msg = AgentMessage(
            sender="agent1",
            recipient="non_existent_agent",
            message_type=MessageType.REQUEST,
            content="Hello?"
        )
        with self.assertRaises(KeyError) as ctx:
            self.orchestrator.send_message(msg)
        self.assertIn("non_existent_agent", str(ctx.exception))

    # 4. Basic Agent 1 -> Agent 2 Message Routing Test
    def test_04_agent1_to_agent2_routing(self):
        req = AgentMessage(
            sender="agent1",
            recipient="agent2",
            message_type=MessageType.REQUEST,
            content="I need the backend API endpoint for user registration."
        )
        response = self.orchestrator.send_message(req)
        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent2")
        self.assertEqual(response.recipient, "agent1")
        self.assertEqual(response.message_type, MessageType.RESPONSE)
        self.assertEqual(response.correlation_id, req.message_id)
        self.assertIn("Agent2 received: I need the backend API endpoint", response.content)

    # 5. Agent 2 -> Agent 3 Routing Test
    def test_05_agent2_to_agent3_routing(self):
        req = AgentMessage(
            sender="agent2",
            recipient="agent3",
            message_type=MessageType.REQUEST,
            content="Please provide the database schema for users table."
        )
        response = self.orchestrator.send_message(req)
        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent3")
        self.assertEqual(response.recipient, "agent2")
        self.assertIn("Agent3 received", response.content)

    # 6. Escalation to Agent 4 Test
    def test_06_escalation_to_agent4(self):
        response = self.orchestrator.escalate(
            sender="agent2",
            content="Scope change detected: User requested payment gateway integration."
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent4")
        self.assertEqual(response.recipient, "agent2")
        self.assertEqual(response.content, "Escalation ACKNOWLEDGED by Agent 4")

    # 7. Permission Request to Agent 4 Test
    def test_07_permission_request_to_agent4(self):
        response = self.orchestrator.request_permission(
            sender="agent3",
            content="Requesting permission to run destructive migration on database."
        )
        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent4")
        self.assertEqual(response.recipient, "agent3")
        self.assertEqual(response.content, "Permission GRANTED by Agent 4")

    # 8. Agent 1 -> Agent 5 Routing Test
    def test_08_agent1_to_agent5_routing(self):
        req = AgentMessage(
            sender="agent1",
            recipient="agent5",
            message_type=MessageType.REQUEST,
            content="Create frontend/components/Button.tsx file"
        )
        response = self.orchestrator.send_message(req, required_capability="filesystem")
        self.assertIsNotNone(response)
        self.assertEqual(response.sender, "agent5")
        self.assertEqual(response.recipient, "agent1")
        self.assertIn("Agent5 workspace operation queued", response.content)

    # 9. Capability Validation Test
    def test_09_capability_validation(self):
        # Valid capability check on agent2 (has 'api')
        req_valid = AgentMessage(
            sender="agent1",
            recipient="agent2",
            message_type=MessageType.REQUEST,
            content="Check API routes"
        )
        resp_valid = self.orchestrator.send_message(req_valid, required_capability="api")
        self.assertIsNotNone(resp_valid)

        # Invalid capability check on agent2 (does NOT have 'database_schema')
        req_invalid = AgentMessage(
            sender="agent1",
            recipient="agent2",
            message_type=MessageType.REQUEST,
            content="Alter database schema"
        )
        with self.assertRaises(PermissionError) as ctx:
            self.orchestrator.send_message(req_invalid, required_capability="database_schema")
        self.assertIn("Capability Validation Failed", str(ctx.exception))

    # 10. Message History Test
    def test_10_message_history(self):
        self.orchestrator.clear_history()
        self.assertEqual(len(self.orchestrator.get_message_history()), 0)

        msg = AgentMessage(
            sender="agent1",
            recipient="agent2",
            message_type=MessageType.REQUEST,
            content="Ping"
        )
        self.orchestrator.send_message(msg)

        history = self.orchestrator.get_message_history()
        # History should contain both outgoing request and incoming response
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].sender, "agent1")
        self.assertEqual(history[0].content, "Ping")
        self.assertEqual(history[1].sender, "agent2")
        self.assertEqual(history[1].correlation_id, history[0].message_id)

    # 11. Message IDs, Timestamps, and Correlation IDs Behavior
    def test_11_message_ids_timestamps_correlation(self):
        msg = AgentMessage(
            sender="agent1",
            recipient="agent2",
            message_type=MessageType.REQUEST,
            content="Test correlation and metadata",
            metadata={"priority": "high", "attempt": 1}
        )
        self.assertTrue(msg.message_id.startswith("msg_"))
        self.assertIsNotNone(msg.timestamp)
        self.assertEqual(msg.metadata["priority"], "high")

        # Serialization / Deserialization
        msg_dict = msg.to_dict()
        reconstructed = AgentMessage.from_dict(msg_dict)
        self.assertEqual(reconstructed.message_id, msg.message_id)
        self.assertEqual(reconstructed.sender, msg.sender)
        self.assertEqual(reconstructed.recipient, msg.recipient)
        self.assertEqual(reconstructed.message_type, msg.message_type)
        self.assertEqual(reconstructed.content, msg.content)
        self.assertEqual(reconstructed.metadata, msg.metadata)

        # Correlated response
        response = msg.create_response("Response to test")
        self.assertEqual(response.correlation_id, msg.message_id)
        self.assertEqual(response.sender, "agent2")
        self.assertEqual(response.recipient, "agent1")


if __name__ == "__main__":
    unittest.main()

