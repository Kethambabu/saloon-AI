/**
 * Analytics Dashboard - Main executive dashboard page
 * Aggregates all analytics sections with real-time updates and premium dark UI.
 */

import React, { useState } from 'react';
import { useAnalytics } from '../../hooks/useAnalytics';
import { KPICard } from './KPICard';
import { RevenueChart } from './RevenueChart';
import { StaffPerformance } from './StaffPerformance';
import { AppointmentTrends } from './AppointmentTrends';
import { RetentionAnalyticsView } from './RetentionAnalytics';
import type { TimeRange } from '../../types/analytics';

// Icons as inline SVG for zero-dependency setup
const Icons = {
  revenue: (
    <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  bookings: (
    <svg className="w-6 h-6 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  ),
  ticket: (
    <svg className="w-6 h-6 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
    </svg>
  ),
  retention: (
    <svg className="w-6 h-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
  refresh: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  ),
};

const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
  { value: '12m', label: '12 Months' },
  { value: 'all', label: 'All Time' },
];

const SECTIONS = ['overview', 'revenue', 'staff', 'appointments', 'retention'] as const;
type Section = typeof SECTIONS[number];

const SECTION_LABELS: Record<Section, string> = {
  overview: 'Overview',
  revenue: 'Revenue',
  staff: 'Staff',
  appointments: 'Appointments',
  retention: 'Retention',
};

export const AnalyticsDashboard: React.FC = () => {
  const { data, loading, error, lastUpdated, refresh } = useAnalytics();
  const [timeRange, setTimeRange] = useState<TimeRange>('12m');
  const [activeSection, setActiveSection] = useState<Section>('overview');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  // Loading state
  if (loading && !data) {
    return (
      <div className="min-h-screen bg-[#0a0b14] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="relative mx-auto w-16 h-16">
            <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20" />
            <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-indigo-500 animate-spin" />
          </div>
          <p className="text-sm font-medium text-slate-500">Loading analytics...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !data) {
    return (
      <div className="min-h-screen bg-[#0a0b14] flex items-center justify-center">
        <div className="text-center space-y-4 max-w-md">
          <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center mx-auto">
            <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <p className="text-sm text-red-400">{error}</p>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 rounded-xl bg-indigo-500/10 text-indigo-400 text-sm font-medium border border-indigo-500/20 hover:bg-indigo-500/20 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const revenue = data?.revenue;
  const staff = data?.staff;
  const retention = data?.retention;
  const services = data?.services;

  const showSection = (s: Section) => activeSection === 'overview' || activeSection === s;

  return (
    <div id="analytics-dashboard" className="min-h-screen bg-[#0a0b14]">
      {/* Fixed noise texture overlay */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.015]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
      }} />

      <div className="relative z-10 max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* ─── Dashboard Header ─────────────────────────────────── */}
        <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/25">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl font-extrabold text-white tracking-tight">
                  Analytics Dashboard
                </h1>
                <p className="text-xs text-slate-500 font-medium">
                  SalonAI Workforce Intelligence
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Time Range Filter */}
            <div className="flex items-center rounded-xl bg-white/[0.04] border border-white/[0.06] p-0.5">
              {TIME_RANGES.map((range) => (
                <button
                  key={range.value}
                  onClick={() => setTimeRange(range.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                    timeRange === range.value
                      ? 'bg-indigo-500/20 text-indigo-300 shadow-sm'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {range.label}
                </button>
              ))}
            </div>

            {/* Refresh Button */}
            <button
              id="refresh-dashboard"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.04] border border-white/[0.06] text-xs font-semibold text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all duration-200 disabled:opacity-50"
            >
              <span className={isRefreshing ? 'animate-spin' : ''}>{Icons.refresh}</span>
              <span className="hidden sm:inline">Refresh</span>
            </button>

            {/* Last updated */}
            {lastUpdated && (
              <span className="text-[10px] text-slate-600 font-medium">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </header>

        {/* ─── Section Nav Tabs ─────────────────────────────────── */}
        <nav className="flex items-center gap-1 mb-8 overflow-x-auto pb-2">
          {SECTIONS.map((section) => (
            <button
              key={section}
              onClick={() => setActiveSection(section)}
              className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-all duration-200 ${
                activeSection === section
                  ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/20'
                  : 'text-slate-500 hover:text-slate-300 border border-transparent'
              }`}
            >
              {SECTION_LABELS[section]}
            </button>
          ))}
        </nav>

        {/* ─── KPI Cards Row ───────────────────────────────────── */}
        {showSection('overview') && revenue && retention && (
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8 animate-fade-in">
            <KPICard
              id="kpi-revenue"
              title="Total Revenue"
              value={revenue.metrics.total_revenue}
              prefix="$"
              trend={12.4}
              trendLabel="vs last period"
              icon={Icons.revenue}
              accentColor="bg-emerald-500/10"
              bgGradient="bg-emerald-500"
            />
            <KPICard
              id="kpi-bookings"
              title="Total Bookings"
              value={revenue.metrics.total_bookings}
              trend={8.2}
              trendLabel="vs last period"
              icon={Icons.bookings}
              accentColor="bg-indigo-500/10"
              bgGradient="bg-indigo-500"
            />
            <KPICard
              id="kpi-avg-ticket"
              title="Avg Ticket Size"
              value={revenue.metrics.average_ticket}
              prefix="$"
              trend={3.8}
              trendLabel="vs last period"
              icon={Icons.ticket}
              accentColor="bg-violet-500/10"
              bgGradient="bg-violet-500"
            />
            <KPICard
              id="kpi-retention"
              title="Retention Rate"
              value={retention.retention_metrics.retention_rate_pct}
              suffix="%"
              trend={5.1}
              trendLabel="vs last period"
              icon={Icons.retention}
              accentColor="bg-amber-500/10"
              bgGradient="bg-amber-500"
            />
          </section>
        )}

        {/* ─── Revenue Analytics ───────────────────────────────── */}
        {showSection('revenue') && revenue && (
          <section className="mb-8 animate-fade-in">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-6 rounded-full bg-gradient-to-b from-indigo-500 to-violet-600" />
              <h2 className="text-lg font-bold text-white">Revenue Analytics</h2>
            </div>
            <RevenueChart data={revenue} />
          </section>
        )}

        {/* ─── Staff Performance ───────────────────────────────── */}
        {showSection('staff') && staff && (
          <section className="mb-8 animate-fade-in">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-6 rounded-full bg-gradient-to-b from-violet-500 to-purple-600" />
              <h2 className="text-lg font-bold text-white">Staff Performance</h2>
            </div>
            <StaffPerformance data={staff} />
          </section>
        )}

        {/* ─── Appointment Trends ──────────────────────────────── */}
        {showSection('appointments') && services && (
          <section className="mb-8 animate-fade-in">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-6 rounded-full bg-gradient-to-b from-pink-500 to-rose-600" />
              <h2 className="text-lg font-bold text-white">Appointment Trends</h2>
            </div>
            <AppointmentTrends data={services} />
          </section>
        )}

        {/* ─── Retention Analytics ─────────────────────────────── */}
        {showSection('retention') && retention && (
          <section className="mb-8 animate-fade-in">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-1 h-6 rounded-full bg-gradient-to-b from-amber-500 to-orange-600" />
              <h2 className="text-lg font-bold text-white">Retention Analytics</h2>
            </div>
            <RetentionAnalyticsView data={retention} />
          </section>
        )}

        {/* ─── Footer ──────────────────────────────────────────── */}
        <footer className="text-center py-8 border-t border-white/[0.04]">
          <p className="text-[10px] text-slate-600 font-medium uppercase tracking-wider">
            SalonAI Workforce Analytics Engine &middot; Real-Time Intelligence Platform
          </p>
        </footer>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
