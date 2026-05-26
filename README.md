# SalonAI Workforce

An enterprise-grade AI-powered workforce management system for salons.

## Project Structure

```
saloon/
├── backend/                    # Python FastAPI backend
│   ├── core/                   # Core configuration and utilities
│   │   ├── __init__.py
│   │   ├── config.py          # Application settings
│   │   └── logging.py         # Logging configuration
│   ├── venv/                   # Python virtual environment (created on setup)
│   ├── requirements.txt        # Python dependencies
│   ├── pyproject.toml          # Python project configuration
│   └── .flake8                 # Flake8 linting config
│
├── frontend/                   # React + TypeScript + Vite frontend
│   ├── src/                    # Source code
│   ├── public/                 # Static assets
│   ├── package.json            # Node dependencies and scripts
│   ├── tsconfig.json           # TypeScript configuration
│   ├── vite.config.ts          # Vite configuration
│   ├── tailwind.config.js      # Tailwind CSS configuration
│   ├── eslint.config.js        # ESLint configuration
│   ├── .prettierrc             # Prettier code formatting
│   └── .prettierignore
│
├── .env.example                # Environment variables template
├── .env                        # Environment variables (not in git)
├── .gitignore                  # Git ignore rules
├── .vscode/settings.json       # VS Code workspace settings
├── setup.md                    # Complete setup guide
├── start.ps1                   # Windows startup script
├── start.sh                    # macOS/Linux startup script
└── README.md                   # This file
```

## Quick Start

### 1. Clone and Setup

```bash
# Clone repository
git clone <repository>
cd saloon

# Run setup script
# Windows
.\start.ps1

# macOS/Linux
chmod +x start.sh
./start.sh
```

### 2. Access Applications

- **Frontend:** http://localhost:5173
- **Backend API:** http://127.0.0.1:8000
- **API Docs:** http://127.0.0.1:8000/docs

## Technology Stack

### Backend

- **Framework:** FastAPI 0.104.1
- **Server:** Uvicorn 0.24.0
- **Language:** Python 3.11
- **ORM:** SQLAlchemy 2.0.23
- **Migrations:** Alembic 1.12.1
- **AI Integration:** LangChain, PyAutoGen
- **Vector Search:** FAISS
- **Database:** PostgreSQL (psycopg2)
- **Environment:** python-dotenv
- **Validation:** Pydantic 2.5.0
- **Testing:** pytest 7.4.3
- **API Client:** httpx 0.25.1
- **Backend Services:** Supabase

### Frontend

- **Framework:** React 18.2
- **Language:** TypeScript 5.2
- **Build Tool:** Vite 5.2
- **Styling:** Tailwind CSS 3.4
- **Linting:** ESLint 8.57
- **Formatting:** Prettier 3.1
- **Package Manager:** npm

## Development Setup

For detailed setup instructions, see [setup.md](setup.md).

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+
- VS Code (recommended)

### Quick Commands

**Backend:**
```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Environment Configuration

1. Copy `.env.example` to `.env`
2. Configure the following:
   - Database connection string
   - API keys (Groq, Supabase)
   - Application settings

See `.env.example` for all available options.

## Available Scripts

### Backend

```bash
cd backend
.\venv\Scripts\Activate.ps1

# Development
uvicorn main:app --reload

# Linting
pylint core/

# Testing
pytest tests/

# Update dependencies
pip freeze > requirements.txt
```

### Frontend

```bash
cd frontend

# Development
npm run dev

# Build
npm run build

# Linting
npm run lint

# Fix linting issues
npm run lint:fix

# Format code
npm run format

# Type checking
npm run type-check
```

## Adding Dependencies

### Python Backend

**IMPORTANT:** Always update requirements.txt after installing packages.

```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install <package_name>
pip freeze > requirements.txt
```

### Node Frontend

```bash
cd frontend
npm install <package_name>
# or dev dependency
npm install -D <package_name>
```

## Code Quality

### Linting and Formatting

The project uses:

- **Backend:** Black (formatter), Pylint, Flake8
- **Frontend:** ESLint, Prettier

Auto-formatting is enabled in VS Code on file save.

### Type Checking

- **Backend:** MyPy integration
- **Frontend:** TypeScript strict mode

## Testing

```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend
npm test
```

## Project Status

**Version:** 0.1.0  
**Status:** Initial Setup Phase  
**Last Updated:** May 24, 2026

## Contributing

1. Follow the code style guidelines (enforced by linters)
2. Add tests for new features
3. Update dependencies properly (see section above)
4. Ensure all tests pass before committing
5. Update documentation as needed

## Documentation

- [Setup Guide](setup.md) - Complete installation and configuration
- Backend API docs: http://127.0.0.1:8000/docs (when running)
- Code comments and docstrings for implementation details

## Troubleshooting

See [setup.md - Troubleshooting Section](setup.md#troubleshooting) for common issues and solutions.

## License

[Your License Here]

## Support

For issues and questions, please refer to the [setup guide](setup.md) or contact the development team.

---

**SalonAI Workforce** | Enterprise AI-Powered Salon Management System
