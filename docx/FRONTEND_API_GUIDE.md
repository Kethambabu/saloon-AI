# SalonAI Workforce - Frontend API Integration Guide

## Overview

This guide explains how to integrate the React frontend with the FastAPI backend using the provided API client, custom hooks, and state management.

## API Client Architecture

### 1. Axios Client (`src/api/client.ts`)

Configured Axios instance with:
- Base URL from environment variables
- Request/response interceptors
- CORS credentials
- Bearer token authentication
- Automatic error handling

```typescript
import { apiClient, API_BASE_URL } from '@/api/client';

// Direct API calls
const response = await apiClient.get('/users');
const created = await apiClient.post('/users', { name: 'John' });
const updated = await apiClient.put('/users/1', { name: 'Jane' });
await apiClient.delete('/users/1');
```

### 2. API Services (`src/api/services.ts`)

High-level service functions for common operations:

```typescript
import { apiServices } from '@/api';

// Health check
const health = await apiServices.healthCheck();

// API info
const info = await apiServices.getApiInfo();
```

### 3. Custom Hook (`src/hooks/useApi.ts`)

The `useApi` hook provides a convenient way to make API calls with state management:

```typescript
import { useApi } from '@/hooks/useApi';

function MyComponent() {
  const { get, post, data, loading, error } = useApi<UserType>();

  const fetchUsers = async () => {
    try {
      const response = await get('/users');
      // Uses global state for loading
    } catch (err) {
      // Error handled automatically
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  
  return <div>{/* render data */}</div>;
}
```

## Making API Requests

### GET Requests

```typescript
import { useApi } from '@/hooks/useApi';

interface User {
  id: number;
  name: string;
  email: string;
}

function UserList() {
  const { get, data: users, loading } = useApi<User[]>();

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        await get('/users');
      } catch (error) {
        console.error('Failed to fetch users:', error);
      }
    };

    fetchUsers();
  }, [get]);

  if (loading) return <p>Loading users...</p>;

  return (
    <ul>
      {users?.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}
```

### POST Requests (Create)

```typescript
import { useApi } from '@/hooks/useApi';

interface CreateUserRequest {
  name: string;
  email: string;
}

interface User extends CreateUserRequest {
  id: number;
}

function CreateUserForm() {
  const { post, loading, error } = useApi<User>();
  const [formData, setFormData] = useState<CreateUserRequest>({
    name: '',
    email: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const newUser = await post('/users', formData);
      console.log('User created:', newUser);
      setFormData({ name: '', email: '' });
    } catch (err) {
      console.error('Failed to create user:', err);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={formData.name}
        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
        placeholder="Name"
      />
      <input
        type="email"
        value={formData.email}
        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
        placeholder="Email"
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create User'}
      </button>
      {error && <p className="text-red-600">{error.message}</p>}
    </form>
  );
}
```

### PUT Requests (Update)

```typescript
import { useApi } from '@/hooks/useApi';

interface User {
  id: number;
  name: string;
  email: string;
}

function EditUserForm({ userId, initialUser }: Props) {
  const { put, loading, error } = useApi<User>();
  const [user, setUser] = useState(initialUser);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const updated = await put(`/users/${userId}`, user);
      console.log('User updated:', updated);
    } catch (err) {
      console.error('Failed to update user:', err);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        value={user.name}
        onChange={(e) => setUser({ ...user, name: e.target.value })}
      />
      <input
        value={user.email}
        onChange={(e) => setUser({ ...user, email: e.target.value })}
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Saving...' : 'Save'}
      </button>
      {error && <p className="text-red-600">{error.message}</p>}
    </form>
  );
}
```

### DELETE Requests

```typescript
import { useApi } from '@/hooks/useApi';

function DeleteUserButton({ userId }: { userId: number }) {
  const { delete: deleteUser, loading, error } = useApi();

  const handleDelete = async () => {
    if (confirm('Are you sure?')) {
      try {
        await deleteUser(`/users/${userId}`);
        console.log('User deleted');
        // Refresh user list or navigate away
      } catch (err) {
        console.error('Failed to delete user:', err);
      }
    }
  };

  return (
    <>
      <button onClick={handleDelete} disabled={loading}>
        {loading ? 'Deleting...' : 'Delete'}
      </button>
      {error && <p className="text-red-600">{error.message}</p>}
    </>
  );
}
```

