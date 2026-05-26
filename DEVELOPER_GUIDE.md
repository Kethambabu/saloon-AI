# SalonAI Workforce - Developer Guidelines

Complete guidelines for development on the SalonAI Workforce project.

## Table of Contents

1. [Development Environment](#development-environment)
2. [Code Style and Standards](#code-style-and-standards)
3. [Git Workflow](#git-workflow)
4. [Dependency Management](#dependency-management)
5. [Testing](#testing)
6. [Documentation](#documentation)
7. [Performance Considerations](#performance-considerations)
8. [Security Best Practices](#security-best-practices)

## Development Environment

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+
- Git
- VS Code with recommended extensions

### Workspace Setup

1. Open the root directory in VS Code
2. Install recommended extensions when prompted
3. Run `.\start.ps1` (Windows) or `./start.sh` (macOS/Linux)
4. VS Code will automatically detect both Python and Node environments

### Environment Variables

**Always use `.env.example` as reference:**

1. Copy `.env.example` to `.env`
2. Fill in required values:
   - Database connection string (leave empty for development)
   - API keys (for external services)
   - Debug mode (true for development)
3. Never commit `.env` file

## Code Style and Standards

### Python (Backend)

**Style Guide:** PEP 8 (enforced by Black, Pylint)

**Key Rules:**

- Line length: 100 characters (configurable in `pyproject.toml`)
- Use type hints for function arguments and returns
- Write docstrings for modules, classes, and public functions
- Use logging instead of print statements

**Code Examples:**

```python
# Good
def calculate_total_hours(employee_id: int) -> float:
    """
    Calculate total working hours for an employee.
    
    Args:
        employee_id: Unique employee identifier
        
    Returns:
        Total hours worked in the current month
    """
    logger.info(f"Calculating hours for employee {employee_id}")
    # Implementation...
    return total_hours

# Bad
def calc_hours(eid):
    print(f"Calculating for {eid}")  # Use logger instead
    return total
```

**Auto-formatting:**

```bash
cd backend
./venv/Scripts/Activate.ps1
black . --line-length 100
```

**Linting:**

```bash
pylint core/ main.py
flake8 core/
```

### TypeScript/React (Frontend)

**Style Guide:** ESLint + Prettier (enforced)

**Key Rules:**

- Use functional components with hooks
- Use TypeScript strict mode
- Props should be typed interfaces
- Use meaningful variable names
- Organize imports at top of file

**Code Examples:**

```typescript
// Good
interface UserProps {
  userId: string;
  onUpdate: (user: User) => void;
}

const UserCard: React.FC<UserProps> = ({ userId, onUpdate }) => {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    fetchUser(userId).then(setUser);
  }, [userId]);

  return <div>{user?.name}</div>;
};

// Bad
const UserCard = ({ user_id, updateUser }) => {
  // Missing types
  // Unclear prop naming
  return <div>{user.name}</div>;
};
```

**Auto-formatting:**

```bash
cd frontend
npm run format
npm run lint:fix
```

## Git Workflow

### Branching Strategy

```
main                          # Production-ready code
├── develop                   # Integration branch
│   ├── feature/feature-name  # Feature branches
│   ├── fix/issue-name        # Bug fix branches
│   └── docs/description      # Documentation branches
```

### Commit Messages

**Format:** `type(scope): description`

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Build process, dependencies, tools

**Examples:**

```
feat(auth): add JWT token validation
fix(scheduler): correct timezone conversion error
docs(api): update endpoint documentation
chore(deps): update fastapi to 0.105.0
```

### Pull Request Guidelines

1. Create feature branch from `develop`
2. Commit logical, atomic changes
3. Write descriptive commit messages
4. Before creating PR:
   - Run `npm run lint && npm run format` (frontend)
   - Run `pylint` and `black` (backend)
   - Ensure all tests pass
   - Update documentation if needed
5. Push to remote and create PR with description
6. Address review comments
7. Merge after approval

## Dependency Management

### Adding Dependencies

**CRITICAL: Always follow these steps**

#### Backend Python

```bash
cd backend
.\venv\Scripts\Activate.ps1

# 1. Install the package
pip install package_name==version

# 2. Verify it works in your code
# ... test code ...

# 3. Update requirements.txt
pip freeze > requirements.txt

# 4. Commit both changes
git add requirements.txt
git commit -m "feat: add package_name for feature_description"
```

**Example:**

```bash
pip install langchain==0.1.0
pip freeze > requirements.txt
```

#### Frontend Node/npm

```bash
cd frontend

# 1. Install the package
npm install package-name --save       # Runtime dependency
npm install -D package-name           # Dev dependency

# 2. Test the package
# ... test code ...

# 3. Commit
# package-lock.json is automatically updated
git add package.json package-lock.json
git commit -m "feat: add package-name for feature_description"
```

### Updating Dependencies

**Backend:**

```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install --upgrade package_name
pip freeze > requirements.txt
```

**Frontend:**

```bash
cd frontend
npm update package-name
# or for all packages
npm update
```

### Dependency Review

**Every Pull Request should:**

1. Include only necessary dependencies
2. Use specific versions (not wildcards where possible)
3. Include security patches
4. Be compatible with existing dependencies

## Testing

### Backend Testing

**Framework:** pytest

**Structure:**

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared test configuration
│   ├── test_config.py           # Config tests
│   ├── api/
│   │   └── test_endpoints.py    # Endpoint tests
│   └── services/
│       └── test_service.py      # Service tests
```

**Running Tests:**

```bash
cd backend
.\venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -v

# Run specific file
pytest tests/test_config.py -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html
```

**Writing Tests:**

```python
import pytest
from core.config import Settings

def test_settings_loading():
    """Test that settings load correctly from environment."""
    settings = Settings(
        app_name="Test App",
        debug=True
    )
    assert settings.app_name == "Test App"
    assert settings.debug is True

@pytest.mark.asyncio
async def test_async_function():
    """Test async functions with pytest-asyncio."""
    result = await async_operation()
    assert result is not None
```

### Frontend Testing

**Framework:** Jest/Vitest (configured in package.json)

**Running Tests:**

```bash
cd frontend

# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Watch mode
npm test -- --watch
```

## Documentation

### Code Documentation

**Python Docstrings:**

```python
def calculate_commission(hours: float, rate: float) -> float:
    """
    Calculate commission based on hours and rate.
    
    Uses the standard commission formula:
    commission = hours * rate * 0.05
    
    Args:
        hours: Number of hours worked
        rate: Hourly rate in dollars
        
    Returns:
        Commission amount in dollars
        
    Raises:
        ValueError: If hours or rate is negative
        
    Example:
        >>> calculate_commission(40, 50)
        100.0
    """
    if hours < 0 or rate < 0:
        raise ValueError("Hours and rate must be non-negative")
    return hours * rate * 0.05
```

**TypeScript JSDoc:**

```typescript
/**
 * Validates user email format.
 * 
 * @param email - The email address to validate
 * @returns True if email is valid, false otherwise
 * 
 * @example
 * isValidEmail("user@example.com") // true
 */
function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
```

### API Documentation

**FastAPI auto-generates OpenAPI docs:**

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

**Document endpoints with:**

```python
@app.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: int):
    """
    Retrieve employee information.
    
    - **employee_id**: Unique employee identifier
    
    Returns employee details including name, position, and hours.
    """
```

## Performance Considerations

### Backend Optimization

1. **Database Queries:**
   - Use eager loading for relationships
   - Paginate large result sets
   - Index frequently queried columns

2. **Caching:**
   - Use `@lru_cache()` for expensive computations
   - Consider Redis for distributed caching
   - Set appropriate TTL values

3. **Async Operations:**
   - Use `async def` for I/O-bound operations
   - Don't use `time.sleep()`, use `asyncio.sleep()`
   - Pool database connections

### Frontend Optimization

1. **Code Splitting:**
   - Use dynamic imports for route components
   - Vite handles this automatically

2. **Bundle Size:**
   - Check bundle size: `npm run build -- --analyze`
   - Remove unused dependencies
   - Use tree-shaking compatible imports

3. **Rendering:**
   - Use React.memo for expensive components
   - Optimize re-renders with useCallback
   - Use lazy loading for images

## Security Best Practices

### Authentication & Authorization

1. Never log sensitive information
2. Use secure token storage (HttpOnly cookies)
3. Validate all API requests
4. Implement rate limiting

### Data Protection

1. Hash passwords with strong algorithms (bcrypt, argon2)
2. Encrypt sensitive data at rest
3. Use HTTPS in production
4. Sanitize user input
5. Protect against SQL injection (use ORM)

### Environment Secrets

1. Never commit `.env` file
2. Use `.env.example` as reference only
3. Use secret management service in production
4. Rotate credentials regularly

### Dependencies

1. Keep dependencies updated
2. Use `npm audit` and `pip check`
3. Review security advisories
4. Use specific versions in production

---

**Document Version:** 1.0  
**Last Updated:** May 24, 2026
