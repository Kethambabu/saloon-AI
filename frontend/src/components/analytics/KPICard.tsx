/**
 * KPICard Component - Executive metric display card
 * Premium glassmorphic card with animated counters and trend indicators.
 */

import React, { useEffect, useState } from 'react';

interface KPICardProps {
  id: string;
  title: string;
  value: number;
  prefix?: string;
  suffix?: string;
  trend?: number;
  trendLabel?: string;
  icon: React.ReactNode;
  accentColor: string;
  bgGradient: string;
}

function animateValue(start: number, end: number, duration: number, callback: (val: number) => void) {
  const startTime = performance.now();
  const step = (currentTime: number) => {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
    callback(start + (end - start) * eased);
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export const KPICard: React.FC<KPICardProps> = ({
  id,
  title,
  value,
  prefix = '',
  suffix = '',
  trend,
  trendLabel,
  icon,
  accentColor,
  bgGradient,
}) => {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    animateValue(0, value, 1200, (v) => setDisplayValue(v));
  }, [value]);

  const formattedValue = Number.isInteger(value)
    ? Math.round(displayValue).toLocaleString()
    : displayValue.toFixed(1);

  const trendIsPositive = trend !== undefined && trend >= 0;

  return (
    <div
      id={id}
      className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-5 transition-all duration-500 hover:border-white/20 hover:bg-white/[0.06] hover:shadow-2xl hover:-translate-y-1"
    >
      {/* Accent glow */}
      <div
        className={`absolute -top-12 -right-12 w-32 h-32 rounded-full blur-3xl opacity-20 group-hover:opacity-35 transition-opacity duration-700 ${bgGradient}`}
      />

      <div className="relative z-10 flex items-start justify-between">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">
            {title}
          </p>
          <p className="text-3xl font-extrabold tracking-tight text-white">
            {prefix}{formattedValue}{suffix}
          </p>
          {trend !== undefined && (
            <div className="flex items-center gap-1.5">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold ${
                  trendIsPositive
                    ? 'bg-emerald-500/15 text-emerald-400'
                    : 'bg-red-500/15 text-red-400'
                }`}
              >
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                  <path
                    d={trendIsPositive ? 'M6 2L10 7H2L6 2Z' : 'M6 10L2 5H10L6 10Z'}
                    fill="currentColor"
                  />
                </svg>
                {Math.abs(trend).toFixed(1)}%
              </span>
              {trendLabel && (
                <span className="text-xs text-slate-500">{trendLabel}</span>
              )}
            </div>
          )}
        </div>

        <div
          className={`flex items-center justify-center w-12 h-12 rounded-xl ${accentColor} bg-opacity-10 ring-1 ring-white/10`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
};

export default KPICard;
