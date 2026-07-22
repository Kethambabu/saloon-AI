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
from api.routes.lead_routes import router as lead_router
router.include_router(lead_router)

# Include notification sub-routes
from api.routes.notification_routes import router as notification_router
router.include_router(notification_router)

# Include recommendation/upsell sub-routes
from api.routes.recommendation_routes import router as recommendation_router
router.include_router(recommendation_router)

# Include reputation/review sub-routes
from api.routes.review_routes import router as review_router
router.include_router(review_router)

# Include memory pipeline sub-routes
from api.routes.memory_routes import router as memory_router
router.include_router(memory_router)

# Include admin knowledge base sub-routes
from api.routes.admin_knowledge_routes import router as admin_knowledge_router
router.include_router(admin_knowledge_router)

# Include MCP test sub-routes (Phase 1 — runs alongside existing agent/tool system)
from api.routes.mcp_routes import router as mcp_router
router.include_router(mcp_router)

# Include MCP metrics & cache routes
from api.routes.mcp_metrics_routes import router as mcp_metrics_router
router.include_router(mcp_metrics_router)





# Health check endpoint
@router.get("/health")
async def health():
    """Health check endpoint with database mode reporting"""
    from infrastructure.db.database import is_using_fallback
    return {
        "status": "healthy",
        "database_mode": "sqlite_fallback" if is_using_fallback() else "supabase",
    }



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

