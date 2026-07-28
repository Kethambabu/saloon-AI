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
    <div className="h-screen overflow-hidden flex flex-col bg-slate-950 text-white font-sans">
      {/* Skip link: keyboard/screen-reader users can jump past the header
          and any per-portal sidebar nav straight to the page content. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:rounded-lg focus:bg-blue-600 focus:text-white focus:font-bold focus:text-sm"
      >
        Skip to main content
      </a>

      {/* Header */}
      <header className="bg-slate-900/80 border-b border-slate-850 sticky top-0 z-40 backdrop-blur-md bg-slate-900/90 text-white">
        <nav className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between" aria-label="Primary">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-gradient-to-tr from-cyan-500 to-amber-500 shadow-lg shadow-cyan-500/10 text-white">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <h1 className="text-sm font-extrabold tracking-tight text-white m-0">
              SalonHubAI Workforce
            </h1>
          </div>

          {isAuthenticated && user && (
            <div className="flex items-center space-x-3">
              <div className="hidden sm:flex flex-col text-right">
                <span className="text-[11px] font-extrabold text-slate-355 leading-tight">{user.email}</span>
                <span className="text-[9px] font-black text-cyan-400 uppercase tracking-widest leading-none">{user.role}</span>
              </div>
              <span className="px-2 py-0.5 text-[9px] font-black bg-cyan-500/10 text-cyan-400 rounded-full border border-cyan-500/20 sm:hidden uppercase tracking-wider">
                {user.role}
              </span>
              <button
                onClick={logout}
                aria-label="Log out"
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 border border-slate-800 hover:border-red-900/50 rounded-lg text-[11px] font-bold text-slate-400 hover:text-red-400 bg-slate-900 hover:bg-red-955/20 transition-all duration-300 cursor-pointer shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-500"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          )}
        </nav>
      </header>

      {/* Main Content - flex-1 min-h-0 so h-full works on child dashboards */}
      <main id="main-content" tabIndex={-1} className="flex-1 min-h-0 overflow-hidden">
        {children}
      </main>

      {/* Footer — only on public pages; dashboards are full-screen apps */}
      {!isAuthenticated && (
        <footer className="shrink-0 bg-slate-900/80 border-t border-slate-800 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs font-semibold text-slate-500">
            <span>© {new Date().getFullYear()} <span className="text-cyan-400 font-bold">SalonHubAI Workforce</span>. All rights reserved.</span>
            <span className="flex items-center gap-3">
              <span className="text-slate-600">Powered by AI</span>
              <span className="w-1 h-1 rounded-full bg-slate-700 inline-block" />
              <span className="text-slate-600">v2.0</span>
            </span>
          </div>
        </footer>
      )}
    </div>
  );
};

export default Layout;
