-- ============================================================================
-- SalonAI Workforce Platform - Fix Migration Script
-- Run this in your Supabase SQL Editor to fix existing data
-- This fixes the user role enum mismatch that prevents login
-- ============================================================================

-- Step 1: Add missing columns to customers table
ALTER TABLE customers ADD COLUMN IF NOT EXISTS loyalty_points INTEGER DEFAULT 0 NOT NULL;

-- Step 2: Add missing columns to reviews table
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS staff_id UUID REFERENCES staff(id) ON DELETE SET NULL;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS review_text TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment VARCHAR(50) DEFAULT 'NEUTRAL';
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS ai_response TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS escalation_required BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS responded BOOLEAN DEFAULT FALSE NOT NULL;

-- Step 3: Add missing columns to leads table
ALTER TABLE leads ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id) ON DELETE SET NULL;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS customer_name TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS customer_email TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS customer_phone TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS service_name TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS preferred_date DATE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS preferred_time TIME;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_staff UUID REFERENCES staff(id) ON DELETE SET NULL;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS lead_score INTEGER DEFAULT 0 NOT NULL;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_count INTEGER DEFAULT 0 NOT NULL;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_contacted TIMESTAMP WITH TIME ZONE;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS converted BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS converted_at TIMESTAMP WITH TIME ZONE;

-- Migrate old leads data (first_name + last_name -> customer_name, email -> customer_email, phone -> customer_phone)
UPDATE leads SET 
    customer_name = COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''),
    customer_email = email,
    customer_phone = phone
WHERE customer_name IS NULL AND first_name IS NOT NULL;

-- Step 4: Add missing columns to chat_logs table
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id) ON DELETE SET NULL;
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS staff_id UUID REFERENCES staff(id) ON DELETE SET NULL;
ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS agent_type VARCHAR(50) DEFAULT 'RECEPTIONIST' NOT NULL;

-- Step 5: Create missing tables

-- Waitlists
CREATE TABLE IF NOT EXISTS waitlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE CASCADE NOT NULL,
    service_id UUID REFERENCES services(id) ON DELETE CASCADE NOT NULL,
    staff_id UUID REFERENCES staff(id) ON DELETE CASCADE,
    date_str VARCHAR(50) NOT NULL,
    time_str VARCHAR(50) NOT NULL,
    is_notified BOOLEAN DEFAULT FALSE NOT NULL
);

-- Loyalty Transactions
DO $$ BEGIN
    CREATE TYPE loyalty_transaction_type AS ENUM ('APPOINTMENT_COMPLETED', 'APPOINTMENT_CANCELLED', 'REVIEW_SUBMITTED', 'RATING_BONUS', 'APP_USAGE_BONUS', 'POINT_REDEMPTION', 'MANUAL_ADJUSTMENT');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE NOT NULL,
    transaction_type loyalty_transaction_type NOT NULL,
    points_change INTEGER NOT NULL,
    previous_balance INTEGER NOT NULL,
    new_balance INTEGER NOT NULL,
    description TEXT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    review_id UUID REFERENCES reviews(id) ON DELETE SET NULL
);

-- Service Recommendations
CREATE TABLE IF NOT EXISTS service_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    service_id UUID REFERENCES services(id) ON DELETE CASCADE NOT NULL,
    recommended_service_id UUID REFERENCES services(id) ON DELETE CASCADE NOT NULL,
    confidence_score FLOAT DEFAULT 1.0 NOT NULL
);

-- Customer Recommendations
CREATE TABLE IF NOT EXISTS customer_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE NOT NULL,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    recommended_service_id UUID REFERENCES services(id) ON DELETE CASCADE NOT NULL,
    accepted BOOLEAN DEFAULT FALSE NOT NULL
);

-- Business Metrics History
CREATE TABLE IF NOT EXISTS business_metrics_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    metric_date DATE UNIQUE NOT NULL,
    revenue NUMERIC(10, 2) DEFAULT 0.0 NOT NULL,
    appointments INTEGER DEFAULT 0 NOT NULL,
    lead_conversion FLOAT DEFAULT 0.0 NOT NULL,
    average_rating FLOAT DEFAULT 0.0 NOT NULL,
    upsell_revenue NUMERIC(10, 2) DEFAULT 0.0 NOT NULL,
    top_service TEXT,
    top_staff TEXT
);

-- Step 6: *** CRITICAL FIX *** Fix user role values to match Python enum
-- The SQLAlchemy UserRole enum uses: ADMIN, STAFF, CUSTOMER, MANAGER, OWNER
-- The old SQL seed used: Admin, Staff, User (WRONG!)

-- First, check if the role column uses a native enum type or varchar
-- If varchar, we can just update the values directly:
UPDATE users SET role = 'ADMIN' WHERE role = 'Admin' OR role = 'admin';
UPDATE users SET role = 'STAFF' WHERE role = 'Staff' OR role = 'staff';
UPDATE users SET role = 'CUSTOMER' WHERE role = 'User' OR role = 'user' OR role = 'Customer' OR role = 'customer';
UPDATE users SET role = 'MANAGER' WHERE role = 'Manager' OR role = 'manager';
UPDATE users SET role = 'OWNER' WHERE role = 'Owner' OR role = 'owner';

-- Step 7: Fix appointment status values (ensure uppercase)
UPDATE appointments SET status = 'PENDING' WHERE status = 'Pending' OR status = 'pending';
UPDATE appointments SET status = 'CONFIRMED' WHERE status = 'Confirmed' OR status = 'confirmed';
UPDATE appointments SET status = 'COMPLETED' WHERE status = 'Completed' OR status = 'completed';
UPDATE appointments SET status = 'CANCELLED' WHERE status = 'Cancelled' OR status = 'cancelled';

-- Step 8: Fix lead status values
UPDATE leads SET status = 'NEW' WHERE status = 'New' OR status = 'new';
UPDATE leads SET status = 'CONTACTED' WHERE status = 'Contacted' OR status = 'contacted';
UPDATE leads SET status = 'CONVERTED' WHERE status = 'Converted' OR status = 'converted';

-- Step 9: Fix review status values
UPDATE reviews SET status = 'PENDING' WHERE status = 'Pending' OR status = 'pending';
UPDATE reviews SET status = 'APPROVED' WHERE status = 'Approved' OR status = 'approved';

-- Step 10: Ensure RLS allows postgres role (for direct SQLAlchemy connections)
-- Add permissive policies for all operations on all tables
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename IN ('branches', 'services', 'staff', 'customers', 'users', 'appointments', 'leads', 'reviews', 'admins', 'chat_logs', 'notifications', 'analytics_records', 'waitlists', 'loyalty_transactions', 'service_recommendations', 'customer_recommendations', 'business_metrics_history')
    LOOP
        -- Enable RLS
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', tbl);
        
        -- Create permissive policy for all operations (if not exists)
        BEGIN
            EXECUTE format('CREATE POLICY "allow_all_%s" ON %I FOR ALL USING (true) WITH CHECK (true);', tbl, tbl);
        EXCEPTION WHEN duplicate_object THEN
            NULL; -- Policy already exists, skip
        END;
    END LOOP;
END $$;

SELECT 'Migration completed successfully! User roles have been fixed.' AS result;
