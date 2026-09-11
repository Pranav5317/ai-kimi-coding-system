import unittest
import json
import sys
import os

# Add the backend directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

class FlaskTestCase(unittest.TestCase):
    def setUp(self):
        # Set up the test client
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_health_check(self):
        response = self.app.get('/health')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'healthy')

    def test_get_users(self):
        response = self.app.get('/users')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(data, list)

    def test_create_user(self):
        new_user = {
            "name": "Test User",
            "email": "test@example.com",
            "role": "user"
        }
        response = self.app.post('/users', 
                                data=json.dumps(new_user),
                                content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(data['name'], 'Test User')

    def test_get_stats(self):
        response = self.app.get('/stats')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('user_count', data)
        self.assertIn('order_count', data)
        self.assertIn('revenue', data)

    def test_get_data(self):
        response = self.app.get('/data')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', data)
        self.assertIn('count', data)

if __name__ == '__main__':
    unittest.main()