"""
Database module initialization for SalonAI Workforce Platform.
Exposes the database connection engine, session helpers, transaction utilities,
and all ORM models for clean importing across the application.
"""

# Import connection layer components
from infrastructure.db.database import (
    engine,
    SessionLocal,
    get_db,
    db_transaction,
    check_db_health,
    is_using_fallback,
)

# Import ORM models
from infrastructure.db.models import (
    Base,
    BaseModel,
    Branch,
    Staff,
    Customer,
    Service,
    Appointment,
    Lead,
    Review,
    Waitlist,
    User,
    Admin,
    ChatLog,
    Notification,
    AnalyticsRecord,
    LoyaltyTransaction,
    StaffLeave,
    KnowledgeDocument,
    SpecialOffer,
    ServiceRecommendation,
    CustomerRecommendation,
    BusinessMetricsHistory,
    AgentMemory,
    AppointmentStatus,
    LeadStatus,
    ReviewStatus,
    UserRole,
    LoyaltyTransactionType,
)

# Export all symbols for clean import paths
__all__ = [
    # Engine & Session management
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "db_transaction",
    "check_db_health",
    "is_using_fallback",
    # Models & Enums
    "BaseModel",
    "Branch",
    "Staff",
    "Customer",
    "Service",
    "Appointment",
    "Lead",
    "Review",
    "Waitlist",
    "User",
    "Admin",
    "ChatLog",
    "Notification",
    "AnalyticsRecord",
    "LoyaltyTransaction",
    "StaffLeave",
    "KnowledgeDocument",
    "SpecialOffer",
    "ServiceRecommendation",
    "CustomerRecommendation",
    "BusinessMetricsHistory",
    "AgentMemory",
    "AppointmentStatus",
    "LeadStatus",
    "ReviewStatus",
    "UserRole",
    "LoyaltyTransactionType",
]


