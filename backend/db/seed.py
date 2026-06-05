"""
Database Seed Script for SalonAI Workforce Platform.
Creates 1 branch, 4 specialized staff, 4 staff logins, 1 owner login,
and starts all transaction data (appointments, leads, reviews) at zero.

Usage:
    python backend/db/seed.py
"""

import os
import sys
import uuid
import logging
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
    Lead,
    Review,
    User,
    UserRole,
    Admin,
    AnalyticsRecord,
    ServiceRecommendation,
    BusinessMetricsHistory,
    Notification
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_database():
    """
    Seed the database with the core dynamic configuration.
    """
    logger.info("Verifying and creating database schemas on Supabase...")
    Base.metadata.create_all(bind=engine)
    logger.info("✓ Database tables verified/created successfully.")
    
    db = SessionLocal()
    
    try:
        logger.info("🌱 Seeding SalonAI Workforce database...")
        
        # Clear existing transactional tables to ensure they start at 0
        logger.info("Clearing old transactional data for fresh dynamic run...")
        db.query(Notification).delete()
        db.query(Review).delete()
        db.query(Lead).delete()
        db.query(Appointment).delete()
        db.query(AnalyticsRecord).delete()
        db.query(BusinessMetricsHistory).delete()
        db.query(User).delete()
        db.query(Admin).delete()
        db.query(Staff).delete()
        db.query(ServiceRecommendation).delete()
        db.query(Service).delete()
        db.query(Branch).delete()
        db.query(Customer).delete()
        db.commit()
        
        # ====================================================================
        # 1. CREATE BRANCH (only one)
        # ====================================================================
        logger.info("Creating single branch...")
        branch = Branch(
            id=uuid.uuid4(),
            name="Main Salon",
            code="MS1",
            address="123 Main Street",
            city="New York",
            phone="+1-212-555-0100",
            email="mainsalon@salonai.com",
            is_active=True
        )
        db.add(branch)
        db.flush()
        logger.info(f"   ✓ Created branch: {branch.name}")

        # ====================================================================
        # 2. CREATE SERVICES
        # ====================================================================
        logger.info("Creating services...")
        services = [
            Service(id=uuid.uuid4(), name="Precision Haircut", description="Professional haircut with detailed styling consultation", price=Decimal("85.00"), duration_minutes=60, is_active=True),
            Service(id=uuid.uuid4(), name="Bridal Makeup", description="Hand-painted highlighting technique with custom color blending", price=Decimal("220.00"), duration_minutes=120, is_active=True),
            Service(id=uuid.uuid4(), name="Revitalizing Facial", description="Luxurious 75-minute facial with premium skincare products", price=Decimal("120.00"), duration_minutes=75, is_active=True),
            Service(id=uuid.uuid4(), name="Hot Stone Massage", description="Soothing massage with warm stone therapy and aromatherapy", price=Decimal("150.00"), duration_minutes=90, is_active=True),
            Service(id=uuid.uuid4(), name="Hair Spa", description="Rejuvenating conditioning treatment for hair health", price=Decimal("50.00"), duration_minutes=45, is_active=True),
            Service(id=uuid.uuid4(), name="Beard Trim", description="Precision beard trimming and styling", price=Decimal("15.00"), duration_minutes=20, is_active=True),
        ]
        for s in services:
            db.add(s)
        db.flush()
        logger.info(f"   ✓ Created {len(services)} services")

        # ====================================================================
        # 2b. CREATE SERVICE RECOMMENDATIONS
        # ====================================================================
        logger.info("Creating service recommendations...")
        service_map = {s.name: s for s in services}
        recs = [
            ServiceRecommendation(id=uuid.uuid4(), service_id=service_map["Precision Haircut"].id, recommended_service_id=service_map["Hair Spa"].id, confidence_score=0.9),
            ServiceRecommendation(id=uuid.uuid4(), service_id=service_map["Precision Haircut"].id, recommended_service_id=service_map["Beard Trim"].id, confidence_score=0.8),
            ServiceRecommendation(id=uuid.uuid4(), service_id=service_map["Revitalizing Facial"].id, recommended_service_id=service_map["Hot Stone Massage"].id, confidence_score=0.85),
        ]
        for rec in recs:
            db.add(rec)
        db.flush()
        logger.info("   ✓ Created service recommendations")

        # ====================================================================
        # 3. CREATE 4 STAFF MEMBERS (representing 4 specializations)
        # ====================================================================
        logger.info("Creating 4 specialized staff...")
        staff_list = [
            Staff(id=uuid.uuid4(), branch_id=branch.id, first_name="Priya", last_name="Sharma", email="priya@salonai.com", phone="+1-212-555-1001", role="Hair Specialist", is_active=True),
            Staff(id=uuid.uuid4(), branch_id=branch.id, first_name="Alexandra", last_name="Chen", email="alex@salonai.com", phone="+1-212-555-1002", role="Makeup Specialist", is_active=True),
            Staff(id=uuid.uuid4(), branch_id=branch.id, first_name="Marcus", last_name="Johnson", email="marcus@salonai.com", phone="+1-212-555-1003", role="Facial Specialist", is_active=True),
            Staff(id=uuid.uuid4(), branch_id=branch.id, first_name="Isabella", last_name="Martinez", email="isabella@salonai.com", phone="+1-212-555-1004", role="Massage Specialist", is_active=True),
        ]
        for st in staff_list:
            db.add(st)
        db.flush()
        logger.info(f"   ✓ Created {len(staff_list)} staff members")

        # ====================================================================
        # 4. CREATE USERS & LOGINS
        # ====================================================================
        logger.info("Creating user accounts...")
        # Common password is "password"
        hashed_password = "$2b$12$KpmDXGSTHXSVcyR9etDgPO1Jv7XMI6e6rpHseJPHaEgWv2dgp51ZW"
        
        # 1. Admin/Owner (keep same owner@salonai.com login)
        admin_user = User(
            id=uuid.uuid4(),
            email="owner@salonai.com",
            hashed_password=hashed_password,
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        db.flush()
        
        admin_profile = Admin(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            first_name="Balu",
            last_name="Owner",
            email="owner@salonai.com",
            phone="+1-212-555-9000"
        )
        db.add(admin_profile)
        logger.info("   ✓ Created Admin/Owner login: owner@salonai.com / password")

        # 2. Staff Logins (Priya, Alexandra, Marcus, Isabella)
        staff_user_map = {}
        for st in staff_list:
            user = User(
                id=uuid.uuid4(),
                email=st.email,
                hashed_password=hashed_password,
                role=UserRole.STAFF,
                is_active=True,
                staff_id=st.id
            )
            db.add(user)
            staff_user_map[st.email] = user
            logger.info(f"   ✓ Created Staff login: {st.email} / password")
            
        # 3. Create one sample Customer login to start with
        customer = Customer(
            id=uuid.uuid4(),
            first_name="Alice",
            last_name="Smith",
            email="customer@example.com",
            phone="+1-212-555-5001",
            is_active=True,
            loyalty_points=0
        )
        db.add(customer)
        db.flush()
        
        customer_user = User(
            id=uuid.uuid4(),
            email="customer@example.com",
            hashed_password=hashed_password,
            role=UserRole.CUSTOMER,
            is_active=True,
            customer_id=customer.id
        )
        db.add(customer_user)
        logger.info("   ✓ Created Customer login: customer@example.com / password")

        db.commit()
        logger.info("✅ Database seeding completed successfully! All metrics are starting at zero.")
    except Exception as e:
        logger.error(f"❌ Error seeding database: {str(e)}", exc_info=True)
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
