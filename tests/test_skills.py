import unittest
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.base import BaseLLMProvider
from skills.skill_manager import SkillManager, Skill
from agents.workspace_agent import WorkspaceAgent
from tools.filesystem import WorkspaceSandbox
from state import ProjectStateManager


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, fixed_response: str = "Test response") -> None:
        self.fixed_response = fixed_response
        self.tool_calls_sequence: List[Optional[List[Dict[str, Any]]]] = []

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if self.tool_calls_sequence:
            next_calls = self.tool_calls_sequence.pop(0)
            if next_calls:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": next_calls
                }
        return {
            "role": "assistant",
            "content": self.fixed_response,
            "tool_calls": None
        }

    def chat_stream(self, messages: List[Dict[str, Any]], **kwargs: Any):
        yield self.fixed_response

    def health_check(self) -> Tuple[bool, str]:
        return True, "Mock LLM ready"


class TestSkillsArchitecture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.temp_dir)
        self.sandbox = WorkspaceSandbox(workspace_root=self.workspace_root)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)
        self.llm = MockLLMProvider(fixed_response="Skill executed.")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_builtin_skills_discovered(self) -> None:
        mgr = SkillManager()
        skills = mgr.list_skills()
        names = [s["name"] for s in skills]

        self.assertIn("fastapi-backend", names)
        self.assertIn("react-frontend", names)
        self.assertIn("database-migration", names)
        self.assertIn("unit-testing", names)

    def test_02_workspace_custom_skill_discovered(self) -> None:
        ws_skills = self.workspace_root / "skills" / "my_custom_skill"
        ws_skills.mkdir(parents=True, exist_ok=True)
        skill_file = ws_skills / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: my-custom-skill\n"
            "description: Custom workspace testing skill.\n"
            "target_agent: agent1\n"
            "---\n\n"
            "# Custom Instructions\n"
            "Follow custom workflow.",
            encoding="utf-8"
        )

        mgr = SkillManager(workspace_root=self.workspace_root)
        skill = mgr.get_skill("my-custom-skill")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.target_agent, "agent1")
        self.assertIn("Follow custom workflow", skill.instructions)

    def test_03_apply_skill_formatting(self) -> None:
        mgr = SkillManager()
        res = mgr.apply_skill("fastapi-backend")
        self.assertIn("APPLIED SKILL: FASTAPI-BACKEND", res)
        self.assertIn("Specialized Instructions & Guidance", res)

    def test_04_workspace_agent_skill_tools(self) -> None:
        agent = WorkspaceAgent(
            llm_provider=self.llm,
            sandbox=self.sandbox,
            state_manager=self.state_manager
        )

        # Execute list_available_skills
        raw_list = agent._execute_tool("list_available_skills", {})
        skills_data = json.loads(raw_list)
        names = [s["name"] for s in skills_data]
        self.assertIn("fastapi-backend", names)

        # Execute apply_skill
        applied = agent._execute_tool("apply_skill", {"skill_name": "unit-testing"})
        self.assertIn("APPLIED SKILL: UNIT-TESTING", applied)

    def test_05_auto_match_skills(self) -> None:
        mgr = SkillManager()
        # Test FastAPI backend prompt matching
        matched_fastapi = mgr.auto_match_skills("Create a FastAPI backend for user management")
        self.assertTrue(any(s.name == "fastapi-backend" for s in matched_fastapi))

        # Test React frontend prompt matching
        matched_react = mgr.auto_match_skills("Build a React frontend UI dashboard")
        self.assertTrue(any(s.name == "react-frontend" for s in matched_react))

        # Test Unit testing prompt matching
        matched_tests = mgr.auto_match_skills("Write pytest unit tests for backend routes")
        self.assertTrue(any(s.name == "unit-testing" for s in matched_tests))

    def test_06_workspace_agent_auto_activates_skill(self) -> None:
        tool_calls_fired = []
        def on_tool(name: str, args: dict, result: str):
            tool_calls_fired.append((name, args))

        agent = WorkspaceAgent(
            llm_provider=self.llm,
            sandbox=self.sandbox,
            state_manager=self.state_manager
        )

        res = agent.process_request("I need a FastAPI backend API endpoint", on_tool_call=on_tool)
        # Verify apply_skill tool execution was auto-triggered and emitted to on_tool_call listener
        auto_skills = [args.get("skill_name") for name, args in tool_calls_fired if name == "apply_skill"]
        self.assertIn("fastapi-backend", auto_skills)


if __name__ == "__main__":
    unittest.main()

