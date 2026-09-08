from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
import uuid


class MessageType(str, Enum):
    """Types of messages that can be routed across agents."""
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    INFORMATION = "INFORMATION"
    PERMISSION_REQUEST = "PERMISSION_REQUEST"
    ESCALATION = "ESCALATION"
    ERROR = "ERROR"


def _generate_message_id() -> str:
    """Generates a unique message ID."""
    return f"msg_{uuid.uuid4().hex[:12]}"


def _get_utc_timestamp() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentMessage:
    """
    Standard message structure passed between agents on the message bus.
    
    Attributes:
        sender: ID of the originating agent.
        recipient: ID of the intended destination agent.
        message_type: Enum classification of the message.
        content: The text/payload body of the message.
        message_id: Unique identifier for tracking and correlation.
        timestamp: ISO 8601 UTC creation timestamp.
        correlation_id: Optional reference to an earlier message_id (for request/response pairing).
        metadata: Optional dictionary for auxiliary payload properties.
    """
    sender: str
    recipient: str
    message_type: MessageType
    content: str
    message_id: str = field(default_factory=_generate_message_id)
    timestamp: str = field(default_factory=_get_utc_timestamp)
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the message to a plain dictionary."""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type.value if isinstance(self.message_type, MessageType) else str(self.message_type),
            "content": self.content,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Deserializes a dictionary into an AgentMessage."""
        msg_type_raw = data.get("message_type", MessageType.REQUEST)
        msg_type = MessageType(msg_type_raw) if not isinstance(msg_type_raw, MessageType) else msg_type_raw
        
        return cls(
            sender=data["sender"],
            recipient=data["recipient"],
            message_type=msg_type,
            content=data["content"],
            message_id=data.get("message_id", _generate_message_id()),
            timestamp=data.get("timestamp", _get_utc_timestamp()),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {})
        )

    def create_response(self, content: str, message_type: MessageType = MessageType.RESPONSE, metadata: Optional[Dict[str, Any]] = None) -> "AgentMessage":
        """Helper to create a correlated response back to the sender."""
        return AgentMessage(
            sender=self.recipient,
            recipient=self.sender,
            message_type=message_type,
            content=content,
            correlation_id=self.message_id,
            metadata=metadata or {}
        )

