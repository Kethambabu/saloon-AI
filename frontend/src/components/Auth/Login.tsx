import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

interface LoginProps {
  onNavigateToSignup?: () => void;
  onNavigateToForgotPassword?: () => void;
}

export const Login: React.FC<LoginProps> = ({ onNavigateToSignup, onNavigateToForgotPassword }) => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log('[DEBUG] [Login] Submit handler clicked.');
    
    if (!email || !password) {
      console.warn('[DEBUG] [Login] Validation failed: missing fields.');
      setError('Please enter all required fields');
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      console.log('[DEBUG] [Login] Dispatching login call for:', email);
      const userProfile = await login(email, password);
      console.log('[DEBUG] [Login] Login successful. Profile:', userProfile);
      
      // Validate profile data
      if (!userProfile || !userProfile.role) {
        console.error('[DEBUG] [Login] Invalid profile data received:', userProfile);
        setError('Invalid user data received. Please try again.');
        setIsSubmitting(false);
        return;
      }
      
      console.log('[DEBUG] [Login] Initiating route navigation for role:', userProfile.role);
      
      // Use setTimeout to ensure state updates complete before navigation
      setTimeout(() => {
        const role = userProfile.role;
        if (role === 'Admin' || role === 'ADMIN') {
          console.log('[DEBUG] [Login] Navigating to /admin');
          navigate('/admin', { replace: true });
        } else if (role === 'Staff' || role === 'STAFF') {
          console.log('[DEBUG] [Login] Navigating to /staff');
          navigate('/staff', { replace: true });
        } else if (role === 'User' || role === 'CUSTOMER' || role === 'USER') {
          console.log('[DEBUG] [Login] Navigating to /user');
          navigate('/user', { replace: true });
        } else {
          console.error('[DEBUG] [Login] Unknown user role:', userProfile.role);
          setError('Unknown user role. Please contact support.');
        }
      }, 0);
    } catch (err: any) {
      console.error('[DEBUG] [Login] Caught error in submit:', err);
      
      let errorMessage = 'Something went wrong. Please try again.';
      
      if (!err.response) {
        // Network error or no response
        if (err.message === 'Network Error' || err.code === 'ECONNABORTED') {
          errorMessage = 'Unable to connect to server. Please check your connection.';
        } else {
          errorMessage = 'Unable to connect to server';
        }
        console.error('[DEBUG] [Login] Network error:', err.message);
      } else if (err.response.status === 401 || err.response.status === 400) {
        // Invalid credentials
        errorMessage = 'Incorrect username or password. Please try again.';
        console.warn('[DEBUG] [Login] Authentication failed with status:', err.response.status);
      } else if (err.response.status === 403) {
        // Account suspended or inactive
        const detail = err.response.data?.detail;
        errorMessage = detail || 'Your account is suspended or inactive';
        console.warn('[DEBUG] [Login] Access forbidden:', detail);
      } else if (err.response.status === 500) {
        errorMessage = 'Server error. Please try again later.';
        console.error('[DEBUG] [Login] Server error:', err.response.data);
      } else {
        // Generic error response
        const message = err.response.data?.message;
        const detail = err.response.data?.detail;
        errorMessage = message || detail || 'Something went wrong. Please try again.';
        console.warn('[DEBUG] [Login] Error status', err.response.status, ':', errorMessage);
      }
      
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFill = (role: 'Admin' | 'Staff' | 'User') => {
    setError(null);
    if (role === 'Admin') {
      setEmail('owner@salonai.com');
      setPassword('password123');
    } else if (role === 'Staff') {
      setEmail('marcus@salonai.com');
      setPassword('password123');
    } else {
      setEmail('customer@example.com');
      setPassword('password123');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden font-sans">
      {/* Background visual art elements */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl -ml-20 -mt-20 pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-indigo-600/10 rounded-full blur-3xl -mr-32 -mb-32 pointer-events-none" />
      <div className="absolute top-1/3 right-1/3 w-72 h-72 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md z-10 text-center">
        {/* Modern logo display */}
        <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 shadow-lg shadow-blue-500/20 mb-4 animate-bounce-slow">
          <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        </div>
        <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          SalonAI Workforce
        </h2>
        <p className="mt-2 text-sm font-semibold text-slate-400">
          Autonomous multi-agent enterprise hub
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10 px-4 sm:px-0">
        {/* Glassmorphic Panel Container */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 py-8 px-6 shadow-2xl rounded-3xl sm:px-10">
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="text-left space-y-1">
              <h3 className="text-sm font-bold text-slate-300">Or Sign in with Email</h3>
              {error && (
                <p className="text-sm font-bold text-red-500 animate-fade-in">
                  {error}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="email" className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                Email Address
              </label>
              <div className="mt-1">
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError(null); // Clear error when user starts typing
                  }}
                  required
                  placeholder="name@salonai.com"
                  className="appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200 text-sm"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                Password
              </label>
              <div className="mt-1">
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (error) setError(null); // Clear error when user starts typing
                  }}
                  required
                  placeholder="••••••••"
                  className="appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200 text-sm"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center py-3.5 px-4 border border-transparent rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all duration-300 cursor-pointer"
              >
                {isSubmitting ? (
                  <span className="flex items-center space-x-2">
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span>Signing In...</span>
                  </span>
                ) : (
                  <span>Sign In</span>
                )}
              </button>
            </div>
            
            <div className="flex items-center justify-between text-xs font-bold mt-4">
              <button
                type="button"
                onClick={onNavigateToForgotPassword}
                className="text-blue-400 hover:text-blue-300 cursor-pointer focus:outline-none"
              >
                Forgot Password?
              </button>
              <button
                type="button"
                onClick={onNavigateToSignup}
                className="text-blue-400 hover:text-blue-300 cursor-pointer focus:outline-none"
              >
                Create Account
              </button>
            </div>
          </form>

          {/* Quick-fill testing panel */}
          <div className="mt-8 border-t border-slate-800/80 pt-6 text-left">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">
              Developer Quick Fill
            </h4>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill('Admin')}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-900/30 text-blue-300 border border-blue-800/50 hover:bg-blue-900/50 transition-all duration-200 cursor-pointer"
              >
                👑 Admin Fill
              </button>
              <button
                type="button"
                onClick={() => handleQuickFill('Staff')}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-900/30 text-emerald-300 border border-emerald-800/50 hover:bg-emerald-900/50 transition-all duration-200 cursor-pointer"
              >
                💇 Stylist Staff Fill
              </button>
              <button
                type="button"
                onClick={() => handleQuickFill('User')}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-900/30 text-purple-300 border border-purple-800/50 hover:bg-purple-900/50 transition-all duration-200 cursor-pointer"
              >
                👤 Customer User Fill
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};
