"""API v1 routes"""

from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["v1"])

# Include core sub-routes (public endpoints for services, branches)
from api.routes.core_routes import router as core_router
router.include_router(core_router)

# Include agent sub-routes
from api.routes.agent_routes import router as agent_router
router.include_router(agent_router)

# Include auth sub-routes
from api.routes.auth_routes import router as auth_router
router.include_router(auth_router)

# Include customer sub-routes (isolated customer data access)
from api.routes.customer_routes import router as customer_router
router.include_router(customer_router)

# Include staff sub-routes (isolated staff data access)
from api.routes.staff_routes import router as staff_router
router.include_router(staff_router)

# Include analytics sub-routes
from api.routes.analytics_routes import router as analytics_router
router.include_router(analytics_router)

# Include storage sub-routes
from api.routes.storage_routes import router as storage_router
router.include_router(storage_router)

# Include lead sub-routes
from routes.lead_routes import router as lead_router
router.include_router(lead_router)

# Include recommendation/upsell sub-routes
from api.routes.recommendation_routes import router as recommendation_router
router.include_router(recommendation_router)

# Include reputation/review sub-routes
from api.routes.review_routes import router as review_router
router.include_router(review_router)




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
