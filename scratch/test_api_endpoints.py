import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_endpoints():
    print("=== Testing FastAPI Live Server API Endpoints ===")
    
    # 1. Health check
    res = requests.get(f"{BASE_URL}/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print(f"[PASS] /api/health -> Status: {health_data.get('status')}, Model: {health_data.get('model')}")

    # 2. List Agents
    res = requests.get(f"{BASE_URL}/api/agents")
    assert res.status_code == 200, f"Agents list failed: {res.text}"
    agents_data = res.json()
    print(f"[PASS] /api/agents -> Registered Agents: {len(agents_data.get('agents', []))}")

    # 3. List Skills
    res = requests.get(f"{BASE_URL}/api/skills")
    assert res.status_code == 200, f"Skills list failed: {res.text}"
    skills_data = res.json()
    skills_list = [s['name'] for s in skills_data.get('skills', [])]
    print(f"[PASS] /api/skills -> Active Skills: {skills_list}")

    # 4. Read Project State
    res = requests.get(f"{BASE_URL}/api/state")
    assert res.status_code == 200, f"State read failed: {res.text}"
    print(f"[PASS] /api/state -> Project State readable ({len(res.json().get('content', ''))} bytes)")

    # 5. List Files
    res = requests.get(f"{BASE_URL}/api/files")
    assert res.status_code == 200, f"Files list failed: {res.text}"
    print(f"[PASS] /api/files -> Workspace file tree fetched")

    # 6. Read Diary Entries
    res = requests.get(f"{BASE_URL}/api/diary")
    assert res.status_code == 200, f"Diary read failed: {res.text}"
    print(f"[PASS] /api/diary -> Audit diary entries fetched ({len(res.json().get('entries', []))} entries)")

    print("\nALL REST API ENDPOINTS ARE FULLY OPERATIONAL AND HEALTHY!")

if __name__ == "__main__":
    test_endpoints()
