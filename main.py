import sys
import json
import argparse
from pathlib import Path

from config import config
from llm import OllamaProvider
from tools import WorkspaceSandbox, DevServerManager
from state import ProjectStateManager
from diary import CodeDiary
from orchestration import Orchestrator
from agents import (
    FrontendAgent,
    BackendAgent,
    DataManagerAgent,
    SupervisorAgent,
    WorkspaceAgent
)


def print_banner():
    print("=" * 72)
    print(" 🤖 Multi-Agent Software Development System (Agents 1 - 5 Active)")
    print("=" * 72)
    print(f" LLM Backend  : {config.default_model} via Ollama ({config.ollama_base_url})")
    print(f" Workspace    : {config.workspace_dir}")
    print(f" Project State: PROJECT_STATE.md")
    print(f" Code Diary   : {config.diary_file.name}")
    print(" Agents       : A1 (Frontend), A2 (Backend), A3 (Data Manager),")
    print("                A4 (Supervisor), A5 (Workspace/Runtime Manager)")
    print(" Commands     : /agents (inspect team)     | /files (inspect sandbox)")
    print("                /state  (view project state)| /server (dev server status)")
    print("                /diary  (view recent log)   | /clear  (reset memory)")
    print("                /history | /help | /exit")
    print("=" * 72)
    print()


def print_help():
    print("\nAvailable Commands:")
    print("  /agents   - List all 5 active agents and their registered capabilities")
    print("  /state    - View the persistent project state in PROJECT_STATE.md")
    print("  /files    - List all files currently in the workspace sandbox")
    print("  /server   - Show status of active development servers")
    print("  /diary    - View the latest entries in CODE_DIARY.md")
    print("  /clear    - Clear conversation memory for this session")
    print("  /history  - View message and tool history stored by Agent 5")
    print("  /help     - Show this help message")
    print("  /exit     - Exit the session\n")


def print_agents(orchestrator: Orchestrator):
    print("\n--- Registered Multi-Agent Team ---")
    registrations = orchestrator.registry.list_agents()
    for reg in registrations:
        caps_str = ", ".join(sorted(reg.capabilities)) if reg.capabilities else "none"
        print(f"  • [{reg.agent_id}] {reg.role:<22} | Capabilities: {caps_str}")
    print("-----------------------------------\n")


def print_server_status(server_manager: DevServerManager):
    print("\n[Development Server Status]")
    print(server_manager.get_server_status())
    print()


def print_history(agent: WorkspaceAgent):
    history = agent.get_history()
    if not history:
        print("\n[History] Conversation memory is currently empty.\n")
        return

    print("\n--- Conversation & Tool History ---")
    for idx, msg in enumerate(history, 1):
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            print(f"[{idx}] {role} (Requested Tools): {json.dumps(tool_calls, indent=2)}")
        elif role == "TOOL":
            tool_name = msg.get("name", "tool")
            print(f"[{idx}] {role} [{tool_name}]: {content}")
        else:
            print(f"[{idx}] {role}: {content}")
    print("-----------------------------------\n")


def show_project_state(state_manager: ProjectStateManager):
    print("\n[Persistent Project State - PROJECT_STATE.md]")
    print(state_manager.read_state())
    print()


def show_workspace_files(sandbox: WorkspaceSandbox):
    print("\n[Workspace Sandbox Contents]")
    print(sandbox.list_files("."))
    print()


def show_diary_entries(diary_path: Path):
    if not diary_path.exists():
        print("\n[Code Diary] No entries recorded yet.\n")
        return
    
    print("\n--- Recent Code Diary Entries ---")
    lines = diary_path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) > 20:
        print("\n".join(lines[:4]))
        print("... [earlier entries omitted] ...")
        print("\n".join(lines[-15:]))
    else:
        print("\n".join(lines))
    print("---------------------------------\n")


