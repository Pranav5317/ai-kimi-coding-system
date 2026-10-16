#!/usr/bin/env python3
import requests
import time

def test_backend():
    """Test if backend server is responding"""
    try:
        response = requests.get('http://localhost:8000/docs', timeout=5)
        print(f"Backend status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Backend error: {e}")
        return False

def test_frontend():
    """Test if frontend server is responding"""
    try:
        response = requests.get('http://localhost:8080/', timeout=5)
        print(f"Frontend status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Frontend error: {e}")
        return False

if __name__ == "__main__":
    print("Testing servers...")
    backend_ok = test_backend()
    frontend_ok = test_frontend()
    
    if backend_ok and frontend_ok:
        print("Both servers are working correctly!")
    elif backend_ok:
        print("Backend is working, but frontend might have issues.")
    else:
        print("Backend is not responding.")