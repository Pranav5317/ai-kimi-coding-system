import os
import tempfile
import unittest
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import AppConfig
from tools.filesystem import WorkspaceSandbox
from tools.verifier import BackendVerifier, VerificationResult
from agents.backend_agent import BackendAgent
from llm.base import BaseLLMProvider


class DummyLLM(BaseLLMProvider):
    def chat(self, messages, tools=None):
        return {"role": "assistant", "content": "Dummy response", "tool_calls": None}

    def chat_stream(self, messages, **kwargs):
        yield "Dummy response"

    def health_check(self):
        return True, "Dummy LLM ready."


class TestMultiStackAndDynamicWorkspace(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name).resolve()
        self.sandbox = WorkspaceSandbox(self.workspace_root)
        self.verifier = BackendVerifier(sandbox=self.sandbox)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_set_workspace_dynamic_path(self):
        cfg = AppConfig()
        new_dir = self.workspace_root / "custom_ws"
        cfg.set_workspace(new_dir)
        self.assertEqual(cfg.workspace_dir, new_dir.resolve())
        self.assertTrue(new_dir.exists())

    def test_02_verify_python_syntax(self):
        # Valid Python
        py_path = "app.py"
        self.sandbox.create_file(py_path, "def hello():\n    return 'world'\n")
        res = self.verifier.verify_code_syntax(py_path)
        self.assertTrue(res.passed)

        # Invalid Python
        bad_py = "bad.py"
        self.sandbox.create_file(bad_py, "def hello(:\n    return 'world'\n")
        res_bad = self.verifier.verify_code_syntax(bad_py)
        self.assertFalse(res_bad.passed)

    def test_03_verify_json_syntax(self):
        # Valid JSON
        json_path = "config.json"
        self.sandbox.create_file(json_path, '{"name": "test", "version": 1}')
        res = self.verifier.verify_code_syntax(json_path)
        self.assertTrue(res.passed)

        # Invalid JSON
        bad_json = "bad.json"
        self.sandbox.create_file(bad_json, '{"name": "test", "version": }')
        res_bad = self.verifier.verify_code_syntax(bad_json)
        self.assertFalse(res_bad.passed)

    def test_04_verify_js_syntax(self):
        # Valid JS
        js_path = "index.js"
        self.sandbox.create_file(js_path, "function greet() { return 'hello'; }")
        res = self.verifier.verify_code_syntax(js_path)
        self.assertTrue(res.passed)

        # Invalid JS (unmatched brace)
        bad_js = "bad.js"
        self.sandbox.create_file(bad_js, "function greet() { return 'hello';")
        res_bad = self.verifier.verify_code_syntax(bad_js)
        self.assertFalse(res_bad.passed)

    def test_05_verify_html_syntax(self):
        # Valid HTML
        html_path = "index.html"
        self.sandbox.create_file(html_path, "<!DOCTYPE html><html><head></head><body><h1>Hello</h1></body></html>")
        res = self.verifier.verify_code_syntax(html_path)
        self.assertTrue(res.passed)

    def test_06_verify_css_syntax(self):
        # Valid CSS
        css_path = "styles.css"
        self.sandbox.create_file(css_path, "body { color: red; font-size: 14px; }")
        res = self.verifier.verify_code_syntax(css_path)
        self.assertTrue(res.passed)

        # Invalid CSS (unclosed brace)
        bad_css = "bad.css"
        self.sandbox.create_file(bad_css, "body { color: red; font-size: 14px;")
        res_bad = self.verifier.verify_code_syntax(bad_css)
        self.assertFalse(res_bad.passed)

    def test_07_verify_cpp_syntax(self):
        # Valid C++ syntax check (or fallback)
        cpp_path = "main.cpp"
        self.sandbox.create_file(cpp_path, "#include <iostream>\nint main() { std::cout << \"Hello\"; return 0; }")
        res = self.verifier.verify_code_syntax(cpp_path)
        self.assertTrue(res.passed)

        # Invalid C++ syntax (unclosed brace)
        bad_cpp = "bad.cpp"
        self.sandbox.create_file(bad_cpp, "int main() { return 0;")
        res_bad = self.verifier.verify_code_syntax(bad_cpp)
        self.assertFalse(res_bad.passed)

    def test_08_verify_java_syntax(self):
        # Valid Java syntax check (or fallback)
        java_path = "Main.java"
        self.sandbox.create_file(java_path, "public class Main { public static void main(String[] args) {} }")
        res = self.verifier.verify_code_syntax(java_path)
        self.assertTrue(res.passed)

        # Invalid Java (unclosed brace)
        bad_java = "BadMain.java"
        self.sandbox.create_file(bad_java, "public class BadMain { public static void main(String[] args) {")
        res_bad = self.verifier.verify_code_syntax(bad_java)
        self.assertFalse(res_bad.passed)

    def test_09_backend_agent_tool_dispatcher_code_syntax(self):
        agent = BackendAgent(
            llm_provider=DummyLLM(),
            sandbox=self.sandbox,
            verifier=self.verifier
        )
        self.assertIn("verify_code_syntax", agent.tool_dispatcher)
        
        # Test executing tool via dispatcher
        self.sandbox.create_file("test.js", "console.log('hello');")
        tool_out = agent._execute_tool("verify_code_syntax", {"file_path": "test.js"})
        self.assertIn("PASSED", tool_out)

    def test_10_verify_comments_with_brackets(self):
        # Code containing brackets inside comments should pass
        c_code = "/* comment ( unmatched bracket */\nint main() { return 0; // line comment ( unmatched\n}"
        self.sandbox.create_file("comment_test.cpp", c_code)
        res = self.verifier.verify_code_syntax("comment_test.cpp")
        self.assertTrue(res.passed)


if __name__ == "__main__":
    unittest.main()
