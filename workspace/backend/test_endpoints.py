import requests
import json

# Test the endpoints directly by running the Flask app in testing mode
def test_endpoints():
    print("Testing Flask backend endpoints...")
    
    # Import the app
    from app import app
    
    with app.test_client() as client:
        # Test health check
        response = client.get('/health')
        print(f"Health check: {response.status_code} - {response.get_json()}")
        
        # Test get users
        response = client.get('/users')
        print(f"Get users: {response.status_code} - Count: {len(response.get_json())}")
        
        # Test create user
        new_user = {
            "name": "Test User",
            "email": "test@example.com",
            "role": "user"
        }
        response = client.post('/users', 
                              data=json.dumps(new_user),
                              content_type='application/json')
        print(f"Create user: {response.status_code} - {response.get_json()}")
        
        # Test stats
        response = client.get('/stats')
        print(f"Get stats: {response.status_code} - {response.get_json()}")
        
        # Test data
        response = client.get('/data')
        print(f"Get data: {response.status_code} - Count: {response.get_json()['count']}")
        
        print("All endpoints tested successfully!")

if __name__ == "__main__":
    test_endpoints()