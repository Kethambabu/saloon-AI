"""
Database migration script to add 'status' column to 'staff_leaves' table.
"""

import os
import sys
import logging
from sqlalchemy import text, inspect

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from infrastructure.db.database import SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_migration():
    db = SessionLocal()
    try:
        dialect_name = engine.name
        logger.info(f"Connected database dialect: {dialect_name}")

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if "staff_leaves" not in tables:
            logger.error("Table 'staff_leaves' does not exist. Please initialize database first.")
            return

        columns = [col['name'] for col in inspector.get_columns('staff_leaves')]
        
        if "status" in columns:
            logger.info("Column 'status' already exists in 'staff_leaves' table.")
            return

        logger.info("Adding 'status' column to 'staff_leaves' table...")
        # Since it's a new column, we default it to 'APPROVED' for existing leaves so they remain active.
        db.execute(text("ALTER TABLE staff_leaves ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'APPROVED'"))
        db.commit()
        logger.info("✓ Column 'status' added successfully.")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
