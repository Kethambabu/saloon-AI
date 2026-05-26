/**
 * Layout Component - Main application layout wrapper
 */

import React from 'react';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white shadow">
        <nav className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-gray-900">SalonAI Workforce</h1>
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 border-t">
        <div className="max-w-7xl mx-auto px-4 py-6 text-center text-gray-600">
          <p>&copy; 2024 SalonAI Workforce. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
