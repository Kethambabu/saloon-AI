"""
API subsystem entry point for SalonAI Workforce.
Defines the main API router/app with custom logging middleware, CORS controls,
health check endpoints, and route aggregator.
"""

import time
import logging
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Project imports
from core.config import get_settings
from api.routes.agent_routes import router as agent_router
from api.routes.analytics_routes import router as analytics_router

logger = logging.getLogger(__name__)
settings = get_settings()

# Setup router-based architecture
router = APIRouter(prefix="/v1")


# Health check response model
class HealthCheckResponse(BaseModel):
    status: str = Field("healthy", description="Status code indicating healthy system state")
    environment: str = Field(..., description="Target server environment (development, testing, production)")
    version: str = Field(..., description="API Version")


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="API Specific Health Check"
)
async def api_health():
    """Lightweight API health verification endpoint."""
    return HealthCheckResponse(
        status="healthy",
        environment=settings.environment,
        version="0.1.0"
    )


# Aggregate sub-routers
router.include_router(agent_router)
router.include_router(analytics_router)


# Optional: Helper to build a standalone sub-app if mounted separately
def create_api_app() -> FastAPI:
    """Application factory for standalone API deployments."""
    app = FastAPI(
        title="SalonAI Workforce API Subsystem",
        version="0.1.0",
        docs_url="/docs",
    )
    
    # Self-healing database check, seeding and RAG index ingestion on startup
    @app.on_event("startup")
    async def startup_event():
        logger.info("Running SalonAI API Startup Checks & Ingestions...")
        
        # 1. Verify database connection & perform conditional seeding
        from db.database import check_db_health, SessionLocal
        from db.models import Branch
        
        if check_db_health():
            logger.info("Database connection is healthy.")
            db = SessionLocal()
            try:
                branch_count = db.query(Branch).count()
                if branch_count == 0:
                    logger.info("Database is empty. Initiating automatic seeding...")
                    from db.seed import seed_database
                    seed_database()
                else:
                    logger.info(f"Database already contains {branch_count} branches. Skipping seeding.")
            except Exception as e:
                logger.error(f"Error checking/seeding database during startup: {e}")
            finally:
                db.close()
        else:
            logger.error("Database connection failed during startup health check!")

        # 2. Build RAG indices if enabled
        if settings.enable_rag:
            logger.info("RAG system enabled. Checking FAISS indices...")
            try:
                from rag.ingest import RAGIngestor
                from rag.retriever import get_retriever
                
                retriever = get_retriever()
                status = retriever.get_status()
                
                if not status["knowledge_index"]["exists"] or not status["interaction_index"]["exists"]:
                    logger.info("FAISS indices missing or incomplete. Initiating automatic ingestion...")
                    ingestor = RAGIngestor()
                    ingestor.ingest_all(force_rebuild=True)
                    logger.info("Automatic RAG ingestion completed successfully.")
                else:
                    logger.info("RAG FAISS indices verified and loaded.")
            except Exception as e:
                logger.error(f"Error initializing RAG system during startup: {e}")

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 2. Custom Logging & Performance Interception Middleware
    @app.middleware("http")
    async def log_requests_middleware(request: Request, call_next):
        start_time = time.time()
        logger.info(f"Incoming Request: {request.method} {request.url.path}")
        
        try:
            response: Response = await call_next(request)
            duration = time.time() - start_time
            logger.info(f"Request Completed: {request.method} {request.url.path} | Status: {response.status_code} | Duration: {duration:.4f}s")
            # Inject performance header
            response.headers["X-Process-Time"] = f"{duration:.4f}s"
            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Request Failed: {request.method} {request.url.path} | Error: {str(e)} | Duration: {duration:.4f}s")
            raise e

    # Include aggregated routes
    app.include_router(router, prefix="/api")
    return app


# Export unified router for main application inclusion
__all__ = ["router", "create_api_app"]
