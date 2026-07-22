/**
 * Shared skeleton-loading primitives.
 *
 * Used in place of a bare spinner/text placeholder on the three portal
 * dashboards so the initial load renders a shape that resembles the real
 * layout instead of a blank pulsing message — reduces perceived load time
 * and layout shift once real data arrives.
 */
import React from 'react';

export const SkeletonBlock: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse rounded-xl bg-slate-800/60 ${className}`} />
);

/** Row of KPI-style stat cards, e.g. revenue / appointments / rating tiles. */
export const SkeletonStatRow: React.FC<{ count?: number }> = ({ count = 4 }) => (
  <div className="grid grid-cols-2 md:grid-cols-4 gap-4" role="status" aria-label="Loading metrics">
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4 space-y-3">
        <SkeletonBlock className="h-3 w-16" />
        <SkeletonBlock className="h-6 w-20" />
      </div>
    ))}
  </div>
);

/** Generic content card placeholder (charts, lists, tables). */
export const SkeletonCard: React.FC<{ lines?: number; className?: string }> = ({ lines = 4, className = '' }) => (
  <div className={`rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 space-y-3 ${className}`}>
    <SkeletonBlock className="h-4 w-1/3" />
    {Array.from({ length: lines }).map((_, i) => (
      <SkeletonBlock key={i} className="h-3 w-full" />
    ))}
  </div>
);

/**
 * Full dashboard-shaped skeleton: stat row + two content cards. Matches the
 * general structure of the Admin/Staff/Customer dashboard "home" tab closely
 * enough to avoid a jarring swap-in once data loads, without coupling this
 * shared component to any one portal's exact layout.
 */
export const DashboardSkeleton: React.FC<{ label?: string }> = ({ label = 'Loading dashboard…' }) => (
  <div className="space-y-6 animate-fade-in" role="status" aria-live="polite" aria-busy="true">
    <span className="sr-only">{label}</span>
    <SkeletonStatRow />
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <SkeletonCard className="lg:col-span-2" lines={6} />
      <SkeletonCard lines={5} />
    </div>
  </div>
);

export default DashboardSkeleton;
