import urllib.request
import json
import sys

# 1. Login to get token
login_url = "http://127.0.0.1:8000/api/v1/auth/login"
login_data = json.dumps({
    "email": "customer@example.com",
    "password": "password123"
}).encode('utf-8')

req = urllib.request.Request(
    login_url,
    data=login_data,
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode('utf-8'))
        token = res["access_token"]
        print("Login successful, token acquired.")
except Exception as e:
    print("Login failed:", e)
    sys.exit(1)

# 2. Call agent chat
chat_url = "http://127.0.0.1:8000/api/v1/agent/chat"
chat_data = json.dumps({
    "message": "reschedule to 12pm",
    "session id": "test-session-123",
    "chat history": []
}).encode('utf-8')

chat_req = urllib.request.Request(
    chat_url,
    data=chat_data,
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
)

try:
    with urllib.request.urlopen(chat_req) as response:
        res = json.loads(response.read().decode('utf-8'))
        print("\n--- Agent Response ---")
        print(json.dumps(res, indent=2))
except Exception as e:
    print("Chat request failed:", e)
