#!/usr/bin/env python3
"""
Test script to verify new receptionist assistant rules:
1. Review eligibility (Only completed appointments can be reviewed)
2. Customer booking limits (Max 3 active bookings)
3. Appointment ownership validation
4. Natural language history queries
5. Past time rollover check
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.database import SessionLocal
from db.models import Customer, Appointment, AppointmentStatus, Service, Branch, Staff, User
from services.review_service import ReviewService
from tools.booking_tools import create_appointment, cancel_appointment, reschedule_appointment
from agents.receptionist_agent import ReceptionistAgent

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def run_tests():
    db = SessionLocal()
    
    # 1. Resolve seed customer 'Alice Smith' (customer@example.com)
    customer = db.query(Customer).filter(Customer.email == "customer@example.com").first()
    if not customer:
        logger.error("Seeded customer 'customer@example.com' not found!")
        return
    customer_id = str(customer.id)
    logger.info(f"Resolved Customer: {customer.full_name} (ID: {customer_id})")

    # Create another mock customer for ownership test
    mock_customer = db.query(Customer).filter(Customer.email == "mock_other@example.com").first()
    if not mock_customer:
        mock_customer = Customer(
            first_name="Bob",
            last_name="Jones",
            email="mock_other@example.com"
        )
        db.add(mock_customer)
        db.commit()
    mock_customer_id = str(mock_customer.id)

    # Resolve branch and service to static strings to prevent DetachedInstanceError
    branch = db.query(Branch).first()
    service = db.query(Service).first()
    staff = db.query(Staff).first()
    
    branch_uuid_str = str(branch.id)
    service_uuid_str = str(service.id)
    staff_uuid_str = str(staff.id)
    
    # Clean up customer's appointments
    db.query(Appointment).filter(Appointment.customer_id == customer.id).delete()
    db.query(Appointment).filter(Appointment.customer_id == mock_customer.id).delete()
    db.commit()
    logger.info("Cleared old test appointments.")

    # -------------------------------------------------------------
    # RULE 1: Review Eligibility
    # -------------------------------------------------------------
    logger.info("\n--- TEST 1: Review Eligibility ---")
    # Book a pending appointment
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    appt_res = create_appointment(
        customer_id=customer_id,
        branch_id=branch_uuid_str,
        service_id=service_uuid_str,
        start_time=tomorrow.isoformat(),
        staff_id=staff_uuid_str,
        db=db
    )
    assert appt_res["success"] is True
    appt_id = appt_res["appointment_id"]
    logger.info(f"Created pending appointment: {appt_id}")
    
    # Try reviewing it
    review_res = ReviewService.submit_review(
        db=db,
        customer_id=customer_id,
        rating=5,
        comment="Great!",
        appointment_id=appt_id,
        staff_id=staff_uuid_str
    )
    logger.info(f"Review response (should fail): {review_res}")
    assert review_res["success"] is False
    assert "Only completed appointments can be reviewed" in review_res["error"]
    logger.info("✓ Review eligibility check passed! Rejected review for pending appointment.")

    # Mark as completed
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    appt.status = AppointmentStatus.COMPLETED
    db.commit()
    
    # Try reviewing again
    review_res2 = ReviewService.submit_review(
        db=db,
        customer_id=customer_id,
        rating=5,
        comment="Great haircut!",
        appointment_id=appt_id,
        staff_id=staff_uuid_str
    )
    logger.info(f"Review response (should succeed): {review_res2}")
    assert review_res2["success"] is True
    logger.info("✓ Review eligibility check passed! Allowed review for completed appointment.")

    # -------------------------------------------------------------
    # RULE 2: Customer Booking Limits
    # -------------------------------------------------------------
    logger.info("\n--- TEST 2: Customer Booking Limits (Max 3 active) ---")
    # Clean up first
    db.query(Appointment).filter(Appointment.customer_id == customer.id).delete()
    db.commit()

    # Create 3 active appointments (PENDING or CONFIRMED)
    for i in range(3):
        slot_time = tomorrow + timedelta(hours=i*2)
        res = create_appointment(
            customer_id=customer_id,
            branch_id=branch_uuid_str,
            service_id=service_uuid_str,
            start_time=slot_time.isoformat(),
            staff_id=staff_uuid_str,
            db=db
        )
        assert res["success"] is True
        logger.info(f"Created active booking {i+1}: {res['appointment_id']}")

    # Try booking a 4th one
    fourth_time = tomorrow + timedelta(hours=5)
    res_fourth = create_appointment(
        customer_id=customer_id,
        branch_id=branch_uuid_str,
        service_id=service_uuid_str,
        start_time=fourth_time.isoformat(),
        staff_id=staff_uuid_str,
        db=db
    )
    logger.info(f"4th booking response (should fail): {res_fourth}")
    assert res_fourth["success"] is False
    assert "maximum limit of 3 active bookings" in res_fourth["error"]
    logger.info("✓ Customer booking limits check passed! Blocked 4th active booking.")

    # -------------------------------------------------------------
    # RULE 3: Appointment Ownership Validation
    # -------------------------------------------------------------
    logger.info("\n--- TEST 3: Appointment Ownership Validation ---")
    # Retrieve one of customer's active appointments
    appt_to_test = db.query(Appointment).filter(Appointment.customer_id == customer.id).first()
    appt_to_test_id = str(appt_to_test.id)

    # Try to cancel it using mock_customer_id
    cancel_fail = cancel_appointment(
        appointment_id=appt_to_test_id,
        customer_id=mock_customer_id,
        db=db
    )
    logger.info(f"Cancel (different customer, should fail): {cancel_fail}")
    assert cancel_fail["success"] is False
    assert "not authorized to cancel" in cancel_fail["error"]

    # Try to reschedule it using mock_customer_id
    new_resched_time = tomorrow + timedelta(days=2)
    resched_fail = reschedule_appointment(
        appointment_id=appt_to_test_id,
        new_start_time=new_resched_time.isoformat(),
        customer_id=mock_customer_id,
        db=db
    )
    logger.info(f"Reschedule (different customer, should fail): {resched_fail}")
    assert resched_fail["success"] is False
    assert "not authorized to reschedule" in resched_fail["error"]

    # Try to cancel it with correct customer_id (should succeed)
    cancel_success = cancel_appointment(
        appointment_id=appt_to_test_id,
        customer_id=customer_id,
        db=db
    )
    logger.info(f"Cancel (correct customer, should succeed): {cancel_success}")
    assert cancel_success["success"] is True
    logger.info("✓ Appointment ownership checks passed! Blocked unauthorized access and allowed authorized cancel.")
    db.close()

    # -------------------------------------------------------------
    # RULE 4: Natural Language History Queries & Rollover
    # -------------------------------------------------------------
    logger.info("\n--- TEST 4: Natural Language History Queries ---")
    # Seed history: 2 completed appointments with prices
    db_history = SessionLocal()
    try:
        db_history.query(Appointment).filter(Appointment.customer_id == customer_id).delete()
        db_history.commit()

        completed_appt1 = Appointment(
            customer_id=customer_id,
            branch_id=branch_uuid_str,
            staff_id=staff_uuid_str,
            service_id=service_uuid_str,
            start_time=datetime.now(timezone.utc) - timedelta(days=5),
            end_time=datetime.now(timezone.utc) - timedelta(days=5) + timedelta(minutes=60),
            status=AppointmentStatus.COMPLETED,
            notes="Service 1 completed"
        )
        db_history.add(completed_appt1)
        db_history.commit()

        completed_appt2 = Appointment(
            customer_id=customer_id,
            branch_id=branch_uuid_str,
            staff_id=staff_uuid_str,
            service_id=service_uuid_str,
            start_time=datetime.now(timezone.utc) - timedelta(days=2),
            end_time=datetime.now(timezone.utc) - timedelta(days=2) + timedelta(minutes=60),
            status=AppointmentStatus.COMPLETED,
            notes="Service 2 completed"
        )
        db_history.add(completed_appt2)
        db_history.commit()
    finally:
        db_history.close()

    # Initialise receptionist agent
    agent = ReceptionistAgent()

    async def send_agent_query(query_text: str):
        # Reset model cooldowns so we don't hit mock fallbacks on transient failures
        agent.MODEL_COOLDOWN.clear()
        now_dt = datetime.now()
        context_prefix = f"[SYSTEM TIME CONTEXT: Current system time is {now_dt.strftime('%Y-%m-%d %H:%M:%S')} (Today is {now_dt.strftime('%A, %B %d, %Y')}). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]\n"
        context_prefix += f"[SYSTEM CUSTOMER CONTEXT: ID: {customer_id}, Email: customer@example.com, Name: Alice Smith]\n"
        full_query = context_prefix + "\nLatest User Message: " + query_text
        logger.info(f"USER: {query_text}")
        response = await agent.process({"query": full_query})
        logger.info(f"CLARA:\n{response.get('response')}\n" + "-"*60)
        return response

    # 4.1 Check spend query
    await send_agent_query("How much did I spend this year?")

    # 4.2 Check last appointment query
    await send_agent_query("What was my last appointment?")

    # 4.3 Check past time rollover query
    logger.info("\n--- TEST 5: Past Time Rollover Check ---")
    db_setup = SessionLocal()
    try:
        tomorrow_booking = datetime.now(timezone.utc) + timedelta(days=1)
        create_appointment(
            customer_id=customer_id,
            branch_id=branch_uuid_str,
            service_id=service_uuid_str,
            start_time=tomorrow_booking.replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
            staff_id=staff_uuid_str,
            db=db_setup
        )
        db_setup.commit()
    finally:
        db_setup.close()

    async def send_agent_query_custom_time(query_text: str, custom_time_str: str):
        # Reset model cooldowns
        agent.MODEL_COOLDOWN.clear()
        context_prefix = f"[SYSTEM TIME CONTEXT: Current system time is {custom_time_str} (Today is Friday, June 05, 2026). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]\n"
        context_prefix += f"[SYSTEM CUSTOMER CONTEXT: ID: {customer_id}, Email: customer@example.com, Name: Alice Smith]\n"
        full_query = context_prefix + "\nLatest User Message: " + query_text
        logger.info(f"USER: {query_text} (with custom system time: {custom_time_str})")
        response = await agent.process({"query": full_query})
        logger.info(f"CLARA:\n{response.get('response')}\n" + "-"*60)
        return response

    res_nl = await send_agent_query_custom_time("reschedule to 12pm", "2026-06-05 17:00:00")
    
    # Assert that the rescheduled appointment is indeed on 2026-06-06 (tomorrow) at 12:00 PM
    db_check = SessionLocal()
    try:
        appt_check = db_check.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status == AppointmentStatus.CONFIRMED
        ).first()
        assert appt_check is not None, "Rescheduled appointment not found!"
        logger.info(f"Rescheduled Appointment Start Time in DB: {appt_check.start_time}")
        # Tomorrow is 2026-06-06
        assert appt_check.start_time.year == 2026
        assert appt_check.start_time.month == 6
        assert appt_check.start_time.day == 6
        assert appt_check.start_time.hour == 12
        assert appt_check.start_time.minute == 0
        logger.info("✓ Past time rollover check passed! Rescheduled past time correctly rolled over to tomorrow.")
    finally:
        db_check.close()

    logger.info("All new business rules tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
