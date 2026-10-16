import unittest
from fastapi.testclient import TestClient
import sys
import os

# Add the backend directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

class FastAPITestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')

    def test_get_agents(self):
        response = self.client.get('/agents')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_get_agent(self):
        response = self.client.get('/agents/agent1')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['agent_id'], 'agent1')
        self.assertEqual(data['role'], 'Frontend Developer')

    def test_get_project_state(self):
        response = self.client.get('/projects')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('project_name', data)
        self.assertIn('description', data)
        self.assertIn('created_at', data)

    def test_get_server_status(self):
        response = self.client.get('/server/status')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('is_running', data)
        self.assertIn('port', data)
        self.assertIn('server_type', data)

    def test_get_tasks(self):
        response = self.client.get('/tasks')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('tasks', data)
        self.assertIsInstance(data['tasks'], list)

if __name__ == '__main__':
    unittest.main()