import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from agents.receptionist_agent import ReceptionistAgent, reschedule_existing_appointment

# Set query context
base_date = "2026-06-05"
ReceptionistAgent.CURRENT_QUERY_CONTEXT = (
    f"[SYSTEM TIME CONTEXT: Current system time is {base_date} 17:13:00 (Today is Friday, June 05, 2026).]\n"
    f"[SYSTEM CUSTOMER CONTEXT: ID: 92266855-7763-408d-a1e5-1bba8c2a83d5, Email: customer@example.com]\n"
    f"Latest User Message: reschedule to 12pm"
)

# Alice's appointment ID
appt_id = "9c451529-79b7-407e-95f1-583587d4bb70" # This is completed, but we can see if the parsing works

# We can call the tool directly
print("Calling reschedule_existing_appointment with 2026-06-05T12:00:00Z...")
res = reschedule_existing_appointment(appt_id, "2026-06-05T12:00:00Z")
print("Result:", res)
