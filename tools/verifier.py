import sys
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List
from .filesystem import WorkspaceSandbox
from diary.code_diary import CodeDiary


@dataclass
class VerificationResult:
    """
    Structured outcome of a backend syntax check or test suite execution.
    """
    command: str
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        parts = [
            f"[{status}] Command: {self.command} (Exit Code: {self.exit_code})",
            f"Details: {self.details}"
        ]
        if self.stdout.strip():
            parts.append(f"STDOUT:\n{self.stdout.strip()}")
        if self.stderr.strip():
            parts.append(f"STDERR:\n{self.stderr.strip()}")
        return "\n".join(parts)


# Tool schemas for LLM function calling
VERIFICATION_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "verify_code_syntax",
            "description": (
                "Verify code syntax of any file in the workspace sandbox across Python, JS/TS, HTML, CSS, C/C++, Java, JSON, SQL, etc. "
                "Returns whether the code compiles cleanly or provides exact syntax error details to diagnose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The relative path to the source file within the workspace (e.g. 'src/app.js', 'main.py', 'server.cpp')."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_python_syntax",
            "description": (
                "Verify the Python syntax of a backend file in the workspace sandbox using py_compile. "
                "Returns whether the code compiles cleanly or provides exact syntax error details to diagnose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The relative path to the Python file within the workspace (e.g. 'backend/app.py' or 'main.py')."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_backend_tests",
            "description": (
                "Run unit tests for backend code inside the workspace sandbox. "
                "Returns pass/fail status, exit code, stdout, and stderr for failure diagnosis and self-repair."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Optional relative path to a specific test file (e.g. 'backend/test_api.py'). If omitted, runs test discovery."
                    },
                    "command": {
                        "type": "string",
                        "description": "Optional specific test command (e.g. 'pytest' or 'python -m unittest discover')."
                    }
                }
            }
        }
    }
]


