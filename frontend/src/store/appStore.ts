/**
 * Zustand Store - Global State Management
 * App-wide state for authentication, UI, and data
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * App state interface
 */
interface AppState {
  // UI State
  isLoading: boolean;
  error: string | null;
  notification: string | null;

  // User State
  isAuthenticated: boolean;
  user: any | null;

  // Actions
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setNotification: (message: string | null) => void;
  setAuthenticated: (authenticated: boolean) => void;
  setUser: (user: any | null) => void;
  reset: () => void;
}

/**
 * Create app store with persistence and devtools
 */
export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set) => ({
        // Initial state
        isLoading: false,
        error: null,
        notification: null,
        isAuthenticated: false,
        user: null,

        // Actions
        setLoading: (loading: boolean) => set({ isLoading: loading }),
        setError: (error: string | null) => set({ error }),
        setNotification: (notification: string | null) => set({ notification }),
        setAuthenticated: (isAuthenticated: boolean) => set({ isAuthenticated }),
        setUser: (user: any | null) => set({ user }),
        reset: () =>
          set({
            isLoading: false,
            error: null,
            notification: null,
            isAuthenticated: false,
            user: null,
          }),
      }),
      {
        name: 'salonai-storage', // localStorage key
        partialize: (state) => ({
          isAuthenticated: state.isAuthenticated,
          user: state.user,
        }), // Only persist auth state
      }
    ),
    { name: 'AppStore', enabled: import.meta.env.DEV }
  )
);

export default useAppStore;
