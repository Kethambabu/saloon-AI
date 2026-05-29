-- ============================================================================
-- SalonAI Workforce Platform - Supabase DDL, RLS & Seed Script
-- Execute this script directly in your Supabase SQL Editor.
-- ============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Drop existing tables if they exist to start fresh
DROP TABLE IF EXISTS analytics_records CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS chat_logs CASCADE;
DROP TABLE IF EXISTS managers CASCADE;
DROP TABLE IF EXISTS admins CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS leads CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS services CASCADE;
DROP TABLE IF EXISTS branches CASCADE;

-- 3. Create Tables
CREATE TABLE branches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    duration_minutes INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE staff (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE CASCADE NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'Staff' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    staff_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    refresh_token VARCHAR(500)
);

CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE CASCADE NOT NULL,
    staff_id UUID REFERENCES staff(id) ON DELETE SET NULL,
    service_id UUID REFERENCES services(id) ON DELETE RESTRICT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
    notes TEXT
);

CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(20),
    source VARCHAR(50),
    status VARCHAR(50) DEFAULT 'NEW' NOT NULL,
    notes TEXT
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE CASCADE NOT NULL,
    appointment_id UUID REFERENCES appointments(id) ON DELETE CASCADE UNIQUE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5) NOT NULL,
    comment TEXT,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL
);

CREATE TABLE admins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20)
);

CREATE TABLE managers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20)
);

CREATE TABLE chat_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    sender VARCHAR(50) NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE NOT NULL
);

CREATE TABLE analytics_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    dimensions TEXT
);

-- ============================================================================
-- 4. Create Optimized Database Indexes
-- ============================================================================
CREATE INDEX idx_appointments_start_status ON appointments (start_time, status);
CREATE INDEX idx_chat_logs_session ON chat_logs (session_id);
CREATE INDEX idx_analytics_records_metric ON analytics_records (metric_name);
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_staff_branch ON staff (branch_id);

-- ============================================================================
-- 5. Row Level Security (RLS) Policies
-- ============================================================================
ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE services ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE managers ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_records ENABLE ROW LEVEL SECURITY;

-- 5.1 Branches RLS Policies
CREATE POLICY "Allow public select on branches" ON branches FOR SELECT USING (true);
CREATE POLICY "Allow authenticated manage on branches" ON branches TO authenticated USING (true) WITH CHECK (true);

-- 5.2 Services RLS Policies
CREATE POLICY "Allow public select on services" ON services FOR SELECT USING (true);
CREATE POLICY "Allow authenticated manage on services" ON services TO authenticated USING (true) WITH CHECK (true);

-- 5.3 Staff RLS Policies
CREATE POLICY "Allow public select on staff" ON staff FOR SELECT USING (true);
CREATE POLICY "Allow authenticated manage on staff" ON staff TO authenticated USING (true) WITH CHECK (true);

-- 5.4 Customers RLS Policies
CREATE POLICY "Allow authenticated manage on customers" ON customers TO authenticated USING (true) WITH CHECK (true);

-- 5.5 Users RLS Policies
CREATE POLICY "Allow authenticated read self users" ON users FOR SELECT USING (true);
CREATE POLICY "Allow admin manage users" ON users TO authenticated USING (true) WITH CHECK (true);

-- 5.6 Appointments RLS Policies
CREATE POLICY "Allow authenticated select appointments" ON appointments FOR SELECT TO authenticated USING (true);
CREATE POLICY "Allow authenticated insert appointments" ON appointments FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Allow authenticated update appointments" ON appointments FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

-- 5.7 Chat Logs RLS Policies
CREATE POLICY "Allow authenticated manage chat logs" ON chat_logs TO authenticated USING (true) WITH CHECK (true);

-- 5.8 Notifications RLS Policies
CREATE POLICY "Allow authenticated manage notifications" ON notifications TO authenticated USING (true) WITH CHECK (true);

-- 5.9 Analytics RLS Policies
CREATE POLICY "Allow authenticated manage analytics" ON analytics_records TO authenticated USING (true) WITH CHECK (true);

-- 5.10 Admins & Managers RLS Policies
CREATE POLICY "Allow authenticated read admins" ON admins FOR SELECT USING (true);
CREATE POLICY "Allow authenticated read managers" ON managers FOR SELECT USING (true);

-- ============================================================================
-- 6. Insert Seed Data
-- ============================================================================

-- 6.1 Insert Branches
INSERT INTO branches (id, name, code, address, city, phone, email, is_active) VALUES
('4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', 'Downtown Elite', 'DTE', '123 Main Street', 'New York', '+1-212-555-0100', 'downtown@salonai.com', TRUE),
('4f3d1b64-884c-4c6e-a342-6a0b985c4bf2', 'Westside Boutique', 'WSB', '456 Park Avenue', 'Los Angeles', '+1-310-555-0200', 'westside@salonai.com', TRUE),
('4f3d1b64-884c-4c6e-a342-6a0b985c4bf3', 'Midtown Luxe', 'MTL', '789 Michigan Avenue', 'Chicago', '+1-312-555-0300', 'midtown@salonai.com', TRUE);

-- 6.2 Insert Services
INSERT INTO services (id, name, description, price, duration_minutes, is_active) VALUES
('5e2f3d64-994c-4c6e-b342-7b0c985c5cf1', 'Signature Precision Haircut', 'Professional haircut with detailed styling consultation', 85.00, 60, TRUE),
('5e2f3d64-994c-4c6e-b342-7b0c985c5cf2', 'Balayage & Creative Color', 'Hand-painted highlighting technique with custom color blending', 220.00, 150, TRUE),
('5e2f3d64-994c-4c6e-b342-7b0c985c5cf3', 'Hydrating Deep-Cleansing Facial', 'Luxurious 75-minute facial with premium skincare products', 120.00, 75, TRUE),
('5e2f3d64-994c-4c6e-b342-7b0c985c5cf4', 'Himalayan Hot Stone Massage', 'Soothing massage with warm stone therapy and aromatherapy', 150.00, 90, TRUE);

