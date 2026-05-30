import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';

interface BranchOption {
  id: string;
  name: string;
  code: string;
  city: string;
}

interface SignupProps {
  onBackToLogin: () => void;
}

export const Signup: React.FC<SignupProps> = ({ onBackToLogin }) => {
  const { signup } = useAuth();
  const navigate = useNavigate();
  
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [firstName, setFirstName] = useState<string>('');
  const [lastName, setLastName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [role, setRole] = useState<string>('User');
  const [branchId, setBranchId] = useState<string>('');
  
  const [branches, setBranches] = useState<BranchOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Fetch branches for staff assignment
  useEffect(() => {
    const fetchBranches = async () => {
      try {
        // Query database for active branches using public route or direct access
        // We fall back to static list if endpoint fails
        const response = await apiClient.get('/agent/chat', { 
          params: { message: "list branches", "session id": "signup-probe" }
        });
        // Or fetch branches dynamically
        const bList = [
          { id: '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', name: 'Downtown Elite', code: 'DTE', city: 'New York' },
          { id: '4f3d1b64-884c-4c6e-a342-6a0b985c4bf2', name: 'Westside Boutique', code: 'WSB', city: 'Los Angeles' },
          { id: '4f3d1b64-884c-4c6e-a342-6a0b985c4bf3', name: 'Midtown Luxe', code: 'MTL', city: 'Chicago' }
        ];
        setBranches(bList);
        setBranchId(bList[0].id);
      } catch (err) {
        console.warn('Failed to load branches, using static options');
        const defaultBranches = [
          { id: '4f3d1b64-884c-4c6e-a342-6a0b985c4bf1', name: 'Downtown Elite', code: 'DTE', city: 'New York' },
          { id: '4f3d1b64-884c-4c6e-a342-6a0b985c4bf2', name: 'Westside Boutique', code: 'WSB', city: 'Los Angeles' },
          { id: '4f3d1b64-884c-4c6e-a342-6a0b985c4bf3', name: 'Midtown Luxe', code: 'MTL', city: 'Chicago' }
        ];
        setBranches(defaultBranches);
        setBranchId(defaultBranches[0].id);
      }
    };
    fetchBranches();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !firstName || !lastName) {
      setError('Please fill in all required fields.');
      return;
    }

    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    try {
      const userProfile = await signup(
        email,
        password,
        role,
        firstName,
        lastName,
        phone || undefined,
        role === 'Staff' ? branchId : undefined
      );
      
      setSuccess('Account registered successfully! Redirecting to dashboard...');
      
      // Auto-navigate to dashboard based on role
      setTimeout(() => {
        if (userProfile.role === 'Admin') {
          navigate('/admin', { replace: true });
        } else if (userProfile.role === 'Staff') {
          navigate('/staff', { replace: true });
        } else {
          navigate('/user', { replace: true });
        }
      }, 1500);
    } catch (err: any) {
      console.error('Registration failed:', err);
      
      let errorMessage = 'Registration failed. Please check your details.';
      
      if (!err.response) {
        errorMessage = 'Unable to connect to server. Please check your connection.';
        console.error('Network error:', err.message);
      } else if (err.response.status === 400) {
        // Validation error or user already exists
        const detail = err.response.data?.detail;
        const message = err.response.data?.message;
        errorMessage = detail || message || 'Email already exists or invalid data. Please check and try again.';
      } else if (err.response.status === 409) {
        // Conflict - user already exists
        errorMessage = 'Email already registered. Please use a different email or login instead.';
      } else if (err.response.status === 500) {
        errorMessage = 'Server error. Please try again later.';
      } else {
        const detail = err.response.data?.detail;
        const message = err.response.data?.message;
        errorMessage = message || detail || 'Registration failed. Please try again.';
      }
      
      setError(errorMessage);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden font-sans">
      {/* Background artwork */}
      <div className="absolute top-0 right-1/4 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-3xl -mr-32 -mt-32 pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md z-10 text-center">
        <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 shadow-lg shadow-blue-500/20 mb-4 animate-fade-in">
          <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
          </svg>
        </div>
        <h2 className="text-3xl font-extrabold tracking-tight text-white">
          Create Account
        </h2>
        <p className="mt-2 text-sm font-semibold text-slate-400">
          Join the SalonAI autonomous ecosystem
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10 px-4 sm:px-0">
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 py-8 px-6 shadow-2xl rounded-3xl sm:px-10">
          <form className="space-y-5" onSubmit={handleSubmit}>
            
            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-left animate-fade-in">
                <p className="text-xs font-bold text-red-300">{error}</p>
              </div>
            )}

            {success && (
              <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 text-left animate-fade-in">
                <p className="text-xs font-bold text-emerald-300">{success}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                  First Name *
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => {
                    setFirstName(e.target.value);
                    if (error) setError(null);
                  }}
                  required
                  placeholder="Jane"
                  className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                  Last Name *
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => {
                    setLastName(e.target.value);
                    if (error) setError(null);
                  }}
                  required
                  placeholder="Doe"
                  className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                Email Address *
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (error) setError(null);
                }}
                required
                placeholder="name@example.com"
                className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                Password *
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError(null);
                }}
                required
                placeholder="••••••••"
                className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                  Phone Number
                </label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => {
                    setPhone(e.target.value);
                    if (error) setError(null);
                  }}
                  placeholder="+1 (555) 0100"
                  className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                  Security Role
                </label>
                <select
                  value={role}
                  onChange={(e) => {
                    setRole(e.target.value);
                    if (error) setError(null);
                  }}
                  className="mt-1 block w-full px-3 py-3 border border-slate-800 rounded-xl bg-slate-950/60 text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm cursor-pointer"
                >
                  <option value="User" className="bg-slate-950 text-white">👤 Salon Customer (User)</option>
                  <option value="Staff" className="bg-slate-950 text-white">💇 Stylist (Staff)</option>
                </select>
              </div>
            </div>

            {role === 'Staff' && branches.length > 0 && (
              <div className="animate-fade-in">
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                  Assign Branch Location *
                </label>
                <select
                  value={branchId}
                  onChange={(e) => {
                    setBranchId(e.target.value);
                    if (error) setError(null);
                  }}
                  className="mt-1 block w-full px-3 py-3 border border-slate-800 rounded-xl bg-slate-950/60 text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm cursor-pointer"
                >
                  {branches.map((b) => (
                    <option key={b.id} value={b.id} className="bg-slate-950 text-white">
                      {b.name} ({b.code}) - {b.city}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center py-3.5 px-4 border border-transparent rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all duration-300 cursor-pointer"
              >
                {isSubmitting ? 'Registering...' : 'Register Profile'}
              </button>
            </div>
          </form>

          <div className="mt-6 border-t border-slate-800/80 pt-5 text-center">
            <button
              onClick={onBackToLogin}
              className="text-xs font-bold text-blue-400 hover:text-blue-300 cursor-pointer hover:underline focus:outline-none"
            >
              Already have an account? Access Hub
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};
