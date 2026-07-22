"""
SalonAI Workforce - FastAPI Application Entry Point
Production-ready enterprise application for salon workforce management (Hugging Face Primary enabled)
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

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from core.config import Settings, get_settings, validate_secret_key_startup
from core.observability import configure_logging
from core.llm_config import validate_llm_startup
from api.routes import router as api_router

# Setup logging immediately using env-driven configuration
configure_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    third_party_level=os.getenv("THIRD_PARTY_LOG_LEVEL", "WARNING"),
    trace_enabled=os.getenv("AGENT_TRACE_ENABLED", "true").lower() in ("1", "true", "yes"),
    log_file=os.path.join(backend_dir, "logs", "salon_debug.log"),
)
logger = logging.getLogger(__name__)





@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application startup and shutdown events"""
    # Startup
    logger.info("=" * 70)
    logger.info("SalonAI Workforce API Starting Up")
    logger.info("=" * 70)
    
    settings = get_settings()
    application.state.settings = settings

    # Refuse to boot in production with the insecure placeholder SECRET_KEY
    if not validate_secret_key_startup(settings):
        raise RuntimeError(
            "Refusing to start: ENVIRONMENT=production but SECRET_KEY is still the "
            "insecure placeholder value. Set a strong, unique SECRET_KEY environment "
            "variable before deploying to production."
        )

    # Validate LLM configuration
    logger.info("[Startup] Validating LLM configuration...")
    llm_valid = validate_llm_startup()
    if not llm_valid:
        logger.error("[Startup] LLM configuration validation failed - some agents may not function correctly")
    else:
        logger.info("[Startup] LLM configuration validated successfully")
        
    # Automatic database schema creation and seeding (disabled in production)
    logger.info("[Startup] Initializing database connection...")
    from infrastructure.db.database import check_db_health, SessionLocal, engine
    from infrastructure.db.models import Base, Branch
    from infrastructure.db.seed import seed_database
    
    if check_db_health():
        logger.info("[Startup] Database connection is healthy.")
        if not settings.is_production:
            try:
                logger.info("[Startup] Checking and creating database schemas (dev/test)...")
                Base.metadata.create_all(bind=engine)
                
                db = SessionLocal()
                branch_count = db.query(Branch).count()
                if branch_count == 0:
                    logger.info("[Startup] Database is empty — seeding...")
                    seed_database()
                else:
                    logger.info("[Startup] Database verified with %d branches.", branch_count)
                db.close()
            except Exception as e:
                logger.error(f"❌ Error during database schema initialization/seeding: {e}", exc_info=True)
        else:
            logger.info("[Startup] Production: schema auto-creation skipped (using Alembic).")
    else:
        logger.error("[Startup] Database connection FAILED during startup!")
        if settings.is_production:
            raise RuntimeError("Database connection failed during startup health check in production.")
    
    # Initialize Domain Services and Register Event Bus Subscribers
    logger.info("[Startup] Initializing enterprise domain services and registering event subscribers...")
    try:
        from application.services.appointment_service import get_appointment_service
        from application.services.analytics_service import get_analytics_service, register_event_subscribers as register_analytics_subscribers
        from application.services.notification_service import get_notification_service, register_event_subscribers as register_notification_subscribers
        from application.services.availability_service import get_availability_service
        from application.services.customer_service import get_customer_service
        from application.services.lead_service import get_lead_service
        from application.services.review_service import get_review_service
        from application.services.staff_service import get_staff_service

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
        
        # Register Curated Memory Event Subscribers
        from application.services.memory_curator_service import register_memory_curator_subscribers
        register_memory_curator_subscribers()

        # Run initial auto-cancellation cleanup for past appointments
        try:
            from application.services.appointment_service import auto_cancel_all_expired_appointments
            cancelled_count = auto_cancel_all_expired_appointments()
            if cancelled_count > 0:
                logger.info(f"[Startup] Cleaned up {cancelled_count} past expired appointment(s).")
        except Exception as cancel_exc:
            logger.warning(f"[Startup] Initial auto-cancellation check failed: {cancel_exc}")

        logger.info("[Startup] Enterprise domain services initialized successfully.")
    except Exception as exc:
        logger.error("[Startup] Failed to initialize domain services: %s", exc, exc_info=True)

    # Start the automated Lead Follow-up Scheduler (disabled in production FastAPI process)
    if settings.is_production:
        logger.info("[Scheduler] Skipping in-process scheduler for production.")
    else:
        try:
             from apscheduler.schedulers.background import BackgroundScheduler
             from application.services.lead_service import process_leads
             from application.services.analytics_service import process_returning_cohort_reminders
             from application.services.appointment_service import auto_cancel_all_expired_appointments
             
             logger.info("[Scheduler] Starting Lead Follow-up, Cohort Reminders & Auto-Cancel Background Scheduler...")
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
             scheduler.add_job(
                 auto_cancel_all_expired_appointments,
                 'interval',
                 minutes=15,
                 id="auto_cancel_expired_appointments"
             )
             scheduler.start()
             application.state.scheduler = scheduler
             logger.info("[Scheduler] Background Scheduler started successfully.")
        except Exception as e:
             logger.error(f"❌ Failed to start background scheduler: {e}", exc_info=True)

    logger.info("=" * 70)
    
    yield
    
    # Shutdown
    logger.info("[Shutdown] SalonAI Workforce API Shutting Down")
    
    # Shutdown Background Scheduler
    if hasattr(application.state, "scheduler"):
        logger.info("[Shutdown] Shutting down Background Scheduler...")
        application.state.scheduler.shutdown()
        logger.info("[Shutdown] Background Scheduler shut down successfully.")



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

    # Global fallback exception handler: guarantees any unhandled exception
    # (in a route that isn't already wrapped in its own try/except) returns a
    # clean, consistent JSON 500 with no traceback/exception message ever
    # reaching the client, regardless of the DEBUG setting.
    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc: Exception):
        from fastapi.responses import JSONResponse
        logger.error(
            "Unhandled exception on %s %s: %s",
            request.method, request.url.path, exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": "An unexpected server error occurred."},
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
    
    # Readiness check endpoint
    @application.get("/ready")
    async def readiness_check():
        """Readiness check endpoint that verifies database connectivity."""
        from infrastructure.db.database import check_db_health
        import json
        from fastapi import Response, status
        if check_db_health():
            return {
                "status": "ready",
                "database_connected": True,
            }
        else:
            return Response(
                content=json.dumps({"status": "not_ready", "database_connected": False}),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json",
            )

    # Real-time WebSocket endpoint
    @application.websocket("/ws/{tenant_id}/{user_id}")
    async def websocket_endpoint(websocket: WebSocket, tenant_id: str, user_id: str):
        from api.websocket_manager import get_websocket_manager
        manager = get_websocket_manager()
        await manager.connect(websocket, tenant_id, user_id)
        try:
            while True:
                # Keep connection alive, listen for incoming packets
                data = await websocket.receive_text()
                await websocket.send_json({"status": "received", "data": data})
        except Exception:
            pass
        finally:
            manager.disconnect(websocket, tenant_id, user_id)
    
    # API Router Integration
    application.include_router(api_router, prefix="/api")
    
    return application


# Create app instance — always required for uvicorn/gunicorn/direct launch
app = create_app()

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

