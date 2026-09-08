from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Any, Union


@dataclass
class AgentRegistration:
    """
    Metadata representation of an agent registered with the system.
    
    Attributes:
        agent_id: Unique string identifier (e.g., 'agent1', 'agent5').
        role: Functional role description (e.g., 'frontend_developer', 'workspace_manager').
        capabilities: Set of capability tokens associated with this agent.
        metadata: Optional dictionary for additional architectural attributes.
    """
    agent_id: str
    role: str
    capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_capability(self, capability: str) -> bool:
        """Checks if this registration has the specified capability token."""
        return capability in self.capabilities


class AgentRegistry:
    """
    Central registry for storing and querying agent metadata and capabilities.
    Rejects duplicate agent registrations and provides capability verification.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentRegistration] = {}

    def register_agent(
        self,
        agent_id: str,
        role: str,
        capabilities: Optional[Union[Set[str], List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentRegistration:
        """
        Registers a new agent with its role and capabilities.
        
        Raises:
            ValueError: If agent_id is empty or already registered.
        """
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id cannot be empty.")

        clean_id = agent_id.strip()
        if clean_id in self._agents:
            raise ValueError(f"Agent '{clean_id}' is already registered in the AgentRegistry.")

        caps_set = set(capabilities) if capabilities else set()
        registration = AgentRegistration(
            agent_id=clean_id,
            role=role.strip() if role else "unspecified",
            capabilities=caps_set,
            metadata=dict(metadata) if metadata else {}
        )
        self._agents[clean_id] = registration
        return registration

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Removes an agent from the registry. Returns True if removed, False if not found.
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[AgentRegistration]:
        """Retrieves registration for the given agent_id, or None if not registered."""
        return self._agents.get(agent_id)

    def has_agent(self, agent_id: str) -> bool:
        """Returns True if agent_id is currently registered."""
        return agent_id in self._agents

    def list_agents(self) -> List[AgentRegistration]:
        """Returns a list of all currently registered agents."""
        return list(self._agents.values())

    def has_capability(self, agent_id: str, capability: str) -> bool:
        """
        Verifies if the specified agent is registered and possesses the capability.
        Returns False if the agent does not exist or lacks the capability.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        return agent.has_capability(capability)

    def clear(self) -> None:
        """Clears all registrations from the registry."""
        self._agents.clear()

