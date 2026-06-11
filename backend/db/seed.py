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

        # ====================================================================
        # 5. CREATE KNOWLEDGE DOCUMENTS & SPECIAL OFFERS (Dynamic Receptionist KB)
        # ====================================================================
        logger.info("Creating dynamic knowledge documents...")
        from db.models import KnowledgeDocument, SpecialOffer
        import datetime
        
        # Clear existing knowledge/offers
        db.query(KnowledgeDocument).delete()
        db.query(SpecialOffer).delete()
        db.commit()

        # Seed static knowledge contents into KnowledgeDocument table
        docs = [
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Business Hours & Scheduling",
                document_type="timings",
                content=(
                    "SalonAI is open daily from 9:00 AM to 8:00 PM (UTC). "
                    "Last appointment slots are based on service duration to ensure completion before closing. "
                    "Online booking is available 24/7 through our AI receptionist Clara. "
                    "Walk-ins are welcome based on availability, but we recommend advance booking for "
                    "guaranteed slots, especially on weekends."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Cancellation Policy",
                document_type="cancellation_policy",
                content=(
                    "SalonAI requires 24-hour advance notice for appointment cancellations. "
                    "Late cancellations (less than 24 hours) may incur a 50% service charge. "
                    "No-shows will be charged the full service amount. "
                    "We understand emergencies happen — please contact us as soon as possible, "
                    "and we'll do our best to accommodate rescheduling."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Pricing & Payment Policy",
                document_type="refund_policy",
                content=(
                    "All prices are displayed inclusive of service costs. "
                    "We accept cash, all major credit/debit cards, Apple Pay, and Google Pay. "
                    "Gratuities are appreciated but never expected. "
                    "Package bundles and loyalty memberships are available — ask our team about "
                    "the SalonAI Elite Membership for exclusive discounts and priority booking."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Signature Precision Haircut Description",
                document_type="services",
                content=(
                    "Our Signature Precision Haircut ($85, 60 minutes) includes a premium tailored wash, "
                    "precision cut, invigorating scalp massage, and professional style blowout. "
                    "Our senior stylists specialize in all hair types and textures. "
                    "Recommended maintenance: every 4-6 weeks for optimal shape retention."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Balayage & Creative Color Description",
                document_type="services",
                content=(
                    "Our Balayage & Creative Color service ($220, 150 minutes) features custom artistic "
                    "coloring and toning with high-end premium bond protectors. Includes a consultation "
                    "to determine the perfect shade palette for your skin tone and lifestyle. "
                    "Our color specialists use Olaplex bond-building treatments to maintain hair integrity. "
                    "Touch-up recommended every 8-12 weeks."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Hydrating Deep-Cleansing Facial Description",
                document_type="services",
                content=(
                    "Our Hydrating Deep-Cleansing Facial ($120, 75 minutes) uses organic advanced botanical "
                    "exfoliation, gentle extraction, and antioxidant hydration treatment. "
                    "Includes LED light therapy for collagen stimulation and a customized serum application. "
                    "Perfect for all skin types, especially dehydrated or congested skin. "
                    "Recommended frequency: monthly for optimal results."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Himalayan Hot Stone Massage Description",
                document_type="services",
                content=(
                    "Our Himalayan Hot Stone Massage ($150, 90 minutes) is a deep tissue somatic therapy "
                    "utilizing warm mineral-rich salt rocks sourced from the Himalayas. "
                    "Combines Swedish massage techniques with heated stones to release chronic tension, "
                    "improve circulation, and promote deep relaxation. "
                    "Ideal for stress relief, muscle recovery, and chronic pain management."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="SalonAI Downtown Elite Branch Info",
                document_type="branches",
                content=(
                    "SalonAI Downtown Elite is located at 100 Enterprise Way, Suite A, Metropolis. "
                    "Phone: 555-0100. Email: downtown@salonai.com. "
                    "Features 8 styling stations, 2 private facial rooms, and 3 massage suites. "
                    "Ample street parking and valet service available on weekends. "
                    "Staff includes Senior Stylist Marcus Vance and Master Esthetician Sarah Jenkins."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="SalonAI Uptown Oasis Branch Info",
                document_type="branches",
                content=(
                    "SalonAI Uptown Oasis is located at 450 Serenity Lane, Building 3, Metropolis. "
                    "Phone: 555-0200. Email: uptown@salonai.com. "
                    "Spa-inspired atmosphere with 6 styling stations, a zen garden waiting area, "
                    "and premium tea service. "
                    "Staff includes Color Specialist Elena Rostova and Licensed Massage Therapist Kai Chen."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="First-Time Visitors FAQ",
                document_type="faq",
                content=(
                    "Welcome to SalonAI! For first-time visitors, we recommend arriving 10 minutes early "
                    "to complete a brief consultation form. Your stylist will discuss your goals, preferences, "
                    "and any concerns before starting the service. "
                    "First-time customers receive a complimentary 20% discount on their first service. "
                    "No referral needed — just mention you're a new client when booking."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Aftercare & Products FAQ",
                document_type="faq",
                content=(
                    "We carry a curated selection of professional-grade hair and skincare products. "
                    "Your stylist will recommend specific products based on your service and hair/skin type. "
                    "All products are available for purchase in-salon or through our online store. "
                    "We offer a 30-day satisfaction guarantee on all retail products."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="Group & Event Bookings FAQ",
                document_type="faq",
                content=(
                    "SalonAI offers special packages for weddings, proms, corporate events, and group sessions. "
                    "Groups of 4+ receive a 10% discount. Bridal packages include trial runs and day-of styling. "
                    "Please contact us at least 2 weeks in advance for group bookings to ensure availability. "
                    "Private salon buyouts are available for groups of 12+ guests."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
            KnowledgeDocument(
                id=uuid.uuid4(),
                title="SalonAI Elite Membership Benefits",
                document_type="loyalty",
                content=(
                    "The SalonAI Elite Membership costs $49/month and includes: "
                    "15% off all services, priority booking, complimentary birthday service, "
                    "exclusive access to new treatments, and a quarterly product gift box. "
                    "Members earn 1 loyalty point per $1 spent. 500 points = $50 credit. "
                    "Cancel anytime with no penalty."
                ),
                version=1,
                is_active=True,
                is_deleted=False
            ),
        ]
        
        for doc in docs:
            db.add(doc)
            
        # Seed an initial special offer
        today = datetime.date.today()
        offer = SpecialOffer(
            id=uuid.uuid4(),
            title="First-Time Customer Discount",
            description="Get 20% off your first salon service when booking with Clara.",
            discount_pct=20.0,
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=365),
            is_active=True,
            is_deleted=False
        )
        db.add(offer)

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
