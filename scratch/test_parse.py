import re
from datetime import datetime, timedelta

def get_query_system_datetime(context) -> datetime:
    if "[SYSTEM TIME CONTEXT:" in context:
        try:
            parts = context.split("Current system time is ")
            if len(parts) > 1:
                tokens = parts[1].split()
                if len(tokens) > 1:
                    dt_str = f"{tokens[0]} {tokens[1].split('(')[0].split(')')[0]}"
                    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print("ERROR parsing system datetime:", e)
    return None

def adjust_past_date_today(date_str: str, time_str: str, sys_dt) -> str:
    if sys_dt:
        try:
            t_parts = time_str.split(":")
            hour = int(t_parts[0])
            minute = int(t_parts[1]) if len(t_parts) > 1 else 0
            
            target_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hour, minute=minute)
            if target_dt < sys_dt:
                today_str = sys_dt.strftime("%Y-%m-%d")
                if date_str == today_str:
                    tomorrow = sys_dt + timedelta(days=1)
                    return tomorrow.strftime("%Y-%m-%d")
        except Exception as e:
            print("ERROR adjusting date:", e)
    return date_str

# Test input
context = "[SYSTEM TIME CONTEXT: Current system time is 2026-06-05 17:13:00 (Today is Friday, June 05, 2026). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]\nLatest User Message: reschedule to 12pm"

sys_dt = get_query_system_datetime(context)
print("Parsed sys_dt:", sys_dt)

# Let's test the flow
date_str = "2026-06-05"
time_str = "12:00"
adjusted_date = adjust_past_date_today(date_str, time_str, sys_dt)
print("Adjusted date:", adjusted_date)
