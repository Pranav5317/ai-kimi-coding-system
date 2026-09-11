import os
import sys
import json
import asyncio
import threading
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

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


app = FastAPI(
    title="Multi-Agent Software Development System API",
    description="Backend API powering the VS Code Extension and Web UI for the 5-Agent team.",
    version="1.0.0"
)

# Enable CORS for VS Code Webview and local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SystemCore:
    """
    Encapsulates state and agent instances for the multi-agent system server.
    """

    def __init__(self, workspace_path: Optional[str] = None):
        if workspace_path:
            config.set_workspace(workspace_path)

        self.llm = OllamaProvider(
            base_url=config.ollama_base_url,
            model=config.default_model,
            default_temperature=config.temperature,
            num_ctx=config.num_ctx,
            timeout=config.llm_timeout
        )
        self.diary = CodeDiary(config.diary_file)
        self.sandbox = WorkspaceSandbox(config.workspace_dir, diary=self.diary)
        self.server_manager = DevServerManager(workspace_root=config.workspace_dir, diary=self.diary)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)
        self.state_manager.onboard_existing_project()
        self.orchestrator = Orchestrator()

        # Agents
        self.agent1 = FrontendAgent(llm_provider=self.llm, agent_id="agent1", orchestrator=self.orchestrator)
        self.agent2 = BackendAgent(llm_provider=self.llm, agent_id="agent2", orchestrator=self.orchestrator, sandbox=self.sandbox, diary=self.diary)
        self.agent3 = DataManagerAgent(llm_provider=self.llm, agent_id="agent3", orchestrator=self.orchestrator)
        self.agent4 = SupervisorAgent(llm_provider=self.llm, agent_id="agent4", orchestrator=self.orchestrator)
        self.agent5 = WorkspaceAgent(
            llm_provider=self.llm,
            agent_id="agent5",
            name="Agent 5 (Workspace Manager)",
            role="workspace_manager",
            system_prompt=config.agent5_system_prompt,
            sandbox=self.sandbox,
            diary=self.diary,
            server_manager=self.server_manager,
            state_manager=self.state_manager,
            orchestrator=self.orchestrator
        )

        # Register agents
        for agent in (self.agent1, self.agent2, self.agent3, self.agent4, self.agent5):
            self.orchestrator.register_agent(
                agent_id=agent.agent_id,
                role=agent.role,
                capabilities=agent.capabilities,
                handler=agent.handle_agent_message
            )
        self.orchestrator.register_observer(self.agent4.observe_message)

    def switch_workspace(self, workspace_path: str) -> None:
        """
        Dynamically switches the core workspace to target project folder.
        Reloads sandbox, dev server manager, project state manager, diary, and chat history.
        """
        if not workspace_path or not str(workspace_path).strip():
            return

        target_path = Path(workspace_path).resolve()
        if self.sandbox and self.sandbox.workspace_root == target_path:
            return

        config.set_workspace(target_path)
        self.diary = CodeDiary(config.diary_file)
        self.sandbox = WorkspaceSandbox(config.workspace_dir, diary=self.diary)
        self.server_manager = DevServerManager(workspace_root=config.workspace_dir, diary=self.diary)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)
        self.state_manager.onboard_existing_project()

        # Update Agent 2 & Agent 5 references
        self.agent2.sandbox = self.sandbox
        self.agent2.diary = self.diary

        self.agent5.sandbox = self.sandbox
        self.agent5.diary = self.diary
        self.agent5.server_manager = self.server_manager
        self.agent5.state_manager = self.state_manager
        self.agent5.load_history_from_disk()


# Global core instance
core: Optional[SystemCore] = None


@app.on_event("startup")
def startup_event():
    global core
    if core is None:
        core = SystemCore()


@app.get("/api/health")
def get_health():
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    is_healthy, health_msg = core.llm.health_check()
    return {
        "status": "online" if is_healthy else "degraded",
        "llm_health": health_msg,
        "model": config.default_model,
        "workspace_dir": str(config.workspace_dir)
    }


@app.get("/api/agents")
def list_agents():
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    agents = []
    for reg in core.orchestrator.registry.list_agents():
        agents.append({
            "agent_id": reg.agent_id,
            "role": reg.role,
            "capabilities": sorted(list(reg.capabilities)) if reg.capabilities else []
        })
    return {"agents": agents}


@app.get("/api/skills")
def list_skills():
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    skills = core.agent5.skill_manager.list_skills()
    return {"skills": skills}


@app.get("/api/state")
def get_project_state():
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    state_text = core.state_manager.read_state()
    return {"content": state_text}


@app.get("/api/files")
def list_workspace_files():
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    file_list = core.sandbox.list_files(".")
    return {"files": file_list}


@app.get("/api/diary")
def get_diary_entries(limit: int = 20):
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    if not config.diary_file.exists():
        return {"entries": []}
    lines = config.diary_file.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-limit:] if len(lines) > limit else lines
    return {"entries": recent}


@app.post("/api/workspace")
def switch_workspace_endpoint(payload: Dict[str, Any]):
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    target_path = payload.get("workspace_path")
    if target_path:
        core.switch_workspace(target_path)
    return {
        "status": "success",
        "workspace_dir": str(config.workspace_dir),
        "history": core.agent5.get_history(),
        "project_state": core.state_manager.read_state()
    }


