"""
Database migration script to drop and recreate the leads table
with the new columns requested in the architecture blueprint.
"""

import os
import sys
import logging

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from infrastructure.db.database import SessionLocal, engine
from infrastructure.db.models import Base, Lead
from infrastructure.db.seed import seed_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def migrate_leads_table():
    db = SessionLocal()
    try:
        logger.info("Dropping existing 'leads' table to apply the new schema...")
        
        # Check database dialect to see if we're on SQLite or Postgres
        dialect_name = engine.name
        logger.info(f"Connected database dialect: {dialect_name}")

        # Drop the table
        db.execute(text("DROP TABLE IF EXISTS leads CASCADE;"))
        db.commit()
        logger.info("✓ Table dropped successfully.")

        # Recreate all tables (this will create leads with the new structure)
        logger.info("Recreating leads table with SQLAlchemy Base...")
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Schema recreated successfully.")
        
        # Re-seed the database to create sample records
        logger.info("Running database seed script to populate sample records...")
        seed_database()
        logger.info("✓ Database seeding complete.")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    migrate_leads_table()

