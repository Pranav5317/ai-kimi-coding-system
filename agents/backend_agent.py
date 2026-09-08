import json
import re
from typing import Optional, Set, Dict, Any, Union, List, Callable, Tuple
from llm.base import BaseLLMProvider
from .base_agent import BaseAgent
from orchestration.messages import AgentMessage, MessageType
from tools.filesystem import WorkspaceSandbox, FILESYSTEM_TOOLS, sanitize_code_content
from tools.verifier import BackendVerifier, VerificationResult, VERIFICATION_TOOLS
from diary.code_diary import CodeDiary


DEFAULT_BACKEND_SYSTEM_PROMPT = (
    "You are Agent 2 (Backend Developer) in an AI multi-agent software engineering system.\n"
    "You are responsible for:\n"
    "- Backend architecture, server-side code, and application logic\n"
    "- API design, routing, request/response models, and endpoint handlers\n"
    "- Backend file creation, implementation, and maintenance\n"
    "- Safe backend verification and autonomous self-repair of syntax and test failures\n"
    "- Integration requirements needed by the Frontend Developer (Agent 1)\n\n"
    "CRITICAL CODE GENERATION & REPAIR RULES:\n"
    "- Always generate pure, syntactically valid backend code.\n"
    "- NEVER wrap code inside JSON wrapper objects (such as `{\"python\": \"...\"}` or `{\"code\": \"...\"}`).\n"
    "- Ensure all imports, syntax, indentation, and quotation marks are completely valid.\n"
    "- When implementing or modifying backend code, verify your work using 'verify_python_syntax' or 'run_backend_tests'.\n"
    "- SELF-REPAIR LOOP: If verification fails, inspect the syntax error or test failure diagnostics, "
    "diagnose the root cause, edit the file using 'edit_file' or 'create_file' to fix it, and re-verify until it passes.\n\n"
    "You are NOT responsible for:\n"
    "- Frontend UI components (managed by Agent 1)\n"
    "- Database schema definitions and migrations (managed by Agent 3)\n"
    "- Project monitoring, governance, and scope enforcement (managed by Agent 4)\n"
    "- Overall workspace layout and server lifecycle (managed by Agent 5)"
)

DEFAULT_BACKEND_CAPABILITIES: Set[str] = {
    "backend_code",
    "backend_files",
    "api",
    "backend_architecture"
}

# Backend-specific file tools
BACKEND_FILE_TOOLS: List[Dict[str, Any]] = [
    t for t in FILESYSTEM_TOOLS if t.get("function", {}).get("name") in ("create_file", "edit_file", "read_file", "search_codebase", "inspect_project_structure")
]

DEFAULT_BACKEND_TOOLS: List[Dict[str, Any]] = VERIFICATION_TOOLS + BACKEND_FILE_TOOLS


