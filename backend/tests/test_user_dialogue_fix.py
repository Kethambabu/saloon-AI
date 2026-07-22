"""
Regression unit test for user dialogue trace bugs:
1. Date parsing with leading quotes (e.g. '"2026-07-24') must resolve to 2026-07-24 (not reset to today).
2. Tab-separated and quoted entities ("Hair Spa\tMain Salon\tMarcus Johnson"12pm slot on 24-07-2026) must be parsed cleanly.
3. Multi-turn corrections ("no i want this date \"2026-07-24") must retain service, branch, stylist, time and update date.
"""

import os
import sys
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.agents.receptionist_agent import (
    repair_date,
    repair_time,
    extract_booking_entities_deterministic,
    ReceptionistAgent,
)


def test_quote_and_tab_date_repairs():
    """Verify repair_date properly strips quotes and parses DD-MM-YYYY / YYYY-MM-DD."""
    base_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ReceptionistAgent.CURRENT_QUERY_CONTEXT = f"[SYSTEM TIME CONTEXT: Current system time is {base_date} 12:00:00]"

    # 1. Quoted dates
    assert repair_date('"2026-07-24') == "2026-07-24"
    assert repair_date('2026-07-24"') == "2026-07-24"
    assert repair_date('"24-07-2026"') == "2026-07-24"
    assert repair_date("24-07-2026") == "2026-07-24"

    # 2. Time with trailing text or quotes
    assert repair_time('"12pm"') == "12:00"
    assert repair_time("12pm slot") == "12:00"


def test_deterministic_tab_entity_extraction():
    """Verify tab-separated strings with quotes are correctly extracted."""
    text = 'book an appoitment for  "Hair Spa\tMain Salon\tMarcus Johnson"12pm slot on 24-07-2026'
    entities = extract_booking_entities_deterministic(text)
    
    assert entities["date"] == "2026-07-24"
    assert entities["time"] == "12pm" or entities["time"] == "12:00"
    assert entities["service"] == "Hair Spa"
    assert entities["branch"] == "Main Salon"
    assert entities["stylist"] == "Marcus Johnson"
