import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.database import SessionLocal
from db.models import ChatLog, User, Customer

db = SessionLocal()
try:
    print("Latest 20 chat logs:")
    logs = db.query(ChatLog).order_by(ChatLog.created_at.desc()).limit(20).all()
    for l in logs:
        print(f"Time: {l.created_at}, Sender: {l.sender}, Message: {l.message[:150]}")
finally:
    db.close()
