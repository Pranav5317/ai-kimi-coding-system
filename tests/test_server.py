import os
import unittest
import tempfile
import asyncio
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server
from server import (
    SystemCore,
    get_health,
    list_agents,
    get_project_state,
    list_workspace_files,
    get_diary_entries,
    chat_endpoint
)
from llm.base import BaseLLMProvider


class DummyLLM(BaseLLMProvider):
    def chat(self, messages, tools=None):
        return {"role": "assistant", "content": "Dummy response", "tool_calls": None}

    def chat_stream(self, messages, **kwargs):
        yield "Dummy response"

    def health_check(self):
        return True, "Dummy LLM ready."


class TestServerAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.workspace_root = Path(cls.temp_dir.name).resolve()
        
        server.core = SystemCore(workspace_path=str(cls.workspace_root))
        server.core.llm = DummyLLM()
        server.core.agent1.llm_provider = server.core.llm
        server.core.agent2.llm_provider = server.core.llm
        server.core.agent3.llm_provider = server.core.llm
        server.core.agent4.llm_provider = server.core.llm
        server.core.agent5.llm_provider = server.core.llm

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_01_health_endpoint(self):
        data = get_health()
        self.assertEqual(data["status"], "online")
        self.assertIn("model", data)
        self.assertIn("workspace_dir", data)

    def test_02_agents_endpoint(self):
        data = list_agents()
        self.assertIn("agents", data)
        self.assertEqual(len(data["agents"]), 5)

        agent_ids = [a["agent_id"] for a in data["agents"]]
        self.assertIn("agent1", agent_ids)
        self.assertIn("agent2", agent_ids)
        self.assertIn("agent3", agent_ids)
        self.assertIn("agent4", agent_ids)
        self.assertIn("agent5", agent_ids)

    def test_03_state_endpoint(self):
        data = get_project_state()
        self.assertIn("content", data)
        self.assertIn("Project State", data["content"])

    def test_04_files_endpoint(self):
        data = list_workspace_files()
        self.assertIn("files", data)

    def test_05_diary_endpoint(self):
        data = get_diary_entries()
        self.assertIn("entries", data)

    def test_06_chat_endpoint(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(chat_endpoint({"prompt": "Hello"}))
        loop.close()
        self.assertIn("response", res)
        self.assertIn("project_state", res)


if __name__ == "__main__":
    unittest.main()
