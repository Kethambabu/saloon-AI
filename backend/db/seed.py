"""
Database Seed Script for SalonAI Workforce Platform.
Creates realistic sample data for branches, staff, customers, services, appointments,
and the new role tables (Admin, Manager, Customer, Staff users) on Supabase.

Usage:
    python backend/db/seed.py
"""

import os
import sys
import uuid
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from db.database import SessionLocal, engine
from db.models import (
    Base,
    Branch,
    Staff,
    Customer,
    Service,
    Appointment,
    AppointmentStatus,
    Lead,
    LeadStatus,
    User,
    UserRole,
    Admin,
    AnalyticsRecord,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_database():
    """
    Seed the database with realistic sample data.
    Creates tables and populates with demo content.
    """
    # Create tables
    logger.info("Verifying and creating database schemas on Supabase...")
    Base.metadata.create_all(bind=engine)
    logger.info("✓ Database tables verified/created successfully.")
    
    db = SessionLocal()
    
    try:
        # Check if users already exist
        existing_users = db.query(User).count()
        if existing_users > 0:
            logger.info("ℹ️  Database already seeded. Skipping...")
            db.close()
            return
        
        logger.info("🌱 Seeding SalonAI Workforce database on Supabase...")
        
        # ====================================================================
        # 1. CREATE BRANCHES
        # ====================================================================
        logger.info("Creating branches...")
        
        branches = [
            Branch(
                id=uuid.uuid4(),
                name="Downtown Elite",
                code="DTE",
                address="123 Main Street",
                city="New York",
                phone="+1-212-555-0100",
                email="downtown@salonai.com",
                is_active=True
            ),
            Branch(
                id=uuid.uuid4(),
                name="Westside Boutique",
                code="WSB",
                address="456 Park Avenue",
                city="Los Angeles",
                phone="+1-310-555-0200",
                email="westside@salonai.com",
                is_active=True
            ),
            Branch(
                id=uuid.uuid4(),
                name="Midtown Luxe",
                code="MTL",
                address="789 Michigan Avenue",
                city="Chicago",
                phone="+1-312-555-0300",
                email="midtown@salonai.com",
                is_active=True
            ),
        ]
        
        for branch in branches:
            db.add(branch)
        db.flush()
        logger.info(f"✓ Created {len(branches)} branches")
        
        # ====================================================================
        # 2. CREATE SERVICES
        # ====================================================================
        logger.info("Creating services...")
        
        services = [
            Service(
                id=uuid.uuid4(),
                name="Signature Precision Haircut",
                description="Professional haircut with detailed styling consultation",
                price=Decimal("85.00"),
                duration_minutes=60,
                is_active=True
            ),
            Service(
                id=uuid.uuid4(),
                name="Balayage & Creative Color",
                description="Hand-painted highlighting technique with custom color blending",
                price=Decimal("220.00"),
                duration_minutes=150,
                is_active=True
            ),
            Service(
                id=uuid.uuid4(),
                name="Hydrating Deep-Cleansing Facial",
                description="Luxurious 75-minute facial with premium skincare products",
                price=Decimal("120.00"),
                duration_minutes=75,
                is_active=True
            ),
            Service(
                id=uuid.uuid4(),
                name="Himalayan Hot Stone Massage",
                description="Soothing massage with warm stone therapy and aromatherapy",
                price=Decimal("150.00"),
                duration_minutes=90,
                is_active=True
            ),
        ]
        
        for service in services:
            db.add(service)
        db.flush()
        logger.info(f"✓ Created {len(services)} services")
        
        # ====================================================================
        # 3. CREATE STAFF
        # ====================================================================
        logger.info("Creating staff members...")
        
        staff_members = [
            Staff(
                id=uuid.uuid4(),
                branch_id=branches[0].id,
                first_name="Alexandra",
                last_name="Chen",
                email="alex.chen@salonai.com",
                phone="+1-212-555-1001",
                role="Senior Stylist",
                is_active=True
            ),
            Staff(
                id=uuid.uuid4(),
                branch_id=branches[0].id,
                first_name="Marcus",
                last_name="Johnson",
                email="marcus.johnson@salonai.com",
                phone="+1-212-555-1002",
                role="Color Specialist",
                is_active=True
            ),
            Staff(
                id=uuid.uuid4(),
                branch_id=branches[1].id,
                first_name="Isabella",
                last_name="Martinez",
                email="isabella.martinez@salonai.com",
                phone="+1-310-555-2001",
                role="Senior Stylist",
                is_active=True
            ),
        ]
        
        for staff in staff_members:
            db.add(staff)
        db.flush()
        logger.info(f"✓ Created {len(staff_members)} staff members")
        
        # ====================================================================
        # 4. CREATE CUSTOMERS
        # ====================================================================
        logger.info("Creating customers...")
        
        customers = [
            Customer(
                id=uuid.uuid4(),
                first_name="Alice",
                last_name="Smith",
                email="alice.smith@example.com",
                phone="+1-212-555-5001",
                is_active=True
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="Robert",
                last_name="Johnson",
                email="robert.johnson@example.com",
                phone="+1-212-555-5002",
                is_active=True
            ),
        ]
        
        for customer in customers:
            db.add(customer)
        db.flush()
        logger.info(f"✓ Created {len(customers)} customers")
        
        # ====================================================================
        # 5. CREATE USERS & ROLES
        # ====================================================================
        logger.info("Creating authenticated users and role profiles...")
        
        # password123 hashed with standard passlib context
        hashed_password = "$2b$12$KpmDXGSTHXSVcyR9etDgPO1Jv7XMI6e6rpHseJPHaEgWv2dgp51ZW"
        
        # 5.1 Admin/Owner User
        owner_user = User(
            id=uuid.uuid4(),
            email="owner@salonai.com",
            hashed_password=hashed_password,
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(owner_user)
        db.flush()
        
        owner_profile = Admin(
            id=uuid.uuid4(),
            user_id=owner_user.id,
            first_name="Balu",
            last_name="Owner",
            email="owner@salonai.com",
            phone="+1-212-555-9000"
        )
        db.add(owner_profile)
        

        
        # 5.3 Staff User (linked to Marcus Stylist)
        staff_user = User(
            id=uuid.uuid4(),
            email="marcus@salonai.com",
            hashed_password=hashed_password,
            role=UserRole.STAFF,
            is_active=True,
            staff_id=staff_members[1].id
        )
        db.add(staff_user)
        
        # 5.4 Customer User
        customer_user = User(
            id=uuid.uuid4(),
            email="customer@example.com",
            hashed_password=hashed_password,
            role=UserRole.USER,
            is_active=True,
            customer_id=customers[0].id
        )
        db.add(customer_user)
        
        db.flush()
        logger.info("✓ Created users for Admin, Staff, and Customer profiles")
        
        # ====================================================================
        # 6. CREATE SAMPLE APPOINTMENTS
        # ====================================================================
        logger.info("Creating appointments...")
        
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        
        appointments = [
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[0].id,
                branch_id=branches[0].id,
                staff_id=staff_members[1].id,  # Marcus
                service_id=services[0].id,  # Haircut
                start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
                end_time=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
                status=AppointmentStatus.CONFIRMED,
                notes="Client prefers tiered haircut"
            ),
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[1].id,
                branch_id=branches[0].id,
                staff_id=staff_members[0].id,  # Alexandra
                service_id=services[1].id,  # Color
                start_time=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
                end_time=tomorrow.replace(hour=16, minute=30, second=0, microsecond=0),
                status=AppointmentStatus.CONFIRMED,
                notes="Full balayage styling"
            ),
        ]
        
        for appointment in appointments:
            db.add(appointment)
        
        # ====================================================================
        # 7. CREATE SAMPLE LEADS & ANALYTICS
        # ====================================================================
        logger.info("Creating leads and business intelligence records...")
        
        lead = Lead(
            id=uuid.uuid4(),
            branch_id=branches[0].id,
            first_name="Jennifer",
            last_name="Taylor",
            email="jennifer.taylor@example.com",
            phone="+1-212-555-6001",
            source="Website",
            status=LeadStatus.NEW,
            notes="Interested in color specialist appointments"
        )
        db.add(lead)
        
        analytics = [
            AnalyticsRecord(metric_name="daily_active_users", metric_value=4.0, dimensions='{"platform":"web"}'),
            AnalyticsRecord(metric_name="total_completed_appointments", metric_value=12.0, dimensions='{"branch":"DTE"}'),
            AnalyticsRecord(metric_name="total_revenue_usd", metric_value=1020.0, dimensions='{"branch":"all"}')
        ]
        for a in analytics:
            db.add(a)
            
        # Commit all changes
        db.commit()
        
        logger.info("✅ Database seeding on Supabase completed successfully!")
        logger.info(f"   - {len(branches)} branches")
        logger.info(f"   - {len(services)} services")
        logger.info(f"   - {len(staff_members)} staff members")
        logger.info(f"   - {len(customers)} customers")
        logger.info(f"   - {len(appointments)} appointments")
        logger.info(f"   - 4 default login roles created with password 'password123'")
    except Exception as e:
        logger.error(f"❌ Error seeding database: {str(e)}", exc_info=True)
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
