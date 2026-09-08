import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple, Set, Union
from llm.base import BaseLLMProvider
from .base_agent import BaseAgent
from tools.filesystem import WorkspaceSandbox, FILESYSTEM_TOOLS
from tools.server_manager import DevServerManager, SERVER_TOOLS
from diary.code_diary import CodeDiary
from state.project_state import ProjectStateManager, PROJECT_STATE_TOOLS
from orchestration.messages import AgentMessage, MessageType


DEFAULT_WORKSPACE_SYSTEM_PROMPT = (
    "You are Agent 5 (Workspace/Runtime Manager & Autonomous Project Manager) in an AI multi-agent software engineering system.\n"
    "You are responsible for:\n"
    "- Autonomous project lifecycle management: receiving high-level user objectives and driving them to completion across iterative rounds\n"
    "- Inspecting and managing persistent project state in PROJECT_STATE.md (requirements, architecture, tech stack, progress, tasks, decisions, issues)\n"
    "- Organizing the project workspace directory layout (e.g., frontend/, backend/, database/)\n"
    "- Ensuring files are placed in correct folders and executing filesystem operations inside the sandbox\n"
    "- Managing the lifecycle of development servers (starting, stopping, monitoring status)\n"
    "- Recording actions, audit entries, and server events in CODE_DIARY.md\n"
    "- Coordinating project tasks by dynamically delegating to specialist agents:\n"
    "  * delegate_task to 'agent1' (Frontend Developer) for UI components, frontend architecture, and client-side logic\n"
    "  * delegate_task to 'agent2' (Backend Developer) for API endpoints, backend logic, server files, routing, and backend verification\n"
    "  * delegate_task to 'agent3' (Data Manager) for database schemas, migrations, CRUD models, and data access layers\n\n"
    "AUTONOMOUS MULTI-ROUND ORCHESTRATION RULES:\n"
    "1. When given a high-level user objective (e.g. 'Build me a task management app with React, FastAPI, PostgreSQL'):\n"
    "   - Read existing state using 'read_project_state' if helpful to understand what is already done.\n"
    "   - Break down the objective into logical specialist phases (e.g. Database schema -> Backend API -> Frontend UI).\n"
    "   - Dynamically delegate tasks to the appropriate specialist agents using 'delegate_task'. The order and targets depend on the specific project.\n"
    "   - When you receive a specialist's result, inspect what was produced (code, schemas, verification reports, or errors).\n"
    "   - Update 'PROJECT_STATE.md' using 'update_project_state' to record updated progress, completed tasks, technical decisions, or known issues.\n"
    "   - Reason about what should happen next and delegate the next phase (e.g., passing schema/API contracts as context to downstream agents).\n"
    "   - Continue until all required components are built, verified, and integrated, then provide a comprehensive final response to the user.\n"
    "2. Do NOT write all specialist code yourself; delegate specialist implementation to Agent 1 (frontend), Agent 2 (backend), or Agent 3 (database).\n"
    "3. Handle failures gracefully: If a specialist reports an issue or verification failure, inspect the error, update known issues, and decide whether to re-delegate, fix, or report.\n"
    "4. PROACTIVE CODE INSPECTION FOR EXISTING REPOSITORIES: When asked about existing features, routes, architecture, or components in a repository (e.g., 'is there a dashboard?', 'how is upload handled?'):\n"
    "   - Do NOT give up if 'read_project_state' returns uninitialized state.\n"
    "   - ALWAYS execute 'inspect_project_structure' or 'search_codebase' (searching for keywords like 'upload', 'dashboard', 'route', 'form', 'predict', 'html') to inspect real code files.\n"
    "   - Update 'PROJECT_STATE.md' with discovered facts using 'update_project_state'.\n"
    "   - Give an accurate answer explaining what exists and offer to implement any missing features.\n"
    "5. ZERO TECH STACK PROMPTING FOR EXISTING CODEBASES:\n"
    "   - EXISTING CODEBASE: If the workspace contains pre-existing code or manifests (e.g. package.json, requirements.txt, .py, .js, .cpp, .java), NEVER ask the user to explain or specify the tech stack! Automatically detect and adopt the existing tech stack from code files.\n"
    "   - BRAND NEW PROJECT: ONLY if the workspace is completely empty or brand new with no code files/manifests, then and ONLY then should you ask the user for their preferred tech stack or propose one.\n\n"
    "PERSISTENT PROJECT MEMORY & STATE RULES:\n"
    "- PROJECT_STATE.md represents what is true about the project RIGHT NOW. It survives LLM conversational context compaction.\n"
    "- Always keep PROJECT_STATE.md accurate and concise using 'read_project_state' and 'update_project_state'.\n"
    "- You have full access to workspace sandbox tools, dev server management tools, project state tools, and the delegate_task tool."
)

