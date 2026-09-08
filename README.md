# Multi-Agent Software Development System

This repository contains the architecture and implementation of the Multi-Agent Software Development System.

---

## 1. Architecture Overview

```
project/
├── agents/
│   ├── __init__.py          # Exports BaseAgent, WorkspaceAgent, FrontendAgent, BackendAgent, DataManagerAgent, SupervisorAgent
│   ├── base_agent.py        # Generic base agent structure with memory & LLM caller
│   ├── frontend_agent.py    # Agent 1: Frontend Developer
│   ├── backend_agent.py     # Agent 2: Backend Developer
│   ├── data_manager_agent.py # Agent 3: Data Manager
│   ├── supervisor_agent.py  # Agent 4: Supervisor / Monitor / Spectator
│   └── workspace_agent.py   # Agent 5: Workspace/Runtime Manager & Project Coordinator
├── state/
│   ├── __init__.py          # Exports ProjectStateManager, PROJECT_STATE_TOOLS, schemas
│   └── project_state.py     # ProjectStateManager for persistent PROJECT_STATE.md memory
├── orchestration/
│   ├── __init__.py          # Exports MessageType, AgentMessage, AgentRegistry, MessageBus, Orchestrator
│   ├── messages.py          # Typed AgentMessage dataclass and MessageType enum
│   ├── registry.py          # AgentRegistry for role & capability management
│   ├── message_bus.py       # Deterministic in-memory message routing & observer dispatcher
│   └── orchestrator.py      # Thin coordinator managing registry and message bus
├── config/
│   ├── __init__.py
│   └── config.py            # Environment-driven app configuration
├── diary/
│   ├── __init__.py
│   └── code_diary.py        # CodeDiary logger writing to CODE_DIARY.md
├── llm/
│   ├── __init__.py
│   ├── base.py              # BaseLLMProvider interface
│   └── ollama_client.py     # Native tool-calling client for Ollama API
├── tools/
│   ├── __init__.py          # Exports WorkspaceSandbox, DevServerManager, BackendVerifier, VerificationResult, schemas
│   ├── filesystem.py        # WorkspaceSandbox and 5 filesystem tool schemas & methods
│   ├── server_manager.py    # DevServerManager for development server lifecycles
│   └── verifier.py          # BackendVerifier and VerificationResult for syntax checking & test runner
├── workspace/               # Dedicated, sandboxed application directory
│   ├── PROJECT_STATE.md     # Persistent current project state memory
│   └── ...                  # Application files (frontend/, backend/, database/)
├── tests/                   # Deterministic, model-free unit test suite (141 unit tests)
│   ├── test_orchestration.py
│   ├── test_frontend_agent.py
│   ├── test_backend_agent.py
│   ├── test_data_manager_agent.py
│   ├── test_supervisor_agent.py
│   ├── test_workspace_agent.py
│   ├── test_project_state.py
│   ├── test_multi_stack.py
│   ├── test_server.py
│   ├── test_onboarding.py
│   └── test_architecture_discovery.py
├── CODE_DIARY.md            # Activity and audit log for workspace operations
├── main.py                  # Interactive terminal interface for the 5-Agent system
├── requirements.txt         # Minimal Python dependencies
└── README.md                # Documentation
```

---

## 2. Multi-Agent Conceptual Architecture vs Technical Infrastructure

```
                         USER
                           │
                           ▼
                          A5
                  App / Project Manager
                  (PROJECT_STATE.md)
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
            A1            A2            A3
         Frontend       Backend       Database
             ↕             ↕             ↕
             └─────────────┼─────────────┘
                           │
                           ▼
                          A4
                  Monitor / Spectator
```

### Communication Rules
1. **Direct Communication**: Agents 1, 2, and 3 communicate directly (`A1 ↔ A2`, `A1 ↔ A3`, `A2 ↔ A3`) when requesting work or specifications from each other.
2. **Non-Intrusive Observation**: Agent 4 observes relevant communication as a spectator/monitor without intercepting, delaying, or acting as a bottleneck.
3. **Escalation Pathway**: Out-of-scope tasks are routed directly to Agent 4 (`ESCALATION`).
4. **Permission Pathway**: Actions requiring user permission route from `Agent → Agent 4 → User`. Agent 4 registers structured pending approval states (`PENDING_USER_APPROVAL`) rather than autonomously granting permissions.
5. **Execution & Delegation Pathway**: Workspace file operations, dev server controls, project state updates, and autonomous task delegations route from `Agent 5` (`delegate_task`, `create_file`, `start_dev_server`, `read_project_state`, `update_project_state`).

### Technical Communication Infrastructure

```
Agents (A1 – A5) ──► Orchestrator ──► MessageBus (with Observers) ──► Agents (A1 – A5)
```
The `MessageBus` and `Orchestrator` are purely technical routing infrastructure and do not act as agents.

### Agents & Responsibilities

- **Agent 1 (Frontend Developer)**:
  - **Responsibilities**: Frontend architecture, UI components, client-side logic, and frontend code generation. Framework-neutral (React, Vue, Angular, Svelte, plain HTML/CSS/JS).
  - **Capabilities**: `frontend_code`, `frontend_files`, `ui_components`, `frontend_architecture`.
- **Agent 2 (Backend Developer)**:
  - **Responsibilities**: Backend architecture, server-side code, API endpoint design, routing, backend business logic, backend syntax checking (`verify_python_syntax`), test execution (`run_backend_tests`), and bounded self-repair loops. Framework-neutral (FastAPI, Flask, Django, Express/Node, etc.).
  - **Capabilities**: `backend_code`, `backend_files`, `api`, `backend_architecture`.
