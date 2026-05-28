"""
Database Seed Script for SalonAI Workforce Platform.
Creates realistic sample data for branches, staff, customers, services, and appointments.
Run this after migrations to populate the database with test data.

Usage:
    python backend/db/seed.py
    or from Python:
    from backend.db.seed import seed_database
    seed_database()
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
    Base.metadata.create_all(bind=engine)
    logger.info("✓ Database tables verified/created")
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_branches = db.query(Branch).count()
        if existing_branches > 0:
            logger.info("ℹ️  Database already seeded. Skipping...")
            db.close()
            return
        
        logger.info("🌱 Seeding SalonAI Workforce database...")
        
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
            Branch(
                id=uuid.uuid4(),
                name="Riverside Premium",
                code="RSP",
                address="321 River Road",
                city="San Francisco",
                phone="+1-415-555-0400",
                email="riverside@salonai.com",
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
            Service(
                id=uuid.uuid4(),
                name="Blowout & Styling",
                description="Professional blowout with premium styling products",
                price=Decimal("65.00"),
                duration_minutes=45,
                is_active=True
            ),
            Service(
                id=uuid.uuid4(),
                name="Manicure Deluxe",
                description="Extended manicure with gel polish and nail art",
                price=Decimal("55.00"),
                duration_minutes=60,
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
        
        staff_data = [
            # Downtown Elite branch
            (branches[0].id, "Alexandra", "Chen", "alex.chen@salonai.com", "+1-212-555-1001", "Senior Stylist"),
            (branches[0].id, "Marcus", "Johnson", "marcus.johnson@salonai.com", "+1-212-555-1002", "Color Specialist"),
            (branches[0].id, "Sofia", "Rodriguez", "sofia.rodriguez@salonai.com", "+1-212-555-1003", "Esthetician"),
            (branches[0].id, "James", "Williams", "james.williams@salonai.com", "+1-212-555-1004", "Massage Therapist"),
            # Westside Boutique branch
            (branches[1].id, "Isabella", "Martinez", "isabella.martinez@salonai.com", "+1-310-555-2001", "Senior Stylist"),
            (branches[1].id, "David", "Lee", "david.lee@salonai.com", "+1-310-555-2002", "Color Specialist"),
            (branches[1].id, "Emma", "Thompson", "emma.thompson@salonai.com", "+1-310-555-2003", "Esthetician"),
            # Midtown Luxe branch
            (branches[2].id, "Daniel", "Brown", "daniel.brown@salonai.com", "+1-312-555-3001", "Senior Stylist"),
            (branches[2].id, "Jessica", "Garcia", "jessica.garcia@salonai.com", "+1-312-555-3002", "Color Specialist"),
            # Riverside Premium branch
            (branches[3].id, "Michael", "Anderson", "michael.anderson@salonai.com", "+1-415-555-4001", "Senior Stylist"),
            (branches[3].id, "Rachel", "White", "rachel.white@salonai.com", "+1-415-555-4002", "Esthetician"),
        ]
        
        staff_members = []
        for branch_id, first, last, email, phone, role in staff_data:
            staff = Staff(
                id=uuid.uuid4(),
                branch_id=branch_id,
                first_name=first,
                last_name=last,
                email=email,
                phone=phone,
                role=role,
                is_active=True
            )
            staff_members.append(staff)
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
            Customer(
                id=uuid.uuid4(),
                first_name="Carol",
                last_name="Williams",
                email="carol.williams@example.com",
                phone="+1-310-555-5003",
                is_active=True
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="David",
                last_name="Brown",
                email="david.brown@example.com",
                phone="+1-312-555-5004",
                is_active=True
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="Elizabeth",
                last_name="Davis",
                email="elizabeth.davis@example.com",
                phone="+1-415-555-5005",
                is_active=True
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="Frank",
                last_name="Miller",
                email="frank.miller@example.com",
                phone="+1-212-555-5006",
                is_active=True
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="Grace",
                last_name="Wilson",
                email="grace.wilson@example.com",
                phone="+1-310-555-5007",
                is_active=True
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="Henry",
                last_name="Moore",
                email="henry.moore@example.com",
                phone="+1-312-555-5008",
                is_active=True
            ),
        ]
        
        for customer in customers:
            db.add(customer)
        db.flush()
        
        logger.info(f"✓ Created {len(customers)} customers")
        
        # ====================================================================
        # 5. CREATE SAMPLE APPOINTMENTS
        # ====================================================================
        logger.info("Creating sample appointments...")
        
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        next_week = now + timedelta(days=7)
        
        appointments = [
            # Near-future appointments
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[0].id,
                branch_id=branches[0].id,
                staff_id=staff_members[0].id,
                service_id=services[0].id,  # Haircut
                start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
                end_time=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
                status=AppointmentStatus.CONFIRMED,
                notes="Client prefers layered cut"
            ),
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[1].id,
                branch_id=branches[0].id,
                staff_id=staff_members[1].id,
                service_id=services[1].id,  # Color
                start_time=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
                end_time=tomorrow.replace(hour=16, minute=30, second=0, microsecond=0),
                status=AppointmentStatus.CONFIRMED,
                notes="Full balayage, warm tones"
            ),
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[2].id,
                branch_id=branches[1].id,
                staff_id=staff_members[4].id,
                service_id=services[0].id,  # Haircut
                start_time=next_week.replace(hour=11, minute=0, second=0, microsecond=0),
                end_time=next_week.replace(hour=12, minute=0, second=0, microsecond=0),
                status=AppointmentStatus.CONFIRMED,
                notes="Regular maintenance cut"
            ),
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[3].id,
                branch_id=branches[2].id,
                staff_id=staff_members[8].id,
                service_id=services[3].id,  # Massage
                start_time=next_week.replace(hour=15, minute=0, second=0, microsecond=0),
                end_time=next_week.replace(hour=16, minute=30, second=0, microsecond=0),
                status=AppointmentStatus.PENDING,
                notes="First time massage client, prefer lighter pressure"
            ),
            # Past completed appointments
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[0].id,
                branch_id=branches[0].id,
                staff_id=staff_members[0].id,
                service_id=services[0].id,
                start_time=now - timedelta(days=14),
                end_time=now - timedelta(days=14) + timedelta(hours=1),
                status=AppointmentStatus.COMPLETED,
                notes="Regular client"
            ),
            Appointment(
                id=uuid.uuid4(),
                customer_id=customers[4].id,
                branch_id=branches[3].id,
                staff_id=staff_members[10].id,
                service_id=services[2].id,  # Facial
                start_time=now - timedelta(days=7),
                end_time=now - timedelta(days=7) + timedelta(minutes=75),
                status=AppointmentStatus.COMPLETED,
                notes="Spring renewal facial"
            ),
        ]
        
        for appointment in appointments:
            db.add(appointment)
        db.flush()
        
        logger.info(f"✓ Created {len(appointments)} appointments")
        
        # ====================================================================
        # 6. CREATE SAMPLE LEADS
        # ====================================================================
        logger.info("Creating sample leads...")
        
        leads = [
            Lead(
                id=uuid.uuid4(),
                branch_id=branches[0].id,
                first_name="Jennifer",
                last_name="Taylor",
                email="jennifer.taylor@example.com",
                phone="+1-212-555-6001",
                source="Website",
                status=LeadStatus.NEW,
                notes="Interested in hair color service"
            ),
            Lead(
                id=uuid.uuid4(),
                branch_id=branches[1].id,
                first_name="Christopher",
                last_name="Harris",
                email="chris.harris@example.com",
                phone="+1-310-555-6002",
                source="Google",
                status=LeadStatus.CONTACTED,
                notes="Inquiry about membership plans"
            ),
            Lead(
                id=uuid.uuid4(),
                branch_id=branches[2].id,
                first_name="Michelle",
                last_name="Clark",
                email="michelle.clark@example.com",
                phone="+1-312-555-6003",
                source="Referral",
                status=LeadStatus.CONVERTED,
                notes="Converted to customer, first appointment scheduled"
            ),
        ]
        
        for lead in leads:
            db.add(lead)
        db.flush()
        
        logger.info(f"✓ Created {len(leads)} leads")
        
        # Commit all changes
        db.commit()
        
        logger.info("✅ Database seeding completed successfully!")
        logger.info(f"   - {len(branches)} branches")
        logger.info(f"   - {len(services)} services")
        logger.info(f"   - {len(staff_members)} staff members")
        logger.info(f"   - {len(customers)} customers")
        logger.info(f"   - {len(appointments)} appointments")
        logger.info(f"   - {len(leads)} leads")
except Exception as e:
        logger.error(f"❌ Error seeding database: {str(e)}", exc_info=True)
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
