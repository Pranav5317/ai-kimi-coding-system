import os
import tempfile
import unittest
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.filesystem import WorkspaceSandbox
from state.project_state import ProjectStateManager


class TestArchitectureDiscovery(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name).resolve()
        self.sandbox = WorkspaceSandbox(self.workspace_root)
        self.state_manager = ProjectStateManager(sandbox=self.sandbox)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_deep_architecture_discovery_routes_and_forms(self):
        # Create mock downloaded repository files
        self.sandbox.create_file(
            "app.py",
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.post('/predict')\n"
            "def predict_pothole():\n"
            "    return {'status': 'pothole detected'}\n"
        )
        self.sandbox.create_file(
            "templates/index.html",
            "<!DOCTYPE html><html><body>\n"
            "<form action='/predict' method='post'>\n"
            "<input type='file' name='pothole_image'>\n"
            "<button type='submit'>Analyze</button>\n"
            "</form></body></html>\n"
        )

        res = self.state_manager.onboard_existing_project(force=True)
        self.assertIn("Project state successfully updated", res)

        state_content = self.state_manager.read_state()
        self.assertIn("## Architecture", state_content)
        self.assertIn("app.py -> /predict", state_content)
        self.assertIn("HTML File Upload Form", state_content)

    def test_02_architecture_discovery_ml_model_hints(self):
        self.sandbox.create_file("model_runner.py", "import cv2\nimport torch\ndef load_model(): pass\n")
        self.state_manager.onboard_existing_project(force=True)

        state_content = self.state_manager.read_state()
        self.assertIn("ML / Image Analysis Pipeline", state_content)


if __name__ == "__main__":
    unittest.main()