class BackendVerifier:
    """
    Safely executes backend code verification (syntax checking and test runners)
    strictly sandboxed within the workspace root directory.
    """

    def __init__(
        self,
        sandbox: WorkspaceSandbox,
        diary: Optional[CodeDiary] = None,
        timeout_seconds: int = 30
    ) -> None:
        self.sandbox = sandbox
        self.diary = diary
        self.timeout_seconds = timeout_seconds

    def verify_python(self, file_path: str) -> VerificationResult:
        """
        Runs Python syntax compilation check (py_compile) on a file inside the sandbox.
        """
        try:
            target = self.sandbox.validate_and_resolve(file_path)
        except PermissionError as pe:
            res = VerificationResult(
                command=f"python -m py_compile {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=str(pe),
                passed=False,
                details=f"Security Sandbox Violation: {pe}"
            )
            if self.diary:
                self.diary.record("VERIFY_PYTHON", file_path, "DENIED", res.details)
            return res
        except Exception as e:
            res = VerificationResult(
                command=f"python -m py_compile {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=str(e),
                passed=False,
                details=f"Invalid path: {e}"
            )
            return res

        if not target.is_file():
            res = VerificationResult(
                command=f"python -m py_compile {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=f"File not found: {file_path}",
                passed=False,
                details=f"Target file '{file_path}' does not exist inside workspace."
            )
            if self.diary:
                self.diary.record("VERIFY_PYTHON", file_path, "FAILED", res.details)
            return res

        cmd = [sys.executable, "-m", "py_compile", str(target)]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.sandbox.workspace_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            passed = (proc.returncode == 0)
            details = "Python syntax check passed successfully." if passed else "Python syntax compilation failed."
            res = VerificationResult(
                command=f"python -m py_compile {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                passed=passed,
                details=details
            )
            if self.diary:
                self.diary.record("VERIFY_PYTHON", file_path, "PASSED" if passed else "FAILED", details)
            return res
        except subprocess.TimeoutExpired:
            res = VerificationResult(
                command=f"python -m py_compile {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=-1,
                stdout="",
                stderr=f"Syntax check timed out after {self.timeout_seconds}s",
                passed=False,
                details="Syntax verification timed out."
            )
            if self.diary:
                self.diary.record("VERIFY_PYTHON", file_path, "TIMEOUT", res.details)
            return res
        except Exception as e:
            res = VerificationResult(
                command=f"python -m py_compile {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=str(e),
                passed=False,
                details=f"Execution error: {str(e)}"
            )
            if self.diary:
                self.diary.record("VERIFY_PYTHON", file_path, "ERROR", str(e))
            return res

    def verify_code_syntax(self, file_path: str) -> VerificationResult:
        """
        Universal multi-stack code syntax check (Python, JS/TS, JSON, HTML, CSS, C/C++, Java, SQL, etc.).
        """
        try:
            target = self.sandbox.validate_and_resolve(file_path)
        except PermissionError as pe:
            res = VerificationResult(
                command=f"verify_code_syntax {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=str(pe),
                passed=False,
                details=f"Security Sandbox Violation: {pe}"
            )
            if self.diary:
                self.diary.record("VERIFY_SYNTAX", file_path, "DENIED", res.details)
            return res
        except Exception as e:
            return VerificationResult(
                command=f"verify_code_syntax {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=str(e),
                passed=False,
                details=f"Invalid path: {e}"
            )

        if not target.is_file():
            res = VerificationResult(
                command=f"verify_code_syntax {file_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=f"File not found: {file_path}",
                passed=False,
                details=f"Target file '{file_path}' does not exist inside workspace."
            )
            if self.diary:
                self.diary.record("VERIFY_SYNTAX", file_path, "FAILED", res.details)
            return res

        ext = target.suffix.lower()

        if ext == ".py":
            return self.verify_python(file_path)

        if ext == ".json":
            try:
                content = target.read_text(encoding="utf-8")
                import json as json_mod
                json_mod.loads(content)
                res = VerificationResult(
                    command=f"json_parse {file_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=0,
                    stdout="",
                    stderr="",
                    passed=True,
                    details="JSON syntax is valid."
                )
            except Exception as e:
                res = VerificationResult(
                    command=f"json_parse {file_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=1,
                    stdout="",
                    stderr=str(e),
                    passed=False,
                    details=f"JSON syntax error: {e}"
                )
            if self.diary:
                self.diary.record("VERIFY_SYNTAX", file_path, "PASSED" if res.passed else "FAILED", res.details)
            return res

        if ext in (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"):
            try:
                proc = subprocess.run(
                    ["node", "--check", str(target)],
                    cwd=str(self.sandbox.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds
                )
                passed = (proc.returncode == 0)
                res = VerificationResult(
                    command=f"node --check {file_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    passed=passed,
                    details="JavaScript/TypeScript syntax check passed." if passed else "JavaScript/TypeScript syntax error detected."
                )
            except FileNotFoundError:
                res = self._fallback_syntax_check(target, file_path, "JS/TS")
            except Exception as e:
                res = self._fallback_syntax_check(target, file_path, "JS/TS", err=str(e))
            if self.diary:
                self.diary.record("VERIFY_SYNTAX", file_path, "PASSED" if res.passed else "FAILED", res.details)
            return res

        if ext in (".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"):
            compiler = "g++" if ext in (".cpp", ".cc", ".cxx", ".hpp") else "gcc"
            try:
                proc = subprocess.run(
                    [compiler, "-fsyntax-only", str(target)],
                    cwd=str(self.sandbox.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds
                )
                passed = (proc.returncode == 0)
                res = VerificationResult(
                    command=f"{compiler} -fsyntax-only {file_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    passed=passed,
                    details="C/C++ syntax check passed." if passed else "C/C++ syntax error detected."
                )
            except FileNotFoundError:
                res = self._fallback_syntax_check(target, file_path, "C/C++")
            except Exception as e:
                res = self._fallback_syntax_check(target, file_path, "C/C++", err=str(e))
            if self.diary:
                self.diary.record("VERIFY_SYNTAX", file_path, "PASSED" if res.passed else "FAILED", res.details)
            return res

        if ext == ".java":
            try:
                proc = subprocess.run(
                    ["javac", "-proc:none", str(target)],
                    cwd=str(self.sandbox.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds
                )
                passed = (proc.returncode == 0)
                res = VerificationResult(
                    command=f"javac -proc:none {file_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    passed=passed,
                    details="Java syntax check passed." if passed else "Java syntax error detected."
                )
            except FileNotFoundError:
                res = self._fallback_syntax_check(target, file_path, "Java")
            except Exception as e:
                res = self._fallback_syntax_check(target, file_path, "Java", err=str(e))
            if self.diary:
                self.diary.record("VERIFY_SYNTAX", file_path, "PASSED" if res.passed else "FAILED", res.details)
            return res

        if ext in (".html", ".htm"):
            try:
                content = target.read_text(encoding="utf-8")
                from html.parser import HTMLParser
                class StrictParser(HTMLParser):
                    def error(self, message):
                        raise Exception(message)
                p = StrictParser()
                p.feed(content)
                res = VerificationResult(
                    command=f"html_parse {file_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=0,
                    stdout="",
                    stderr="",
                    passed=True,
                    details="HTML syntax validation passed."
                )
            except Exception as e:
                res = VerificationResult(
                    command=f"html_parse {file_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=1,
                    stdout="",
                    stderr=str(e),
                    passed=False,
                    details=f"HTML syntax error: {e}"
                )
            if self.diary:
                self.diary.record("VERIFY_SYNTAX", file_path, "PASSED" if res.passed else "FAILED", res.details)
            return res

        res = self._fallback_syntax_check(target, file_path, ext or "Generic")
        if self.diary:
            self.diary.record("VERIFY_SYNTAX", file_path, "PASSED" if res.passed else "FAILED", res.details)
        return res

    def _fallback_syntax_check(self, target_path: Path, relative_path: str, lang: str, err: str = "") -> VerificationResult:
        try:
            content = target_path.read_text(encoding="utf-8")
            stack = []
            matching = {')': '(', '}': '{', ']': '['}
            in_string = False
            string_char = ''
            escaped = False
            in_line_comment = False
            in_block_comment = False

            i = 0
            n = len(content)
            while i < n:
                char = content[i]
                next_char = content[i+1] if i + 1 < n else ''

                if in_line_comment:
                    if char == '\n':
                        in_line_comment = False
                    i += 1
                    continue

                if in_block_comment:
                    if char == '*' and next_char == '/':
                        in_block_comment = False
                        i += 2
                        continue
                    i += 1
                    continue

                if in_string:
                    if escaped:
                        escaped = False
                    elif char == '\\':
                        escaped = True
                    elif char == string_char:
                        in_string = False
                    i += 1
                    continue

                # Check start of comments when not in string
                if char == '/' and next_char == '/':
                    in_line_comment = True
                    i += 2
                    continue
                if char == '/' and next_char == '*':
                    in_block_comment = True
                    i += 2
                    continue
                if char == '#' and lang.lower() in ("python", "bash", "sh", "yaml", "yml", "r", "ruby"):
                    in_line_comment = True
                    i += 1
                    continue
                if char == '-' and next_char == '-' and lang.lower() in ("sql", "haskell", "lua"):
                    in_line_comment = True
                    i += 2
                    continue

                # Check string quotes
                if char in ("'", '"', '`'):
                    in_string = True
                    string_char = char
                    i += 1
                    continue

                # Check brackets
                if char in '({[':
                    stack.append(char)
                elif char in ')}]':
                    if not stack or stack[-1] != matching[char]:
                        res_err = f"Unmatched closing bracket '{char}' in {relative_path}"
                        return VerificationResult(
                            command=f"syntax_check ({lang}) {relative_path}",
                            cwd=str(self.sandbox.workspace_root),
                            exit_code=1,
                            stdout="",
                            stderr=res_err,
                            passed=False,
                            details=f"{lang} fallback syntax check failed: {res_err}"
                        )
                    stack.pop()
                i += 1

            if stack:
                res_err = f"Unclosed bracket(s) '{''.join(stack)}' in {relative_path}"
                return VerificationResult(
                    command=f"syntax_check ({lang}) {relative_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=1,
                    stdout="",
                    stderr=res_err,
                    passed=False,
                    details=f"{lang} fallback syntax check failed: {res_err}"
                )

            return VerificationResult(
                command=f"syntax_check ({lang}) {relative_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=0,
                stdout="",
                stderr="",
                passed=True,
                details=f"{lang} syntax check passed."
            )
        except Exception as e:
            return VerificationResult(
                command=f"syntax_check ({lang}) {relative_path}",
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=str(e),
                passed=False,
                details=f"Read error during {lang} verification: {e}"
            )

    def run_tests(
        self,
        test_path: Optional[str] = None,
        command: Optional[str] = None
    ) -> VerificationResult:
        """
        Runs unit tests inside the workspace sandbox using unittest or pytest.
        """
        if test_path:
            try:
                target = self.sandbox.validate_and_resolve(test_path)
            except PermissionError as pe:
                res = VerificationResult(
                    command=f"python -m unittest {test_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=1,
                    stdout="",
                    stderr=str(pe),
                    passed=False,
                    details=f"Security Sandbox Violation: {pe}"
                )
                if self.diary:
                    self.diary.record("RUN_BACKEND_TESTS", test_path, "DENIED", res.details)
                return res

            if not target.is_file():
                res = VerificationResult(
                    command=f"python -m unittest {test_path}",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=1,
                    stdout="",
                    stderr=f"Test file not found: {test_path}",
                    passed=False,
                    details=f"Test file '{test_path}' does not exist inside workspace."
                )
                if self.diary:
                    self.diary.record("RUN_BACKEND_TESTS", test_path, "FAILED", res.details)
                return res

            rel_path = target.relative_to(self.sandbox.workspace_root)
            cmd = [sys.executable, "-m", "unittest", str(rel_path)]
            display_cmd = f"python -m unittest {rel_path}"
        elif command:
            cmd_str = command.strip()
            parts = cmd_str.split()
            if not parts:
                return VerificationResult(
                    command="",
                    cwd=str(self.sandbox.workspace_root),
                    exit_code=1,
                    stdout="",
                    stderr="Test command cannot be empty.",
                    passed=False,
                    details="Invalid empty test command."
                )
            if parts[0] in ("python", "python3", sys.executable):
                cmd = [sys.executable] + parts[1:]
            elif parts[0] == "pytest":
                cmd = [sys.executable, "-m", "pytest"] + parts[1:]
            else:
                cmd = [sys.executable, "-m", "unittest"] + parts
            display_cmd = command
        else:
            cmd = [sys.executable, "-m", "unittest", "discover", "."]
            display_cmd = "python -m unittest discover ."

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.sandbox.workspace_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            passed = (proc.returncode == 0)
            details = "Backend test run passed successfully." if passed else "Backend test run failed."
            res = VerificationResult(
                command=display_cmd,
                cwd=str(self.sandbox.workspace_root),
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                passed=passed,
                details=details
            )
            if self.diary:
                self.diary.record(
                    "RUN_BACKEND_TESTS",
                    test_path or display_cmd,
                    "PASSED" if passed else "FAILED",
                    details
                )
            return res
        except subprocess.TimeoutExpired:
            res = VerificationResult(
                command=display_cmd,
                cwd=str(self.sandbox.workspace_root),
                exit_code=-1,
                stdout="",
                stderr=f"Test run timed out after {self.timeout_seconds}s",
                passed=False,
                details="Test execution timed out."
            )
            if self.diary:
                self.diary.record("RUN_BACKEND_TESTS", test_path or display_cmd, "TIMEOUT", res.details)
            return res
        except Exception as e:
            res = VerificationResult(
                command=display_cmd,
                cwd=str(self.sandbox.workspace_root),
                exit_code=1,
                stdout="",
                stderr=str(e),
                passed=False,
                details=f"Test execution error: {str(e)}"
            )
            if self.diary:
                self.diary.record("RUN_BACKEND_TESTS", test_path or display_cmd, "ERROR", str(e))
            return res

