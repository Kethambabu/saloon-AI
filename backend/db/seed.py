"""
Database Seeder Script for SalonAI Workforce Platform.
Populates the database with realistic, high-quality sample data for development and testing.
Runnable directly from CLI.
"""

import os
import sys
import uuid
import logging
from datetime import datetime, timedelta, timezone

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.sql import text
from db import (
    engine,
    db_transaction,
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
    AppointmentStatus,
    LeadStatus,
    ReviewStatus
)
from core.security import hash_password


# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def clean_existing_data(db) -> None:
    """Deletes existing data in order of dependency to respect foreign key constraints."""
    logger.info("Cleaning existing database records...")
    # Order of deletion is critical to avoid violating foreign key constraints
    db.query(User).delete()
    db.query(Review).delete()
    db.query(Appointment).delete()
    db.query(Lead).delete()
    db.query(Staff).delete()
    db.query(Branch).delete()
    db.query(Customer).delete()
    db.query(Service).delete()
    db.commit()
    logger.info("Cleaned existing data.")


def seed_database() -> None:
    """Main seeder logic executing inside a single database transaction."""
    logger.info("Starting database seeding process...")

    # Automatically create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")

    with db_transaction() as db:
        # 1. Clean existing records for a fresh state
        clean_existing_data(db)

        # 2. Seed Branches (Locations)
        logger.info("Seeding Branches...")
        branch_downtown = Branch(
            name="SalonAI Downtown Elite",
            code="BR-DWTN-01",
            address="100 Enterprise Way, Suite A",
            city="Metropolis",
            phone="555-0100",
            email="downtown@salonai.com",
            is_active=True
        )
        branch_uptown = Branch(
            name="SalonAI Uptown Oasis",
            code="BR-UPTN-02",
            address="450 Serenity Lane, Building 3",
            city="Metropolis",
            phone="555-0200",
            email="uptown@salonai.com",
            is_active=True
        )
        db.add_all([branch_downtown, branch_uptown])
        db.commit()  # Commit to populate UUIDs
        logger.info(f"Seed branches created: {branch_downtown.name}, {branch_uptown.name}")

        # 3. Seed Services
        logger.info("Seeding Services...")
        srv_haircut = Service(
            name="Signature Precision Haircut",
            description="Premium tailored wash, cut, scalp massage, and style blowout.",
            price=85.00,
            duration_minutes=60,
            is_active=True
        )
        srv_color = Service(
            name="Balayage & Creative Color",
            description="Custom artistic coloring and toning with high-end premium bond protectors.",
            price=220.00,
            duration_minutes=150,
            is_active=True
        )
        srv_facial = Service(
            name="Hydrating Deep-Cleansing Facial",
            description="Organic advanced botanical exfoliation, extraction, and antioxidant hydration treatment.",
            price=120.00,
            duration_minutes=75,
            is_active=True
        )
        srv_massage = Service(
            name="Himalayan Hot Stone Massage",
            description="Deep tissue somatic therapy utilizing warm mineral-rich salt rocks.",
            price=150.00,
            duration_minutes=90,
            is_active=True
        )
        db.add_all([srv_haircut, srv_color, srv_facial, srv_massage])
        db.commit()
        logger.info("Seed services created successfully.")

        # 4. Seed Staff members
        logger.info("Seeding Staff...")
        staff_stylist1 = Staff(
            branch_id=branch_downtown.id,
            first_name="Marcus",
            last_name="Vance",
            email="marcus@salonai.com",
            phone="555-1111",
            role="Senior Stylist",
            is_active=True
        )
        staff_stylist2 = Staff(
            branch_id=branch_uptown.id,
            first_name="Elena",
            last_name="Rostova",
            email="elena@salonai.com",
            phone="555-2222",
            role="Color Specialist",
            is_active=True
        )
        staff_therapist = Staff(
            branch_id=branch_uptown.id,
            first_name="Kai",
            last_name="Chen",
            email="kai@salonai.com",
            phone="555-3333",
            role="Licensed Massage Therapist",
            is_active=True
        )
        staff_aesthetician = Staff(
            branch_id=branch_downtown.id,
            first_name="Sarah",
            last_name="Jenkins",
            email="sarah@salonai.com",
            phone="555-4444",
            role="Master Esthetician",
            is_active=True
        )
        db.add_all([staff_stylist1, staff_stylist2, staff_therapist, staff_aesthetician])
        db.commit()
        logger.info("Seed staff members created.")

        # 4.5. Seed Users (Authenticated credentials)
        logger.info("Seeding Users...")
        default_pwd_hash = hash_password("password123")
        
        user_owner = User(
            email="owner@salonai.com",
            hashed_password=default_pwd_hash,
            role=UserRole.OWNER,
            is_active=True
        )
        user_manager = User(
            email="manager@salonai.com",
            hashed_password=default_pwd_hash,
            role=UserRole.MANAGER,
            is_active=True
        )
        user_staff1 = User(
            email="marcus@salonai.com",
            hashed_password=default_pwd_hash,
            role=UserRole.STAFF,
            staff_id=staff_stylist1.id,
            is_active=True
        )
        user_staff2 = User(
            email="elena@salonai.com",
            hashed_password=default_pwd_hash,
            role=UserRole.STAFF,
            staff_id=staff_stylist2.id,
            is_active=True
        )
        user_staff3 = User(
            email="kai@salonai.com",
            hashed_password=default_pwd_hash,
            role=UserRole.STAFF,
            staff_id=staff_therapist.id,
            is_active=True
        )
        db.add_all([user_owner, user_manager, user_staff1, user_staff2, user_staff3])
        db.commit()
        logger.info("Seed authenticated users created.")


        # 5. Seed Customers
        logger.info("Seeding Customers...")
        cust1 = Customer(
            first_name="Alice",
            last_name="Smith",
            email="alice.smith@gmail.com",
            phone="555-9001",
            is_active=True
        )
        cust2 = Customer(
            first_name="Bob",
            last_name="Miller",
            email="bob.miller@yahoo.com",
            phone="555-9002",
            is_active=True
        )
        cust3 = Customer(
            first_name="Diana",
            last_name="Prince",
            email="diana.prince@outlook.com",
            phone="555-9003",
            is_active=True
        )
        db.add_all([cust1, cust2, cust3])
        db.commit()
        logger.info("Seed customers created.")

        # 6. Seed Appointments (Historically completed, upcoming pending, upcoming confirmed)
        logger.info("Seeding Appointments...")
        now = datetime.now(timezone.utc)

        # Completed past appointment
        appt1 = Appointment(
            customer_id=cust1.id,
            branch_id=branch_downtown.id,
            staff_id=staff_stylist1.id,
            service_id=srv_haircut.id,
            start_time=now - timedelta(days=2, hours=4),
            end_time=now - timedelta(days=2, hours=3),
            status=AppointmentStatus.COMPLETED,
            notes="Client wanted to keep length but add layers. Highly satisfied."
        )

        # Completed past appointment with therapist
        appt2 = Appointment(
            customer_id=cust2.id,
            branch_id=branch_uptown.id,
            staff_id=staff_therapist.id,
            service_id=srv_massage.id,
            start_time=now - timedelta(days=1, hours=2),
            end_time=now - timedelta(days=1, hours=0.5),
            status=AppointmentStatus.COMPLETED,
            notes="Prefers medium to firm pressure on back shoulders."
        )

        # Confirmed upcoming appointment
        appt3 = Appointment(
            customer_id=cust3.id,
            branch_id=branch_downtown.id,
            staff_id=staff_aesthetician.id,
            service_id=srv_facial.id,
            start_time=now + timedelta(days=1, hours=3),
            end_time=now + timedelta(days=1, hours=4.25),
            status=AppointmentStatus.CONFIRMED,
            notes="First time customer. Focus on hydration and gentle botanical extracts."
        )

        # Pending upcoming appointment
        appt4 = Appointment(
            customer_id=cust1.id,
            branch_id=branch_uptown.id,
            staff_id=staff_stylist2.id,
            service_id=srv_color.id,
            start_time=now + timedelta(days=3, hours=1),
            end_time=now + timedelta(days=3, hours=3.5),
            status=AppointmentStatus.PENDING,
            notes="Client requested rose gold tones. Stylist needs to review current base color."
        )

        db.add_all([appt1, appt2, appt3, appt4])
        db.commit()
        logger.info("Seed appointments created.")

        # 7. Seed Reviews for completed appointments
        logger.info("Seeding Reviews...")
        rev1 = Review(
            customer_id=cust1.id,
            branch_id=branch_downtown.id,
            appointment_id=appt1.id,
            rating=5,
            comment="Marcus was fantastic! The precision haircut was exactly what I wanted. Beautiful layering!",
            status=ReviewStatus.APPROVED
        )
        rev2 = Review(
            customer_id=cust2.id,
            branch_id=branch_uptown.id,
            appointment_id=appt2.id,
            rating=4,
            comment="Excellent hot stone treatment. Kai was highly skilled. Left feeling super relaxed.",
            status=ReviewStatus.APPROVED
        )
        db.add_all([rev1, rev2])
        db.commit()
        logger.info("Seed reviews created.")

        # 8. Seed Leads
        logger.info("Seeding Leads...")
        lead1 = Lead(
            branch_id=branch_downtown.id,
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@gmail.com",
            phone="555-8001",
            source="website",
            status=LeadStatus.NEW,
            notes="Requested information about wedding package pricing."
        )
        lead2 = Lead(
            branch_id=branch_uptown.id,
            first_name="Robert",
            last_name="Glover",
            email="rob.g@outlook.com",
            phone="555-8002",
            source="social_media",
            status=LeadStatus.CONTACTED,
            notes="Called back to discuss monthly massage subscriptions. Very interested."
        )
        lead3 = Lead(
            branch_id=branch_downtown.id,
            first_name="Sarah",
            last_name="Connor",
            email="sconnor@cyberdyne.net",
            phone="555-1984",
            source="referral",
            status=LeadStatus.CONVERTED,
            notes="Referred by Alice Smith. Converted directly to Customer (cust3)."
        )
        db.add_all([lead1, lead2, lead3])
        db.commit()
        logger.info("Seed leads created.")

    logger.info("Database seeding successfully completed!")


if __name__ == "__main__":
    seed_database()