## Global State Management

### Using Zustand Store

```typescript
import { useAppStore } from '@/store/appStore';

function MyComponent() {
  // Access state
  const { isLoading, error, notification } = useAppStore();

  // Update state
  const { setLoading, setError, setNotification } = useAppStore();

  return (
    <div>
      {isLoading && <p>Loading...</p>}
      {error && <p className="text-red-600">{error}</p>}
      {notification && <p className="text-green-600">{notification}</p>}
    </div>
  );
}
```

### Authentication State

```typescript
import { useAppStore } from '@/store/appStore';

function LoginForm() {
  const { setAuthenticated, setUser } = useAppStore();
  const { post } = useApi();

  const handleLogin = async (credentials: LoginRequest) => {
    try {
      const response = await post('/auth/login', credentials);
      setAuthenticated(true);
      setUser(response.user);
      localStorage.setItem('auth_token', response.token);
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  return (
    // Form JSX
  );
}
```

## Request Interceptors

### Adding Bearer Token

The API client automatically adds the bearer token from localStorage:

```typescript
// Token is automatically added if present in localStorage
localStorage.setItem('auth_token', 'your-jwt-token');

// All subsequent requests will include:
// Authorization: Bearer your-jwt-token
```

### Custom Interceptors

Add custom interceptors in `src/api/client.ts`:

```typescript
// Request interceptor
instance.interceptors.request.use(
  (config) => {
    // Add custom headers
    config.headers['X-Custom-Header'] = 'value';
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
instance.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle specific errors
    if (error.response?.status === 401) {
      // Handle unauthorized - logout user
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

## Error Handling

### Hook-level Error Handling

```typescript
function MyComponent() {
  const { get, error } = useApi<DataType>();

  useEffect(() => {
    const fetchData = async () => {
      try {
        await get('/data');
      } catch (err) {
        // Error is also in 'error' state
        if (err.response?.status === 404) {
          console.log('Not found');
        } else if (err.response?.status === 500) {
          console.log('Server error');
        }
      }
    };

    fetchData();
  }, []);

  if (error) {
    return <Error message={error.message} />;
  }
}
```

### Global Error Handling

```typescript
import { useAppStore } from '@/store/appStore';

function ErrorNotification() {
  const { error, setError } = useAppStore();

  return (
    error && (
      <Error
        message={error}
        onDismiss={() => setError(null)}
      />
    )
  );
}

// Add to main App component
function App() {
  return (
    <>
      <ErrorNotification />
      {/* Rest of app */}
    </>
  );
}
```

## Advanced Usage

### Query Parameters

```typescript
const { get } = useApi();

// With query parameters
await get('/users?page=1&limit=10');

// Or use params config
await get('/users', {
  params: {
    page: 1,
    limit: 10,
    sort: 'name'
  }
});
```

### Request Configuration

```typescript
const { get } = useApi();

// Custom headers
await get('/users', {
  headers: {
    'X-Custom-Header': 'value'
  }
});

// Custom timeout
await get('/users', {
  timeout: 5000
});

// Disable global state update
await get('/users', {}, false); // Last param = updateAppState
```

### Retry Logic

```typescript
async function withRetry(
  fn: () => Promise<any>,
  maxRetries = 3,
  delay = 1000
) {
  let lastError;

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}

// Usage
const { get } = useApi();
const data = await withRetry(() => get('/users'));
```

### Handling Large Responses

```typescript
// Stream large files
const { request } = useApi();

const downloadFile = async () => {
  try {
    const response = await request('/export/users', {
      method: 'GET',
      responseType: 'blob'
    });

    const url = window.URL.createObjectURL(response);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'users.csv';
    link.click();
  } catch (error) {
    console.error('Download failed:', error);
  }
};
```

## TypeScript Support

### Type-safe API Calls

```typescript
// Define request/response types
interface ListUsersRequest {
  page?: number;
  limit?: number;
  search?: string;
}

interface ListUsersResponse {
  users: User[];
  total: number;
  page: number;
}

// Use in component
function UserList() {
  const { get, data } = useApi<ListUsersResponse>();

  const fetchUsers = async (params: ListUsersRequest) => {
    await get('/users', { params });
  };

  return (
    <>
      {data?.users.map(user => (
        <div key={user.id}>{user.name}</div>
      ))}
      <p>Total: {data?.total}</p>
    </>
  );
}
```

## Testing API Integration

### Mock API Calls

```typescript
import { vi } from 'vitest';
import { apiClient } from '@/api/client';

