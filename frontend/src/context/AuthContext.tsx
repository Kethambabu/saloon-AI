import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '../api/client';

export type UserRole = 'Admin' | 'Staff' | 'User';

export interface UserProfile {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  staff_id: string | null;
  customer_id: string | null;
}

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<UserProfile>;
  logout: () => Promise<void>;
  signup: (
    email: string,
    password: string,
    role: string,
    firstName: string,
    lastName: string,
    phone?: string,
    branchId?: string
  ) => Promise<UserProfile>;
  forgotPassword: (email: string) => Promise<string>;
  resetPassword: (email: string, token: string, newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const normalizeRole = (role: string): UserRole => {
  if (!role) return 'User';
  const upper = role.toUpperCase();
  if (upper === 'ADMIN') return 'Admin';
  if (upper === 'STAFF') return 'Staff';
  return 'User';
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Retrieve user info using token
  const fetchCurrentUser = async () => {
    try {
      console.log('[DEBUG] [AuthContext] Restoring session: querying /auth/me');
      const response = await apiClient.get<UserProfile>('/auth/me');
      console.log('[DEBUG] [AuthContext] Session restored successfully. Profile:', response.data);
      const normalizedUser = {
        ...response.data,
        role: normalizeRole(response.data.role),
      };
      setUser(normalizedUser);
    } catch (error) {
      console.error('[DEBUG] [AuthContext] fetchCurrentUser failed:', error);
      // Clear tokens if getting /me fails on startup
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    console.log('[DEBUG] [AuthContext] Startup check: token is', token ? 'PRESENT' : 'MISSING');
    if (token) {
      fetchCurrentUser();
    } else {
      setLoading(false);
    }

    // Bind global event listener to capture API forced logouts
    const handleForcedLogout = () => {
      setUser(null);
    };

    window.addEventListener('auth_logged_out', handleForcedLogout);
    return () => {
      window.removeEventListener('auth_logged_out', handleForcedLogout);
    };
  }, []);

  const login = async (email: string, password: string): Promise<UserProfile> => {
    console.log('[DEBUG] [AuthContext] Login request initiated for:', email);
    setLoading(true);
    try {
      const response = await apiClient.post('/auth/login', { email, password });
      console.log('[DEBUG] [AuthContext] Login response received:', response.data);
      
      // Validate response structure
      if (!response.data || !response.data.access_token || !response.data.refresh_token) {
        console.error('[DEBUG] [AuthContext] Invalid login response structure:', response.data);
        throw new Error('Invalid login response: missing tokens');
      }
      
      const { access_token, refresh_token } = response.data;
      console.log('[DEBUG] [AuthContext] Tokens received. Access token length:', access_token?.length, 'Refresh token length:', refresh_token?.length);
      
      if (!access_token || !refresh_token) {
        console.error('[DEBUG] [AuthContext] Tokens are empty or null');
        throw new Error('Received empty tokens from server');
      }
      
      console.log('[DEBUG] [AuthContext] Storing JWT tokens in localStorage');
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      console.log('[DEBUG] [AuthContext] Fetching user profile details via /auth/me');
      const meResponse = await apiClient.get<UserProfile>('/auth/me');
      console.log('[DEBUG] [AuthContext] User profile received:', meResponse.data);
      
      // Validate profile data
      if (!meResponse.data || !meResponse.data.id || !meResponse.data.role) {
        console.error('[DEBUG] [AuthContext] Invalid profile data received:', meResponse.data);
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        throw new Error('Invalid user profile data received');
      }
      
      const normalizedUser = {
        ...meResponse.data,
        role: normalizeRole(meResponse.data.role),
      };
      setUser(normalizedUser);
      return normalizedUser;
    } catch (error) {
      console.error('[DEBUG] [AuthContext] Login failed:', error);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      // Attempt backend revocation (ignore errors if token already expired)
      await apiClient.post('/auth/logout');
    } catch (e) {
      console.warn('Backend logout failed or was already revoked:', e);
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
      setLoading(false);
    }
  };

  const signup = async (
    email: string,
    password: string,
    role: string,
    firstName: string,
    lastName: string,
    phone?: string,
    branchId?: string
  ): Promise<UserProfile> => {
    console.log('[DEBUG] [AuthContext] Signup request initiated for:', email);
    setLoading(true);
    try {
      const response = await apiClient.post('/auth/signup', {
        email,
        password,
        role,
        first_name: firstName,
        last_name: lastName,
        phone: phone || null,
        branch_id: branchId || null,
      });
      
      console.log('[DEBUG] [AuthContext] Signup response received:', response.data);
      
      // Extract tokens from response
      const { access_token, refresh_token } = response.data;
      
      if (access_token && refresh_token) {
        console.log('[DEBUG] [AuthContext] Storing JWT tokens in localStorage');
        localStorage.setItem('auth_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        
        console.log('[DEBUG] [AuthContext] Fetching user profile details via /auth/me');
        const meResponse = await apiClient.get<UserProfile>('/auth/me');
        console.log('[DEBUG] [AuthContext] User profile received:', meResponse.data);
        const normalizedUser = {
          ...meResponse.data,
          role: normalizeRole(meResponse.data.role),
        };
        setUser(normalizedUser);
        return normalizedUser;
      } else {
        throw new Error('No tokens received from signup');
      }
    } catch (error) {
      console.error('[DEBUG] [AuthContext] Signup failed:', error);
      setUser(null);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const forgotPassword = async (email: string): Promise<string> => {
    setLoading(true);
    try {
      const response = await apiClient.post('/auth/forgot-password', { email });
      return response.data.token || '';
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async (email: string, token: string, newPassword: string): Promise<void> => {
    setLoading(true);
    try {
      await apiClient.post('/auth/reset-password', {
        email,
        token,
        new_password: newPassword,
      });
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        logout,
        signup,
        forgotPassword,
        resetPassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
