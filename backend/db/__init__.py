"""
Database module initialization for SalonAI Workforce Platform.
Exposes the database connection engine, session helpers, transaction utilities,
and all ORM models for clean importing across the application.
"""

# Import connection layer components
from db.database import (
    engine,
    SessionLocal,
    get_db,
    db_transaction,
    check_db_health,
)

# Import ORM models
from db.models import (
    Base,
    BaseModel,
    Branch,
    Staff,
    Customer,
    Service,
    Appointment,
    Lead,
    Review,
    User,
    Admin,
    ChatLog,
    Notification,
    AnalyticsRecord,
    AppointmentStatus,
    LeadStatus,
    ReviewStatus,
    UserRole,
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
    # Models & Enums
    "BaseModel",
    "Branch",
    "Staff",
    "Customer",
    "Service",
    "Appointment",
    "Lead",
    "Review",
    "User",
    "Admin",
    "ChatLog",
    "Notification",
    "AnalyticsRecord",
    "AppointmentStatus",
    "LeadStatus",
    "ReviewStatus",
    "UserRole",
]

