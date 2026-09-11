import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm import OllamaProvider
from agents import WorkspaceAgent
from tools import WorkspaceSandbox, DevServerManager
from diary import CodeDiary
from config import config

def main():
    print("Testing WorkspaceAgent with real Ollama model...")
    llm = OllamaProvider(model=config.default_model)
    is_ok, msg = llm.health_check()
    print(f"Health check: {is_ok} - {msg}")

    test_ws = Path.cwd() / "workspace"
    test_ws.mkdir(exist_ok=True)
    diary = CodeDiary(test_ws / "CODE_DIARY.md")
    sandbox = WorkspaceSandbox(test_ws, diary=diary)
    server_mgr = DevServerManager(test_ws, diary=diary)

    agent = WorkspaceAgent(
        llm_provider=llm,
        agent_id="agent5",
        sandbox=sandbox,
        diary=diary,
        server_manager=server_mgr
    )

    def on_tool(name, args, result):
        print(f"\n[TOOL CALLED] {name}({args})\n--> RESULT: {result[:200]}")

    print("\nSending prompt: 'List all files in the current workspace directory'")
    res = agent.process_request("List all files in the current workspace directory", on_tool_call=on_tool)
    print("\n--- Final Agent Response ---")
    print(res)

if __name__ == "__main__":
    main()

