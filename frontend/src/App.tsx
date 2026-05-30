import React, { useEffect } from 'react';
import { HashRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import {
  Layout,
  Login,
  Signup,
  ForgotPassword,
  ResetPassword,
  AdminDashboard,
  StaffDashboard,
  UserDashboard,
  LandingPage,
  Unauthorized,
  Loading
} from './components';

// Protected Route Guard wrapper
const ProtectedRouteWrapper: React.FC<{ allowedRoles: ('Admin' | 'Staff' | 'User')[]; children: React.ReactNode }> = ({ allowedRoles, children }) => {
  const { user, isAuthenticated, loading } = useAuth();

  useEffect(() => {
    console.log('[DEBUG] [ProtectedRouteWrapper] Evaluating security guard:', {
      isAuthenticated,
      userRole: user?.role,
      allowedRoles,
      userEmail: user?.email
    });
  }, [user, isAuthenticated, allowedRoles]);

  if (loading) {
    console.log('[DEBUG] [ProtectedRouteWrapper] Authentication state is loading. Rendering spinner...');
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center">
        <Loading />
        <span className="mt-4 text-xs font-bold text-slate-500 uppercase tracking-widest animate-pulse">
          Verifying security privileges...
        </span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    console.warn('[DEBUG] [ProtectedRouteWrapper] Guard failed: unauthenticated session. Redirecting to /login');
    return <Navigate to="/login" replace />;
  }

  const isAuthorized = allowedRoles.includes(user.role);
  if (!isAuthorized) {
    console.warn('[DEBUG] [ProtectedRouteWrapper] Guard failed: unauthorized role privilege. Redirecting to /unauthorized');
    return <Navigate to="/unauthorized" replace />;
  }

  console.log('[DEBUG] [ProtectedRouteWrapper] Guard passed. Rendering layout container shell.');
  return <Layout>{children}</Layout>;
};

// Landing Page route with automatic redirect
const LandingPageRoute: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated && user) {
      console.log('[DEBUG] [LandingPage] Authenticated session detected. Routing to dashboard for:', user.role);
      if (user.role === 'Admin') navigate('/admin/dashboard', { replace: true });
      else if (user.role === 'Staff') navigate('/staff/dashboard', { replace: true });
      else navigate('/user/dashboard', { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  return <LandingPage onNavigateToLogin={() => navigate('/login')} />;
};

// Login Route with automatic redirect if already logged in
const LoginRoute: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated && user) {
      console.log('[DEBUG] [LoginRoute] Authenticated session detected. Routing to dashboard for:', user.role);
      if (user.role === 'Admin') navigate('/admin/dashboard', { replace: true });
      else if (user.role === 'Staff') navigate('/staff/dashboard', { replace: true });
      else navigate('/user/dashboard', { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  return (
    <Login
      onNavigateToSignup={() => navigate('/signup')}
      onNavigateToForgotPassword={() => navigate('/forgot-password')}
    />
  );
};

// Signup Route with redirect if logged in
const SignupRoute: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated && user) {
      console.log('[DEBUG] [SignupRoute] Authenticated session detected. Routing to dashboard for:', user.role);
      if (user.role === 'Admin') navigate('/admin/dashboard', { replace: true });
      else if (user.role === 'Staff') navigate('/staff/dashboard', { replace: true });
      else navigate('/user/dashboard', { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  return <Signup onBackToLogin={() => navigate('/login')} />;
};

// Forgot Password Route
const ForgotPasswordRoute: React.FC = () => {
  const navigate = useNavigate();
  return (
    <ForgotPassword
      onBackToLogin={() => navigate('/login')}
    />
  );
};

// Reset Password Route
const ResetPasswordRoute: React.FC = () => {
  const navigate = useNavigate();
  return (
    <ResetPassword
      onBackToLogin={() => navigate('/login')}
    />
  );
};

// Unauthorized Access Block Route
const UnauthorizedRoute: React.FC = () => {
  const navigate = useNavigate();
  return <Unauthorized onBackToHome={() => navigate('/')} />;
};

function AppContent() {
  const { loading } = useAuth();

  useEffect(() => {
    console.log('[DEBUG] [AppContent] Component mounted. Loading state:', loading);
  }, [loading]);

  if (loading) {
    console.log('[DEBUG] [AppContent] Main session state is loading. Rendering startup loading page...');
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center">
        <Loading />
        <span className="mt-4 text-xs font-bold text-slate-500 uppercase tracking-widest animate-pulse">
          Establishing Secure Session...
        </span>
      </div>
    );
  }

  return (
    <Routes>
      {/* Public Pages */}
      <Route path="/" element={<LandingPageRoute />} />
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/signup" element={<SignupRoute />} />
      <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
      <Route path="/reset-password" element={<ResetPasswordRoute />} />
      <Route path="/unauthorized" element={<UnauthorizedRoute />} />

      {/* Role Protected Admin Routes */}
      <Route
        path="/admin/*"
        element={
          <ProtectedRouteWrapper allowedRoles={['Admin']}>
            <AdminDashboard />
          </ProtectedRouteWrapper>
        }
      />

      {/* Role Protected Staff Routes */}
      <Route
        path="/staff/*"
        element={
          <ProtectedRouteWrapper allowedRoles={['Staff']}>
            <StaffDashboard />
          </ProtectedRouteWrapper>
        }
      />

      {/* Role Protected User Routes */}
      <Route
        path="/user/*"
        element={
          <ProtectedRouteWrapper allowedRoles={['User']}>
            <UserDashboard />
          </ProtectedRouteWrapper>
        }
      />

      {/* Catch-all Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}

export default App;
