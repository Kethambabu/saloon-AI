"""
Database models - SQLAlchemy ORM models for SalonAI Workforce Platform.
All models use UUID primary keys, support timezone-aware timestamps,
and enforce strict database constraints and proper indexing.
"""

import enum
import uuid
from decimal import Decimal
from typing import List, Optional
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Numeric,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Uuid,
    Enum as SQLEnum,
    CheckConstraint
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class AppointmentStatus(str, enum.Enum):
    """Lifecycle states of a booking appointment"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class LeadStatus(str, enum.Enum):
    """Lifecycle states of a prospective client lead"""
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    CONVERTED = "CONVERTED"
    LOST = "LOST"


class ReviewStatus(str, enum.Enum):
    """Moderation status of customer feedback"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UserRole(str, enum.Enum):
    """Security roles for platform access"""
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"
    MANAGER = "MANAGER"
    OWNER = "OWNER"


class LoyaltyTransactionType(str, enum.Enum):
    """Types of loyalty point transactions"""
    APPOINTMENT_COMPLETED = "APPOINTMENT_COMPLETED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED"
    RATING_BONUS = "RATING_BONUS"
    APP_USAGE_BONUS = "APP_USAGE_BONUS"
    POINT_REDEMPTION = "POINT_REDEMPTION"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"



class BaseModel(Base):
    """
    Enterprise abstract base model with UUID primary key
    and timezone-aware created_at and updated_at metadata.
    """
    __abstract__ = True
    
    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class Branch(BaseModel):
    """
    Represents physical salon locations.
    Supports multi-location deployments and tracks active status.
    """
    __tablename__ = "branches"

    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    staff = relationship(
        "Staff",
        back_populates="branch",
        cascade="all, delete-orphan"
    )
    appointments = relationship(
        "Appointment",
        back_populates="branch",
        cascade="all, delete-orphan"
    )
    leads = relationship(
        "Lead",
        back_populates="branch",
        cascade="all, delete-orphan"
    )
    reviews = relationship(
        "Review",
        back_populates="branch",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Branch name={self.name} code={self.code}>"


class Staff(BaseModel):
    """
    Represents professional salon employees (stylists, receptionists, etc.).
    Belongs to a specific physical Branch location.
    """
    __tablename__ = "staff"

    branch_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(50), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    branch = relationship("Branch", back_populates="staff")
    appointments = relationship("Appointment", back_populates="staff")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Staff name={self.full_name} role={self.role}>"


class Customer(BaseModel):
    """
    Represents a client who has visited or inquired with the salon.
    Holds contact details and historical bookings.
    """
    __tablename__ = "customers"

    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), index=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    loyalty_points = Column(Integer, default=0, nullable=False, index=True)

    # Relationships
    appointments = relationship(
        "Appointment",
        back_populates="customer",
        cascade="all, delete-orphan"
    )
    reviews = relationship(
        "Review",
        back_populates="customer",
        cascade="all, delete-orphan"
    )
    loyalty_transactions = relationship(
        "LoyaltyTransaction",
        back_populates="customer",
        cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Customer name={self.full_name} email={self.email} loyalty_points={self.loyalty_points}>"


class LoyaltyTransaction(BaseModel):
    """
    Tracks loyalty point transactions for customers.
    Records how points are earned/spent and reasons for changes.
    """
    __tablename__ = "loyalty_transactions"

    customer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    transaction_type = Column(
        SQLEnum(LoyaltyTransactionType, name="loyalty_transaction_type"),
        nullable=False,
        index=True
    )
    points_change = Column(Integer, nullable=False)
    previous_balance = Column(Integer, nullable=False)
    new_balance = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    appointment_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    review_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("reviews.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Relationships
    customer = relationship("Customer", back_populates="loyalty_transactions")
    appointment = relationship("Appointment")
    review = relationship("Review")

    def __repr__(self) -> str:
        return f"<LoyaltyTransaction customer_id={self.customer_id} type={self.transaction_type} points_change={self.points_change}>"


class Service(BaseModel):
    """
    Represents high-value salon service catalog items.
    Toggled on/off dynamically by management.
    """
    __tablename__ = "services"

    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    appointments = relationship("Appointment", back_populates="service")

    def __repr__(self) -> str:
        return f"<Service name={self.name} price={self.price}>"


class Appointment(BaseModel):
    """
    Represents a booked service slot.
    Aggregates Customer, Staff, Service, and physical Branch together.
    """
    __tablename__ = "appointments"

    customer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    branch_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    staff_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    service_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        SQLEnum(AppointmentStatus, name="appointment_status"),
        default=AppointmentStatus.PENDING,
        nullable=False,
        index=True
    )
    notes = Column(Text, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="appointments")
    branch = relationship("Branch", back_populates="appointments")
    staff = relationship("Staff", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    review = relationship(
        "Review",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Appointment customer_id={self.customer_id} start_time={self.start_time} status={self.status}>"


class Lead(BaseModel):
    """
    Represents customer acquisition inquiries and prospective opportunities.
    """
    __tablename__ = "leads"

    branch_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=True)
    email = Column(String(100), index=True, nullable=True)
    phone = Column(String(20), index=True, nullable=True)
    source = Column(String(50), index=True, nullable=True)
    status = Column(
        SQLEnum(LeadStatus, name="lead_status"),
        default=LeadStatus.NEW,
        nullable=False,
        index=True
    )
    notes = Column(Text, nullable=True)

    # Relationships
    branch = relationship("Branch", back_populates="leads")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name or ''}".strip()

    def __repr__(self) -> str:
        return f"<Lead name={self.full_name} status={self.status}>"


class Review(BaseModel):
    """
    Represents customer feedback on a service appointment or a physical location.
    Enforces distinct rating bound logic.
    """
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_rating_range"),
    )

    customer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    branch_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    appointment_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=True,
        index=True
    )
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    status = Column(
        SQLEnum(ReviewStatus, name="review_status"),
        default=ReviewStatus.PENDING,
        nullable=False,
        index=True
    )

    # Relationships
    customer = relationship("Customer", back_populates="reviews")
    branch = relationship("Branch", back_populates="reviews")
    appointment = relationship("Appointment", back_populates="review")

    def __repr__(self) -> str:
        return f"<Review rating={self.rating} status={self.status}>"


