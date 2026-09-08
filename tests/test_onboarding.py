import os
import tempfile
import unittest
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.filesystem import WorkspaceSandbox
from state.project_state import ProjectStateManager


class TestExistingCodebaseOnboarding(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name).resolve()
        self.sandbox = WorkspaceSandbox(self.workspace_root)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_search_codebase(self):
        # Create test files
        self.sandbox.create_file("src/app.py", "def calculate_total(items):\n    return sum(items)\n")
        self.sandbox.create_file("src/utils.js", "function calculate_total(items) { return items.reduce((a,b)=>a+b,0); }")
        self.sandbox.create_file("README.md", "# Test Project\nThis is a calculate_total test.\n")

        # Search without extension filter
        res_all = self.sandbox.search_codebase("calculate_total")
        self.assertIn("src/app.py:1:", res_all)
        self.assertIn("src/utils.js:1:", res_all)
        self.assertIn("README.md:2:", res_all)

        # Search with extension filter
        res_py = self.sandbox.search_codebase("calculate_total", extension="py")
        self.assertIn("src/app.py", res_py)
        self.assertNotIn("src/utils.js", res_py)

    def test_02_inspect_project_structure(self):
        self.sandbox.create_file("requirements.txt", "fastapi>=0.100.0\nuvicorn\n")
        self.sandbox.create_file("main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        self.sandbox.create_file("backend/routes.py", "# Routes\n")

        tree_res = self.sandbox.inspect_project_structure(max_depth=3)
        self.assertIn("requirements.txt [MANIFEST]", tree_res)
        self.assertIn("main.py [ENTRY_POINT]", tree_res)
        self.assertIn("Manifests Found   : requirements.txt", tree_res)
        self.assertIn("Entry Points Found: main.py", tree_res)

    def test_03_onboard_existing_python_project(self):
        # Setup existing project codebase
        self.sandbox.create_file("requirements.txt", "fastapi>=0.100.0\nsqlalchemy\nsqlite3\n")
        self.sandbox.create_file("main.py", "from fastapi import FastAPI\n")
        self.sandbox.create_file("database.py", "import sqlite3\n")

        res = self.state_manager.onboard_existing_project(force=True)
        self.assertIn("Project state successfully updated", res)

        state_content = self.state_manager.read_state()
        self.assertIn("Pre-existing project detected", state_content)
        self.assertIn("requirements.txt", state_content)
        self.assertIn("fastapi", state_content)
        self.assertIn("sqlite", state_content)

    def test_04_onboard_existing_node_project(self):
        # Setup existing Node/React project codebase
        self.sandbox.create_file("package.json", '{"dependencies": {"express": "^4.18.0", "react": "^18.0.0"}}')
        self.sandbox.create_file("index.js", "const express = require('express');")

        res = self.state_manager.onboard_existing_project(force=True)
        self.assertIn("Project state successfully updated", res)

        state_content = self.state_manager.read_state()
        self.assertIn("Pre-existing project detected", state_content)
        self.assertIn("package.json", state_content)
        self.assertIn("express", state_content)
        self.assertIn("react", state_content)


if __name__ == "__main__":
    unittest.main()