class BackendAgent(BaseAgent):
    """
    Agent 2: Backend Developer.
    
    Specializes in backend architecture, server-side business logic, API endpoints,
    backend file structure, verification (syntax check & tests), and bounded self-repair.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        agent_id: str = "agent2",
        name: str = "Backend Developer",
        role: str = "backend_developer",
        system_prompt: Optional[str] = None,
        capabilities: Optional[Union[Set[str], list]] = None,
        orchestrator: Optional[Any] = None,
        sandbox: Optional[WorkspaceSandbox] = None,
        verifier: Optional[BackendVerifier] = None,
        diary: Optional[CodeDiary] = None,
        max_repair_attempts: int = 3,
        max_tool_iterations: int = 10
    ) -> None:
        super().__init__(
            name=name,
            role=role,
            system_prompt=system_prompt if system_prompt is not None else DEFAULT_BACKEND_SYSTEM_PROMPT,
            llm_provider=llm_provider
        )
        self.agent_id = agent_id
        self.capabilities = set(capabilities) if capabilities is not None else set(DEFAULT_BACKEND_CAPABILITIES)
        self.orchestrator = orchestrator
        self.sandbox = sandbox
        self.diary = diary
        self.max_repair_attempts = max_repair_attempts
        self.max_tool_iterations = max_tool_iterations

        # Initialize verifier if sandbox is available
        if verifier is not None:
            self.verifier = verifier
        elif self.sandbox is not None:
            self.verifier = BackendVerifier(sandbox=self.sandbox, diary=self.diary)
        else:
            self.verifier = None

        # Build tool dispatcher
        self.tool_dispatcher: Dict[str, Callable] = {}
        if self.verifier is not None:
            self.tool_dispatcher["verify_code_syntax"] = self._tool_verify_code_syntax
            self.tool_dispatcher["verify_python_syntax"] = self._tool_verify_python
            self.tool_dispatcher["run_backend_tests"] = self._tool_run_tests

        if self.sandbox is not None:
            self.tool_dispatcher["create_file"] = self._tool_create_file
            self.tool_dispatcher["edit_file"] = self._tool_edit_file
            self.tool_dispatcher["read_file"] = self.sandbox.read_file
            self.tool_dispatcher["search_codebase"] = self.sandbox.search_codebase
            self.tool_dispatcher["inspect_project_structure"] = self.sandbox.inspect_project_structure

    def has_capability(self, capability: str) -> bool:
        """Checks if BackendAgent possesses the given capability token."""
        return capability in self.capabilities

    def _tool_verify_code_syntax(self, file_path: str) -> str:
        """Tool handler for verifying multi-stack code syntax."""
        if self.verifier is None:
            return "Verification Error: Verifier is not configured for Agent 2."
        result = self.verifier.verify_code_syntax(file_path)
        return result.summary()

    def _tool_verify_python(self, file_path: str) -> str:
        """Tool handler for verifying python syntax."""
        if self.verifier is None:
            return "Verification Error: Verifier is not configured for Agent 2."
        result = self.verifier.verify_python(file_path)
        return result.summary()

    def _tool_run_tests(self, test_path: Optional[str] = None, command: Optional[str] = None) -> str:
        """Tool handler for running backend tests."""
        if self.verifier is None:
            return "Verification Error: Verifier is not configured for Agent 2."
        result = self.verifier.run_tests(test_path=test_path, command=command)
        return result.summary()

    def _tool_create_file(self, path: str, content: str) -> Dict[str, Any]:
        """Tool handler for creating backend files with sanitized content."""
        if self.sandbox is None:
            raise RuntimeError("Sandbox is not configured for Agent 2.")
        clean_code = sanitize_code_content(content)
        return self.sandbox.create_file(path=path, content=clean_code)

    def _tool_edit_file(self, path: str, content: str) -> Dict[str, Any]:
        """Tool handler for editing backend files with sanitized content."""
        if self.sandbox is None:
            raise RuntimeError("Sandbox is not configured for Agent 2.")
        clean_code = sanitize_code_content(content)
        return self.sandbox.edit_file(path=path, content=clean_code)

    def _validate_tool_args(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates tool arguments prior to execution."""
        if not isinstance(args, dict):
            return False, f"Tool arguments must be a dictionary, got {type(args).__name__}."

        if tool_name in ("create_file", "edit_file"):
            if "path" not in args or not str(args["path"]).strip():
                return False, "Missing or empty required 'path' parameter."
            if "content" not in args or args["content"] is None:
                return False, "Missing required 'content' parameter."
        elif tool_name in ("verify_code_syntax", "verify_python_syntax", "read_file"):
            target_key = "file_path" if tool_name in ("verify_code_syntax", "verify_python_syntax") else "path"
            if target_key not in args or not str(args[target_key]).strip():
                return False, f"Missing required '{target_key}' parameter."

        return True, ""

    def _execute_tool(self, function_name: str, arguments: Any) -> str:
        """Executes a registered tool with robust error handling."""
        if function_name not in self.tool_dispatcher:
            return f"Unknown tool: '{function_name}'. Available: {list(self.tool_dispatcher.keys())}"

        parsed_args = arguments
        if isinstance(arguments, str):
            try:
                parsed_args = json.loads(arguments)
            except Exception as e:
                return f"Malformed tool arguments JSON: {e}"

        if not isinstance(parsed_args, dict):
            parsed_args = {}

        is_valid, err_msg = self._validate_tool_args(function_name, parsed_args)
        if not is_valid:
            return f"Argument Error: {err_msg}"

        tool_fn = self.tool_dispatcher[function_name]
        try:
            res = tool_fn(**parsed_args)
            return str(res)
        except Exception as e:
            return f"Tool execution error in '{function_name}': {e}"

    def process_request(
        self,
        prompt: str,
        on_tool_call: Optional[Callable[[str, Dict[str, Any], str], None]] = None
    ) -> str:
        """
        Processes a backend development request.
        If tools (sandbox/verifier) are available, executes an autonomous reasoning,
        verification, and bounded self-repair loop (up to max_repair_attempts).
        """
        self.add_message("user", prompt)

        # If no tools are configured, fallback to standard LLM chat
        if not self.tool_dispatcher:
            messages = self._prepare_messages()
            raw_response = self.llm_provider.chat(messages)
            if isinstance(raw_response, dict):
                response_text = raw_response.get("content", "").strip()
            else:
                response_text = str(raw_response).strip()
            self.add_message("assistant", response_text)
            return response_text

        tools_to_pass = [t for t in DEFAULT_BACKEND_TOOLS if t.get("function", {}).get("name") in self.tool_dispatcher]

        iteration = 0
        repair_attempts = 0

        while iteration < self.max_tool_iterations:
            iteration += 1
            messages = self._prepare_messages()

            response = self.llm_provider.chat(messages, tools=tools_to_pass)
            tool_calls = response.get("tool_calls") if isinstance(response, dict) else None
            raw_content = response.get("content", "") if isinstance(response, dict) else str(response)

            # If no native tool calls, check if text has extracted tool calls
            if not tool_calls:
                extracted = self._extract_tool_calls_from_text(raw_content)
                if extracted:
                    tool_calls = extracted

            # If no tool calls at all, finalize
            if not tool_calls:
                final_text = (raw_content or "").strip()
                self.add_message("assistant", final_text)
                return final_text

            # Record assistant call in history
            self.history.append({
                "role": "assistant",
                "content": raw_content or "",
                "tool_calls": tool_calls
            })

            # Execute tool calls
            for call in tool_calls:
                fn = call.get("function", {})
                tool_name = fn.get("name", "")
                tool_args = fn.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except Exception:
                        pass

                tool_result = self._execute_tool(tool_name, tool_args)

                # Check if this was a verification call that failed
                if tool_name in ("verify_code_syntax", "verify_python_syntax", "run_backend_tests"):
                    if "[FAILED]" in tool_result or "failed" in tool_result.lower() or "error" in tool_result.lower():
                        repair_attempts += 1
                        if repair_attempts > self.max_repair_attempts:
                            diagnostic_summary = (
                                f"{tool_result}\n\n[WARNING] Maximum self-repair attempts ({self.max_repair_attempts}) "
                                "exhausted. Reporting failure to caller."
                            )
                            self.history.append({
                                "role": "tool",
                                "name": tool_name,
                                "content": diagnostic_summary
                            })
                            final_msg = f"Self-repair stopped after {self.max_repair_attempts} attempts. Diagnosis:\n{diagnostic_summary}"
                            self.add_message("assistant", final_msg)
                            return final_msg

                if on_tool_call:
                    try:
                        on_tool_call(tool_name, tool_args if isinstance(tool_args, dict) else {}, tool_result)
                    except Exception:
                        pass

                self.history.append({
                    "role": "tool",
                    "name": tool_name,
                    "content": tool_result
                })

        # Max iterations reached
        timeout_msg = f"Backend agent reached maximum iteration limit ({self.max_tool_iterations})."
        self.add_message("assistant", timeout_msg)
        return timeout_msg

    def _extract_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Fallback tool extractor for local LLMs returning JSON in text."""
        if not text or not text.strip():
            return []

        cleaned = text.strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and "name" in data:
                params = data.get("parameters") or data.get("arguments", {})
                return [{"function": {"name": data["name"], "arguments": params}}]
            elif isinstance(data, list):
                calls = []
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        calls.append({"function": {"name": item["name"], "arguments": item.get("parameters", {})}})
                if calls:
                    return calls
        except Exception:
            pass

        calls = []
        pattern = r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"(?:parameters|arguments)"\s*:\s*(\{.*?\})\s*\}'
        for match in re.finditer(pattern, cleaned, re.DOTALL):
            tool_name = match.group(1)
            params_str = match.group(2)
            try:
                params = json.loads(params_str)
                calls.append({"function": {"name": tool_name, "arguments": params}})
            except Exception:
                pass
        return calls

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
        Message handler invoked when the MessageBus delivers an AgentMessage to Agent 2.
        Processes the request and returns a correlated response message.
        """
        if message.message_type == MessageType.REQUEST:
            meta_action = message.metadata.get("action")
            if meta_action and meta_action in self.tool_dispatcher:
                args = message.metadata.get("args", {})
                result = self._execute_tool(meta_action, args)
                return message.create_response(
                    content=result,
                    message_type=MessageType.RESPONSE,
                    metadata={"action": meta_action, "status": "COMPLETED"}
                )

            response_content = self.process_request(message.content)
            return message.create_response(
                content=response_content,
                message_type=MessageType.RESPONSE
            )
        elif message.message_type == MessageType.INFORMATION:
            self.add_message("user", f"[Info from {message.sender}]: {message.content}")
            return message.create_response(
                content=f"Agent 2 acknowledged information from {message.sender}",
                message_type=MessageType.RESPONSE
            )
        elif message.message_type == MessageType.ESCALATION:
            return message.create_response(
                content=f"Agent 2 received escalation: {message.content}",
                message_type=MessageType.RESPONSE
            )
        else:
            return message.create_response(
                content=f"Agent 2 received message of type {message.message_type.value}",
                message_type=MessageType.RESPONSE
            )
