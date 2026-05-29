import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

interface ResetPasswordProps {
  onBackToLogin: () => void;
}

export const ResetPassword: React.FC<ResetPasswordProps> = ({ onBackToLogin }) => {
  const { resetPassword } = useAuth();
  
  const [email, setEmail] = useState<string>('');
  const [token, setToken] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !token || !newPassword) {
      setError('Please fill in all fields.');
      return;
    }

    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    try {
      await resetPassword(email, token, newPassword);
      setSuccess('Password updated successfully! Redirecting to login...');
      setTimeout(() => {
        onBackToLogin();
      }, 2500);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to reset password. Verify email and token are correct.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden font-sans">
      {/* Background artwork */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl -ml-20 -mt-20 pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-indigo-600/10 rounded-full blur-3xl -mr-32 -mb-32 pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md z-10 text-center">
        <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 shadow-lg shadow-blue-500/20 mb-4 animate-fade-in">
          <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-3xl font-extrabold tracking-tight text-white">
          Reset Password
        </h2>
        <p className="mt-2 text-sm font-semibold text-slate-400">
          Enter the recovery token, your email, and a new password
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10 px-4 sm:px-0">
        <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 py-8 px-6 shadow-2xl rounded-3xl sm:px-10">
          
          {error && (
            <div className="mb-4 rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-left animate-fade-in">
              <p className="text-xs font-bold text-red-300">{error}</p>
            </div>
          )}

          {success && (
            <div className="mb-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 text-left animate-fade-in">
              <p className="text-xs font-bold text-emerald-300">{success}</p>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleResetPassword}>
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="name@example.com"
                className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                Recovery Token
              </label>
              <input
                type="text"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
                placeholder="reset-token-xxxx"
                className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm font-mono text-center"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider text-left">
                New Password
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="mt-1 appearance-none block w-full px-4 py-3 border border-slate-800 rounded-xl bg-slate-950/60 placeholder-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
              />
            </div>

            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center py-3.5 px-4 border border-transparent rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all duration-300 cursor-pointer"
              >
                {isSubmitting ? 'Updating password...' : 'Confirm Reset'}
              </button>
            </div>
          </form>

          <div className="mt-6 border-t border-slate-800/80 pt-5 text-center">
            <button
              onClick={onBackToLogin}
              className="text-xs font-bold text-blue-400 hover:text-blue-300 cursor-pointer hover:underline focus:outline-none"
            >
              Back to Login
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};
