import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '../api/client';

export type UserRole = 'Owner' | 'Manager' | 'Staff';

export interface UserProfile {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  staff_id: string | null;
}

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<UserProfile>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Retrieve user info using token
  const fetchCurrentUser = async () => {
    try {
      const response = await apiClient.get<UserProfile>('/auth/me');
      setUser(response.data);
    } catch (error) {
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
    setLoading(true);
    try {
      const response = await apiClient.post('/auth/login', { email, password });
      const { access_token, refresh_token, role, email: userEmail } = response.data;

      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Immediately query for full /me details to get staff_id and populate provider
      const meResponse = await apiClient.get<UserProfile>('/auth/me');
      setUser(meResponse.data);
      return meResponse.data;
    } catch (error) {
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

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        logout,
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
