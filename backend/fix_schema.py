#!/usr/bin/env python
"""Quick script to add missing loyalty_points column to customers table"""

from infrastructure.db.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Check if the column exists
    result = db.execute(text("""
        SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = 'customers' AND column_name = 'loyalty_points'
    """))
    
    exists = result.scalar() > 0
    
    if not exists:
        print('Column does not exist. Adding loyalty_points column...')
        db.execute(text('ALTER TABLE customers ADD COLUMN loyalty_points INTEGER DEFAULT 0 NOT NULL'))
        db.commit()
        print('✅ Column added successfully!')
    else:
        print('✅ Column already exists')
except Exception as e:
    print(f'Error: {e}')
    db.rollback()
finally:
    db.close()

