import os
import sys
from sqlalchemy import text

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import engine

def main():
    print("Running migration to add 'INTERESTED' to lead_status enum...")
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Check if enum value already exists to avoid errors
            res = conn.execute(text("""
                SELECT enumlabel FROM pg_enum 
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
                WHERE pg_type.typname = 'lead_status' AND enumlabel = 'INTERESTED'
            """))
            exists = res.fetchone() is not None
            
            if not exists:
                conn.execute(text("ALTER TYPE lead_status ADD VALUE 'INTERESTED'"))
                print("SUCCESS: Added 'INTERESTED' value to lead_status enum.")
            else:
                print("SUCCESS: 'INTERESTED' value already exists in lead_status enum.")
    except Exception as e:
        print(f"ERROR: Error altering enum: {e}")

if __name__ == "__main__":
    main()
