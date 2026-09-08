from typing import Optional, Set, Dict, Any, Union
from llm.base import BaseLLMProvider
from .base_agent import BaseAgent
from orchestration.messages import AgentMessage, MessageType


DEFAULT_DATA_MANAGER_SYSTEM_PROMPT = (
    "You are Agent 3 (Data Manager) in an AI multi-agent software engineering system.\n"
    "You are responsible for:\n"
    "- Database architecture and schema design\n"
    "- Database migrations, versioning, and seed scripts\n"
    "- Defining CRUD operations, queries, and data access layers\n"
    "- Data models, entities, and relationship definitions\n"
    "- Communicating data response structures and entity shapes to the Frontend Developer (Agent 1)\n"
    "- Communicating database schemas, fields, and queries to the Backend Developer (Agent 2)\n\n"
    "CRITICAL CODE GENERATION RULES:\n"
    "- Always output pure, syntactically valid database schemas, migrations, SQL, ORM models, or query code.\n"
    "- NEVER wrap code in JSON wrapper objects (such as `{\"sql\": \"...\"}` or `{\"python\": \"...\"}`).\n"
    "- Ensure all SQL/Python statements, constraints, and data types are syntactically valid.\n\n"
    "You are NOT responsible for:\n"
    "- Frontend implementation or UI components (managed by Agent 1)\n"
    "- General backend routing, web servers, and API business logic (managed by Agent 2)\n"
    "- Project governance, monitoring, and scope validation (managed by Agent 4)\n"
    "- Approving permissions or direct user escalation (managed by Agent 4)\n"
    "- Overall application lifecycle, server startup, or direct workspace execution (managed by Agent 5)\n\n"
    "Do not assume a specific database engine (e.g. PostgreSQL, SQLite, MySQL, MongoDB) or ORM/tooling "
    "(e.g. SQLAlchemy, Alembic, Prisma, Mongoose) unless requested by the user or required by project specifications. "
    "Adapt your data design to the user-selected technology."
)

DEFAULT_DATA_MANAGER_CAPABILITIES: Set[str] = {
    "database_schema",
    "migrations",
    "crud",
    "data_models"
}


class DataManagerAgent(BaseAgent):
    """
    Agent 3: Data Manager.
    
    Specializes in database schema design, migrations, CRUD operations,
    and data models. Communicates data structures and requirements with peer agents
    (Agents 1, 2, 4, 5) via the Orchestrator and MessageBus infrastructure.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        agent_id: str = "agent3",
        name: str = "Data Manager",
        role: str = "data_manager",
        system_prompt: Optional[str] = None,
        capabilities: Optional[Union[Set[str], list]] = None,
        orchestrator: Optional[Any] = None
    ) -> None:
        super().__init__(
            name=name,
            role=role,
            system_prompt=system_prompt if system_prompt is not None else DEFAULT_DATA_MANAGER_SYSTEM_PROMPT,
            llm_provider=llm_provider
        )
        self.agent_id = agent_id
        self.capabilities = set(capabilities) if capabilities is not None else set(DEFAULT_DATA_MANAGER_CAPABILITIES)
        self.orchestrator = orchestrator

    def has_capability(self, capability: str) -> bool:
        """Checks if DataManagerAgent possesses the given capability token."""
        return capability in self.capabilities

    def process_request(self, prompt: str) -> str:
        """
        Processes a user or peer-agent data management request using the injected LLM provider.
        Maintains conversational history within the existing BaseAgent history structure.
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

    def send_agent_message(
        self,
        recipient: str,
        content: str,
        message_type: MessageType = MessageType.REQUEST,
        required_capability: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """
        Constructs and sends an AgentMessage to a peer agent via the configured Orchestrator.
        
        Raises:
            RuntimeError: If no Orchestrator was injected into this DataManagerAgent.
        """
        if self.orchestrator is None:
            raise RuntimeError(f"Agent '{self.agent_id}' has no Orchestrator configured for inter-agent messaging.")

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
        Message handler invoked when the MessageBus delivers an AgentMessage to Agent 3.
        Processes the request and returns a correlated response message.
        """
        if message.message_type == MessageType.REQUEST:
            response_content = self.process_request(message.content)
            return message.create_response(
                content=response_content,
                message_type=MessageType.RESPONSE
            )
        elif message.message_type == MessageType.INFORMATION:
            self.add_message("user", f"[Info from {message.sender}]: {message.content}")
            return message.create_response(
                content=f"Agent 3 acknowledged information from {message.sender}",
                message_type=MessageType.RESPONSE
            )
        elif message.message_type == MessageType.ESCALATION:
            return message.create_response(
                content=f"Agent 3 received escalation: {message.content}",
                message_type=MessageType.RESPONSE
            )
        else:
            return message.create_response(
                content=f"Agent 3 received message of type {message.message_type.value}",
                message_type=MessageType.RESPONSE
            )

