from typing import Dict, Set, List, Optional, Any, Union
from .messages import AgentMessage, MessageType
from .registry import AgentRegistry, AgentRegistration
from .message_bus import MessageBus, MessageHandler


class Orchestrator:
    """
    Central coordinator responsible for managing registered agents and the message bus.
    
    Acts as a thin, deterministic coordinator:
    - Coordinates AgentRegistry and MessageBus
    - Performs sender/recipient existence checks
    - Enforces capability validation on operations
    - Provides explicit routing helpers for escalation and permission requests to Agent 4
    - Does NOT contain any LLM reasoning
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        bus: Optional[MessageBus] = None
    ) -> None:
        self.registry = registry if registry is not None else AgentRegistry()
        self.bus = bus if bus is not None else MessageBus()

    def register_agent(
        self,
        agent_id: str,
        role: str,
        capabilities: Optional[Union[Set[str], List[str]]] = None,
        handler: Optional[MessageHandler] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentRegistration:
        """
        Registers an agent with the registry and optionally attaches its message handler to the bus.
        """
        registration = self.registry.register_agent(
            agent_id=agent_id,
            role=role,
            capabilities=capabilities,
            metadata=metadata
        )
        if handler is not None:
            self.bus.register_handler(agent_id, handler)
        return registration

    def unregister_agent(self, agent_id: str) -> bool:
        """Removes an agent from both registry and message bus."""
        self.bus.unregister_handler(agent_id)
        return self.registry.unregister_agent(agent_id)

    def register_handler(self, agent_id: str, handler: MessageHandler) -> None:
        """Attaches a message handler to an already registered agent."""
        if not self.registry.has_agent(agent_id):
            raise KeyError(f"Cannot register handler: Agent '{agent_id}' is not in the AgentRegistry.")
        self.bus.register_handler(agent_id, handler)

    def register_observer(self, observer: Any) -> None:
        """Registers a non-intrusive spectator/observer with the message bus."""
        self.bus.register_observer(observer)

    def unregister_observer(self, observer: Any) -> bool:
        """Unregisters an observer from the message bus."""
        return self.bus.unregister_observer(observer)

    def send_message(
        self,
        message: AgentMessage,
        required_capability: Optional[str] = None
    ) -> Optional[AgentMessage]:
        """
        Validates sender/recipient existence and required capabilities, then dispatches the message.
        
        Raises:
            KeyError: If sender or recipient is not registered in the AgentRegistry.
            PermissionError: If recipient lacks the required_capability.
            ValueError: If message payload is invalid.
        """
        if not isinstance(message, AgentMessage):
            raise TypeError(f"Expected AgentMessage, got {type(message).__name__}")

        # 1. Validate sender registration
        if not self.registry.has_agent(message.sender):
            raise KeyError(f"Message sender '{message.sender}' is not registered in AgentRegistry.")

        # 2. Validate recipient registration
        if not self.registry.has_agent(message.recipient):
            raise KeyError(f"Message recipient '{message.recipient}' is not registered in AgentRegistry.")

        # 3. Validate recipient capability if required
        if required_capability:
            if not self.registry.has_capability(message.recipient, required_capability):
                raise PermissionError(
                    f"Capability Validation Failed: Recipient '{message.recipient}' lacks required capability '{required_capability}'."
                )

        # 4. Route through message bus
        return self.bus.send_message(message)

    def request_permission(
        self,
        sender: str,
        content: str,
        supervisor_id: str = "agent4",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """
        Helper to route a permission request from any agent to the supervisor (Agent 4).
        """
        msg = AgentMessage(
            sender=sender,
            recipient=supervisor_id,
            message_type=MessageType.PERMISSION_REQUEST,
            content=content,
            metadata=metadata or {}
        )
        return self.send_message(msg, required_capability="permission_handling")

    def escalate(
        self,
        sender: str,
        content: str,
        supervisor_id: str = "agent4",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """
        Helper to route an escalation from any agent to the supervisor (Agent 4).
        """
        msg = AgentMessage(
            sender=sender,
            recipient=supervisor_id,
            message_type=MessageType.ESCALATION,
            content=content,
            metadata=metadata or {}
        )
        return self.send_message(msg, required_capability="escalation")

    def get_message_history(self) -> List[AgentMessage]:
        """Retrieves the message history from the message bus."""
        return self.bus.get_message_history()

    def clear_history(self) -> None:
        """Clears the message bus history."""
        self.bus.clear_history()

