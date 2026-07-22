"""
Dedicated background worker and scheduler process.
Runs APScheduler jobs for lead follow-ups, cohort reminders, and memory snapshots.
"""

import sys
import os
import time
import logging

# Ensure backend directory is in path
backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.config import get_settings
from core.logging import setup_logging
from infrastructure.db.database import check_db_health, SessionLocal
from application.services.lead_service import process_leads
from application.services.analytics_service import process_returning_cohort_reminders

setup_logging()
logger = logging.getLogger("salon_worker")
settings = get_settings()



def run_worker():
    logger.info("=" * 70)
    logger.info("🚀 Starting Dedicated Background Worker & Scheduler Process")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 70)

    # Eager database connection check
    if not check_db_health():
        logger.critical("❌ Database connection is unhealthy. Exiting worker.")
        sys.exit(1)
    
    logger.info("✅ Database connectivity verified.")

    # Register Event Bus Subscribers
    logger.info("🔄 Registering event bus subscribers...")
    try:
        from application.services.analytics_service import register_event_subscribers as register_analytics_subscribers
        from application.services.notification_service import register_event_subscribers as register_notification_subscribers
        from application.services.memory_curator_service import register_memory_curator_subscribers
        register_analytics_subscribers()
        register_notification_subscribers()
        register_memory_curator_subscribers()
    except Exception as exc:
        logger.error(f"❌ Failed to register event subscribers: {exc}", exc_info=True)

    # Initialize and start APScheduler
    from apscheduler.schedulers.blocking import BlockingScheduler
    
    scheduler = BlockingScheduler()
    
    from application.services.appointment_service import auto_cancel_all_expired_appointments

    # Lead follow-up execution
    scheduler.add_job(
        process_leads,
        'interval',
        minutes=60,
        id="process_leads"
    )
    # Returning cohort reminders
    scheduler.add_job(
        process_returning_cohort_reminders,
        'interval',
        minutes=60,
        id="process_cohort_reminders"
    )
    # Auto-cancel expired past appointments
    scheduler.add_job(
        auto_cancel_all_expired_appointments,
        'interval',
        minutes=15,
        id="auto_cancel_expired_appointments"
    )

    logger.info("⏱️ Scheduler loaded with 3 jobs. Blocking until terminated.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Shutting down Background Worker.")
        scheduler.shutdown()

if __name__ == "__main__":
    run_worker()
