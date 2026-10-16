from typing import Optional, Set, Dict, Any, Union
from llm.base import BaseLLMProvider
from .base_agent import BaseAgent
from orchestration.messages import AgentMessage, MessageType


DEFAULT_FRONTEND_SYSTEM_PROMPT = (
    "You are Agent 1 (Frontend Developer) in an AI multi-agent software engineering system.\n"
    "You are responsible for:\n"
    "- Frontend architecture and application structure\n"
    "- UI components, styling, and visual layouts\n"
    "- Writing clean, maintainable frontend code and component files\n"
    "- Defining frontend state management and client-side logic\n"
    "- Integrating with backend APIs based on contracts provided by the Backend Developer (Agent 2)\n\n"
    "CRITICAL CODE GENERATION RULES:\n"
    "- Always output clean, syntactically valid frontend code (HTML, CSS, JS, TS, JSX, TSX).\n"
    "- NEVER wrap file content in JSON wrapper objects (such as `{\"html\": \"...\"}` or `{\"code\": \"...\"}`).\n"
    "- Ensure tags, brackets, and string quotes are cleanly closed and valid.\n\n"
    "You are NOT responsible for backend implementation, database schemas/migrations, project governance, "
    "or performing direct filesystem operations outside of requests to the Workspace Manager (Agent 5).\n"
    "Do not assume a specific frontend framework (e.g. React, Vue, Angular, Svelte, or plain HTML/CSS/JS) "
    "unless requested by the user or required by the project specifications."
)

DEFAULT_FRONTEND_CAPABILITIES: Set[str] = {
    "frontend_code",
    "frontend_files",
    "ui_components",
    "frontend_architecture"
}


class FrontendAgent(BaseAgent):
    """
    Agent 1: Frontend Developer.
    
    Specializes in frontend architecture, UI components, client-side logic,
    and frontend file design. Communicates with peer agents (Agents 2, 3, 4, 5)
    via the Orchestrator and MessageBus infrastructure.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        agent_id: str = "agent1",
        name: str = "Frontend Developer",
        role: str = "frontend_developer",
        system_prompt: Optional[str] = None,
        capabilities: Optional[Union[Set[str], list]] = None,
        orchestrator: Optional[Any] = None,
        sandbox: Optional[Any] = None,
        diary: Optional[Any] = None
    ) -> None:
        super().__init__(
            name=name,
            role=role,
            system_prompt=system_prompt if system_prompt is not None else DEFAULT_FRONTEND_SYSTEM_PROMPT,
            llm_provider=llm_provider
        )
        self.agent_id = agent_id
        self.capabilities = set(capabilities) if capabilities is not None else set(DEFAULT_FRONTEND_CAPABILITIES)
        self.orchestrator = orchestrator
        self.sandbox = sandbox
        self.diary = diary

    def has_capability(self, capability: str) -> bool:
        """Checks if FrontendAgent possesses the given capability token."""
        return capability in self.capabilities

    def _auto_write_files_to_sandbox(self, text: str) -> None:
        """Extracts code blocks or HTML/CSS/JS from text and saves them to sandbox files."""
        if not self.sandbox or not text:
            return

        import re
        # 1. Check for HTML code
        html_match = re.search(r'```html\r?\n([\s\S]*?)\r?\n```', text, re.IGNORECASE)
        html_code = html_match.group(1).strip() if html_match else None
        if not html_code and ("<!DOCTYPE html>" in text or "<html" in text):
            # Extract raw html block
            h_start = text.find("<!DOCTYPE html>") if "<!DOCTYPE html>" in text else text.find("<html")
            h_end = text.rfind("</html>")
            if h_start != -1 and h_end != -1 and h_end > h_start:
                html_code = text[h_start:h_end + 7].strip()

        if html_code:
            try:
                self.sandbox.create_file("index.html", html_code)
                self.sandbox.create_file("frontend/index.html", html_code)
                if self.diary:
                    self.diary.record("AUTO_CREATE_FILE", "index.html", "SUCCESS", "Saved frontend HTML to workspace")
            except Exception:
                pass

        # 2. Check for CSS code
        css_match = re.search(r'```css\r?\n([\s\S]*?)\r?\n```', text, re.IGNORECASE)
        if css_match:
            css_code = css_match.group(1).strip()
            try:
                self.sandbox.create_file("frontend/styles.css", css_code)
                self.sandbox.create_file("styles.css", css_code)
                if self.diary:
                    self.diary.record("AUTO_CREATE_FILE", "styles.css", "SUCCESS", "Saved frontend CSS to workspace")
            except Exception:
                pass

        # 3. Check for JS code
        js_match = re.search(r'```(?:js|javascript)\r?\n([\s\S]*?)\r?\n```', text, re.IGNORECASE)
        if js_match:
            js_code = js_match.group(1).strip()
            try:
                self.sandbox.create_file("frontend/app.js", js_code)
                self.sandbox.create_file("app.js", js_code)
                if self.diary:
                    self.diary.record("AUTO_CREATE_FILE", "app.js", "SUCCESS", "Saved frontend JS to workspace")
            except Exception:
                pass

    def process_request(self, prompt: str) -> str:
        """
        Processes a user or peer-agent frontend development request using the injected LLM provider.
        Maintains conversational history within the existing BaseAgent history structure.
        """
        # Prepare full message payload
        messages = self._prepare_messages(prompt)
        self.add_message("user", prompt)

        # Call LLM provider
        raw_response = self.llm_provider.chat(messages)

        # Normalize response (handles dict or string return from BaseLLMProvider)
        if isinstance(raw_response, dict):
            response_text = raw_response.get("content", "").strip()
        else:
            response_text = str(raw_response).strip()

        self._auto_write_files_to_sandbox(response_text)
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
            RuntimeError: If no Orchestrator was injected into this FrontendAgent.
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
        Message handler invoked when the MessageBus delivers an AgentMessage to Agent 1.
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
                content=f"Agent 1 acknowledged information from {message.sender}",
                message_type=MessageType.RESPONSE
            )
        else:
            return message.create_response(
                content=f"Agent 1 received message of type {message.message_type.value}",
                message_type=MessageType.RESPONSE
            )

