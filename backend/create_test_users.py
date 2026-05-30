#!/usr/bin/env python3
import uuid
from sqlalchemy import text
from db.database import SessionLocal, engine
from db.models import User, Admin, Staff, Customer, Branch, Base

# Ensure tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Hash for 'password123'
# Created with: bcrypt.hashpw(b'password123', bcrypt.gensalt(rounds=12))
hashed_password = '$2b$12$KpmDXGSTHXSVcyR9etDgPO1Jv7XMI6e6rpHseJPHaEgWv2dgp51ZW'

try:
    # Get or create a default branch for staff
    branch = db.query(Branch).first()
    if not branch:
        branch = Branch(
            id=uuid.uuid4(),
            name='Main Branch',
            code='MAIN',
            address='123 Main St',
            city='New York',
            phone='+1-212-555-0000'
        )
        db.add(branch)
        db.flush()
        print('✓ Created default branch')
    
    # 1. Create Admin user (owner@salonai.com)
    admin_check = db.query(User).filter(User.email == 'owner@salonai.com').first()
    if not admin_check:
        admin_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Create user with raw SQL using the actual database enum value 'ADMIN'
        db.execute(text("""
            INSERT INTO users (id, email, hashed_password, role, is_active, refresh_token, created_at, updated_at)
            VALUES (:id, 'owner@salonai.com', :hashed_password, 'ADMIN'::user_role, true, NULL, NOW(), NOW())
        """), {'id': user_id, 'hashed_password': hashed_password})
        db.flush()
        
        # Create admin profile
        db.execute(text("""
            INSERT INTO admins (id, user_id, first_name, last_name, email, phone, created_at, updated_at)
            VALUES (:id, :user_id, 'Balu', 'Owner', 'owner@salonai.com', '+1-212-555-9000', NOW(), NOW())
        """), {'id': admin_id, 'user_id': user_id})
        
        db.commit()
        print('✓ Created admin user: owner@salonai.com / password123')
    else:
        print('✓ Admin user already exists: owner@salonai.com')
    
    # 2. Create Staff user (marcus@salonai.com)
    staff_check = db.query(User).filter(User.email == 'marcus@salonai.com').first()
    if not staff_check:
        staff_profile_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # Create staff profile first
        db.execute(text("""
            INSERT INTO staff (id, branch_id, first_name, last_name, email, phone, role, is_active, created_at, updated_at)
            VALUES (:id, :branch_id, 'Marcus', 'Staff', 'marcus@salonai.com', '+1-212-555-9001', 'Stylist', true, NOW(), NOW())
        """), {'id': staff_profile_id, 'branch_id': branch.id})
        db.flush()
        
        # Create user with raw SQL using the actual database enum value 'STAFF'
        db.execute(text("""
            INSERT INTO users (id, email, hashed_password, role, is_active, staff_id, refresh_token, created_at, updated_at)
            VALUES (:id, 'marcus@salonai.com', :hashed_password, 'STAFF'::user_role, true, :staff_id, NULL, NOW(), NOW())
        """), {'id': user_id, 'hashed_password': hashed_password, 'staff_id': staff_profile_id})
        
        db.commit()
        print('✓ Created staff user: marcus@salonai.com / password123')
    else:
        print('✓ Staff user already exists: marcus@salonai.com')
    
    # 3. Create Customer user (customer@example.com)
    customer_check = db.query(User).filter(User.email == 'customer@example.com').first()
    if not customer_check:
        customer_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # First create customer profile
        db.execute(text("""
            INSERT INTO customers (id, first_name, last_name, email, phone, is_active, created_at, updated_at)
            VALUES (:id, 'John', 'Customer', 'customer@example.com', '+1-212-555-9002', true, NOW(), NOW())
        """), {'id': customer_id})
        db.flush()
        
        # Then create user with raw SQL using the database enum value 'CUSTOMER'
        db.execute(text("""
            INSERT INTO users (id, email, hashed_password, role, is_active, customer_id, refresh_token, created_at, updated_at)
            VALUES (:id, 'customer@example.com', :hashed_password, 'CUSTOMER'::user_role, true, :customer_id, NULL, NOW(), NOW())
        """), {'id': user_id, 'hashed_password': hashed_password, 'customer_id': customer_id})
        
        db.commit()
        print('✓ Created customer user: customer@example.com / password123')
    else:
        print('✓ Customer user already exists: customer@example.com')
    
    # Summary
    conn = engine.connect()
    users = conn.execute(text("SELECT email, role FROM users ORDER BY email")).fetchall()
    print(f'\n✓ Database has {len(users)} total users:')
    for user in users:
        print(f'  - {user[0]} (role: {user[1]})')
    conn.close()
    
except Exception as e:
    db.rollback()
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
finally:
    db.close()
