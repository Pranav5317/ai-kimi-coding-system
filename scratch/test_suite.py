import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config
from llm import OllamaProvider
from tools import WorkspaceSandbox
from diary import CodeDiary
from agents import WorkspaceAgent


def run_tests():
    diary = CodeDiary(config.diary_file)
    sandbox = WorkspaceSandbox(config.workspace_dir, diary=diary)
    llm = OllamaProvider(model=config.default_model)
    agent = WorkspaceAgent(
        name="Agent 5",
        role="Workspace Manager",
        system_prompt=config.agent5_system_prompt,
        llm_provider=llm,
        sandbox=sandbox,
        diary=diary
    )

    results = {}

    print("\n--- TEST A: Create Directory ---")
    resp_a = agent.process_request("Create a directory called frontend.")
    print("Agent Response A:", resp_a)
    frontend_dir = config.workspace_dir / "frontend"
    results["Test A (create_directory)"] = frontend_dir.exists() and frontend_dir.is_dir()

    print("\n--- TEST B: Create Python file containing quotes ---")
    prompt_b = 'Create a file named backend/app.py containing:\nprint("Hello from backend!")'
    resp_b = agent.process_request(prompt_b)
    print("Agent Response B:", resp_b)
    app_file = config.workspace_dir / "backend" / "app.py"
    if app_file.exists():
        content_b = app_file.read_text(encoding="utf-8")
        print("Actual file on disk (app.py):\n", repr(content_b))
        results["Test B (file with quotes)"] = 'print("Hello from backend!")' in content_b or "Hello from backend!" in content_b
    else:
        results["Test B (file with quotes)"] = False

    print("\n--- TEST C: Create multiline Python file ---")
    multiline_code = (
        'def greet(name: str) -> str:\n'
        '    """Return a greeting message."""\n'
        '    return f"Hello, {name}!"\n\n'
        'def add(a: int, b: int) -> int:\n'
        '    return a + b\n\n'
        'if __name__ == "__main__":\n'
        '    msg = greet("World")\n'
        '    print(f"Message: {msg}")\n'
        '    print("Sum:", add(5, 7))\n'
    )
    prompt_c = f'Create a file named backend/utils.py with this exact multiline content:\n```python\n{multiline_code}\n```'
    resp_c = agent.process_request(prompt_c)
    print("Agent Response C:", resp_c)
    utils_file = config.workspace_dir / "backend" / "utils.py"
    if utils_file.exists():
        content_c = utils_file.read_text(encoding="utf-8")
        print("Actual file on disk (utils.py):\n", content_c)
        results["Test C (multiline file)"] = "def greet" in content_c and "def add" in content_c
    else:
        results["Test C (multiline file)"] = False

    print("\n--- TEST D: Read file back ---")
    resp_d = agent.process_request("Read the file backend/utils.py and display its contents.")
    print("Agent Response D:", resp_d)
    diary_content = config.diary_file.read_text(encoding="utf-8")
    results["Test D (read_file)"] = "READ_FILE" in diary_content and ("backend/utils.py" in diary_content or "backend\\utils.py" in diary_content)

    print("\n--- TEST E: List workspace files ---")
    resp_e = agent.process_request("List all files and directories in the workspace.")
    print("Agent Response E:", resp_e)
    results["Test E (list_files)"] = "backend" in resp_e or "frontend" in resp_e

    print("\n--- TEST F: Modify existing file ---")
    resp_f = agent.process_request('Edit backend/app.py so its content is:\nprint("Updated backend message!")')
    print("Agent Response F:", resp_f)
    if app_file.exists():
        content_f = app_file.read_text(encoding="utf-8")
        print("Actual file on disk after edit:\n", repr(content_f))
        results["Test F (edit_file)"] = "Updated backend message!" in content_f
    else:
        results["Test F (edit_file)"] = False

    print("\n--- TEST G: Path Traversal Security Violation ---")
    resp_g = agent.process_request("Read the file ../config/config.py")
    print("Agent Response G:", resp_g)
    diary_content = config.diary_file.read_text(encoding="utf-8")
    results["Test G (sandbox rejection)"] = "Security Sandbox Violation" in diary_content or "DENIED" in diary_content

    print("\n--- TEST H: Verify CODE_DIARY.md ---")
    print("Recent Diary Entries:\n", "\n".join(diary_content.strip().splitlines()[-10:]))
    results["Test H (code diary logging)"] = "CREATE_DIRECTORY" in diary_content and "CREATE_FILE" in diary_content

    print("\n--- TEST I: Malformed tool call handling ---")
    # Test invalid tool argument handling
    err_test1 = agent._execute_tool("create_file", {"path": "test.py", "content": "print("})
    err_test2 = agent._execute_tool("unknown_tool", {})
    print("Malformed execution 1 result:", err_test1)
    print("Malformed execution 2 result:", err_test2)
    results["Test I (malformed tool error handling)"] = "Argument Error" in err_test1 and "Unknown tool" in err_test2

    print("\n================ TEST SUMMARY ================")
    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print(f"{status}: {test_name}")
    print("==============================================")
    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

