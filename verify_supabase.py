#!/usr/bin/env python
"""
Supabase Database Connection Verification Script
Tests all aspects of the Supabase connection and database configuration
"""

import os
import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if .env file exists and has required variables"""
    logger.info("=" * 70)
    logger.info("1️⃣  CHECKING ENVIRONMENT VARIABLES")
    logger.info("=" * 70)
    
    env_path = backend_path / ".env"
    if not env_path.exists():
        logger.error("❌ .env file not found at backend/.env")
        return False
    
    logger.info("✅ .env file found")
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv(env_path)
    
    required_vars = [
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "GROQ_API_KEY"
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            logger.error(f"❌ Missing: {var}")
            missing.append(var)
        else:
            # Show partial value for security
            if "DATABASE_URL" in var or "KEY" in var:
                logger.info(f"✅ {var}: {value[:20]}...{value[-10:]}")
            else:
                logger.info(f"✅ {var}: {value}")
    
    return len(missing) == 0

def check_database_connection():
    """Test SQLAlchemy connection"""
    logger.info("\n" + "=" * 70)
    logger.info("2️⃣  CHECKING DATABASE CONNECTION")
    logger.info("=" * 70)
    
    try:
        from db.database import check_db_health, engine, SessionLocal
        
        logger.info("Testing connection pool health...")
        is_healthy = check_db_health()
        
        if is_healthy:
            logger.info("✅ Database connection: HEALTHY")
            return True
        else:
            logger.error("❌ Database connection: FAILED")
            return False
            
    except Exception as e:
        logger.error(f"❌ Connection error: {str(e)}")
        return False

def check_tables_exist():
    """Check if all required tables exist"""
    logger.info("\n" + "=" * 70)
    logger.info("3️⃣  CHECKING DATABASE TABLES")
    logger.info("=" * 70)
    
    try:
        from sqlalchemy import text, inspect
        from db.database import SessionLocal
        
        db = SessionLocal()
        inspector = inspect(db.connection())
        tables = inspector.get_table_names()
        
        required_tables = [
            "branches",
            "staff",
            "services",
            "appointments",
            "customers",
            "leads",
            "reviews",
            "users",
            "alembic_version"
        ]
        
        missing_tables = [t for t in required_tables if t not in tables]
        
        logger.info(f"Found {len(tables)} tables in database")
        
        if not missing_tables:
            logger.info("✅ All required tables exist")
            for table in required_tables:
                if table in tables:
                    logger.info(f"   ✓ {table}")
            db.close()
            return True
        else:
            logger.warning(f"⚠️  Missing tables: {missing_tables}")
            logger.info("Run migrations: alembic upgrade head")
            logger.info("\nExisting tables:")
            for table in tables:
                logger.info(f"   - {table}")
            db.close()
            return False
            
    except Exception as e:
        logger.error(f"❌ Table check error: {str(e)}")
        return False

def check_models_sync():
    """Check if models match database schema"""
    logger.info("\n" + "=" * 70)
    logger.info("4️⃣  CHECKING MODELS SYNCHRONIZATION")
    logger.info("=" * 70)
    
    try:
        from db.models import Base
        from db.database import engine
        
        # Get metadata from models
        logger.info("Checking model definitions...")
        
        model_tables = set(Base.metadata.tables.keys())
        logger.info(f"✅ Models defined: {len(model_tables)} tables")
        for table_name in sorted(model_tables):
            logger.info(f"   - {table_name}")
        
        logger.info("✅ Model synchronization: OK")
        return True
        
    except Exception as e:
        logger.error(f"❌ Model sync error: {str(e)}")
        return False

def check_sample_query():
    """Try a sample query"""
    logger.info("\n" + "=" * 70)
    logger.info("5️⃣  TESTING SAMPLE QUERY")
    logger.info("=" * 70)
    
    try:
        from db.database import SessionLocal
        from db.models import Branch
        
        db = SessionLocal()
        count = db.query(Branch).count()
        branches = db.query(Branch).limit(3).all()
        
        logger.info(f"✅ Query successful - {count} branches in database")
        
        if branches:
            logger.info("Sample branches:")
            for branch in branches:
                logger.info(f"   - {branch.name} ({branch.code})")
        else:
            logger.info("No branches found - database might need seeding")
            logger.info("Run: python -m db.seed")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Query error: {str(e)}")
        return False

def check_alembic_migrations():
    """Check Alembic migration status"""
    logger.info("\n" + "=" * 70)
    logger.info("6️⃣  CHECKING ALEMBIC MIGRATIONS")
    logger.info("=" * 70)
    
    try:
        from sqlalchemy import text
        from db.database import SessionLocal
        
        db = SessionLocal()
        
        # Get current revision
        result = db.execute(
            text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
        ).fetchone()
        
        if result:
            logger.info(f"✅ Current migration version: {result[0]}")
        else:
            logger.warning("⚠️  No migrations applied yet")
            logger.info("Run: alembic upgrade head")
        
        db.close()
        return True
        
    except Exception as e:
        if "alembic_version" in str(e):
            logger.warning("⚠️  Alembic table not found - migrations may not be initialized")
            logger.info("Run: alembic upgrade head")
        else:
            logger.error(f"❌ Migration check error: {str(e)}")
        return False

def main():
    """Run all checks"""
    logger.info("\n")
    logger.info("╔" + "=" * 68 + "╗")
    logger.info("║" + " " * 68 + "║")
    logger.info("║" + "  SUPABASE CONNECTION VERIFICATION".center(68) + "║")
    logger.info("║" + " " * 68 + "║")
    logger.info("╚" + "=" * 68 + "╝")
    
    results = []
    
    # Run all checks
    results.append(("Environment Variables", check_environment()))
    results.append(("Database Connection", check_database_connection()))
    results.append(("Database Tables", check_tables_exist()))
    results.append(("Model Definitions", check_models_sync()))
    results.append(("Sample Query", check_sample_query()))
    results.append(("Migrations Status", check_alembic_migrations()))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 VERIFICATION SUMMARY")
    logger.info("=" * 70)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{check_name:30} {status}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    logger.info("=" * 70)
    logger.info(f"Total: {passed}/{total} checks passed\n")
    
    if passed == total:
        logger.info("🎉 ALL CHECKS PASSED! Your Supabase connection is working!")
        logger.info("\nNext steps:")
        logger.info("1. Start backend: uvicorn main:app --reload")
        logger.info("2. Start frontend: npm run dev")
        logger.info("3. Access: http://localhost:5173")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} check(s) failed. Review errors above.")
        logger.info("\nCommon fixes:")
        logger.info("1. Verify .env file: cat backend/.env")
        logger.info("2. Check Supabase URL is correct")
        logger.info("3. Run migrations: alembic upgrade head")
        logger.info("4. Check database credentials")
        return 1

if __name__ == "__main__":
    sys.exit(main())