class Waitlist(BaseModel):
    """
    Represents customer waitlist bookings for fully booked slots.
    """
    __tablename__ = "waitlists"

    customer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    branch_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    service_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    staff_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    date_str = Column(String(50), nullable=False, index=True)
    time_str = Column(String(50), nullable=False)
    is_notified = Column(Boolean, default=False, nullable=False)

    # Relationships
    customer = relationship("Customer")
    branch = relationship("Branch")
    service = relationship("Service")
    staff = relationship("Staff")

    def __repr__(self) -> str:
        return f"<Waitlist customer={self.customer_id} date={self.date_str} time={self.time_str}>"


class User(BaseModel):
    """
    Represents an authenticated dashboard user.
    Handles JWT access credentials and role assignment.
    """
    __tablename__ = "users"

    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        SQLEnum(UserRole, name="user_role"),
        default=UserRole.STAFF,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=True, nullable=False)
    staff_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    customer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    refresh_token = Column(String(500), nullable=True)

    # Relationships
    staff = relationship("Staff", backref="user", uselist=False)
    customer = relationship("Customer", backref="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User email={self.email} role={self.role}>"


class Admin(BaseModel):
    """Represents an administrator user profile."""
    __tablename__ = "admins"

    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), nullable=True)

    # Relationships
    user = relationship("User", backref="admin_profile", uselist=False)





class ChatLog(BaseModel):
    """Stores customer or staff interaction logs with AI agents."""
    __tablename__ = "chat_logs"

    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    customer_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    staff_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    agent_type = Column(String(50), nullable=False, default="RECEPTIONIST")
    sender = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)

    # Relationships
    user = relationship("User", backref="chat_logs")
    customer = relationship("Customer", backref="chat_logs")
    staff = relationship("Staff", backref="chat_logs")


class Notification(BaseModel):
    """Stores notifications for authenticated dashboard users."""
    __tablename__ = "notifications"

    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", backref="notifications")


class AnalyticsRecord(BaseModel):
    """Stores operational, business, and performance analytics records."""
    __tablename__ = "analytics_records"

    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    dimensions = Column(Text, nullable=True)  # JSON-formatted string for flexible dimensions


# Export all models and enums
__all__ = [
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

