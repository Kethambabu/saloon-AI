import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from agents.receptionist_agent import (
    ReceptionistAgent,
    repair_date,
    repair_time,
    adjust_past_date_today,
    get_query_system_datetime,
    get_query_base_date
)

# Set query context
base_date = "2026-06-05"
ReceptionistAgent.CURRENT_QUERY_CONTEXT = (
    f"[SYSTEM TIME CONTEXT: Current system time is {base_date} 17:13:00 (Today is Friday, June 05, 2026).]\n"
    f"[SYSTEM CUSTOMER CONTEXT: ID: 92266855-7763-408d-a1e5-1bba8c2a83d5, Email: customer@example.com]\n"
    f"Latest User Message: reschedule to 12pm"
)

print("get_query_base_date():", get_query_base_date())
print("get_query_system_datetime():", get_query_system_datetime())

new_start_time = "2026-06-05T12:00:00Z"
dt_str = str(new_start_time).strip()

parts = dt_str.split("T")
print("parts:", parts)
rep_d = repair_date(parts[0])
print("rep_d after repair_date:", rep_d)
rep_t = repair_time(parts[1])
print("rep_t after repair_time:", rep_t)
rep_d_adjusted = adjust_past_date_today(rep_d, rep_t)
print("rep_d after adjust_past_date_today:", rep_d_adjusted)
repaired_time_str = f"{rep_d_adjusted}T{rep_t}:00"
if not repaired_time_str.endswith("Z") and not "+" in repaired_time_str:
    repaired_time_str += "Z"
print("Final repaired_time_str:", repaired_time_str)
