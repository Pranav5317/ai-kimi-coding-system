from typing import Dict, List, Callable, Optional
from .messages import AgentMessage, MessageType


# Handler type signature: receives an AgentMessage, optionally returns an AgentMessage response
MessageHandler = Callable[[AgentMessage], Optional[AgentMessage]]

# Observer type signature: receives an observation copy of an AgentMessage (read-only listener)
MessageObserver = Callable[[AgentMessage], None]


class MessageBus:
    """
    In-memory deterministic message bus for routing AgentMessages between agents.
    
    Supports:
    - Direct, unblocked routing to recipient handlers
    - Non-intrusive observation events to spectators (e.g. Agent 4 Supervisor)
    - In-memory message history log for debugging and verification
    - Does NOT use an LLM; routes strictly based on explicit recipient registrations
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, MessageHandler] = {}
        self._observers: List[MessageObserver] = []
        self._message_history: List[AgentMessage] = []

    def register_handler(self, agent_id: str, handler: MessageHandler) -> None:
        """
        Registers a message handler for a specific agent ID.
        """
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id cannot be empty when registering a handler.")
        if not callable(handler):
            raise TypeError(f"Handler for agent '{agent_id}' must be callable.")

        self._handlers[agent_id.strip()] = handler

    def unregister_handler(self, agent_id: str) -> bool:
        """
        Unregisters the message handler for the given agent ID.
        """
        if agent_id in self._handlers:
            del self._handlers[agent_id]
            return True
        return False

    def is_handler_registered(self, agent_id: str) -> bool:
        """Checks if a handler is registered for the agent ID."""
        return agent_id in self._handlers

    def register_observer(self, observer: MessageObserver) -> None:
        """
        Registers a non-intrusive spectator/observer function that receives observation copies
        of all messages routed through the bus.
        """
        if not callable(observer):
            raise TypeError("Observer must be callable.")
        if observer not in self._observers:
            self._observers.append(observer)

    def unregister_observer(self, observer: MessageObserver) -> bool:
        """
        Unregisters an observer function from the bus.
        """
        if observer in self._observers:
            self._observers.remove(observer)
            return True
        return False

    def _notify_observers(self, message: AgentMessage) -> None:
        """Notifies all registered observers with an observation copy of the message."""
        for observer in self._observers:
            try:
                observer(message)
            except Exception as e:
                # Observers must never break normal message delivery
                print(f"[Warning] Observer error in MessageBus: {e}")

    def send_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Routes an AgentMessage directly to the registered recipient handler.
        Emits non-blocking observation events to registered observers (e.g. Supervisor).
        Logs the message in message history.
        
        Raises:
            KeyError: If no handler is registered for the message recipient.
            ValueError: If the message is invalid or missing sender/recipient.
        """
        if not isinstance(message, AgentMessage):
            raise TypeError(f"Expected AgentMessage, got {type(message).__name__}")

        if not message.sender:
            raise ValueError("Message sender cannot be empty.")
        if not message.recipient:
            raise ValueError("Message recipient cannot be empty.")

        # 1. Log outgoing message
        self._message_history.append(message)

        # 2. Check recipient registration
        if message.recipient not in self._handlers:
            err_msg = f"No handler registered for recipient '{message.recipient}'."
            error_response = AgentMessage(
                sender="message_bus",
                recipient=message.sender,
                message_type=MessageType.ERROR,
                content=err_msg,
                correlation_id=message.message_id
            )
            self._message_history.append(error_response)
            self._notify_observers(message)
            self._notify_observers(error_response)
            raise KeyError(err_msg)

        # 3. Notify observers of the outgoing message (non-blocking observation)
        self._notify_observers(message)

        # 4. Direct dispatch to recipient handler
        handler = self._handlers[message.recipient]
        response = handler(message)

        # 5. If handler produced a response message, record it and notify observers
        if response is not None:
            if isinstance(response, AgentMessage):
                self._message_history.append(response)
                self._notify_observers(response)
            else:
                raise TypeError(f"Handler for '{message.recipient}' must return AgentMessage or None, got {type(response).__name__}")

        return response

    def get_message_history(self) -> List[AgentMessage]:
        """Returns a shallow copy of all messages routed through the bus."""
        return list(self._message_history)

    def clear_history(self) -> None:
        """Clears the in-memory message history."""
        self._message_history.clear()

    def reset(self) -> None:
        """Clears handlers, observers, and message history."""
        self._handlers.clear()
        self._observers.clear()
        self._message_history.clear()