def on_tool_executed(tool_name: str, args: dict, result: str):
    """Callback displayed in the terminal when Agent 5 executes a tool."""
    args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
    print(f"\n  ⚙️  [Tool Execution] {tool_name}({args_str})")
    
    result_lines = result.strip().splitlines()
    if len(result_lines) == 1:
        print(f"  ↳  [Result] {result_lines[0]}")
    else:
        print(f"  ↳  [Result]")
        for line in result_lines[:6]:
            print(f"     {line}")
        if len(result_lines) > 6:
            print(f"     ... ({len(result_lines) - 6} more lines)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Software Development System")
    parser.add_argument("workspace_dir", nargs="?", default=None, help="Root workspace directory path (defaults to current working directory)")
    parser.add_argument("--model", type=str, default=None, help="Ollama LLM model name")
    parser.add_argument("--temperature", type=float, default=None, help="LLM temperature setting")
    args = parser.parse_args()

    if args.workspace_dir:
        config.set_workspace(args.workspace_dir)

    if args.model:
        config.default_model = args.model
    if args.temperature is not None:
        config.temperature = args.temperature

    print_banner()

    # 1. Initialize LLM Provider
    llm = OllamaProvider(
        base_url=config.ollama_base_url,
        model=config.default_model,
        default_temperature=config.temperature
    )

    # 2. Health check
    print("[*] Checking Ollama service & model availability...")
    is_healthy, health_msg = llm.health_check()
    if not is_healthy:
        print(f"\n❌ [Warning/Error]\n{health_msg}\n")
        choice = input("Do you want to continue anyway? (y/N): ").strip().lower()
        if choice != "y":
            print("Exiting.")
            sys.exit(1)
    else:
        print(f"✅ {health_msg}\n")

    # 3. Initialize Shared Infrastructure
    diary = CodeDiary(config.diary_file)
    sandbox = WorkspaceSandbox(config.workspace_dir, diary=diary)
    server_manager = DevServerManager(workspace_root=config.workspace_dir, diary=diary)
    state_manager = ProjectStateManager(sandbox=sandbox)
    onboard_res = state_manager.onboard_existing_project()
    print(f"[*] Workspace Onboarding: {onboard_res}")
    orchestrator = Orchestrator()

    # 4. Initialize Agents 1 through 5
    agent1 = FrontendAgent(
        llm_provider=llm,
        agent_id="agent1",
        orchestrator=orchestrator
    )
    agent2 = BackendAgent(
        llm_provider=llm,
        agent_id="agent2",
        orchestrator=orchestrator,
        sandbox=sandbox,
        diary=diary
    )
    agent3 = DataManagerAgent(
        llm_provider=llm,
        agent_id="agent3",
        orchestrator=orchestrator
    )
    agent4 = SupervisorAgent(
        llm_provider=llm,
        agent_id="agent4",
        orchestrator=orchestrator
    )
    agent5 = WorkspaceAgent(
        llm_provider=llm,
        agent_id="agent5",
        name="Agent 5 (Workspace Manager)",
        role="workspace_manager",
        system_prompt=config.agent5_system_prompt,
        sandbox=sandbox,
        diary=diary,
        server_manager=server_manager,
        state_manager=state_manager,
        orchestrator=orchestrator
    )

    # 5. Register All Agents with Orchestrator
    orchestrator.register_agent(
        agent_id=agent1.agent_id,
        role=agent1.role,
        capabilities=agent1.capabilities,
        handler=agent1.handle_agent_message
    )
    orchestrator.register_agent(
        agent_id=agent2.agent_id,
        role=agent2.role,
        capabilities=agent2.capabilities,
        handler=agent2.handle_agent_message
    )
    orchestrator.register_agent(
        agent_id=agent3.agent_id,
        role=agent3.role,
        capabilities=agent3.capabilities,
        handler=agent3.handle_agent_message
    )
    orchestrator.register_agent(
        agent_id=agent4.agent_id,
        role=agent4.role,
        capabilities=agent4.capabilities,
        handler=agent4.handle_agent_message
    )
    orchestrator.register_agent(
        agent_id=agent5.agent_id,
        role=agent5.role,
        capabilities=agent5.capabilities,
        handler=agent5.handle_agent_message
    )

    # 6. Register Supervisor as Non-Intrusive Message Bus Observer
    orchestrator.register_observer(agent4.observe_message)

    print(f"All 5 agents initialized and registered. Sandbox is '{config.workspace_dir.name}/'.")
    print("Type your instructions below (e.g., 'Create a fullstack project with frontend and backend').\n")

    # 7. Interactive REPL Loop
    while True:
        try:
            user_input = input("You > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSession terminated by user. Stopping servers and exiting...")
            server_manager.stop_all_servers()
            print("Goodbye!")
            break

        if not user_input:
            continue

        # Handle CLI commands
        lower_input = user_input.lower()
        if lower_input in ("/exit", "/quit"):
            print("\nStopping active servers and exiting session. Goodbye!")
            server_manager.stop_all_servers()
            break
        elif lower_input == "/clear":
            agent5.clear_history()
            print("\n🧹 Agent 5 conversation memory cleared.\n")
            continue
        elif lower_input == "/history":
            print_history(agent5)
            continue
        elif lower_input == "/agents":
            print_agents(orchestrator)
            continue
        elif lower_input == "/state":
            show_project_state(state_manager)
            continue
        elif lower_input == "/server":
            print_server_status(server_manager)
            continue
        elif lower_input == "/files":
            show_workspace_files(sandbox)
            continue
        elif lower_input == "/diary":
            show_diary_entries(config.diary_file)
            continue
        elif lower_input == "/help":
            print_help()
            continue

        # Process user request through Agent 5 with live tool execution feedback
        try:
            response = agent5.process_request(
                user_input=user_input,
                on_tool_call=on_tool_executed
            )
            print(f"Agent 5 > {response}\n")
        except ConnectionError as ce:
            print(f"\n❌ Connection Error: {ce}\n")
        except Exception as e:
            print(f"\n❌ Execution Error: {e}\n")


if __name__ == "__main__":
    main()
