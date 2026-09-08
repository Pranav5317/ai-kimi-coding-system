import subprocess
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from diary.code_diary import CodeDiary


class DevServerManager:
    """
    Manages development server lifecycle (start, stop, status) within the workspace.
    Tracks active subprocesses in a non-blocking manner and records server lifecycle events to CodeDiary.
    """

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        diary: Optional[CodeDiary] = None
    ) -> None:
        self.workspace_root = workspace_root.resolve() if workspace_root else Path.cwd().resolve()
        self.diary = diary
        # Map of server_name -> process metadata dict
        self.processes: Dict[str, Dict[str, Any]] = {}

    def start_server(
        self,
        command: str,
        port: Optional[int] = None,
        name: str = "default",
        cwd: Optional[Path] = None,
        **kwargs: Any
    ) -> str:
        """
        Starts a development server in the background using subprocess.Popen.
        
        Args:
            command: The command line string to run.
            port: Port number on which the server is expected to listen.
            name: Identifier name for the server instance (e.g. 'default', 'frontend', 'backend').
            cwd: Working directory for the process (defaults to workspace_root).
        
        Returns:
            Status message detailing PID, command, and port.
        """
        if not command or not command.strip():
            return "Error: Command cannot be empty."

        clean_name = name.strip() if name else "default"
        target_cwd = cwd if cwd is not None else self.workspace_root

        # Check if already running
        if clean_name in self.processes:
            proc_info = self.processes[clean_name]
            popen_obj = proc_info.get("popen")
            if popen_obj and popen_obj.poll() is None:
                return (
                    f"Server '{clean_name}' is already running with PID {proc_info.get('pid')} "
                    f"(command: '{proc_info.get('command')}'). Stop it first to restart."
                )

        try:
            # Start process non-blocking
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=str(target_cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            self.processes[clean_name] = {
                "name": clean_name,
                "command": command,
                "port": port,
                "popen": proc,
                "pid": proc.pid,
                "status": "RUNNING",
                "start_time": now,
                "cwd": str(target_cwd)
            }

            port_info = f", port: {port}" if port is not None else ""
            msg = f"Development server '{clean_name}' started successfully with PID {proc.pid} (command: '{command}'{port_info})."

            if self.diary:
                self.diary.record(
                    action="START_DEV_SERVER",
                    target_path=f"{clean_name} (PID: {proc.pid})",
                    status="SUCCESS",
                    details=f"Command: '{command}'{port_info}"
                )

            return msg

        except Exception as e:
            err = f"Failed to start development server '{clean_name}': {str(e)}"
            if self.diary:
                self.diary.record(
                    action="START_DEV_SERVER",
                    target_path=clean_name,
                    status="ERROR",
                    details=str(e)
                )
            return err

    def stop_server(self, name: str = "default", **kwargs: Any) -> str:
        """
        Stops a running development server process by name.
        
        Args:
            name: Identifier name of the server to stop.
        
        Returns:
            Status message confirming termination or failure.
        """
        clean_name = name.strip() if name else "default"

        if clean_name not in self.processes:
            return f"No server named '{clean_name}' is currently registered."

        proc_info = self.processes[clean_name]
        popen_obj = proc_info.get("popen")
        pid = proc_info.get("pid")

        if popen_obj is None:
            return f"Server '{clean_name}' has no active process handle."

        if popen_obj.poll() is not None:
            proc_info["status"] = "STOPPED"
            return f"Server '{clean_name}' (PID {pid}) was already stopped (exit code: {popen_obj.poll()})."

        try:
            # Terminate process gracefully
            popen_obj.terminate()
            try:
                popen_obj.wait(timeout=2)
            except subprocess.TimeoutExpired:
                popen_obj.kill()
                popen_obj.wait(timeout=1)

            proc_info["status"] = "STOPPED"
            msg = f"Development server '{clean_name}' (PID {pid}) stopped successfully."

            if self.diary:
                self.diary.record(
                    action="STOP_DEV_SERVER",
                    target_path=f"{clean_name} (PID: {pid})",
                    status="SUCCESS",
                    details="Terminated process"
                )

            return msg

        except Exception as e:
            err = f"Error stopping server '{clean_name}' (PID {pid}): {str(e)}"
            if self.diary:
                self.diary.record(
                    action="STOP_DEV_SERVER",
                    target_path=f"{clean_name} (PID: {pid})",
                    status="ERROR",
                    details=str(e)
                )
            return err

    def get_server_status(self, name: Optional[str] = None, **kwargs: Any) -> str:
        """
        Checks the status of one or all tracked servers.
        
        Args:
            name: Specific server name to check. If None, checks all servers.
        
        Returns:
            Formatted status report.
        """
        # Refresh statuses
        for s_name, info in self.processes.items():
            proc = info.get("popen")
            if proc:
                exit_code = proc.poll()
                if exit_code is not None:
                    info["status"] = f"STOPPED (exit code {exit_code})"
                else:
                    info["status"] = "RUNNING"

        if not self.processes:
            return "No development servers are currently tracked."

        if name and name.strip():
            clean_name = name.strip()
            if clean_name not in self.processes:
                return f"Server '{clean_name}' is not registered."
            info = self.processes[clean_name]
            port_str = f" | Port: {info['port']}" if info.get("port") else ""
            return f"Server '{clean_name}': {info['status']} | PID: {info.get('pid')} | Command: '{info.get('command')}'{port_str} | Started: {info.get('start_time')}"

        lines = ["--- Tracked Development Servers ---"]
        for s_name, info in sorted(self.processes.items()):
            port_str = f" | Port: {info['port']}" if info.get("port") else ""
            lines.append(f"[{info['status']}] '{s_name}' (PID: {info.get('pid')}) - Command: '{info.get('command')}'{port_str} (Started: {info.get('start_time')})")
        lines.append("-----------------------------------")
        return "\n".join(lines)

    def stop_all_servers(self) -> str:
        """Stops all currently running development servers."""
        results = []
        for s_name in list(self.processes.keys()):
            proc_info = self.processes[s_name]
            popen_obj = proc_info.get("popen")
            if popen_obj and popen_obj.poll() is None:
                res = self.stop_server(s_name)
                results.append(res)

        if not results:
            return "No active development servers to stop."
        return "\n".join(results)


# --- Tool Definitions for LLM Function Calling ---

SERVER_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "start_dev_server",
            "description": "Start a background development server process (e.g. web server, backend API, frontend dev server).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command line string to execute the development server (e.g., 'python app.py' or 'npm run dev')."
                    },
                    "port": {
                        "type": "integer",
                        "description": "The port number on which the server listens (optional)."
                    },
                    "name": {
                        "type": "string",
                        "description": "Identifier name for the server instance (e.g., 'default', 'backend', 'frontend'). Defaults to 'default'."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_dev_server",
            "description": "Stop a running development server process by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Identifier name of the server to stop. Defaults to 'default'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_server_status",
            "description": "Check the status and details of active development server processes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Optional identifier name of a specific server to check. If omitted, returns all servers."
                    }
                },
                "required": []
            }
        }
    }
]

