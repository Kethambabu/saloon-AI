import os
import sys
from datetime import datetime

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agents.receptionist_agent import repair_date, ReceptionistAgent

def test_date_parsing():
    print("Running date parsing unit tests...")
    
    # Mock system context time (June 6, 2026)
    ReceptionistAgent.CURRENT_QUERY_CONTEXT = "[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]"
    
    test_cases = [
        # Relative dates
        ("today", "2026-06-06"),
        ("tomorrow", "2026-06-07"),
        ("day after tomorrow", "2026-06-08"),
        
        # Absolute dates
        ("june 8th 2026", "2026-06-08"),
        ("June 8, 2026", "2026-06-08"),
        ("08-06-2026", "2026-06-08"),
        ("08-06- 2026", "2026-06-08"),
        ("2026-06-08", "2026-06-08"),
        ("8-6-2026", "2026-06-08"),
        
        # Fallbacks
        ("", "2026-06-06"),
        (None, "2026-06-06")
    ]
    
    all_passed = True
    for input_val, expected in test_cases:
        res = repair_date(input_val)
        status = "PASSED" if res == expected else "FAILED"
        print(f"Input: {str(input_val):25} -> Result: {res:12} (Expected: {expected:12}) [{status}]")
        if res != expected:
            all_passed = False
            
    assert all_passed, "Some date parsing test cases failed!"
    print("SUCCESS: All date parsing tests passed successfully!")

if __name__ == "__main__":
    test_date_parsing()
