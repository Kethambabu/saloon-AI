/**
 * RetentionAnalytics Component - Customer retention and LTV visualization
 * Donut chart for retention distribution + LTV leaderboard table.
 */

import React from 'react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
} from 'recharts';
import type { RetentionAnalytics as RetentionData } from '../../types/analytics';

interface RetentionAnalyticsProps {
  data: RetentionData;
}

const RETENTION_COLORS = ['#f97316', '#6366f1'];

export const RetentionAnalyticsView: React.FC<RetentionAnalyticsProps> = ({ data }) => {
  const metrics = data.retention_metrics;
  const pieData = [
    { name: 'One-Time', value: metrics.one_time_visitors },
    { name: 'Repeat', value: metrics.repeat_visitors },
  ];

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      {/* Retention Overview */}
      <div
        id="retention-overview"
        className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="mb-4">
          <h3 className="text-lg font-bold text-white">Retention Rate</h3>
          <p className="text-xs text-slate-500 mt-0.5">Customer loyalty distribution</p>
        </div>

        {/* Central metric */}
        <div className="relative h-52 flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={85}
                paddingAngle={4}
                dataKey="value"
                strokeWidth={0}
                startAngle={90}
                endAngle={-270}
              >
                {pieData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={RETENTION_COLORS[index]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number, name: string) => [value, name]}
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
          {/* Center text overlay */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-3xl font-extrabold text-white">
              {metrics.retention_rate_pct}%
            </span>
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Retained</span>
          </div>
        </div>

        {/* Metric cards */}
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-3 text-center">
            <p className="text-xl font-extrabold text-indigo-400">{metrics.repeat_visitors}</p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">Repeat</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-3 text-center">
            <p className="text-xl font-extrabold text-orange-400">{metrics.one_time_visitors}</p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">One-Time</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-3 text-center">
            <p className="text-xl font-extrabold text-emerald-400">{metrics.loyal_visitors_3plus}</p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">Loyal (3+)</p>
          </div>
          <div className="rounded-xl bg-white/[0.03] border border-white/5 p-3 text-center">
            <p className="text-xl font-extrabold text-white">{metrics.total_registered_customers}</p>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">Total</p>
          </div>
        </div>
      </div>

      {/* LTV Leaderboard */}
      <div
        id="ltv-leaderboard"
        className="xl:col-span-2 rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-bold text-white">Customer Lifetime Value</h3>
            <p className="text-xs text-slate-500 mt-0.5">Top customers by total spend</p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            High-Value Cohort
          </span>
        </div>

        {/* Table */}
        <div className="overflow-hidden rounded-xl border border-white/5">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5 bg-white/[0.02]">
                <th className="text-left text-[10px] font-bold text-slate-500 uppercase tracking-wider px-4 py-3">
                  Rank
                </th>
                <th className="text-left text-[10px] font-bold text-slate-500 uppercase tracking-wider px-4 py-3">
                  Customer
                </th>
                <th className="text-right text-[10px] font-bold text-slate-500 uppercase tracking-wider px-4 py-3">
                  Lifetime Value
                </th>
                <th className="text-right text-[10px] font-bold text-slate-500 uppercase tracking-wider px-4 py-3">
                  Share
                </th>
              </tr>
            </thead>
            <tbody>
              {data.top_customers_by_ltv.map((customer, i) => {
                const maxLtv = data.top_customers_by_ltv[0]?.ltv || 1;
                const share = (customer.ltv / maxLtv) * 100;
                return (
                  <tr
                    key={customer.customer_name}
                    className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center justify-center w-6 h-6 rounded-lg text-xs font-bold ${
                        i === 0 ? 'bg-amber-500/15 text-amber-400' :
                        i === 1 ? 'bg-slate-500/15 text-slate-300' :
                        i === 2 ? 'bg-orange-500/15 text-orange-400' :
                        'bg-white/5 text-slate-500'
                      }`}>
                        {i + 1}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-semibold text-white">{customer.customer_name}</p>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-bold text-indigo-400">
                        ${customer.ltv.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-indigo-500 transition-all duration-1000"
                            style={{ width: `${share}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-medium text-slate-500 w-8 text-right">
                          {share.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default RetentionAnalyticsView;
