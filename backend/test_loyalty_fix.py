#!/usr/bin/env python
"""
Test script to verify loyalty points system is working correctly.
Tests:
1. New customer starts with 0 points
2. Points increase on operations
3. Points decrease on operations (min 0)
4. Transaction records are created
"""

import sys
import logging
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.models import (
    Customer,
    LoyaltyTransaction,
    LoyaltyTransactionType,
)
from tools.loyalty_service import (
    add_loyalty_points,
    get_customer_loyalty_summary,
    reset_customer_loyalty_points,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_loyalty_system():
    """Run comprehensive loyalty points tests."""
    db = SessionLocal()
    
    try:
        # Create test customer
        test_customer = Customer(
            id=uuid4(),
            first_name="Test",
            last_name="Customer",
            email=f"test_loyalty_{datetime.now().timestamp()}@test.com",
            phone="555-0001",
            is_active=True,
            loyalty_points=0
        )
        db.add(test_customer)
        db.commit()
        logger.info(f"✅ Created test customer: {test_customer.id}")
        
        # Test 1: Verify initial points are 0
        db.refresh(test_customer)
        assert test_customer.loyalty_points == 0, f"Initial points should be 0, got {test_customer.loyalty_points}"
        logger.info("✅ Test 1 PASSED: Initial loyalty points = 0")
        
        # Test 2: Award 100 points
        transaction = add_loyalty_points(
            db=db,
            customer_id=test_customer.id,
            points=100,
            transaction_type=LoyaltyTransactionType.APPOINTMENT_COMPLETED,
            description="Test: +100 points"
        )
        
        db.refresh(test_customer)
        assert test_customer.loyalty_points == 100, f"After adding 100 points, should be 100, got {test_customer.loyalty_points}"
        assert transaction.points_change == 100, "Transaction should record +100 points"
        assert transaction.previous_balance == 0, "Previous balance should be 0"
        assert transaction.new_balance == 100, "New balance should be 100"
        logger.info("✅ Test 2 PASSED: Award 100 points")
        
        # Test 3: Award more points (cumulative)
        transaction2 = add_loyalty_points(
            db=db,
            customer_id=test_customer.id,
            points=100,
            transaction_type=LoyaltyTransactionType.APPOINTMENT_COMPLETED,
            description="Test: +100 points (2nd)"
        )
        
        db.refresh(test_customer)
        assert test_customer.loyalty_points == 200, f"After 2x100, should be 200, got {test_customer.loyalty_points}"
        logger.info("✅ Test 3 PASSED: Points accumulate correctly (200)")
        
        # Test 4: Deduct 50 points
        transaction3 = add_loyalty_points(
            db=db,
            customer_id=test_customer.id,
            points=-50,
            transaction_type=LoyaltyTransactionType.APPOINTMENT_CANCELLED,
            description="Test: -50 points"
        )
        
        db.refresh(test_customer)
        assert test_customer.loyalty_points == 150, f"After deducting 50, should be 150, got {test_customer.loyalty_points}"
        assert transaction3.points_change == -50, "Transaction should record -50 points"
        logger.info("✅ Test 4 PASSED: Deduct 50 points (200 - 50 = 150)")
        
        # Test 5: Prevent negative points - try to deduct more than balance
        transaction4 = add_loyalty_points(
            db=db,
            customer_id=test_customer.id,
            points=-200,  # Try to deduct 200 when only 150 available
            transaction_type=LoyaltyTransactionType.APPOINTMENT_CANCELLED,
            description="Test: Try -200 (blocked at 0)"
        )
        
        db.refresh(test_customer)
        assert test_customer.loyalty_points == 0, f"After trying to deduct 200 from 150, should be 0, got {test_customer.loyalty_points}"
        logger.info("✅ Test 5 PASSED: Points cannot go below 0 (blocked at 0)")
        
        # Test 6: Get loyalty summary
        summary = get_customer_loyalty_summary(db=db, customer_id=test_customer.id)
        assert summary["current_balance"] == 0, f"Summary balance should be 0, got {summary['current_balance']}"
        assert len(summary["recent_transactions"]) >= 4, f"Should have 4+ transactions, got {len(summary['recent_transactions'])}"
        logger.info(f"✅ Test 6 PASSED: Loyalty summary shows {len(summary['recent_transactions'])} transactions")
        
        # Test 7: Manual reset - add points first
        add_loyalty_points(
            db=db,
            customer_id=test_customer.id,
            points=100,
            transaction_type=LoyaltyTransactionType.APPOINTMENT_COMPLETED,
            description="Test: +100 points for reset test"
        )
        
        db.refresh(test_customer)
        assert test_customer.loyalty_points == 100, f"Should have 100 points before reset"
        
        # Then reset
        reset_transaction = reset_customer_loyalty_points(db=db, customer_id=test_customer.id, reason="Test reset")
        db.refresh(test_customer)
        assert test_customer.loyalty_points == 0, f"After reset, points should be 0, got {test_customer.loyalty_points}"
        logger.info("✅ Test 7 PASSED: Manual reset works correctly")
        
        # Test 8: Verify all transactions are recorded
        transactions = db.query(LoyaltyTransaction).filter(
            LoyaltyTransaction.customer_id == test_customer.id
        ).all()
        assert len(transactions) >= 5, f"Should have 5+ transactions, got {len(transactions)}"
        logger.info(f"✅ Test 8 PASSED: All {len(transactions)} transactions recorded correctly")
        
        # Test 9: Verify transaction details
        completed_count = sum(1 for t in transactions if t.transaction_type == LoyaltyTransactionType.APPOINTMENT_COMPLETED)
        cancelled_count = sum(1 for t in transactions if t.transaction_type == LoyaltyTransactionType.APPOINTMENT_CANCELLED)
        reset_count = sum(1 for t in transactions if t.transaction_type == LoyaltyTransactionType.MANUAL_ADJUSTMENT)
        
        assert completed_count >= 2, f"Should have 2+ completed transactions, got {completed_count}"
        assert cancelled_count >= 1, f"Should have 1+ cancelled transactions, got {cancelled_count}"
        assert reset_count == 1, f"Should have 1 reset transaction, got {reset_count}"
        logger.info(f"✅ Test 9 PASSED: Transaction types are correct (Completed: {completed_count}, Cancelled: {cancelled_count}, Reset: {reset_count})")
        
        logger.info("\n" + "="*60)
        logger.info("✅ ALL TESTS PASSED - Loyalty Points System is Working!")
        logger.info("="*60)
        
        return True
        
    except AssertionError as e:
        logger.error(f"❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_loyalty_system()
    sys.exit(0 if success else 1)
