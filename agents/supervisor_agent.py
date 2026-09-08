from typing import Optional, Set, Dict, Any, List, Union
from llm.base import BaseLLMProvider
from .base_agent import BaseAgent
from orchestration.messages import AgentMessage, MessageType


DEFAULT_SUPERVISOR_SYSTEM_PROMPT = (
    "You are Agent 4 (Supervisor / Monitor / Spectator) in an AI multi-agent software engineering system.\n"
    "You are responsible for:\n"
    "- Actively observing activity and communication between Agents 1, 2, and 3\n"
    "- Monitoring project scope, boundaries, and logistics\n"
    "- Receiving and managing escalations from other agents\n"
    "- Receiving permission requests and registering them for user review\n"
    "- Communicating guidance and scope clarifications to Agents 1, 2, 3, and 5\n\n"
    "You are NOT a development agent and you must NOT:\n"
    "- Implement frontend code, backend code, or database schemas\n"
    "- Perform database migrations or execute direct filesystem operations\n"
    "- Start/stop servers or replace the workspace management duties of Agent 5\n"
    "- Silently approve or autonomously grant user permission requests without human review\n"
    "- Intercept, block, or delay normal direct communication between Agents 1, 2, and 3."
)

DEFAULT_SUPERVISOR_CAPABILITIES: Set[str] = {
    "monitoring",
    "scope_validation",
    "escalation",
    "permission_handling",
    "logistics_monitoring"
}


class SupervisorAgent(BaseAgent):
    """
    Agent 4: Supervisor / Monitor / Spectator.
    
    Serves as the governance and monitoring layer for the multi-agent system.
    Observes normal agent communication non-intrusively, monitors project scope,
    logs escalations, registers pending permission requests for human review,
    and communicates guidance across all agents.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        agent_id: str = "agent4",
        name: str = "Supervisor",
        role: str = "supervisor",
        system_prompt: Optional[str] = None,
        capabilities: Optional[Union[Set[str], list]] = None,
        orchestrator: Optional[Any] = None,
        project_scope: str = "General software engineering project"
    ) -> None:
        super().__init__(
            name=name,
            role=role,
            system_prompt=system_prompt if system_prompt is not None else DEFAULT_SUPERVISOR_SYSTEM_PROMPT,
            llm_provider=llm_provider
        )
        self.agent_id = agent_id
        self.capabilities = set(capabilities) if capabilities is not None else set(DEFAULT_SUPERVISOR_CAPABILITIES)
        self.orchestrator = orchestrator
        self.project_scope = project_scope

        # Supervisor-specific in-memory logs (kept separate from CodeDiary)
        self.observation_history: List[AgentMessage] = []
        self.pending_permissions: Dict[str, Dict[str, Any]] = {}
        self.escalations: List[Dict[str, Any]] = []

    def has_capability(self, capability: str) -> bool:
        """Checks if SupervisorAgent possesses the given capability token."""
        return capability in self.capabilities

    def observe_message(self, message: AgentMessage) -> None:
        """
        Non-intrusive observation callback.
        Receives an observation copy of any message routed across the MessageBus
        and records it in the supervisor observation history.
        """
        if isinstance(message, AgentMessage):
            self.observation_history.append(message)

    def get_observation_history(self) -> List[AgentMessage]:
        """Returns a copy of all observed messages."""
        return list(self.observation_history)

    def clear_observation_history(self) -> None:
        """Clears the supervisor observation history."""
        self.observation_history.clear()

    def get_pending_permissions(self) -> List[Dict[str, Any]]:
        """Returns all structured permission requests currently pending user approval."""
        return list(self.pending_permissions.values())

    def get_escalations(self) -> List[Dict[str, Any]]:
        """Returns all recorded escalation events."""
        return list(self.escalations)

    def process_request(self, prompt: str) -> str:
        """
        Processes a monitoring, supervision, or scope analysis prompt using the injected LLM provider.
        """
        messages = self._prepare_messages(prompt)
        self.add_message("user", prompt)

        raw_response = self.llm_provider.chat(messages)

        if isinstance(raw_response, dict):
            response_text = raw_response.get("content", "").strip()
        else:
            response_text = str(raw_response).strip()

        self.add_message("assistant", response_text)
        return response_text

    def check_scope(self, activity_description: str) -> Dict[str, Any]:
        """
        Evaluates whether a described activity or requirement falls within the defined project scope.
        """
        eval_prompt = (
            f"Defined Project Scope: {self.project_scope}\n\n"
            f"Proposed Activity/Feature: {activity_description}\n\n"
            "Assess whether this activity is within the project scope or represents scope creep. "
            "Provide your assessment and reasoning."
        )
        assessment = self.process_request(eval_prompt)
        is_in_scope = "out of scope" not in assessment.lower() and "outside scope" not in assessment.lower()

        return {
            "in_scope": is_in_scope,
            "project_scope": self.project_scope,
            "assessment": assessment
        }

    def send_agent_message(
        self,
        recipient: str,
        content: str,
        message_type: MessageType = MessageType.REQUEST,
        required_capability: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """
        Sends an AgentMessage to a peer agent (A1, A2, A3, A5) via the Orchestrator.
        """
        if self.orchestrator is None:
            raise RuntimeError(f"Agent '{self.agent_id}' has no Orchestrator configured for messaging.")

        msg = AgentMessage(
            sender=self.agent_id,
            recipient=recipient,
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )
        return self.orchestrator.send_message(msg, required_capability=required_capability)

    def handle_agent_message(self, message: AgentMessage) -> AgentMessage:
        """
        Handles messages directed specifically to Agent 4:
        - PERMISSION_REQUEST: Creates a structured pending user-approval state (does not auto-grant).
        - ESCALATION: Logs and acknowledges the escalation.
        - REQUEST: Processes via LLM reasoning.
        """
        # Always record incoming direct message in observation history
        self.observe_message(message)

        if message.message_type == MessageType.PERMISSION_REQUEST:
            # Create structured pending user approval state
            pending_record: Dict[str, Any] = {
                "request_id": message.message_id,
                "status": "PENDING_USER_APPROVAL",
                "requesting_agent": message.sender,
                "action": message.content,
                "timestamp": message.timestamp,
                "metadata": dict(message.metadata)
            }
            self.pending_permissions[message.message_id] = pending_record

            # Respond without silently granting permission
            return message.create_response(
                content=(
                    f"Permission request [{message.message_id}] registered as PENDING_USER_APPROVAL "
                    f"for agent '{message.sender}'. Action: {message.content}"
                ),
                message_type=MessageType.RESPONSE,
                metadata={"status": "PENDING_USER_APPROVAL", "request_id": message.message_id}
            )

        elif message.message_type == MessageType.ESCALATION:
            escalation_record: Dict[str, Any] = {
                "escalation_id": message.message_id,
                "sender": message.sender,
                "content": message.content,
                "timestamp": message.timestamp,
                "metadata": dict(message.metadata)
            }
            self.escalations.append(escalation_record)

            return message.create_response(
                content=f"Supervisor logged escalation [{message.message_id}] from {message.sender}: {message.content}",
                message_type=MessageType.RESPONSE,
                metadata={"status": "ESCALATION_LOGGED", "escalation_id": message.message_id}
            )

        elif message.message_type == MessageType.REQUEST:
            response_content = self.process_request(message.content)
            return message.create_response(
                content=response_content,
                message_type=MessageType.RESPONSE
            )

        else:
            return message.create_response(
                content=f"Supervisor acknowledged {message.message_type.value} from {message.sender}",
                message_type=MessageType.RESPONSE
            )

