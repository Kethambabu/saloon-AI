# SalonAI Workforce - Quick Start Guide

## Prerequisites

- Docker & Docker Compose (for containerized development)
- Python 3.11+ (for local backend development)
- Node.js 18+ (for local frontend development)
- PostgreSQL 15+ (if running locally without Docker)

## Quick Start

### Option 1: Docker Compose (Recommended for Development)

```bash
# Clone or navigate to project directory
cd salon-ai-workforce

# Copy example environment file
cp .env.example .env

# Start all services (PostgreSQL, Backend, Frontend)
docker-compose up

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/api/docs
```

### Option 2: Local Development Setup

#### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp ../.env.example ../.env

# Run database migrations (when applicable)
alembic upgrade head

# Start the backend server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create .env file from example
cp .env.example .env

# Start the development server
npm run dev

# Application runs at http://localhost:5173
```

## Project Structure Overview

### Backend Architecture

```
backend/
├── main.py                 # FastAPI app entry point
├── core/                   # Configuration & logging
├── agents/                 # AI agent implementations
├── tools/                  # Agent tools & utilities
├── rag/                    # RAG (document processing)
├── api/routes/             # REST API endpoints
├── db/                     # Database models & session
└── tests/                  # Test suite
```

### Frontend Architecture

```
frontend/src/
├── components/             # Reusable React components
├── hooks/                  # Custom React hooks
├── store/                  # Zustand state management
├── api/                    # Axios client & services
├── App.tsx                 # Root component
└── main.tsx                # React app entry
```

## Key Configuration Files

### Backend Configuration

- **`backend/core/config.py`**: Application settings (database, logging, API keys)
- **`backend/pyproject.toml`**: Project metadata and tool configurations
- **`backend/requirements.txt`**: Python package dependencies
- **`.env`**: Environment variables (create from `.env.example`)

### Frontend Configuration

- **`frontend/vite.config.ts`**: Vite build configuration
- **`frontend/tsconfig.json`**: TypeScript configuration
- **`frontend/tailwind.config.js`**: Tailwind CSS setup
- **`frontend/.env`**: Environment variables (API URL, etc.)

## Common Commands

### Backend

```bash
# Run server with auto-reload
uvicorn main:app --reload

# Run tests
pytest

# Run tests with coverage
pytest --cov=. --cov-report=html

# Format code
black .

# Lint code
pylint backend

# Type check
mypy .
```

### Frontend

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run linter
npm run lint

# Fix linting issues
npm run lint:fix

# Format code
npm run format

# Check formatting
npm run format:check

# Type check
npm run type-check
```

## API Documentation

Once the backend is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

### Example API Calls

```bash
# Health check
curl http://localhost:8000/health

# Get API info
curl http://localhost:8000/api/v1

# With authentication (when implemented)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/users
```

## Frontend API Integration

### Making API Calls

```typescript
import { useApi } from '@/hooks/useApi';

function MyComponent() {
  const { get, post, data, loading, error } = useApi();

  const fetchUsers = async () => {
    try {
      const response = await get('/users');
      console.log(response);
    } catch (err) {
      console.error(err);
    }
  };

  return <button onClick={fetchUsers}>Load Users</button>;
}
```

### Using Global State

```typescript
import { useAppStore } from '@/store/appStore';

function MyComponent() {
  const { isLoading, error, setError } = useAppStore();

  return (
    <div>
      {isLoading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
    </div>
  );
}
```

## Environment Setup

### Development Environment

1. Copy `.env.example` to `.env`
2. Update values for your local setup:
   ```env
   ENVIRONMENT=development
   DEBUG=true
   DATABASE_URL=postgresql://localhost/salonai_db
   VITE_API_URL=http://localhost:8000/api/v1
   ```

### Production Environment

1. Copy `.env.production` and update:
   ```env
   ENVIRONMENT=production
   DEBUG=false
   SECRET_KEY=your-secure-key-here
   DATABASE_URL=your-production-db-url
   ```
2. Update domain names and API URLs

## Database Setup

### Using Docker Compose

```bash
# Database is automatically created in docker-compose.yml
# Connect with:
# Host: localhost
# Port: 5432
# User: salonai_user
# Password: salonai_password
# Database: salonai_db
```

### Local PostgreSQL

```bash
# Install PostgreSQL
brew install postgresql  # macOS
# or
sudo apt-get install postgresql  # Linux

# Create database
createdb salonai_db

# Create user
createuser -P salonai_user
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :8000  # Backend
lsof -i :3000  # Frontend

# Kill process
kill -9 <PID>
```

### Docker Issues

```bash
# Remove all containers and volumes
docker-compose down -v

# Rebuild containers
docker-compose up --build

# View logs
docker-compose logs -f [service-name]
```

### Database Connection Issues

```bash
# Check if PostgreSQL is running
psql -U salonai_user -d salonai_db

# Reset database (development only)
dropdb salonai_db
createdb salonai_db
```

### Module Import Errors (Python)

```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify Python version
python --version  # Should be 3.11+
```

## Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_health.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=backend --cov-report=html
```

### Frontend Tests (Ready to Configure)

```bash
# Setup testing (when needed)
npm install -D vitest @testing-library/react @testing-library/jest-dom

# Run tests
npm run test
```

## Deployment

### Docker Build

```bash
# Build backend image
docker build -f Dockerfile.backend -t salonai-backend .

# Build frontend image
docker build -f Dockerfile.frontend -t salonai-frontend .

# Run with docker-compose
docker-compose up -d
```

### Production Deployment

1. Update `.env.production` with production credentials
2. Set environment variable: `export ENVIRONMENT=production`
3. Use docker-compose with production settings:
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

## Code Quality & Standards

### Backend

- **Formatter**: Black (auto-format on save in VS Code)
- **Linter**: Pylint
- **Type Checking**: MyPy (ready)
- **Testing**: Pytest

### Frontend

- **Formatter**: Prettier (auto-format on save in VS Code)
- **Linter**: ESLint with TypeScript
- **Testing**: Vitest (ready)

All tools are pre-configured in VS Code via `.vscode/settings.json`

## Git Workflow

### Never Commit

```
.env                # Local environment variables
.env.local          # Local overrides
venv/              # Python virtual environment
node_modules/      # Node packages
dist/              # Build outputs
__pycache__/       # Python cache
.DS_Store          # macOS files
*.log              # Log files
```

### Use .gitignore

All important files are already in `.gitignore` - verify before committing.

## Additional Resources

- **Architecture**: See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **API Documentation**: http://localhost:8000/api/docs (when running)
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **React Documentation**: https://react.dev/
- **Docker Documentation**: https://docs.docker.com/

## Next Steps

1. ✅ Architecture is set up
2. ⏭️ Implement database models
3. ⏭️ Create API endpoints
4. ⏭️ Build React components
5. ⏭️ Implement authentication
6. ⏭️ Add business logic (agents, RAG, tools)
7. ⏭️ Write comprehensive tests
8. ⏭️ Deploy to production

## Support & Issues

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review [ARCHITECTURE.md](./ARCHITECTURE.md) for design patterns
3. Check API docs: http://localhost:8000/api/docs
4. Review environment variables in `.env.example`

---

**Happy coding! 🚀**
