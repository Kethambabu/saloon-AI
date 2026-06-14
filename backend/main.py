"""
SalonAI Workforce - FastAPI Application Entry Point
Production-ready enterprise application for salon workforce management
"""

import sys
import os
# Add both backend and project root directories to sys.path to resolve imports correctly
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
project_root = os.path.abspath(os.path.join(backend_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import Settings, get_settings
from core.logging import setup_logging
from core.llm_config import validate_llm_startup
from api.routes import router as api_router

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# App instance
# App instance
app: FastAPI | None = None


def process_daily_memory_snapshots():
    """Scheduled task to run daily memory pipeline."""
    from db.database import SessionLocal
    from services.memory_pipeline_service import MemoryPipelineService
    import asyncio
    
    logger.info("⏱️ [Scheduler] Starting automated daily memory snapshot pipeline...")
    db = SessionLocal()
    try:
        service = MemoryPipelineService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(service.run_daily_pipeline(db))
        loop.close()
        logger.info("✅ [Scheduler] Automated daily memory snapshot pipeline completed successfully.")
    except Exception as e:
        logger.error(f"[Scheduler] Error running automated daily memory snapshots: {e}", exc_info=True)
    finally:
        db.close()


def process_weekly_memory_snapshots():
    """Scheduled task to run weekly memory consolidation pipeline."""
    from db.database import SessionLocal
    from services.memory_pipeline_service import MemoryPipelineService
    import asyncio
    import datetime
    
    logger.info("⏱️ [Scheduler] Starting automated weekly memory consolidation pipeline...")
    db = SessionLocal()
    try:
        service = MemoryPipelineService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(service.run_weekly_pipeline(db, datetime.date.today()))
        loop.close()
        logger.info("✅ [Scheduler] Automated weekly memory consolidation pipeline completed successfully.")
    except Exception as e:
        logger.error(f"[Scheduler] Error running automated weekly memory consolidation: {e}", exc_info=True)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application startup and shutdown events"""
    # Startup
    logger.info("=" * 70)
    logger.info("🚀 SalonAI Workforce API Starting Up")
    logger.info("=" * 70)
    
    settings = get_settings()
    application.state.settings = settings
    
    # Validate LLM configuration
    logger.info("🔍 Validating LLM configuration at startup...")
    llm_valid = validate_llm_startup()
    if not llm_valid:
        logger.error("❌ LLM configuration validation failed - some agents may not function correctly")
    else:
        logger.info("✅ LLM configuration validated successfully")
        
    # Automatic Supabase database schema creation and seeding
    logger.info("🔍 Initializing Supabase database connection and schemas...")
    from db.database import check_db_health, SessionLocal, engine
    from db.models import Base, Branch
    from db.seed import seed_database
    
    if check_db_health():
        logger.info("✅ Database connection to Supabase is healthy.")
        try:
            logger.info("🔄 Checking and creating database schemas...")
            Base.metadata.create_all(bind=engine)
            
            db = SessionLocal()
            branch_count = db.query(Branch).count()
            if branch_count == 0:
                logger.info("🌱 Supabase database is empty. Performing automatic database seeding...")
                seed_database()
            else:
                logger.info(f"✅ Supabase database verified with {branch_count} branches.")
            db.close()
        except Exception as e:
            logger.error(f"❌ Error during database schema initialization/seeding: {e}", exc_info=True)
    else:
        logger.error("❌ Supabase database connection failed during startup health check!")
    
    # Initialize Domain Services and Register Event Bus Subscribers
    logger.info("🔍 Initializing enterprise domain services and registering event subscribers...")
    try:
        from domain.appointment_service import get_appointment_service
        from domain.analytics_service import get_analytics_service, register_event_subscribers as register_analytics_subscribers
        from domain.notification_service import get_notification_service, register_event_subscribers as register_notification_subscribers
        from domain.availability_service import get_availability_service
        from domain.customer_service import get_customer_service
        from domain.lead_service import get_lead_service
        from domain.review_service import get_review_service
        from domain.staff_service import get_staff_service

        get_appointment_service()
        get_analytics_service()
        get_notification_service()
        get_availability_service()
        get_customer_service()
        get_lead_service()
        get_review_service()
        get_staff_service()

        # Register Event Bus Subscribers
        logger.info("🔄 Registering event bus subscribers...")
        register_analytics_subscribers()
        register_notification_subscribers()

        logger.info("✅ Enterprise domain services and event subscribers initialized successfully.")
    except Exception as exc:
        logger.error(f"❌ Failed to initialize domain services: {exc}", exc_info=True)

    # Start the automated Lead Follow-up Scheduler
    try:
         from apscheduler.schedulers.background import BackgroundScheduler
         from services.lead_service import process_leads
         from services.analytics_service import process_returning_cohort_reminders
         
         logger.info("⏱️ Starting Lead Follow-up & Cohort Reminders Background Scheduler...")
         scheduler = BackgroundScheduler()
         scheduler.add_job(
             process_leads,
             'interval',
             minutes=60
         )
         scheduler.add_job(
             process_returning_cohort_reminders,
             'interval',
             minutes=60
         )
         # Daily memory run at 11:59 PM
         scheduler.add_job(
             process_daily_memory_snapshots,
             'cron',
             hour=23,
             minute=59
         )
         # Weekly memory consolidation on Sunday at 11:59 PM
         scheduler.add_job(
             process_weekly_memory_snapshots,
             'cron',
             day_of_week='sun',
             hour=23,
             minute=59
         )
         scheduler.start()
         application.state.scheduler = scheduler
         logger.info("✅ Background Scheduler started successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to start background scheduler: {e}", exc_info=True)

    logger.info("=" * 70)
    
    yield
    
    # Shutdown
    logger.info("🛑 SalonAI Workforce API Shutting Down")
    
    # Shutdown Background Scheduler
    if hasattr(application.state, "scheduler"):
        logger.info("⏱️ Shutting down Background Scheduler...")
        application.state.scheduler.shutdown()
        logger.info("✅ Background Scheduler shutdown successfully.")



def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Application factory for creating FastAPI app instance
    
    Args:
        settings: Optional Settings instance. If None, uses default from environment
        
    Returns:
        Configured FastAPI application
    """
    if settings is None:
        settings = get_settings()
    
    application = FastAPI(
        title="SalonAI Workforce API",
        description="Enterprise API for salon workforce management with AI agents",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS Configuration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health check endpoint
    @application.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "environment": settings.environment,
            "version": "0.1.0",
        }
    
    # API Router Integration
    application.include_router(api_router, prefix="/api")
    
    return application


# Create app instance for deployment
if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
else:
    # For gunicorn/production deployment
    app = create_app()
