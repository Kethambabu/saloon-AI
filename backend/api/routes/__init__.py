"""API v1 routes"""

from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["v1"])

# Include agent sub-routes
from api.routes.agent_routes import router as agent_router
router.include_router(agent_router)

# Include auth sub-routes
from api.routes.auth_routes import router as auth_router
router.include_router(auth_router)

# Include analytics sub-routes
from api.routes.analytics_routes import router as analytics_router
router.include_router(analytics_router)

# Include storage sub-routes
from api.routes.storage_routes import router as storage_router
router.include_router(storage_router)



# Health check endpoint
@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# Root API endpoint
@router.get("/")
async def api_root():
    """API v1 root endpoint"""
    return {
        "message": "SalonAI Workforce API v1",
        "docs": "/api/docs",
    }


# Export router for main app
__all__ = ["router"]
