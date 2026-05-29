# ⚡ Supabase Quick Reference Card

## 🚀 5-Minute Setup

### Step 1: Verify Credentials
```bash
# Check .env file has Supabase credentials
cat backend/.env | grep SUPABASE_
cat backend/.env | grep DATABASE_URL
```

### Step 2: Run Migrations
```bash
cd backend
alembic upgrade head
```

### Step 3: Verify Connection
```bash
# From project root
python verify_supabase.py
```

Expected output:
```
📊 VERIFICATION SUMMARY
========================
Environment Variables        ✅ PASS
Database Connection           ✅ PASS
Database Tables               ✅ PASS
Model Definitions             ✅ PASS
Sample Query                  ✅ PASS
Migrations Status             ✅ PASS

Total: 6/6 checks passed

🎉 ALL CHECKS PASSED!
```

### Step 4: Seed Data (Optional)
```bash
cd backend
python -m db.seed
```

### Step 5: Start Services

**Terminal 1 - Backend:**
```bash
cd backend
uvicorn main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - Verification:**
```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{"status": "healthy", "database": "connected"}
```

---

## 🔧 Common Commands

| Command | Purpose |
|---------|---------|
| `alembic upgrade head` | Create all tables in database |
| `alembic downgrade -1` | Rollback last migration |
| `alembic history` | Show migration history |
| `python verify_supabase.py` | Test database connection |
| `python -m db.seed` | Populate with sample data |
| `uvicorn main:app --reload` | Start backend server |
| `npm run dev` | Start frontend dev server |
| `psql $DATABASE_URL` | Connect directly to database |

---

## 📊 API Endpoints

### Health & Status
```
GET /api/v1/health
```

### Branches
```
GET    /api/v1/branches          # List all branches
GET    /api/v1/branches/{id}     # Get specific branch
POST   /api/v1/branches          # Create branch
PUT    /api/v1/branches/{id}     # Update branch
DELETE /api/v1/branches/{id}     # Delete branch
```

### Staff
```
GET    /api/v1/staff
GET    /api/v1/staff/{id}
POST   /api/v1/staff
PUT    /api/v1/staff/{id}
DELETE /api/v1/staff/{id}
```

### Services
```
GET    /api/v1/services
GET    /api/v1/services/{id}
POST   /api/v1/services
```

### Appointments
```
GET    /api/v1/appointments
POST   /api/v1/appointments
PUT    /api/v1/appointments/{id}
```

---

## 🐛 Quick Troubleshooting

### Connection Error
```bash
# Check credentials
cat backend/.env

# Test connection directly
psql -c "SELECT 1;" $DATABASE_URL

# Check Supabase status
curl https://status.supabase.com
```

### Tables Not Found
```bash
# Run migrations
cd backend
alembic upgrade head

# Verify tables
alembic history
```

### Too Many Connections
```python
# In backend/db/database.py, reduce pool_size
pool_kwargs = {
    "pool_size": 5,          # Reduced from 20
    "max_overflow": 2,
    "pool_recycle": 1800,
    "pool_pre_ping": True,
}
```

### SSL Certificate Error
```bash
# Add to .env
DATABASE_URL="postgresql://...?sslmode=require"
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `backend/.env` | Supabase credentials |
| `backend/db/database.py` | Connection & pooling |
| `backend/db/models.py` | ORM models (tables) |
| `backend/core/config.py` | Settings loader |
| `verify_supabase.py` | Verification script |
| `alembic.ini` | Migration config |
| `SUPABASE_SETUP_GUIDE.md` | Full documentation |

---

## 💾 Database Schema

```
Branches (salons)
  ├── id (UUID, PK)
  ├── name, code, address, city
  └── created_at, updated_at

Staff (employees)
  ├── id (UUID, PK)
  ├── branch_id (FK → Branches)
  ├── first_name, last_name, email, phone
  └── created_at, updated_at

Services (offerings)
  ├── id (UUID, PK)
  ├── name, description, price, duration
  ├── branch_id (FK → Branches)
  └── created_at, updated_at

Appointments (bookings)
  ├── id (UUID, PK)
  ├── customer_id (FK → Customers)
  ├── staff_id (FK → Staff)
  ├── service_id (FK → Services)
  ├── branch_id (FK → Branches)
  ├── appointment_time, duration
  ├── status (PENDING|CONFIRMED|COMPLETED|CANCELLED|NO_SHOW)
  └── created_at, updated_at

Customers (clients)
  ├── id (UUID, PK)
  ├── first_name, last_name, email, phone
  ├── branch_id (FK → Branches)
  └── created_at, updated_at

Leads (prospects)
  ├── id (UUID, PK)
  ├── first_name, last_name, email, phone
  ├── branch_id (FK → Branches)
  ├── status (NEW|CONTACTED|CONVERTED|LOST)
  └── created_at, updated_at

Reviews (feedback)
  ├── id (UUID, PK)
  ├── customer_id (FK → Customers)
  ├── branch_id (FK → Branches)
  ├── rating, comment
  ├── status (PENDING|APPROVED|REJECTED)
  └── created_at, updated_at

Users (authentication)
  ├── id (UUID, PK)
  ├── email, hashed_password
  ├── role (ADMIN|OWNER|MANAGER|STAFF|CUSTOMER)
  └── created_at, updated_at
```

---

## ✅ Verification Checklist

- [ ] `.env` file exists with Supabase credentials
- [ ] `alembic upgrade head` runs without errors
- [ ] `python verify_supabase.py` shows 6/6 PASS
- [ ] Backend starts: `uvicorn main:app --reload`
- [ ] Frontend starts: `npm run dev`
- [ ] `curl http://localhost:8000/api/v1/health` returns 200
- [ ] Database has data: `python -c "from db.database import SessionLocal; from db.models import Branch; db = SessionLocal(); print(db.query(Branch).count())"`

---

## 📚 Full Documentation

- **SUPABASE_SETUP_GUIDE.md** - Complete setup guide with troubleshooting
- **verify_supabase.py** - Automated verification script
- **backend/db/database.py** - Connection pooling details
- **START_HERE.md** - Project overview
- **DEPLOYMENT_GUIDE.md** - Production deployment

---

## 🎯 Next Steps

1. ✅ Run `python verify_supabase.py` to verify connection
2. ✅ Start backend: `uvicorn main:app --reload`
3. ✅ Start frontend: `npm run dev`
4. ✅ Open http://localhost:5173
5. ✅ Build your application!

🚀 **You're ready to go!**
