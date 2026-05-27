/**
 * Layout Component - Main application layout wrapper
 * Displays the premium header navigation with active user profiles and secure Logout.
 */

import React from 'react';
import { useAuth } from '../context/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-slate-50/50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200/80 sticky top-0 z-40 backdrop-blur-md bg-white/95">
        <nav className="max-w-7xl mx-auto px-4 py-3.5 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 shadow-lg shadow-blue-500/10 text-white">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <h1 className="text-lg font-extrabold tracking-tight text-slate-800">
              SalonAI Workforce
            </h1>
          </div>

          {isAuthenticated && user && (
            <div className="flex items-center space-x-4">
              <div className="hidden sm:flex flex-col text-right">
                <span className="text-xs font-extrabold text-slate-700">{user.email}</span>
                <span className="text-[10px] font-black text-blue-600 uppercase tracking-widest">{user.role}</span>
              </div>
              <span className="px-2.5 py-1 text-[10px] font-black bg-blue-50 text-blue-600 rounded-full border border-blue-100 sm:hidden uppercase tracking-wider">
                {user.role}
              </span>
              <button
                onClick={logout}
                className="inline-flex items-center space-x-1 px-3.5 py-2 border border-slate-200 hover:border-red-200 rounded-xl text-xs font-bold text-slate-500 hover:text-red-500 bg-white hover:bg-red-50/10 transition-all duration-300 cursor-pointer shadow-sm"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          )}
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200/80">
        <div className="max-w-7xl mx-auto px-4 py-5 text-center text-slate-400 text-xs font-medium">
          <p>&copy; {new Date().getFullYear()} SalonAI Workforce. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
