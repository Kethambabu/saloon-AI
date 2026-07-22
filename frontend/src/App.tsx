import React, { Suspense, lazy, useEffect } from 'react';
import { HashRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
// Importing these directly from their own files rather than the
// `./components` barrel is deliberate: that barrel also re-exports
// AgentChat (which pulls in recharts + lucide-react). Since App.tsx is the
// eager entry point, going through the barrel dragged those dashboard-only
// dependencies into the main bundle that even the public login/landing page
// had to download — direct imports keep the eager entry's dependency graph
// limited to what these specific public/shell components actually use.
// (See also vite.config.ts's manualChunks, which forces recharts/lucide-react
// into their own lazily-loaded vendor chunks as a second line of defense.)
import { Layout } from './components/Layout';
import { Loading } from './components/Loading';
import { Login } from './components/Auth/Login';
import { Signup } from './components/Auth/Signup';
import { ForgotPassword } from './components/Auth/ForgotPassword';
import { ResetPassword } from './components/Auth/ResetPassword';
import { LandingPage } from './components/Public/LandingPage';
import { Unauthorized } from './components/Public/Unauthorized';

// Each portal is its own route-level chunk: a Customer session never
// downloads/parses the Admin or Staff dashboard bundle (and vice versa).
// These are large, chart/animation-heavy screens (recharts + framer-motion),
// so this materially cuts initial JS payload and parse time per role.
const AdminDashboard = lazy(() =>
  import('./components/Admin/AdminDashboard').then((m) => ({ default: m.AdminDashboard }))
);
const StaffDashboard = lazy(() =>
  import('./components/Staff/StaffDashboard').then((m) => ({ default: m.StaffDashboard }))
);
const UserDashboard = lazy(() =>
  import('./components/Customer/UserDashboard').then((m) => ({ default: m.UserDashboard }))
);

const RouteLoadingFallback: React.FC = () => (
  <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center">
    <Loading />
  </div>
);

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
  return (
    <Layout>
      <Suspense fallback={<RouteLoadingFallback />}>{children}</Suspense>
    </Layout>
  );
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
