/**
 * AppointmentTrends Component - Booking volume and status analytics
 * Combines a stacked bar chart with service popularity breakdown.
 */

import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell,
} from 'recharts';
import type { ServiceAnalytics } from '../../types/analytics';

interface AppointmentTrendsProps {
  data: ServiceAnalytics;
}

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c084fc', '#e879f9', '#f472b6'];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/95 backdrop-blur-xl px-4 py-3 shadow-2xl">
      <p className="text-xs font-semibold text-slate-400 mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-bold text-white">
          {entry.value} bookings
        </p>
      ))}
    </div>
  );
};

export const AppointmentTrends: React.FC<AppointmentTrendsProps> = ({ data }) => {
  const chartData = data.services.map((s) => ({
    name: s.service_name.length > 12 ? s.service_name.slice(0, 12) + '…' : s.service_name,
    fullName: s.service_name,
    bookings: s.total_bookings,
    revenue: s.total_revenue,
  }));

  const totalBookings = data.services.reduce((acc, s) => acc + s.total_bookings, 0);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      {/* Bookings Bar Chart */}
      <div
        id="appointment-bookings-chart"
        className="xl:col-span-2 rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-white">Service Demand</h3>
            <p className="text-xs text-slate-500 mt-0.5">Booking volume per service category</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-extrabold text-white">{totalBookings.toLocaleString()}</p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider">Total Bookings</p>
          </div>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="name"
                tick={{ fill: '#64748b', fontSize: 10 }}
                axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                tickLine={false}
                interval={0}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="bookings" radius={[8, 8, 0, 0]} maxBarSize={48}>
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Service Popularity Cards */}
      <div
        id="service-popularity-list"
        className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="mb-5">
          <h3 className="text-lg font-bold text-white">Trending Services</h3>
          <p className="text-xs text-slate-500 mt-0.5">Ranked by booking volume</p>
        </div>
        <div className="space-y-3">
          {data.services.map((service, i) => {
            const pct = totalBookings > 0 ? (service.total_bookings / totalBookings) * 100 : 0;
            return (
              <div key={service.service_name} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: COLORS[i % COLORS.length] }}
                    />
                    <span className="text-xs font-medium text-slate-300 truncate max-w-[130px]">
                      {service.service_name}
                    </span>
                  </div>
                  <span className="text-xs font-bold text-slate-400">
                    {service.total_bookings}
                  </span>
                </div>
                {/* Progress bar */}
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: COLORS[i % COLORS.length],
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default AppointmentTrends;
