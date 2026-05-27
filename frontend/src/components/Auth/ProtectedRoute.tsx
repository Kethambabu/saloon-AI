import React from 'react';
import { useAuth, UserRole } from '../../context/AuthContext';

interface ProtectedRouteProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const RoleProtectedRoute: React.FC<ProtectedRouteProps> = ({
  allowedRoles,
  children,
  fallback,
}) => {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated || !user) {
    return null;
  }

  const isAuthorized = allowedRoles.includes(user.role);

  if (!isAuthorized) {
    if (fallback) {
      return <>{fallback}</>;
    }

    return (
      <div className="bg-slate-900/40 backdrop-blur-md border border-slate-800/80 rounded-3xl p-8 max-w-lg mx-auto my-12 text-center shadow-xl animate-fade-in text-left">
        <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-500 mb-4">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 className="text-xl font-extrabold text-white text-center">Access Denied</h3>
        <p className="mt-2 text-sm text-slate-400 text-center leading-relaxed">
          Your current security role (<span className="text-blue-400 font-bold">{user.role}</span>) does not have authorization to view this analytical domain. Please request administrative elevation if necessary.
        </p>
      </div>
    );
  }

  return <>{children}</>;
};
