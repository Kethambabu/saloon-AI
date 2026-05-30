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
        logger.info("🌱 Seeding SalonAI Workforce database on Supabase...")
        
        # ====================================================================
        # 1. CREATE BRANCHES (if not exist)
        # ====================================================================
        logger.info("Checking and creating branches...")
        branches = []
        branch_data = [
            ("Downtown Elite", "DTE", "123 Main Street", "New York", "+1-212-555-0100", "downtown@salonai.com"),
            ("Westside Boutique", "WSB", "456 Park Avenue", "Los Angeles", "+1-310-555-0200", "westside@salonai.com"),
            ("Midtown Luxe", "MTL", "789 Michigan Avenue", "Chicago", "+1-312-555-0300", "midtown@salonai.com"),
        ]
        for name, code, addr, city, phone, email in branch_data:
            existing = db.query(Branch).filter(Branch.code == code).first()
            if not existing:
                b = Branch(id=uuid.uuid4(), name=name, code=code, address=addr, city=city, phone=phone, email=email, is_active=True)
                db.add(b)
                branches.append(b)
                logger.info(f"   ✓ Created branch: {name}")
            else:
                branches.append(existing)
        db.flush()

        # ====================================================================
        # 2. CREATE SERVICES (if not exist)
        # ====================================================================
        logger.info("Checking and creating services...")
        services = []
        service_data = [
            ("Signature Precision Haircut", "Professional haircut with detailed styling consultation", Decimal("85.00"), 60),
            ("Balayage & Creative Color", "Hand-painted highlighting technique with custom color blending", Decimal("220.00"), 150),
            ("Hydrating Deep-Cleansing Facial", "Luxurious 75-minute facial with premium skincare products", Decimal("120.00"), 75),
            ("Himalayan Hot Stone Massage", "Soothing massage with warm stone therapy and aromatherapy", Decimal("150.00"), 90),
        ]
        for name, desc, price, dur in service_data:
            existing = db.query(Service).filter(Service.name == name).first()
            if not existing:
                s = Service(id=uuid.uuid4(), name=name, description=desc, price=price, duration_minutes=dur, is_active=True)
                db.add(s)
                services.append(s)
                logger.info(f"   ✓ Created service: {name}")
            else:
                services.append(existing)
        db.flush()

        # ====================================================================
        # 3. CREATE STAFF (if not exist)
        # ====================================================================
        logger.info("Checking and creating staff...")
        staff_members = []
        staff_data = [
            (branches[0].id, "Alexandra", "Chen", "alex.chen@salonai.com", "+1-212-555-1001", "Senior Stylist"),
            (branches[0].id, "Marcus", "Johnson", "marcus.johnson@salonai.com", "+1-212-555-1002", "Color Specialist"),
            (branches[1].id, "Isabella", "Martinez", "isabella.martinez@salonai.com", "+1-310-555-2001", "Senior Stylist"),
        ]
        for b_id, fn, ln, email, phone, role in staff_data:
            existing = db.query(Staff).filter(Staff.email == email).first()
            if not existing:
                st = Staff(id=uuid.uuid4(), branch_id=b_id, first_name=fn, last_name=ln, email=email, phone=phone, role=role, is_active=True)
                db.add(st)
                staff_members.append(st)
                logger.info(f"   ✓ Created staff: {fn} {ln}")
            else:
                staff_members.append(existing)
        db.flush()

        # ====================================================================
        # 4. CREATE CUSTOMERS (if not exist)
        # ====================================================================
        logger.info("Checking and creating customers...")
        customers = []
        customer_data = [
            ("Alice", "Smith", "alice.smith@example.com", "+1-212-555-5001"),
            ("Robert", "Johnson", "robert.johnson@example.com", "+1-212-555-5002"),
        ]
        for fn, ln, email, phone in customer_data:
            existing = db.query(Customer).filter(Customer.email == email).first()
            if not existing:
                c = Customer(id=uuid.uuid4(), first_name=fn, last_name=ln, email=email, phone=phone, is_active=True)
                db.add(c)
                customers.append(c)
                logger.info(f"   ✓ Created customer: {fn} {ln}")
            else:
                customers.append(existing)
        db.flush()

        # ====================================================================
        # 5. CREATE USERS & ROLES (if not exist)
        # ====================================================================
        logger.info("Checking and creating users...")
        hashed_password = "$2b$12$KpmDXGSTHXSVcyR9etDgPO1Jv7XMI6e6rpHseJPHaEgWv2dgp51ZW"
        
        # Admin
        existing_owner = db.query(User).filter(User.email == "owner@salonai.com").first()
        if not existing_owner:
            owner_user = User(id=uuid.uuid4(), email="owner@salonai.com", hashed_password=hashed_password, role=UserRole.ADMIN, is_active=True)
            db.add(owner_user)
            db.flush()
            owner_profile = Admin(id=uuid.uuid4(), user_id=owner_user.id, first_name="Balu", last_name="Owner", email="owner@salonai.com", phone="+1-212-555-9000")
            db.add(owner_profile)
            logger.info("   ✓ Created owner user")
            
        # Staff
        existing_staff_user = db.query(User).filter(User.email == "marcus@salonai.com").first()
        if not existing_staff_user and len(staff_members) > 1:
            staff_user = User(id=uuid.uuid4(), email="marcus@salonai.com", hashed_password=hashed_password, role=UserRole.STAFF, is_active=True, staff_id=staff_members[1].id)
            db.add(staff_user)
            logger.info("   ✓ Created staff user (Marcus)")

        # Customer
        existing_cust_user = db.query(User).filter(User.email == "customer@example.com").first()
        if not existing_cust_user and len(customers) > 0:
            customer_user = User(id=uuid.uuid4(), email="customer@example.com", hashed_password=hashed_password, role=UserRole.USER, is_active=True, customer_id=customers[0].id)
            db.add(customer_user)
            logger.info("   ✓ Created customer user")
        db.flush()

        # ====================================================================
        # 6. CREATE SAMPLE APPOINTMENTS (if not exist)
        # ====================================================================
        logger.info("Checking and creating appointments...")
        if db.query(Appointment).count() == 0 and len(customers) > 1 and len(staff_members) > 1 and len(services) > 1:
            now = datetime.now(timezone.utc)
            tomorrow = now + timedelta(days=1)
            appointments = [
                Appointment(
                    id=uuid.uuid4(), customer_id=customers[0].id, branch_id=branches[0].id,
                    staff_id=staff_members[1].id, service_id=services[0].id,
                    start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
                    end_time=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
                    status=AppointmentStatus.CONFIRMED, notes="Client prefers tiered haircut"
                ),
                Appointment(
                    id=uuid.uuid4(), customer_id=customers[1].id, branch_id=branches[0].id,
                    staff_id=staff_members[0].id, service_id=services[1].id,
                    start_time=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
                    end_time=tomorrow.replace(hour=16, minute=30, second=0, microsecond=0),
                    status=AppointmentStatus.CONFIRMED, notes="Full balayage styling"
                ),
            ]
            for appt in appointments:
                db.add(appt)
            logger.info(f"   ✓ Created {len(appointments)} appointments")

        # Leads & Analytics
        if db.query(Lead).count() == 0:
            lead = Lead(
                id=uuid.uuid4(), branch_id=branches[0].id, first_name="Jennifer", last_name="Taylor",
                email="jennifer.taylor@example.com", phone="+1-212-555-6001", source="Website",
                status=LeadStatus.NEW, notes="Interested in color specialist appointments"
            )
            db.add(lead)
            logger.info("   ✓ Created sample lead")

        if db.query(AnalyticsRecord).count() == 0:
            analytics = [
                AnalyticsRecord(metric_name="daily_active_users", metric_value=4.0, dimensions='{"platform":"web"}'),
                AnalyticsRecord(metric_name="total_completed_appointments", metric_value=12.0, dimensions='{"branch":"DTE"}'),
                AnalyticsRecord(metric_name="total_revenue_usd", metric_value=1020.0, dimensions='{"branch":"all"}')
            ]
            for a in analytics:
                db.add(a)
            logger.info("   ✓ Created analytics records")

        db.commit()
        logger.info("✅ Database seeding completed successfully!")
    except Exception as e:
        logger.error(f"❌ Error seeding database: {str(e)}", exc_info=True)
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
