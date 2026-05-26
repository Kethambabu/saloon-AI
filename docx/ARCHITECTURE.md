# SalonAI Workforce - Architecture Documentation

## Project Overview

SalonAI Workforce is a production-ready full-stack application for salon workforce management powered by AI agents. The architecture follows enterprise software patterns with separation of concerns, scalability, and maintainability.

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **AI/ML**: Microsoft AutoGen, LangChain
- **Task Queue**: Ready for Celery integration
- **Testing**: Pytest
- **Code Quality**: Black, Pylint, MyPy

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **State Management**: Zustand
- **HTTP Client**: Axios
- **Styling**: Tailwind CSS
- **Testing**: Vitest (ready)

### DevOps
- **Containerization**: Docker & Docker Compose
- **Orchestration**: Ready for Kubernetes
- **Reverse Proxy**: Nginx (frontend)
- **Process Manager**: Uvicorn (backend)

## Folder Structure

### Backend (`backend/`)

```
backend/
├── main.py                 # FastAPI application entry point
├── core/                   # Core application utilities
│   ├── config.py          # Configuration management
│   └── logging.py         # Logging setup
├── agents/                # AI agents module
│   ├── __init__.py        # Agent and AgentOrchestrator classes
│   └── [agent_modules]    # Individual agent implementations
├── tools/                 # Tools for agents
│   ├── __init__.py        # Tool and ToolRegistry classes
│   └── [tool_modules]     # Individual tool implementations
├── rag/                   # RAG (Retrieval Augmented Generation)
│   ├── __init__.py        # RAGManager class
│   └── [rag_modules]      # Document processing, embeddings, etc.
├── api/                   # API endpoints
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py    # Route definitions
│       └── [route_modules] # Specific routes (users, tasks, etc.)
├── db/                    # Database configuration
│   ├── __init__.py        # SQLAlchemy engine, session, Base
│   ├── models.py          # ORM models
│   └── [model_files]      # Additional model definitions
└── tests/                 # Test suite
    ├── conftest.py        # Pytest fixtures and configuration
    ├── test_health.py     # Health check tests
    └── [test_modules]     # Feature-specific tests
```

### Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── main.tsx           # React app entry point
│   ├── App.tsx            # Root component
│   ├── index.css          # Global styles
│   ├── components/        # Reusable React components
│   │   ├── Layout.tsx     # Main layout wrapper
│   │   ├── Loading.tsx    # Loading spinner
│   │   ├── Error.tsx      # Error display
│   │   └── index.ts       # Component exports
│   ├── hooks/             # Custom React hooks
│   │   ├── useApi.ts      # API call hook with state management
│   │   └── index.ts       # Hook exports
│   ├── store/             # Zustand store (state management)
│   │   ├── appStore.ts    # Global app state
│   │   └── index.ts       # Store exports
│   ├── api/               # API client and services
│   │   ├── client.ts      # Axios instance configuration
│   │   ├── services.ts    # API service layer
│   │   └── index.ts       # API exports
│   └── assets/            # Static assets
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.js
```

### Root Level Configuration Files

```
├── Dockerfile.backend     # Backend container image
├── Dockerfile.frontend    # Frontend container image
├── docker-compose.yml     # Multi-container orchestration
├── .dockerignore           # Docker build context exclusions
├── .env.example            # Environment variables template
├── .env.production         # Production environment variables
├── ARCHITECTURE.md         # This file
└── [other config files]
```

## Architecture Patterns

### Backend Architecture

#### 1. **Layered Architecture**
- **Presentation Layer**: FastAPI routes in `api/routes/`
- **Business Logic Layer**: Agents, Tools, and RAG modules
- **Data Access Layer**: SQLAlchemy models in `db/`
- **Infrastructure Layer**: Config, Logging, Database connections

#### 2. **Dependency Injection**
- Configuration via `core.config.get_settings()`
- Database session via `db.get_db()` dependency
- Request/Response validation with Pydantic

#### 3. **Module Organization**
- **Agents**: AI processing and orchestration
- **Tools**: Agent capabilities and utilities
- **RAG**: Document retrieval and embedding
- **API**: REST endpoint definitions

### Frontend Architecture

#### 1. **Component-Based**
- **Layout**: Wrapper components for page structure
- **UI Components**: Reusable, stateless components
- **Feature Components**: Business logic components

#### 2. **State Management**
- **Global State**: Zustand store (`store/appStore.ts`)
- **Local State**: React hooks where appropriate
- **Async State**: `useApi` hook for API calls

#### 3. **API Integration**
- **Client**: Axios with interceptors (`api/client.ts`)
- **Services**: High-level API functions (`api/services.ts`)
- **Hooks**: Custom hook for API calls with state (`hooks/useApi.ts`)

## Key Features

### Backend Features

1. **Configuration Management**
   - Environment-based configuration
   - Pydantic BaseSettings for type safety
   - Support for development, staging, production

2. **Logging**
   - Structured JSON logging
   - Console and file output
   - Rotating file handlers
   - Different levels per environment

3. **Database**
   - SQLAlchemy ORM with async support ready
   - Connection pooling
   - Migration support via Alembic (ready)

4. **AI/Agent System**
   - Agent orchestrator for managing multiple agents
   - Tool registry for agent capabilities
   - RAG manager for document processing

5. **API**
   - OpenAPI documentation at `/api/docs`
   - Health checks at `/health`
   - CORS configuration
   - Error handling middleware ready

6. **Testing**
   - Pytest fixtures and configuration
   - TestClient for integration tests
   - Health check tests included

### Frontend Features

1. **API Client**
   - Axios instance with interceptors
   - Bearer token authentication ready
   - Error handling and redirects
   - Request/response transformation

2. **State Management**
   - Global app state with Zustand
   - Persistent localStorage integration
   - Redux DevTools support
   - Loading and error state management

3. **Custom Hooks**
   - `useApi`: Handles GET, POST, PUT, DELETE
   - Integration with global state
   - Automatic error handling

4. **Components**
   - Layout wrapper with header/footer
   - Loading spinner with size variants
   - Error display with dismiss option
   - Ready for feature components

5. **Environment Configuration**
   - Vite env variables with `VITE_` prefix
   - Separate `.env` files for each environment
   - Runtime configuration

## Data Flow

### API Call Flow (Frontend)

```
User Action
    ↓
