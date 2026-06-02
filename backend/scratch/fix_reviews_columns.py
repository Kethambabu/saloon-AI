import sys
from sqlalchemy import text
sys.path.insert(0, r"C:\Users\N Balu\Documents\saloon\backend")

from db.database import SessionLocal

def add_columns_postgres():
    db = SessionLocal()
    try:
        dialect = db.bind.dialect.name
        print(f"Database dialect: {dialect}")
        if dialect == "postgresql":
            print("Adding missing columns to reviews table on PostgreSQL...")
            columns = [
                ("review_text", "TEXT"),
                ("sentiment", "VARCHAR(50) DEFAULT 'NEUTRAL'"),
                ("ai_response", "TEXT"),
                ("escalation_required", "BOOLEAN DEFAULT FALSE"),
                ("responded", "BOOLEAN DEFAULT FALSE")
            ]
            for col_name, col_type in columns:
                try:
                    db.execute(text(f"ALTER TABLE reviews ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
                    print(f"  Added column: {col_name}")
                except Exception as ex:
                    print(f"  Failed/already exists for column {col_name}: {ex}")
            db.commit()
            print("PostgreSQL update completed.")
    except Exception as e:
        print(f"Error updating PostgreSQL: {e}")
        db.rollback()
    finally:
        db.close()

def add_columns_sqlite():
    import sqlite3
    try:
        print("Checking SQLite test.db...")
        conn = sqlite3.connect('C:/Users/N Balu/Documents/saloon/backend/test.db')
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(reviews);")
        existing_cols = {row[1] for row in cursor.fetchall()}
        print(f"SQLite existing columns: {existing_cols}")
        
        columns = [
            ("staff_id", "CHAR(32)"),
            ("review_text", "TEXT"),
            ("sentiment", "VARCHAR(50) DEFAULT 'NEUTRAL'"),
            ("ai_response", "TEXT"),
            ("escalation_required", "BOOLEAN DEFAULT FALSE"),
            ("responded", "BOOLEAN DEFAULT FALSE")
        ]
        
        for col_name, col_type in columns:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE reviews ADD COLUMN {col_name} {col_type};")
                    print(f"  Added column to SQLite: {col_name}")
                except Exception as ex:
                    print(f"  Failed to add column {col_name} to SQLite: {ex}")
        conn.commit()
        conn.close()
        print("SQLite update completed.")
    except Exception as e:
        print(f"Error updating SQLite: {e}")

if __name__ == "__main__":
    add_columns_postgres()
    add_columns_sqlite()
