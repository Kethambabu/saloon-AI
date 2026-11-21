/**
 * Loading Spinner Component
 *
 * Dual counter-rotating rings (cyan/amber, matching the app's header
 * gradient) over a soft glow, used anywhere a page/route is still resolving
 * (initial auth check, role guard, lazy-loaded dashboard chunk).
 */

import React from 'react';

interface LoadingProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  message?: string;
  /** Center the spinner in a full-viewport dark backdrop — for whole-page loads. */
  fullScreen?: boolean;
}

const SIZE_CLASSES: Record<NonNullable<LoadingProps['size']>, string> = {
  sm: 'w-6 h-6',
  md: 'w-10 h-10',
  lg: 'w-14 h-14',
  xl: 'w-20 h-20',
};

export const Loading: React.FC<LoadingProps> = ({ size = 'md', message, fullScreen = false }) => {
  const dimension = SIZE_CLASSES[size];

  const spinner = (
    <div className="flex flex-col items-center justify-center gap-4" role="status" aria-live="polite" aria-busy="true">
      <div className={`relative ${dimension}`}>
        {/* Soft ambient glow behind the rings */}
        <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-cyan-500 to-amber-500 opacity-30 blur-lg animate-pulse" />
        {/* Outer ring — cyan leading edge, spins clockwise */}
        <div className="absolute inset-0 rounded-full border-[3px] border-slate-800/80 border-t-cyan-400 border-r-cyan-400/40 animate-spin" />
        {/* Inner ring — amber leading edge, spins counter-clockwise, slightly slower */}
        <div
          className="absolute inset-[3px] rounded-full border-[3px] border-transparent border-b-amber-400 border-l-amber-400/40 animate-spin"
          style={{ animationDirection: 'reverse', animationDuration: '1.1s' }}
        />
        {/* Center dot */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="w-1.5 h-1.5 rounded-full bg-white/80 shadow-[0_0_6px_2px_rgba(56,189,248,0.5)]" />
        </div>
      </div>
      {message && (
        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest animate-pulse text-center">
          {message}
        </span>
      )}
      <span className="sr-only">{message || 'Loading'}</span>
    </div>
  );

  if (!fullScreen) return spinner;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center">
      {spinner}
    </div>
  );
};

export default Loading;
