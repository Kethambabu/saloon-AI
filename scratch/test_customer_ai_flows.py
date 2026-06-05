#!/usr/bin/env python3
"""
Integration test script for AI Receptionist (Clara) customer-side workflows.
Executes various natural language queries and verifies database state.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.database import SessionLocal
from db.models import Customer, Appointment, AppointmentStatus, Service, Branch, Staff
from agents.receptionist_agent import ReceptionistAgent

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def run_flow_tests():
    logger.info("Initializing ReceptionistAgent...")
    agent = ReceptionistAgent()
    
    # 1. Resolve seed customer 'Alice Smith'
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.email == "customer@example.com").first()
        if not customer:
            logger.error("Seeded customer 'customer@example.com' not found! Please seed the database first.")
            return
        
        customer_id = str(customer.id)
        logger.info(f"Resolved Customer: {customer.full_name} (ID: {customer_id})")
        
        # Ensure customer has no old appointments so we test fresh
        old_appts = db.query(Appointment).filter(Appointment.customer_id == customer.id).all()
        for appt in old_appts:
            db.delete(appt)
        db.commit()
        logger.info("Cleared old customer appointments.")
        
    finally:
        db.close()
        
    # Helper to send message with injected context prefix
    async def send_query(query_text: str):
        now_dt = datetime.now()
        context_prefix = f"[SYSTEM TIME CONTEXT: Current system time is {now_dt.strftime('%Y-%m-%d %H:%M:%S')} (Today is {now_dt.strftime('%A, %B %d, %Y')}). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]\n"
        context_prefix += f"[SYSTEM CUSTOMER CONTEXT: ID: {customer_id}, Email: customer@example.com, Name: Alice Smith]\n"
        
        full_query = context_prefix + "\nLatest User Message: " + query_text
        logger.info(f"Query: {query_text}")
        response = await agent.process({"query": full_query})
        logger.info(f"Response:\n{response.get('response')}\n" + "-"*60)
        return response

    # Test 1: Discover Services
    logger.info("TEST 1: Discover Services")
    await send_query("What services do you offer?")

    # Test 2: Check Availability
    logger.info("TEST 2: Check Availability")
    await send_query("Is there slot available for Precision Haircut at Main Salon tomorrow at 1:00 PM?")

    # Test 3: Book Appointment
    logger.info("TEST 3: Book Appointment")
    booking_response = await send_query("Please book a Precision Haircut at Main Salon tomorrow at 1:00 PM with Priya Sharma.")
    
    # Verify DB state after booking
    db = SessionLocal()
    try:
        appt = db.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status == AppointmentStatus.PENDING
        ).first()
        assert appt is not None, "DB Verification Failed: Appointment not created or status is not PENDING"
        logger.info(f"DB Verification Passed: Appointment created successfully! ID: {appt.id}, Status: {appt.status}")
        
        # Check service & branch
        assert appt.service.name == "Precision Haircut"
        assert appt.branch.name == "Main Salon"
        logger.info("DB Verification Passed: Correct Service and Branch assigned.")
    finally:
        db.close()

    # Test 4: History Retrieval
    logger.info("TEST 4: History Retrieval")
    await send_query("Show my booking history.")

    # Test 5: Rescheduling
    logger.info("TEST 5: Rescheduling")
    resched_response = await send_query("Please reschedule my appointment to tomorrow at 2:30 PM.")
    
    # Verify DB state after rescheduling
    db = SessionLocal()
    try:
        appt = db.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status == AppointmentStatus.CONFIRMED
        ).first()
        assert appt is not None, "DB Verification Failed: Rescheduled appointment not found or status not CONFIRMED"
        logger.info(f"DB Verification Passed: Appointment rescheduled! ID: {appt.id}, New Time: {appt.start_time.isoformat()}, Status: {appt.status}")
        
        # Check time
        assert appt.start_time.hour == 14 and appt.start_time.minute == 30
        logger.info("DB Verification Passed: Correct new time slot assigned.")
    finally:
        db.close()

    # Test 6: Cancellation
    logger.info("TEST 6: Cancellation")
    cancel_response = await send_query("Actually, please cancel my appointment tomorrow.")
    
    # Verify DB state after cancellation
    db = SessionLocal()
    try:
        appt = db.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status == AppointmentStatus.CANCELLED
        ).first()
        assert appt is not None, "DB Verification Failed: Cancelled appointment not found"
        logger.info(f"DB Verification Passed: Appointment is CANCELLED! ID: {appt.id}")
    finally:
        db.close()
        
    logger.info("All flows test completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_flow_tests())