vi.mock('@/api/client');

describe('UserList', () => {
  it('fetches and displays users', async () => {
    const mockUsers = [
      { id: 1, name: 'Alice' },
      { id: 2, name: 'Bob' }
    ];

    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: mockUsers
    });

    // Test component
  });
});
```

## Best Practices

### 1. Separate Concerns

```typescript
// ❌ Bad - API logic mixed with component
function UserList() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    fetch('/api/v1/users')
      .then(r => r.json())
      .then(setUsers);
  }, []);
}

// ✅ Good - Use custom hook
function useUsers() {
  const { get, data } = useApi<User[]>();
  
  useEffect(() => {
    get('/users');
  }, []);

  return data;
}

function UserList() {
  const users = useUsers();
  return <div>{/* render users */}</div>;
}
```

### 2. Loading States

```typescript
// Always handle loading and error states
function DataComponent() {
  const { data, loading, error } = useApi();

  if (loading) return <Loading />;
  if (error) return <Error message={error.message} />;
  if (!data) return <div>No data</div>;

  return <div>{/* render data */}</div>;
}
```

### 3. Cleanup

```typescript
// Clean up on unmount
function MyComponent() {
  useEffect(() => {
    return () => {
      // Cleanup code
      setAppState(null);
    };
  }, []);
}
```

### 4. Error Boundaries

```typescript
// Use error boundaries for API errors
import { ErrorBoundary } from 'react-error-boundary';

function App() {
  return (
    <ErrorBoundary
      fallback={<Error message="Something went wrong" />}
    >
      <YourApp />
    </ErrorBoundary>
  );
}
```

## Common API Patterns

### CRUD Operations

```typescript
// Create
const { post } = useApi<User>();
await post('/users', { name: 'John' });

// Read
const { get } = useApi<User>();
await get(`/users/${id}`);

// Update
const { put } = useApi<User>();
await put(`/users/${id}`, { name: 'Jane' });

// Delete
const { delete: deleteUser } = useApi();
await deleteUser(`/users/${id}`);
```

### Pagination

```typescript
function PaginatedList() {
  const { get, data } = useApi<ListResponse>();
  const [page, setPage] = useState(1);

  useEffect(() => {
    get('/users', { params: { page, limit: 10 } });
  }, [page, get]);

  return (
    <>
      {/* Render items */}
      <button onClick={() => setPage(p => p - 1)}>Previous</button>
      <button onClick={() => setPage(p => p + 1)}>Next</button>
    </>
  );
}
```

### Search/Filter

```typescript
function SearchUsers() {
  const { get, data } = useApi<User[]>();
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (query) {
      get('/users', { params: { search: query } });
    }
  }, [query, get]);

  return (
    <>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search..."
      />
      {data?.map(user => <div key={user.id}>{user.name}</div>)}
    </>
  );
}
```

## Environment Configuration

### Frontend API URL

Update `src/api/client.ts` to use environment variable:

```typescript
// Reads VITE_API_URL from .env
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
```

Set in `.env`:
```
VITE_API_URL=http://localhost:8000/api/v1
```

Or in production (`.env.production`):
```
VITE_API_URL=https://api.yourdomain.com/api/v1
```

## Troubleshooting

### CORS Errors

```
Access to XMLHttpRequest from origin 'http://localhost:3000' 
has been blocked by CORS policy
```

**Solution**: Ensure backend has correct CORS configuration in `core/config.py`

### Token Expiration

The API client automatically:
- Adds bearer token from localStorage
- Clears token and redirects on 401 response
- Handles token refresh (if implemented)

### Network Errors

```typescript
const { get, error } = useApi();

try {
  await get('/users');
} catch (err) {
  if (err.code === 'ERR_NETWORK') {
    console.log('Network error - backend may be down');
  }
}
```

## References

- Axios Documentation: https://axios-http.com/
- React Hooks: https://react.dev/reference/react/hooks
- Zustand: https://github.com/pmndrs/zustand
- TypeScript: https://www.typescriptlang.org/

---

**Happy coding! For backend API documentation, visit `/api/docs` when running the backend.**