-- 6.3 Insert Staff
INSERT INTO staff (id, branch_id, first_name, last_name, email, phone, role, is_active) VALUES
('6a3e2b64-004c-4c6e-c342-8c0d985c6df1', '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', 'Alexandra', 'Chen', 'alex.chen@salonai.com', '+1-212-555-1001', 'Senior Stylist', TRUE),
('6a3e2b64-004c-4c6e-c342-8c0d985c6df2', '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', 'Marcus', 'Johnson', 'marcus.johnson@salonai.com', '+1-212-555-1002', 'Color Specialist', TRUE),
('6a3e2b64-004c-4c6e-c342-8c0d985c6df3', '4f3d1b64-884c-4c6e-a342-6a0b985c4bf2', 'Isabella', 'Martinez', 'isabella.martinez@salonai.com', '+1-310-555-2001', 'Senior Stylist', TRUE);

-- 6.4 Insert Customers
INSERT INTO customers (id, first_name, last_name, email, phone, is_active) VALUES
('7b3f1b64-114c-4c6e-d342-9d0e985c7df1', 'Alice', 'Smith', 'alice.smith@example.com', '+1-212-555-5001', TRUE),
('7b3f1b64-114c-4c6e-d342-9d0e985c7df2', 'Robert', 'Johnson', 'robert.johnson@example.com', '+1-212-555-5002', TRUE);

-- 6.5 Insert Authenticated Users
-- Default Hashed password matches "password123" under standard bcrypt passlib hash context
INSERT INTO users (id, email, hashed_password, role, is_active, staff_id, customer_id) VALUES
('8c3f1b64-224c-4c6e-e342-ae0e985c8df1', 'owner@salonai.com', '$2b$12$yA3W8jP74Z.0xRmWq3v2Eu.QY9m.H1JtA2qXlVz8w2f6Q2jXwT2S.', 'Admin', TRUE, NULL, NULL),
('8c3f1b64-224c-4c6e-e342-ae0e985c8df2', 'manager@salonai.com', '$2b$12$yA3W8jP74Z.0xRmWq3v2Eu.QY9m.H1JtA2qXlVz8w2f6Q2jXwT2S.', 'Manager', TRUE, NULL, NULL),
('8c3f1b64-224c-4c6e-e342-ae0e985c8df3', 'marcus@salonai.com', '$2b$12$yA3W8jP74Z.0xRmWq3v2Eu.QY9m.H1JtA2qXlVz8w2f6Q2jXwT2S.', 'Staff', TRUE, '6a3e2b64-004c-4c6e-c342-8c0d985c6df2', NULL),
('8c3f1b64-224c-4c6e-e342-ae0e985c8df4', 'customer@example.com', '$2b$12$yA3W8jP74Z.0xRmWq3v2Eu.QY9m.H1JtA2qXlVz8w2f6Q2jXwT2S.', 'Customer', TRUE, NULL, '7b3f1b64-114c-4c6e-d342-9d0e985c7df1');

-- 6.6 Insert Role Tables Profile Records
INSERT INTO admins (id, user_id, first_name, last_name, email, phone) VALUES
('9d3f1b64-334c-4c6e-f342-bf0e985c9df1', '8c3f1b64-224c-4c6e-e342-ae0e985c8df1', 'Balu', 'Owner', 'owner@salonai.com', '+1-212-555-9000');

INSERT INTO managers (id, user_id, branch_id, first_name, last_name, email, phone) VALUES
('9d3f1b64-334c-4c6e-f342-bf0e985c9df2', '8c3f1b64-224c-4c6e-e342-ae0e985c8df2', '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', 'Kethambabu', 'Manager', 'manager@salonai.com', '+1-212-555-8000');

-- 6.7 Insert Sample Appointments
INSERT INTO appointments (id, customer_id, branch_id, staff_id, service_id, start_time, end_time, status, notes) VALUES
('0e3f1b64-444c-4c6e-0342-cf0e985c0df1', '7b3f1b64-114c-4c6e-d342-9d0e985c7df1', '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', '6a3e2b64-004c-4c6e-c342-8c0d985c6df2', '5e2f3d64-994c-4c6e-b342-7b0c985c5cf1', NOW() + INTERVAL '1 day', NOW() + INTERVAL '1 day 1 hour', 'CONFIRMED', 'Wants soft layers haircut');

-- 6.8 Insert Sample Lead
INSERT INTO leads (id, branch_id, first_name, last_name, email, phone, source, status, notes) VALUES
('0e3f1b64-444c-4c6e-0342-cf0e985c0df2', '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', 'Alice', 'Smith', 'alice.smith@example.com', '+1-212-555-5001', 'Website', 'NEW', 'Interested in custom balayage');

-- 6.9 Insert Sample Review
INSERT INTO reviews (id, customer_id, branch_id, appointment_id, rating, comment, status) VALUES
('0e3f1b64-444c-4c6e-0342-cf0e985c0df3', '7b3f1b64-114c-4c6e-d342-9d0e985c7df1', '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', NULL, 5, 'Great haircut and incredible professional service!', 'APPROVED');

-- 6.10 Insert Sample Analytics
INSERT INTO analytics_records (metric_name, metric_value, dimensions) VALUES
('daily_active_users', 4.0, '{"platform": "web"}'),
('successful_bookings', 1.0, '{"branch": "Downtown Elite"}');
