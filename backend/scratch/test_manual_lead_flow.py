import requests
import sys
import os

BASE_URL = "http://localhost:8000/api/v1"

def test_flow():
    # 1. Login as customer
    login_payload = {
        "email": "customer@example.com",
        "password": "password123"
    }
    print("Logging in as customer...")
    res = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if res.status_code != 200:
        print("Login failed:", res.text)
        return
    cust_token = res.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}
    
    # 2. Login as staff
    staff_payload = {
        "email": "marcus@salonai.com",
        "password": "password123"
    }
    print("Logging in as staff...")
    res = requests.post(f"{BASE_URL}/auth/login", json=staff_payload)
    if res.status_code != 200:
        print("Staff login failed:", res.text)
        return
    staff_token = res.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Get branch & service
    print("Fetching branches...")
    res = requests.get(f"{BASE_URL}/branches", headers=cust_headers)
    branch_id = res.json()[0]["id"]
    
    print("Fetching services...")
    res = requests.get(f"{BASE_URL}/services", headers=cust_headers)
    service_id = res.json()[0]["id"]
    service_name = res.json()[0]["name"]

    print("Fetching staff...")
    res = requests.get(f"{BASE_URL}/staff", headers=cust_headers)
    staff_id = res.json()[0]["id"]

    # 3. Customer starts booking wizard -> saves draft lead
    print("\nStep 1: Saving manual booking draft...")
    draft_payload = {
        "branch_id": branch_id,
        "service_id": service_id,
        "staff_id": staff_id,
        "date": "2026-06-12",
        "time": "15:00",
        "notes": "Looking for a precision haircut."
    }
    res = requests.post(f"{BASE_URL}/leads/draft", json=draft_payload, headers=cust_headers)
    if res.status_code != 200:
        print("Draft failed:", res.text)
        return
    print("Draft response:", res.json())
    lead_id = res.json()["lead_id"]

    # 4. Check active lead for customer
    print("\nStep 2: Checking active lead for customer...")
    res = requests.get(f"{BASE_URL}/leads/active", headers=cust_headers)
    print("Active lead response status:", res.status_code)
    print("Active lead response body:", res.json())
    active_lead = res.json()

    # 5. Staff fetches assigned leads
    print("\nStep 3: Staff fetching assigned leads...")
    res = requests.get(f"{BASE_URL}/staff/leads", headers=staff_headers)
    print("Staff leads count:", len(res.json()))
    matching_leads = [l for l in res.json() if l["id"] == lead_id]
    if not matching_leads:
        print("ERROR: Lead not found in staff assigned leads list!")
        return
    print("Found lead in staff leads list, status:", matching_leads[0]["status"])

    # 6. Staff marks lead as contacted/followup
    print("\nStep 4: Staff marking lead as contacted...")
    followup_payload = {"lead_id": lead_id}
    res = requests.post(f"{BASE_URL}/leads/followup", json=followup_payload, headers=staff_headers)
    print("Followup response:", res.json())

    # 7. Check customer notifications
    print("\nStep 5: Fetching customer notifications...")
    res = requests.get(f"{BASE_URL}/notifications", headers=cust_headers)
    print("Notifications response:", res.json())

    # 8. Check customer active lead again (should be CONTACTED)
    print("\nStep 6: Checking active lead for customer again...")
    res = requests.get(f"{BASE_URL}/leads/active", headers=cust_headers)
    print("Active lead status:", res.json()["status"])

    # 9. Book appointment to convert lead
    print("\nStep 7: Customer books appointment to finalize...")
    booking_payload = {
        "branch_id": branch_id,
        "service_id": service_id,
        "start_time": "2026-06-12T15:00:00Z",
        "staff_id": staff_id,
        "notes": "Resuming from lead."
    }
    res = requests.post(f"{BASE_URL}/appointments", json=booking_payload, headers=cust_headers)
    print("Booking response:", res.json())

    # 10. Verify active lead is now null/converted
    print("\nStep 8: Checking active lead for customer after booking...")
    res = requests.get(f"{BASE_URL}/leads/active", headers=cust_headers)
    print("Active lead after booking:", res.json())

if __name__ == "__main__":
    test_flow()