DEFAULT_WORKSPACE_CAPABILITIES: Set[str] = {
    "filesystem",
    "workspace",
    "dev_server",
    "diary",
    "project_management",
    "agent_coordination",
    "project_state"
}

ALLOWED_DELEGATION_TARGETS: Set[str] = {"agent1", "agent2", "agent3"}

# Tool definitions for LLM task delegation
DELEGATION_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": (
                "Delegate a specialized development or data-management task to a specialist agent "
                "(agent1: Frontend Developer, agent2: Backend Developer, agent3: Data Manager). "
                "Returns the specialist agent's generated code, architecture, or response so you can manage workspace files and next steps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_agent": {
                        "type": "string",
                        "description": "The ID of the specialist agent to delegate to. Allowed values: 'agent1' (Frontend), 'agent2' (Backend), 'agent3' (Data Manager).",
                        "enum": ["agent1", "agent2", "agent3"]
                    },
                    "task": {
                        "type": "string",
                        "description": "The specific task instructions, technical requirements, or specification for the specialist agent."
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional additional technical context, existing API specifications, or database schemas."
                    }
                },
                "required": ["target_agent", "task"]
            }
        }
    }
]

# Combined tool definitions for function-calling LLMs
ALL_WORKSPACE_TOOLS: List[Dict[str, Any]] = (
    FILESYSTEM_TOOLS + SERVER_TOOLS + DELEGATION_TOOLS + PROJECT_STATE_TOOLS
)


