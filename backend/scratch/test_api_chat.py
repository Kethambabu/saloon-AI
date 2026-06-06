import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_api():
    # 1. Login as Admin
    login_payload = {
        "email": "owner@salonai.com",
        "password": "password123"
    }
    print("Logging in...")
    r = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} - {r.text}")
        return
        
    token = r.json().get("access_token")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Send message to BI assistant
    chat_payload = {
        "message": "hi",
        "session id": "test-bi-api-session",
        "chat history": [],
        "intent override": "business_intelligence"
    }
    print("Sending request to /agent/chat...")
    r = requests.post(f"{BASE_URL}/agent/chat", json=chat_payload, headers=headers)
    print(f"Status Code: {r.status_code}")
    try:
        print("Response JSON:")
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Raw response: {r.text}")

if __name__ == "__main__":
    test_api()
