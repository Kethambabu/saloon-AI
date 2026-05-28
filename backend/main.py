"""
SalonAI Workforce - FastAPI Application Entry Point
Production-ready enterprise application for salon workforce management
"""

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
app: FastAPI | None = None


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
    
    logger.info("=" * 70)
    
    yield
    
    # Shutdown
    logger.info("🛑 SalonAI Workforce API Shutting Down")


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
