/**
 * StaffPerformance Component - Staff analytics with bar chart and leaderboard
 * Horizontal bar chart + detailed performance cards for each team member.
 */

import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import type { StaffAnalytics } from '../../types/analytics';

interface StaffPerformanceProps {
  data: StaffAnalytics;
}

const RANK_BADGES = ['🥇', '🥈', '🥉', '', ''];

const CustomBarTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/95 backdrop-blur-xl px-4 py-3 shadow-2xl">
      <p className="text-xs font-semibold text-slate-400 mb-1">{label}</p>
      <p className="text-sm font-bold text-white">
        ${payload[0]?.value?.toLocaleString()}
      </p>
    </div>
  );
};

export const StaffPerformance: React.FC<StaffPerformanceProps> = ({ data }) => {
  const barData = data.staff_metrics.map((m) => ({
    name: m.name.split(' ')[0],
    revenue: m.revenue_generated,
    bookings: m.completed_bookings,
  }));

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      {/* Revenue Bar Chart */}
      <div
        id="staff-revenue-chart"
        className="xl:col-span-2 rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-white">Staff Revenue</h3>
            <p className="text-xs text-slate-500 mt-0.5">Revenue generated per team member</p>
          </div>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0.6} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="name"
                tick={{ fill: '#64748b', fontSize: 11 }}
                axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip content={<CustomBarTooltip />} />
              <Bar
                dataKey="revenue"
                fill="url(#barGradient)"
                radius={[8, 8, 0, 0]}
                maxBarSize={48}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Staff Leaderboard */}
      <div
        id="staff-leaderboard"
        className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="mb-5">
          <h3 className="text-lg font-bold text-white">Performance Board</h3>
          <p className="text-xs text-slate-500 mt-0.5">Top performing stylists</p>
        </div>
        <div className="space-y-3">
          {data.staff_metrics.slice(0, 5).map((member, i) => (
            <div
              key={member.staff_id}
              className="group flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 transition-all duration-300 hover:border-white/10 hover:bg-white/[0.04]"
            >
              {/* Rank */}
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/5 text-sm font-bold">
                {RANK_BADGES[i] || (
                  <span className="text-slate-500">#{i + 1}</span>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white truncate">{member.name}</p>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">{member.role}</p>
              </div>

              {/* Stats */}
              <div className="text-right">
                <p className="text-sm font-bold text-indigo-400">
                  ${member.revenue_generated.toLocaleString()}
                </p>
                <div className="flex items-center justify-end gap-1 mt-0.5">
                  <svg className="w-3 h-3 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  <span className="text-[10px] font-bold text-amber-400/80">
                    {member.average_rating}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default StaffPerformance;
