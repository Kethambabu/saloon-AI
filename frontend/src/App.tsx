import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import {
  Layout,
  AgentChat,
  Login,
  Signup,
  ForgotPassword,
  AdminDashboard,
  ManagerDashboard,
  StaffDashboard,
  Loading
} from './components';

function AppContent() {
  const { user, isAuthenticated, loading } = useAuth();
  
  // Local state to toggle between Login, Signup, and ForgotPassword
  const [authScreen, setAuthScreen] = useState<'login' | 'signup' | 'forgot-password'>('login');
  
  // Toggle for Staff to open the live Clara Chat receptionist view
  const [viewClaraChat, setViewClaraChat] = useState<boolean>(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center">
        <Loading />
        <span className="mt-4 text-xs font-bold text-slate-500 uppercase tracking-widest animate-pulse">
          Establishing Secure Session...
        </span>
      </div>
    );
  }

  // Render authentication screens if not logged in
  if (!isAuthenticated || !user) {
    if (authScreen === 'signup') {
      return <Signup onBackToLogin={() => setAuthScreen('login')} />;
    }
    if (authScreen === 'forgot-password') {
      return <ForgotPassword onBackToLogin={() => setAuthScreen('login')} />;
    }
    return (
      <Login
        onNavigateToSignup={() => setAuthScreen('signup')}
        onNavigateToForgotPassword={() => setAuthScreen('forgot-password')}
      />
    );
  }

  // Render role-specific dashboards
  return (
    <Layout>
      <div className="animate-fade-in space-y-6">
        
        {/* Admin or Owner dashboard */}
        {(user.role === 'Admin' || user.role === 'Owner') && (
          <AdminDashboard />
        )}

        {/* Manager dashboard */}
        {user.role === 'Manager' && (
          <ManagerDashboard />
        )}

        {/* Staff / Stylist dashboard */}
        {user.role === 'Staff' && (
          <>
            {viewClaraChat ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-200/80 pb-4">
                  <div className="text-left">
                    <h2 className="text-xl font-bold text-slate-800">Receptionist Console</h2>
                    <p className="text-xs text-slate-500 font-medium">Interact with Clara in real-time to book services or check branch slots.</p>
                  </div>
                  <button
                    onClick={() => setViewClaraChat(false)}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-250 text-slate-700 text-xs font-bold rounded-xl transition-all cursor-pointer border border-slate-200 shadow-sm"
                  >
                    ⬅️ Back to Stylist Roster
                  </button>
                </div>
                <AgentChat />
              </div>
            ) : (
              <StaffDashboard onToggleChat={() => setViewClaraChat(true)} />
            )}
          </>
        )}

      </div>
    </Layout>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