@app.post("/api/chat")
async def chat_endpoint(payload: Dict[str, Any]):
    if core is None:
        raise HTTPException(status_code=500, detail="Core not initialized.")
    
    workspace_path = payload.get("workspace_path")
    if workspace_path:
        core.switch_workspace(workspace_path)

    prompt = payload.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")

    tool_executions = []

    def on_tool(name: str, args: dict, result: str):
        tool_executions.append({"tool": name, "args": args, "result": result})

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: core.agent5.process_request(user_input=prompt, on_tool_call=on_tool)
    )

    return {
        "response": response,
        "tool_executions": tool_executions,
        "project_state": core.state_manager.read_state()
    }


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                pass


ws_manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, workspace: Optional[str] = Query(None)):
    await ws_manager.connect(websocket)
    loop = asyncio.get_event_loop()
    pending_permission_events: Dict[str, Tuple[threading.Event, List[bool]]] = {}

    if workspace and core:
        core.switch_workspace(workspace)

    # Send initial status on connect
    if core:
        await websocket.send_json({
            "type": "init",
            "model": config.default_model,
            "workspace_dir": str(config.workspace_dir),
            "project_state": core.state_manager.read_state()
        })
        await websocket.send_json({
            "type": "history",
            "history": core.agent5.get_history()
        })

    request_lock = asyncio.Lock()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "switch_workspace":
                target_ws = data.get("workspace_path")
                if target_ws and core:
                    core.switch_workspace(target_ws)
                    await websocket.send_json({
                        "type": "init",
                        "model": config.default_model,
                        "workspace_dir": str(config.workspace_dir),
                        "project_state": core.state_manager.read_state()
                    })
                    await websocket.send_json({
                        "type": "history",
                        "history": core.agent5.get_history()
                    })

            elif msg_type == "clear_history":
                if core:
                    core.agent5.clear_history()
                    await websocket.send_json({
                        "type": "history",
                        "history": []
                    })

            elif msg_type == "permission_response":
                req_id = data.get("request_id")
                approved = bool(data.get("approved", False))
                if req_id and req_id in pending_permission_events:
                    evt, holder = pending_permission_events.pop(req_id)
                    holder[0] = approved
                    evt.set()

            elif msg_type == "prompt":
                prompt = data.get("content", "").strip()
                require_perm = bool(data.get("require_permission", True))
                if not prompt:
                    continue

                if request_lock.locked():
                    await websocket.send_json({
                        "type": "assistant_response",
                        "content": "Agent 5 is currently processing another request. Please wait until it completes."
                    })
                    continue

                async with request_lock:
                    await websocket.send_json({"type": "status", "content": "Agent 5 reasoning..."})

                    mutating_tools = {"create_file", "edit_file", "write_file", "delete_file", "run_command", "start_dev_server", "stop_dev_server"}

                    def pre_tool_call(tool_name: str, args: dict) -> bool:
                        target = args.get("path") or args.get("file_path") or args.get("file") or args.get("target") or args.get("command") or ""

                        # Live active file / tool status indicator
                        if tool_name in {"create_file", "edit_file", "write_file"} and target:
                            status_txt = f"✍️ Editing {target}..."
                        elif tool_name == "read_file" and target:
                            status_txt = f"📖 Reading {target}..."
                        elif tool_name == "run_command":
                            status_txt = f"⚡ Running command: {str(target)[:30]}..."
                        else:
                            status_txt = f"⚙️ Executing {tool_name}..."

                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json({"type": "status", "content": status_txt}),
                            loop
                        )

                        if require_perm and tool_name in mutating_tools:
                            req_id = f"req_{uuid.uuid4().hex[:8]}"
                            evt = threading.Event()
                            holder = [False]
                            pending_permission_events[req_id] = (evt, holder)

                            # Notify status spinner of approval prompt
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_json({"type": "status", "content": f"⚠️ Waiting for approval: {tool_name} {target}"}),
                                loop
                            )

                            asyncio.run_coroutine_threadsafe(
                                websocket.send_json({
                                    "type": "permission_request",
                                    "request_id": req_id,
                                    "tool": tool_name,
                                    "args": args,
                                    "target_file": str(target)
                                }),
                                loop
                            )

                            # Block worker thread until client approves/denies or timeout occurs
                            evt.wait(timeout=120)
                            return holder[0]

                        return True

                    def on_tool_call(tool_name: str, args: dict, result: str):
                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json({
                                "type": "tool_execution",
                                "tool": tool_name,
                                "args": args,
                                "result": result
                            }),
                            loop
                        )

                    try:
                        response = await loop.run_in_executor(
                            None,
                            lambda: core.agent5.process_request(
                                user_input=prompt,
                                on_tool_call=on_tool_call,
                                pre_tool_call=pre_tool_call
                            )
                        )
                    except Exception as req_err:
                        response = f"⚠️ System error while executing request: {str(req_err)}"

                    await websocket.send_json({
                        "type": "assistant_response",
                        "content": response
                    })

                    if core:
                        await websocket.send_json({
                            "type": "project_state",
                            "content": core.state_manager.read_state()
                        })

            elif msg_type == "get_state":
                if core:
                    await websocket.send_json({
                        "type": "project_state",
                        "content": core.state_manager.read_state()
                    })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Agent System FastAPI Server")
    parser.add_argument("workspace_dir", nargs="?", default=None, help="Root workspace directory path")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    args = parser.parse_args()

    if args.workspace_dir:
        core = SystemCore(workspace_path=args.workspace_dir)

    uvicorn.run(app, host=args.host, port=args.port)

