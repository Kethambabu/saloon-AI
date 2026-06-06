import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from db.database import SessionLocal
from db import ChatLog

db = SessionLocal()
try:
    now_utc = datetime.now(timezone.utc)
    print(f"Current UTC time: {now_utc}")
    print(f"Current Local time: {datetime.now()}")
    
    cutoff = now_utc - timedelta(minutes=2)
    print(f"Cutoff UTC (2 min ago): {cutoff}")
    
    logs = db.query(ChatLog).order_by(ChatLog.created_at.desc()).limit(10).all()
    print(f"\nLast 10 Chat Logs:")
    for log in logs:
        print(f"ID: {log.id}, Session: {log.session_id}, Sender: {log.sender}, Message: {log.message[:30]}, Created At: {log.created_at}")
        if log.created_at:
            # Check if timezone aware
            is_aware = log.created_at.tzinfo is not None and log.created_at.tzinfo.utcoffset(log.created_at) is not None
            print(f"  Is aware: {is_aware}, Diff: {now_utc - log.created_at if is_aware else 'N/A'}")
            
finally:
    db.close()
