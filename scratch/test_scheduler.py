import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from db.database import SessionLocal
from services.lead_service import process_leads
from db import Lead, LeadStatus, Notification, ChatLog

db = SessionLocal()
try:
    print("=== BEFORE RUN ===")
    leads = db.query(Lead).all()
    print(f"Total Leads: {len(leads)}")
    for l in leads:
        print(f"Lead ID: {l.id}, Name: {l.customer_name}, Status: {l.status}, Source: {l.source}, Created At: {l.created_at}")

    notifs = db.query(Notification).all()
    print(f"Total Notifications: {len(notifs)}")
    for n in notifs:
        print(f"Notification ID: {n.id}, User ID: {n.user_id}, Title: {n.title}, Message: {n.message[:40]}, Is Read: {n.is_read}, Is Cleared: {n.is_cleared}")

    chat_logs = db.query(ChatLog).all()
    print(f"Total Chat Logs: {len(chat_logs)}")

    print("\nRunning process_leads()...")
    process_leads()

    print("\n=== AFTER RUN ===")
    leads_after = db.query(Lead).all()
    print(f"Total Leads: {len(leads_after)}")
    for l in leads_after:
        print(f"Lead ID: {l.id}, Name: {l.customer_name}, Status: {l.status}, Source: {l.source}, Created At: {l.created_at}")

    notifs_after = db.query(Notification).all()
    print(f"Total Notifications: {len(notifs_after)}")
    for n in notifs_after:
        print(f"Notification ID: {n.id}, User ID: {n.user_id}, Title: {n.title}, Message: {n.message[:40]}, Is Read: {n.is_read}, Is Cleared: {n.is_cleared}")

finally:
    db.close()
