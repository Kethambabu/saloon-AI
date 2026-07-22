#!/usr/bin/env python
"""
Direct database initialization script - bypasses Alembic
Creates all tables in Supabase PostgreSQL database
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from infrastructure.db.models import Base
from infrastructure.db.database import engine

# Load environment
load_dotenv()

print("=" * 70)
print("🗄️  INITIALIZING SUPABASE DATABASE")
print("=" * 70)

try:
    # Create all tables from SQLAlchemy models
    print("\n📝 Creating tables from models...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")
    
    # Verify tables were created
    print("\n🔍 Verifying tables in database...")
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            result = connection.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ))
        else:
            result = connection.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ))
        tables = [row[0] for row in result]
        
        print(f"\n✅ Found {len(tables)} tables in database:")
        for table in sorted(tables):
            print(f"   ✓ {table}")
    
    print("\n" + "=" * 70)
    print("🎉 DATABASE INITIALIZATION COMPLETE!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Verify in Supabase dashboard: https://supabase.com/dashboard")
    print("2. Start backend: uvicorn main:app --reload")
    print("3. Start frontend: npm run dev")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    print("\nTroubleshooting:")
    print("1. Check .env file has valid DATABASE_URL")
    print("2. Verify Supabase credentials are correct")
    print("3. Ensure network connection to Supabase")
    sys.exit(1)

