#!/usr/bin/env python3
"""
Test script to verify the repair_time function fix.
Tests various time input formats to ensure they parse correctly.
"""

import re

def repair_time(time_input) -> str:
    """Convert relative time slots (e.g. 5pm, 3-4pm, 3-4pm slot) to standard HH:MM format (start time)."""
    if not time_input:
        return "17:00"
        
    time_str = str(time_input).strip()
    
    # Already in HH:MM format
    if re.match(r"^\d{2}:\d{2}$", time_str):
        return time_str
    if re.match(r"^\d{2}:\d{2}:\d{2}$", time_str):
        return time_str[:5]
        
    time_clean = time_str.lower().replace(" ", "")
    is_pm = "pm" in time_clean
    is_am = "am" in time_clean
    
    # Handle time ranges like "3-4pm", "3-4", "03-04pm", etc.
    # Extract ONLY the first number for the start time
    time_no_text = re.sub(r"[^0-9:\-]", "", time_clean)
    
    # Split by dash/hyphen to get the start time (first part)
    if "-" in time_no_text:
        start_part = time_no_text.split("-")[0]
    else:
        start_part = time_no_text
    
    # Extract digits from the start part
    digits = "".join([c for c in start_part if c.isdigit() or c == ":"])
    
    if ":" in digits:
        parts = digits.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            hour, minute = 12, 0
    else:
        try:
            hour = int(digits) if digits else 12
            minute = 0
        except ValueError:
            hour, minute = 12, 0
    
    # Handle AM/PM
    if is_pm and hour < 12:
        hour += 12
    elif is_am and hour == 12:
        hour = 0
        
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return f"{hour:02d}:{minute:02d}"


# Test cases from the bug report
test_cases = [
    # User said "3-4PM", expected start time 15:00 (3 PM)
    ("3-4PM", "15:00"),
    ("3-4pm", "15:00"),
    ("3-4 pm", "15:00"),
    
    # User said "5-6PM", expected start time 17:00 (5 PM)
    ("5-6PM", "17:00"),
    ("5-6pm", "17:00"),
    ("5-6 pm", "17:00"),
    
    # User said "3 PM", expected 15:00
    ("3pm", "15:00"),
    ("3 PM", "15:00"),
    ("3 pm", "15:00"),
    
    # User said "5 PM", expected 17:00
    ("5pm", "17:00"),
    ("5 PM", "17:00"),
    ("5 pm", "17:00"),
    
    # Standard HH:MM format
    ("15:00", "15:00"),
    ("17:00", "17:00"),
    ("03:00", "03:00"),
    
    # Edge cases
    ("12pm", "12:00"),  # 12 PM = noon
    ("12am", "00:00"),  # 12 AM = midnight
    ("1am", "01:00"),
    ("11pm", "23:00"),
    
    # Empty/None
    (None, "17:00"),  # Default
    ("", "17:00"),    # Default
    
    # Slot formats
    ("3-4pm slot", "15:00"),
    ("5-6pm slot", "17:00"),
]

print("Testing repair_time function fix...")
print("=" * 60)

passed = 0
failed = 0

for input_val, expected in test_cases:
    result = repair_time(input_val)
    status = "✓ PASS" if result == expected else "✗ FAIL"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
        
    print(f"{status}: repair_time({repr(input_val):20}) -> {result:5} (expected {expected})")

print("=" * 60)
print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")

if failed == 0:
    print("✓ All tests passed! The fix is working correctly.")
else:
    print(f"✗ {failed} test(s) failed. Review the fix.")
