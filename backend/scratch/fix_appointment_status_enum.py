import sys
from sqlalchemy import text
sys.path.insert(0, r"C:\Users\N Balu\Documents\saloon\backend")

from db.database import SessionLocal

def fix_enum():
    db = SessionLocal()
    try:
        dialect = db.bind.dialect.name
        print(f"Database dialect: {dialect}")
        if dialect == "postgresql":
            print("Altering PostgreSQL appointment_status enum type...")
            # We must run this in autocommit mode because ALTER TYPE ... ADD VALUE cannot run inside a transaction
            engine = db.bind
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                try:
                    conn.execute(text("ALTER TYPE appointment_status ADD VALUE IF NOT EXISTS 'CHECKED_IN';"))
                    print("  Added CHECKED_IN value")
                except Exception as ex:
                    print(f"  Error adding CHECKED_IN: {ex}")
                
                try:
                    conn.execute(text("ALTER TYPE appointment_status ADD VALUE IF NOT EXISTS 'IN_SERVICE';"))
                    print("  Added IN_SERVICE value")
                except Exception as ex:
                    print(f"  Error adding IN_SERVICE: {ex}")
            print("PostgreSQL enum update completed.")
        else:
            print("Dialect is not PostgreSQL. No enum update needed.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_enum()