Component calls useApi hook
    ↓
Hook formats request with Axios client
    ↓
Axios interceptor adds auth token
    ↓
Request sent to FastAPI backend
    ↓
Response received
    ↓
Zustand store updated (loading, error states)
    ↓
Component re-renders with new data
```

### Backend Request Processing

```
HTTP Request arrives
    ↓
CORS middleware validates origin
    ↓
FastAPI route handler processes request
    ↓
Pydantic validates request data
    ↓
Dependency injection provides DB session, config
    ↓
Business logic executes (agents, RAG, etc.)
    ↓
Response formatted and returned
    ↓
JSON response sent to client
```

## Database Schema (Ready for Implementation)

```sql
-- Base model fields (inherited by all models)
- id: Integer (PK)
- created_at: DateTime
- updated_at: DateTime

-- Custom models extend BaseModel
-- Example: User, Salon, Appointment, etc.
```

## API Endpoints (Ready for Implementation)

```
GET /health                  - Health check
GET /api/v1                  - API info
POST /api/v1/auth/login      - [Ready]
GET /api/v1/auth/me          - [Ready]
POST /api/v1/users           - [Ready]
GET /api/v1/users/:id        - [Ready]
```

## Environment Variables

### Backend (.env)
- `APP_NAME`: Application name
- `ENVIRONMENT`: dev/staging/production
- `DATABASE_URL`: PostgreSQL connection string
- `OPENAI_API_KEY`: OpenAI API key
- `SECRET_KEY`: JWT secret
- `CORS_ORIGINS`: Allowed CORS origins

### Frontend (.env)
- `VITE_API_URL`: Backend API URL
- `VITE_ENVIRONMENT`: Environment name
- `VITE_LOG_LEVEL`: Logging level

## Docker Deployment

### Development
```bash
docker-compose up
```

### Production
```bash
docker-compose -f docker-compose.yml up -d
```

Services exposed:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- PostgreSQL: localhost:5432

## Security Considerations

1. **CORS**: Configured for localhost in development
2. **Authentication**: Ready for JWT/Bearer tokens
3. **Database**: Credentials in environment variables
4. **API Keys**: Not hardcoded, loaded from environment
5. **Non-root user**: Docker runs as non-root `appuser`
6. **Secret key**: Must be changed for production

## Performance Optimization

1. **Frontend**
   - Vite for fast builds
   - Gzip compression in Nginx
   - Cache headers on static assets
   - Code splitting ready with React

2. **Backend**
   - Async/await support
   - Database connection pooling
   - Request validation at entry point
   - Ready for horizontal scaling

3. **Database**
   - Connection pooling via SQLAlchemy
   - Indexes on foreign keys (ready)
   - Query optimization ready

## Scaling Considerations

1. **Horizontal Scaling**
   - Stateless API design
   - External session/cache (Redis ready)
   - Load balancer support

2. **Task Processing**
   - Celery integration ready
   - Message queue (RabbitMQ/Redis)
   - Long-running agent tasks

3. **Database**
   - Replication and backups ready
   - Alembic for migrations
   - Connection pooling configured

## Development Workflow

1. **Setup**
   ```bash
   # Backend
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Frontend
   cd frontend
   npm install
   ```

2. **Run Locally**
   ```bash
   # Backend
   uvicorn main:app --reload
   
   # Frontend
   npm run dev
   ```

3. **Docker Development**
   ```bash
   docker-compose up
   ```

4. **Run Tests**
   ```bash
   # Backend
   pytest
   
   # Frontend (ready)
   npm run test
   ```

## Next Steps for Implementation

1. **Database Models**: Define application models extending `BaseModel`
2. **API Routes**: Implement feature routes in `api/routes/`
3. **Business Logic**: Develop agent implementations
4. **Components**: Build UI components using provided base components
5. **Tests**: Write unit and integration tests
6. **Documentation**: API documentation via OpenAPI

## References

- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- TypeScript: https://www.typescriptlang.org/
- Zustand: https://github.com/pmndrs/zustand
- SQLAlchemy: https://www.sqlalchemy.org/
- Docker: https://www.docker.com/