class WorkspaceAgent(BaseAgent):
    """
    Agent 5: Workspace/Runtime Manager & App/Project Manager.
    
    Responsible for workspace file layout, sandboxed filesystem operations,
    development server lifecycle management, code diary auditing,
    persistent project state (PROJECT_STATE.md), and coordinating work among Agents 1, 2, 3, and 4.
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        name: str = "Agent 5 (Workspace Manager)",
        role: str = "workspace_manager",
        system_prompt: Optional[str] = None,
        agent_id: str = "agent5",
        capabilities: Optional[Union[Set[str], list]] = None,
        sandbox: Optional[WorkspaceSandbox] = None,
        diary: Optional[CodeDiary] = None,
        server_manager: Optional[DevServerManager] = None,
        state_manager: Optional[ProjectStateManager] = None,
        orchestrator: Optional[Any] = None,
        max_tool_iterations: int = 10,
        workspace_root: Optional[Path] = None,
        **kwargs: Any
    ):
        # Support legacy positional signatures where name or llm_provider position was varied
        if isinstance(llm_provider, str):
            actual_name = llm_provider
            actual_role = name
            actual_prompt = role if isinstance(role, str) else None
            actual_llm = kwargs.get("llm_provider") or system_prompt
            name = actual_name
            role = actual_role
            system_prompt = actual_prompt
            llm_provider = actual_llm  # type: ignore

        if llm_provider is None:
            raise ValueError("WorkspaceAgent requires an LLM provider instance.")

        prompt_to_use = system_prompt if system_prompt is not None else DEFAULT_WORKSPACE_SYSTEM_PROMPT

        super().__init__(
            name=name,
            role=role,
            system_prompt=prompt_to_use,
            llm_provider=llm_provider
        )

        self.agent_id = agent_id
        self.capabilities = set(capabilities) if capabilities is not None else set(DEFAULT_WORKSPACE_CAPABILITIES)
        self.orchestrator = orchestrator
        self.diary = diary
        self.max_tool_iterations = max_tool_iterations

        # Initialize or assign sandbox
        root_path = workspace_root if workspace_root else (sandbox.workspace_root if sandbox else Path.cwd() / "workspace")
        self.sandbox = sandbox if sandbox is not None else WorkspaceSandbox(root_path, diary=self.diary)

        # Initialize or assign server manager
        self.server_manager = server_manager if server_manager is not None else DevServerManager(
            workspace_root=self.sandbox.workspace_root,
            diary=self.diary
        )

        # Initialize or assign project state manager
        self.state_manager = state_manager if state_manager is not None else ProjectStateManager(
            sandbox=self.sandbox
        )

        # Dispatch table mapping tool name to executable methods
        self.tool_dispatcher: Dict[str, Callable] = {
            # Filesystem tools
            "list_files": self.sandbox.list_files,
            "read_file": self.sandbox.read_file,
            "create_directory": self.sandbox.create_directory,
            "create_file": self.sandbox.create_file,
            "edit_file": self.sandbox.edit_file,
            "search_codebase": self.sandbox.search_codebase,
            "inspect_project_structure": self.sandbox.inspect_project_structure,
            # Dev server tools
            "start_dev_server": self.server_manager.start_server,
            "stop_dev_server": self.server_manager.stop_server,
            "get_server_status": self.server_manager.get_server_status,
            # Autonomous task delegation tool
            "delegate_task": self.delegate_task,
            # Persistent project state tools
            "read_project_state": self.state_manager.read_state,
            "update_project_state": self.state_manager.update_state,
        }

        # Load persistent chat history for this project if it exists
        self.load_history_from_disk()

    def add_message(self, role: str, content: str) -> None:
        """Appends a message to conversational memory and persists history to disk."""
        super().add_message(role, content)
        self.save_history_to_disk()

    def clear_history(self) -> None:
        """Clears conversational memory for this session and persists empty history to disk."""
        super().clear_history()
        self.save_history_to_disk()

    def load_history_from_disk(self) -> None:
        """Loads persistent project chat history from .agent_chat_history.json if present."""
        try:
            target = self.sandbox.validate_and_resolve(".agent_chat_history.json")
            if target.exists() and target.is_file():
                raw = target.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, list):
                    self.history = data
        except Exception:
            pass

    def save_history_to_disk(self) -> None:
        """Saves current chat history to .agent_chat_history.json inside project root."""
        try:
            target = self.sandbox.validate_and_resolve(".agent_chat_history.json")
            target.write_text(json.dumps(self.history, indent=2), encoding="utf-8")
        except Exception:
            pass

    def has_capability(self, capability: str) -> bool:
        """Checks if WorkspaceAgent possesses the specified capability."""
        return capability in self.capabilities

    def delegate_task(
        self,
        target_agent: str,
        task: str,
        context: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """
        Delegates a task to a specialist agent (agent1, agent2, or agent3) via the Orchestrator/MessageBus.
        Returns the response string from the delegated agent to allow the A5 LLM to continue reasoning.
        """
        if not target_agent or not str(target_agent).strip():
            return "Delegation Error: Missing required 'target_agent' parameter."

        clean_target = str(target_agent).strip().lower()

        if clean_target == "agent4":
            return (
                "Delegation Error: 'agent4' is the Supervisor/Monitor agent and cannot be assigned development tasks. "
                "Agent 4 actively observes all agent activities and handles escalations/permissions."
            )

        if clean_target not in ALLOWED_DELEGATION_TARGETS:
            return (
                f"Delegation Error: Invalid target agent '{clean_target}'. "
                f"Allowed development delegation targets: {sorted(list(ALLOWED_DELEGATION_TARGETS))}."
            )

        if not task or not str(task).strip():
            return "Delegation Error: Missing required 'task' description parameter."

        if self.orchestrator is None:
            return "Delegation Error: Agent 5 has no Orchestrator configured for inter-agent communication."

        if not self.orchestrator.registry.has_agent(clean_target):
            return f"Delegation Error: Target agent '{clean_target}' is not registered in the system."

        # Construct payload with optional context
        metadata: Dict[str, Any] = {"delegated_by": self.agent_id}
        if context:
            metadata["context"] = context

        content_payload = str(task).strip()
        if context and str(context).strip():
            content_payload = f"{content_payload}\n\nContext:\n{str(context).strip()}"

        msg = AgentMessage(
            sender=self.agent_id,
            recipient=clean_target,
            message_type=MessageType.REQUEST,
            content=content_payload,
            metadata=metadata
        )

        try:
            # Dispatches across Orchestrator -> MessageBus (Agent 4 observes automatically)
            response = self.orchestrator.send_message(msg)
            if response is None:
                err = f"Delegation Failed: No response received from '{clean_target}'."
                if self.diary:
                    self.diary.record("DELEGATE_TASK", clean_target, "FAILED", err)
                return err

            agent_reg = self.orchestrator.registry.get_agent(clean_target)
            role_name = agent_reg.role if agent_reg else clean_target
            if self.diary:
                self.diary.record(
                    "DELEGATE_TASK",
                    clean_target,
                    "SUCCESS",
                    f"Delegated task: {str(task)[:60]}"
                )

            return f"--- Response from {clean_target} ({role_name}) ---\n{response.content}\n--- End of response ---"

        except Exception as e:
            err = f"Delegation Error while communicating with '{clean_target}': {str(e)}"
            if self.diary:
                self.diary.record("DELEGATE_TASK", clean_target, "ERROR", str(e))
            return err

    def setup_project_structure(
        self,
        custom_structure: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Sets up the project directory layout in the sandbox (e.g., frontend/, backend/, database/).
        Creates directories and optional placeholder files, recording each in the Code Diary.
        """
        default_layout: Dict[str, List[str]] = {
            "frontend": [],
            "backend": [],
            "database": [],
            "database/migrations": [],
            "docs": []
        }
        layout = custom_structure if custom_structure is not None else default_layout
        created_dirs: List[str] = []
        created_files: List[str] = []

        for folder, files in layout.items():
            dir_res = self.sandbox.create_directory(path=folder)
            created_dirs.append(folder)
            for file_name in files:
                rel_file_path = f"{folder}/{file_name}" if folder and folder != "." else file_name
                file_res = self.sandbox.create_file(path=rel_file_path, content="")
                created_files.append(rel_file_path)

        if self.diary:
            self.diary.record(
                action="SETUP_PROJECT_STRUCTURE",
                target_path="workspace",
                status="SUCCESS",
                details=f"Created {len(created_dirs)} dirs, {len(created_files)} files"
            )

        return {
            "created_directories": created_dirs,
            "created_files": created_files,
            "status": "SUCCESS"
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
        Sends an AgentMessage to a peer agent (Agent 1, 2, 3, or 4) via the Orchestrator.
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

    def dispatch_task(
        self,
        target_agent_id: str,
        task_description: str,
        required_capability: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        """
        Dispatches a specific task request to a developer or supervisor agent (A1, A2, A3, A4).
        """
        return self.send_agent_message(
            recipient=target_agent_id,
            content=task_description,
            message_type=MessageType.REQUEST,
            required_capability=required_capability,
            metadata=metadata
        )

    def handle_agent_message(self, message: AgentMessage) -> AgentMessage:
        """
        Handles incoming AgentMessages directed to Agent 5 from peer agents.
        Processes filesystem requests, dev server commands, project state queries, and status inquiries.
        """
        if message.message_type == MessageType.REQUEST:
            meta_action = message.metadata.get("action")
            # Handle explicit tool invocations via metadata if provided
            if meta_action and meta_action in self.tool_dispatcher:
                args = message.metadata.get("args", {})
                result = self._execute_tool(meta_action, args)
                return message.create_response(
                    content=result,
                    message_type=MessageType.RESPONSE,
                    metadata={"action": meta_action, "status": "COMPLETED"}
                )

            # Otherwise process through normal LLM execution
            response_content = self.process_request(message.content)
            return message.create_response(
                content=response_content,
                message_type=MessageType.RESPONSE
            )

        elif message.message_type == MessageType.INFORMATION:
            info_note = f"[Info from {message.sender}]: {message.content}"
            self.add_message("user", info_note)
            if self.diary:
                self.diary.record("PEER_INFO", message.sender, "LOGGED", message.content[:90])
            return message.create_response(
                content=f"Agent 5 received information from {message.sender}",
                message_type=MessageType.RESPONSE
            )

        else:
            return message.create_response(
                content=f"Agent 5 acknowledged {message.message_type.value} from {message.sender}",
                message_type=MessageType.RESPONSE
            )

    def _extract_tool_calls_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Fallback parser that extracts tool calls from text if Ollama placed raw JSON in content
        due to JSON quoting quirks in local LLMs.
        """
        if not text or not text.strip():
            return []

        cleaned = text.strip()

        # 1. Direct single or list JSON parse
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

        # 2. Regex-based extraction for multiple JSON tool call structures
        calls = []
        pattern = r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"(?:parameters|arguments)"\s*:\s*(\{.*?\})\s*\}'
        for match in re.finditer(pattern, cleaned, re.DOTALL):
            tool_name = match.group(1)
            params_str = match.group(2)
            try:
                params = json.loads(params_str)
                calls.append({"function": {"name": tool_name, "arguments": params}})
            except Exception:
                path_m = re.search(r'"path"\s*:\s*"([^"]+)"', params_str)
                path = path_m.group(1) if path_m else None
                
                content_m = re.search(r'"content"\s*:\s*"(.*)"', params_str, re.DOTALL)
                content = content_m.group(1) if content_m else ""
                
                if path is not None:
                    clean_content = content.replace('\\"', '"').replace('\\n', '\n')
                    calls.append({"function": {"name": tool_name, "arguments": {"path": path, "content": clean_content}}})

        return calls

    def _validate_tool_args(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validates tool arguments before execution.
        Detects truncated strings, missing parameters, or invalid structure.
        """
        if not isinstance(args, dict):
            return False, f"Tool arguments must be a dictionary, got {type(args).__name__}."

        if tool_name in ("create_file", "edit_file"):
            if "path" not in args or not str(args["path"]).strip():
                return False, "Missing or empty required 'path' parameter."

            content = args.get("content")
            if content is None:
                return False, "Missing required 'content' parameter."

            stripped = str(content).strip()
            # Detect truncated strings caused by quote tokenizer cutoffs (e.g., 'print(')
            if stripped in ("print(", "print", "def", "=") or re.match(r'^[a-zA-Z_]\w*\s*\(+$', stripped):
                return False, (
                    f"Tool argument validation failed: The 'content' parameter appears truncated ('{stripped}'). "
                    "This happens when internal quotes are not escaped. Please provide the complete, untruncated file content "
                    "with properly escaped JSON quotes."
                )

        elif tool_name in ("create_directory", "read_file"):
            if "path" not in args or not str(args["path"]).strip():
                return False, "Missing or empty required 'path' parameter."

        elif tool_name == "start_dev_server":
            if "command" not in args or not str(args["command"]).strip():
                return False, "Missing required 'command' parameter for starting development server."

        elif tool_name == "delegate_task":
            if "target_agent" not in args or not str(args["target_agent"]).strip():
                return False, "Missing required 'target_agent' parameter for task delegation."
            if "task" not in args or not str(args["task"]).strip():
                return False, "Missing required 'task' description parameter for task delegation."

        return True, ""

    def _execute_tool(self, function_name: str, arguments: Any) -> str:
        """
        Executes a filesystem, server management, project state, or task delegation tool with robust error handling.
        """
        if function_name not in self.tool_dispatcher:
            err = f"Unknown tool: '{function_name}'. Available tools: {list(self.tool_dispatcher.keys())}"
            if self.diary:
                self.diary.record("UNKNOWN_TOOL", function_name, "FAILED", err)
            return err

        # Parse arguments if passed as JSON string
        parsed_args = arguments
        if isinstance(arguments, str):
            try:
                parsed_args = json.loads(arguments)
            except json.JSONDecodeError as e:
                err = f"Malformed tool arguments JSON: {e}"
                if self.diary:
                    self.diary.record(function_name, "arguments", "FAILED", err)
                return err

        if not isinstance(parsed_args, dict):
            parsed_args = {}

        # Validate arguments
        is_valid, val_err = self._validate_tool_args(function_name, parsed_args)
        if not is_valid:
            if self.diary:
                target_str = str(parsed_args.get("path", parsed_args.get("target_agent", function_name)))
                self.diary.record(function_name, target_str, "FAILED", val_err)
            return f"Argument Error: {val_err}"

        tool_func = self.tool_dispatcher[function_name]
        try:
            result = tool_func(**parsed_args)
            return str(result)
        except TypeError as te:
            err = f"Invalid arguments for '{function_name}': {te}"
            if self.diary:
                self.diary.record(function_name, str(parsed_args), "ERROR", err)
            return err
        except PermissionError as pe:
            err = f"Security Sandbox Violation: {pe}"
            if self.diary:
                self.diary.record(function_name, str(parsed_args), "DENIED", err)
            return err
        except Exception as e:
            err = f"Tool execution error in '{function_name}': {str(e)}"
            if self.diary:
                self.diary.record(function_name, str(parsed_args), "ERROR", err)
            return err

    def process_request(
        self,
        user_input: str,
        on_tool_call: Optional[Callable[[str, Dict[str, Any], str], None]] = None
    ) -> str:
        """
        Main reasoning and execution loop for Agent 5:
        1. Adds user prompt to history.
        2. Queries LLM with full tool definitions (filesystem + dev server + delegate_task + project_state).
        3. Parses native tool calls (with fallback to content extraction).
        4. Validates arguments and executes tools inside the sandbox/orchestrator/state_manager.
        5. Feeds results back to LLM until final response is produced.
        """
        self.add_message("user", user_input)

        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            messages = self._prepare_messages()

            # Call LLM backend with combined tool schemas
            response = self.llm_provider.chat(messages, tools=ALL_WORKSPACE_TOOLS)
            tool_calls = response.get("tool_calls") if isinstance(response, dict) else None
            raw_content = response.get("content", "") if isinstance(response, dict) else str(response)

            # Fallback: check if tool call JSON was returned in content
            if not tool_calls and raw_content:
                extracted = self._extract_tool_calls_from_text(raw_content)
                if extracted:
                    tool_calls = extracted

            # Check if LLM requested tool execution
            if tool_calls:
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": raw_content or "",
                    "tool_calls": tool_calls
                }
                self.history.append(assistant_msg)
                self.save_history_to_disk()

                for call in tool_calls:
                    fn_info = call.get("function", {})
                    fn_name = fn_info.get("name", "")
                    fn_args = fn_info.get("arguments", {})

                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}

                    # Execute tool inside sandbox / server manager / orchestrator / state manager
                    tool_result = self._execute_tool(fn_name, fn_args)

                    # Notify caller (CLI / test suite)
                    if on_tool_call:
                        on_tool_call(fn_name, fn_args if isinstance(fn_args, dict) else {}, tool_result)

                    # Record tool output in history for the LLM to inspect
                    tool_msg: Dict[str, Any] = {
                        "role": "tool",
                        "content": tool_result,
                        "name": fn_name
                    }
                    if "id" in call:
                        tool_msg["tool_call_id"] = call["id"]

                    self.history.append(tool_msg)
                    self.save_history_to_disk()

                # Continue loop to let the model read the tool results
                continue

            else:
                # Final text answer reached
                final_content = raw_content.strip()
                self.add_message("assistant", final_content)
                return final_content

        # Max iterations reached - preserve state and report summary
        state_summary = ""
        try:
            state_content = self.state_manager.read_state()
            if state_content and "Project State" in state_content:
                state_summary = f"\n\nCurrent Project State (PROJECT_STATE.md):\n{state_content}"
        except Exception:
            pass

        warning_msg = (
            f"Orchestration limit reached: Completed operations but reached maximum of {self.max_tool_iterations} reasoning steps. "
            "Current project state and workspace progress have been preserved in PROJECT_STATE.md and CODE_DIARY.md. "
            f"You can review the progress or provide follow-up instructions to continue.{state_summary}"
        )
        self.add_message("assistant", warning_msg)
        return warning_msg
