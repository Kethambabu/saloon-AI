/**
 * RevenueChart Component - Revenue time-series and breakdown visualization
 * Area chart for revenue trends + donut chart for service breakdown.
 */

import React from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';
import type { RevenueAnalytics } from '../../types/analytics';

interface RevenueChartProps {
  data: RevenueAnalytics;
}

const GRADIENT_COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#ede9fe'];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/95 backdrop-blur-xl px-4 py-3 shadow-2xl">
      <p className="text-xs font-semibold text-slate-400 mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-bold text-white">
          ${entry.value?.toLocaleString()}
        </p>
      ))}
    </div>
  );
};

export const RevenueChart: React.FC<RevenueChartProps> = ({ data }) => {
  const timeData = data.charts.revenue_over_time.labels.map((label, i) => ({
    name: label,
    revenue: data.charts.revenue_over_time.datasets[0]?.data[i] ?? 0,
  }));

  const serviceData = Object.entries(data.revenue_by_service).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      {/* Revenue Trend - Area Chart */}
      <div
        id="revenue-trend-chart"
        className="xl:col-span-2 rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-white">Revenue Trend</h3>
            <p className="text-xs text-slate-500 mt-0.5">Monthly performance overview</p>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-1.5">
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            <span className="text-xs font-medium text-slate-400">Live</span>
          </div>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timeData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
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
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="#6366f1"
                strokeWidth={2.5}
                fill="url(#revenueGradient)"
                dot={{ fill: '#6366f1', strokeWidth: 0, r: 3 }}
                activeDot={{ r: 6, fill: '#818cf8', stroke: '#6366f1', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Revenue by Service - Donut Chart */}
      <div
        id="revenue-service-chart"
        className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="mb-4">
          <h3 className="text-lg font-bold text-white">Service Revenue</h3>
          <p className="text-xs text-slate-500 mt-0.5">Breakdown by service type</p>
        </div>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={serviceData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
                strokeWidth={0}
              >
                {serviceData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={GRADIENT_COLORS[index % GRADIENT_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number) => [`$${value.toLocaleString()}`, 'Revenue']}
                contentStyle={{
                  backgroundColor: 'rgba(15,23,42,0.95)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  fontSize: '12px',
                  color: '#fff',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        {/* Legend */}
        <div className="space-y-2 mt-2">
          {serviceData.slice(0, 4).map((item, i) => (
            <div key={item.name} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: GRADIENT_COLORS[i] }}
                />
                <span className="text-slate-400 truncate max-w-[120px]">{item.name}</span>
              </div>
              <span className="font-semibold text-slate-300">${item.value.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default RevenueChart;
