import React from 'react';

interface UnauthorizedProps {
  onBackToHome: () => void;
}

export const Unauthorized: React.FC<UnauthorizedProps> = ({ onBackToHome }) => {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-white font-sans relative overflow-hidden">
      {/* Background orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-red-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-8 max-w-md w-full text-center shadow-2xl relative z-10 space-y-6 animate-fade-in">
        <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-500">
          <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>

        <div className="space-y-2">
          <h2 className="text-2xl font-black">Strict Access Blocked</h2>
          <p className="text-xs text-slate-400 leading-relaxed font-medium">
            You do not possess the necessary administrative security keys or credential privileges required to inspect this operations panel.
          </p>
        </div>

        <button
          onClick={onBackToHome}
          className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 text-xs font-bold rounded-xl transition-all shadow-lg shadow-blue-500/20 cursor-pointer uppercase tracking-wider"
        >
          ⬅️ Return to Safety
        </button>
      </div>
    </div>
  );
};
