import os
import sys
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from fastapi.testclient import TestClient
from backend.app import app
from backend.database import engine, Base
from backend.models.user import User
from backend.auth.security import get_password_hash

# Create test database tables
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_register_user():
    response = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "User registered successfully"

def test_login():
    response = client.post("/auth/login", data={
        "username": "testuser",
        "password": "testpassword"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

if __name__ == "__main__":
    test_register_user()
    test_login()
    print("All tests passed!")