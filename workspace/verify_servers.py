#!/usr/bin/env python3
import urllib.request
import urllib.error
import time

def test_url(url, timeout=5):
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
        return True, response.getcode()
    except urllib.error.HTTPError as e:
        return True, e.code
    except Exception as e:
        return False, str(e)

def main():
    print("Testing servers...")
    
    # Test backend API
    backend_ok, backend_code = test_url('http://localhost:8000/docs')
    print(f"Backend API (http://localhost:8000/docs): {'OK' if backend_ok else 'FAILED'} - {backend_code if backend_ok else backend_code}")
    
    # Test frontend
    frontend_ok, frontend_code = test_url('http://localhost:8080/')
    print(f"Frontend (http://localhost:8080/): {'OK' if frontend_ok else 'FAILED'} - {frontend_code if frontend_ok else frontend_code}")

if __name__ == "__main__":
    main()