- **Agent 3 (Data Manager)**:
  - **Responsibilities**: Database architecture, schema design, database migrations, CRUD operations, and data models. Technology-neutral (PostgreSQL, SQLite, MySQL, MongoDB, etc.).
  - **Capabilities**: `database_schema`, `migrations`, `crud`, `data_models`.
- **Agent 4 (Supervisor / Monitor / Spectator)**:
  - **Responsibilities**: Observes agent interactions non-intrusively, monitors project scope and logistics, receives escalations, logs pending permission requests for human review, and communicates guidance across all agents.
  - **Capabilities**: `monitoring`, `scope_validation`, `escalation`, `permission_handling`, `logistics_monitoring`.
- **Agent 5 (Workspace & Runtime Manager / Autonomous Project Manager)**:
  - **Responsibilities**: Application & project management, persistent project memory (`PROJECT_STATE.md`), workspace layout organization, sandboxed filesystem operations, development server lifecycle management, Code Diary logging (`CODE_DIARY.md`), and autonomous iterative task delegation (`delegate_task`, `read_project_state`, `update_project_state`).
  - **Capabilities**: `filesystem`, `workspace`, `dev_server`, `diary`, `project_management`, `agent_coordination`, `project_state`.

---

## 3. Autonomous Multi-Round Project Orchestration Workflow

When the user supplies ONE high-level project objective (e.g., *"Build me a task management app with React, FastAPI and PostgreSQL"*), Agent 5 acts as the single orchestrator driving the project to completion:

```
                                USER
                                  │ (Single High-Level Objective)
                                  ▼
                        AGENT 5 (Project Manager)
                                  │
                                  ├────────► read_project_state() ──► PROJECT_STATE.md
                                  │
                           [Iteration 1]
                                  │
                                  ▼
                delegate_task("agent3", "Database schema...")
                                  │
                                  ▼
                     Agent 3 (Data Manager)
                                  │ (Schema result returned)
                                  ▼
                        AGENT 5 (Project Manager)
                                  │
                                  ├────────► update_project_state("Completed Tasks", ...)
                                  │
                           [Iteration 2]
                                  │
                                  ▼
       delegate_task("agent2", "Backend API...", context="<schema>")
                                  │
                                  ▼
                    Agent 2 (Backend Developer)
                                  │ (Backend + Verification result returned)
                                  ▼
                        AGENT 5 (Project Manager)
                                  │
                                  ├────────► update_project_state("Completed Tasks", ...)
                                  │
                           [Iteration 3]
                                  │
                                  ▼
      delegate_task("agent1", "Frontend UI...", context="<endpoints>")
                                  │
                                  ▼
                    Agent 1 (Frontend Developer)
                                  │ (UI components returned)
                                  ▼
                        AGENT 5 (Project Manager)
                                  │
                                  ├────────► update_project_state("Current Progress", "Complete")
                                  ▼
                                USER
                         (Comprehensive Summary)
```

### Key Workflow Highlights:
1. **Dynamic, Non-Hardcoded Delegation**: The sequence, target agents, and repeat iterations are determined dynamically by the LLM based on user requirements.
2. **Contextual Result Feeding**: Responses from specialist agents (including code, API specs, and verification/repair reports from Agent 2) are fed directly into Agent 5's active conversational reasoning context.
3. **Persistent Project Memory**: `PROJECT_STATE.md` is maintained via `update_project_state()` tool calls and survives conversation context compaction.
4. **Bounded Iteration Loop**: Bounded by `max_tool_iterations` (default 15) to prevent runaway execution while preserving all progress if the bound is reached.
5. **Non-Intrusive Supervisor Monitoring**: Agent 4 observes all inter-agent messages via `MessageBus` without intercepting or slowing down the pipeline.

---

## 4. Persistent Project State vs Code Diary

| Document | Purpose | Question Answered | Lifecycle |
|---|---|---|---|
| **`PROJECT_STATE.md`** | **Persistent Project Memory** | *What is true about the project RIGHT NOW?* | Continuously updated snapshot (requirements, tech stack, architecture, progress, tasks, decisions, issues). Survives context compaction. |
| **`CODE_DIARY.md`** | **Audit Activity Journal** | *What happened historically?* | Append-only chronological log of all filesystem and server lifecycle events. |

---

## 4. Setup & Running Instructions

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) running with `qwen3:8b` pulled:
  ```powershell
  ollama pull qwen3:8b
  ```

### Installation
```powershell
pip install -r requirements.txt
```

### Run Unit Tests (Fast, 100% Deterministic, Model-Free)
```powershell
python -m unittest discover tests
```

### Run Interactive Multi-Agent CLI

Run on the default sandbox directory:
```powershell
python main.py
```

Run dynamically on any active VS Code project root directory (changes will be directly visible in the **Source Control (Git)** tab):
```powershell
python main.py C:\path\to\your\project
```

You can also specify a custom model or temperature:
```powershell
python main.py C:\path\to\your\project --model qwen3:8b --temperature 0.2
```

---

## 5. Terminal Commands

While inside the interactive session:
- `/agents` - List all 5 registered agents and active capabilities
- `/state` - View persistent project state in `PROJECT_STATE.md`
- `/files` - View all files and folders in the sandbox
- `/server` - Check development server status
- `/diary` - View recent activity entries in `CODE_DIARY.md`
- `/clear` - Reset conversation memory
- `/history` - View conversation & tool execution history
- `/help` - Display available commands
- `/exit` or `/quit` - Exit the CLI session and stop active servers
