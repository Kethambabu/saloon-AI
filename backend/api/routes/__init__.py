"""API v1 routes"""

from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["v1"])

# Include agent sub-routes
from api.routes.agent_routes import router as agent_router
router.include_router(agent_router)

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
