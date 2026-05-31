import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_clara():
    # 1. Login as customer
    login_payload = {
        "email": "customer@example.com",
        "password": "password123"
    }
    print("Logging in as customer@example.com...")
    response = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if response.status_code != 200:
        print(f"[ERROR] Login failed! Status: {response.status_code}, Body: {response.text}")
        return
    
    login_data = response.json()
    token = login_data.get("access_token")
    print(f"[OK] Login successful! Token obtained: {token[:15]}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Session ID for Clara
    session_id = f"test_sess_{int(time.time())}"
    
    chat_history = []
    
    # Queries to send to Clara
    queries = [
        # Discovery Query 1: Branches
        "Hello! What branches do you have and where are they located?",
        
        # Discovery Query 2: Services
        "Could you list the services you offer and how much they cost?",
        
        # Discovery Query 3: Staff/Stylist
        "Who is available at Downtown Elite branch?",
        
        # Booking Query 4: Checking history
        "Can you check my booking history first?",
        
        # Booking Query 5: Relative conversational booking
        "Perfect. I'd like to book an appointment for tomorrow at 5pm. Just use Marcus if available, and any haircut service.",
        
        # Booking Query 6: Vague relative conversational booking
        "Also check if there is a stone massage slot available tomorrow afternoon."
    ]
    
    for q in queries:
        print("\n" + "="*80)
        print(f"USER: {q}")
        print("="*80)
        
        payload = {
            "message": q,
            "session id": session_id,
            "chat history": chat_history
        }
        
        start_time = time.time()
        res = requests.post(f"{BASE_URL}/agent/chat", json=payload, headers=headers)
        duration = time.time() - start_time
        
        if res.status_code != 200:
            print(f"[ERROR] API Error: {res.status_code}, Response: {res.text}")
            continue
            
        data = res.json()
        clara_response = data.get("response", "")
        print(f"CLARA (duration: {duration:.2f}s):")
        # Ensure it prints cleanly even if there are special characters
        print(clara_response.encode('ascii', errors='replace').decode('ascii'))
        
        # Update chat history for the next turns
        chat_history.append({"role": "user", "content": q})
        chat_history.append({"role": "assistant", "content": clara_response})
        
        # Wait a moment between calls
        time.sleep(1)

if __name__ == "__main__":
    test_clara()
