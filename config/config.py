import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

# Optional dotenv loading if python-dotenv is installed
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


@dataclass
class AppConfig:
    """Application configuration settings."""
    ollama_base_url: Optional[str] = None
    default_model: Optional[str] = None
    temperature: Optional[float] = None
    num_ctx: Optional[int] = None
    workspace_dir: Optional[Path] = None
    diary_file: Optional[Path] = None
    agent5_system_prompt: Optional[str] = None

    def __post_init__(self):
        if self.ollama_base_url is None:
            self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if self.default_model is None:
            self.default_model = os.getenv("LLM_MODEL") or os.getenv("MODEL_NAME", "qwen3-coder:latest")
        if self.temperature is None:
            self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.0"))
        if self.num_ctx is None:
            self.num_ctx = int(os.getenv("LLM_NUM_CTX") or os.getenv("NUM_CTX", "8192"))
        if self.workspace_dir is None:
            env_ws = os.getenv("WORKSPACE_DIR")
            if env_ws:
                self.workspace_dir = Path(env_ws).resolve()
            else:
                self.workspace_dir = (Path(__file__).resolve().parent.parent / "workspace").resolve()
        else:
            self.workspace_dir = Path(self.workspace_dir).resolve()

        if self.diary_file is None:
            env_diary = os.getenv("DIARY_FILE")
            if env_diary:
                self.diary_file = Path(env_diary).resolve()
            else:
                self.diary_file = (Path(__file__).resolve().parent.parent / "CODE_DIARY.md").resolve()
        else:
            self.diary_file = Path(self.diary_file).resolve()

        if self.agent5_system_prompt is None:
            self.agent5_system_prompt = os.getenv(
                "AGENT5_SYSTEM_PROMPT",
                "You are Agent 5, the Workspace/Runtime Manager & Project Manager for an AI multi-agent software engineering system. "
                "Your responsibility is to manage the project workspace, maintain persistent project memory in PROJECT_STATE.md, "
                "and autonomously coordinate project implementation by delegating specialist tasks to Agent 1 (Frontend), "
                "Agent 2 (Backend), and Agent 3 (Data Manager). "
                "When given a project objective, inspect project state, dynamically delegate tasks across multiple iterations, "
                "update PROJECT_STATE.md as progress occurs, and drive the project to completion."
            )

    def set_workspace(self, target_dir: Union[str, Path]) -> None:
        """
        Dynamically configures the active workspace directory at runtime (e.g. from CLI arguments).
        """
        resolved = Path(target_dir).resolve()
        self.workspace_dir = resolved
        resolved.mkdir(parents=True, exist_ok=True)


# Global config instance
config = AppConfig()
