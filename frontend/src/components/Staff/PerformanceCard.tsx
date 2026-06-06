import React from 'react';

interface PerformanceMetrics {
  totalAppointments: number;
  completedAppointments: number;
  cancelledAppointments: number;
  averageRating: number;
  name: string;
  role: string;
}

interface PerformanceCardProps {
  metrics: PerformanceMetrics;
}

export const PerformanceCard: React.FC<PerformanceCardProps> = ({ metrics }) => {
  const completionRate = metrics.totalAppointments > 0 
    ? Math.round((metrics.completedAppointments / (metrics.totalAppointments - metrics.cancelledAppointments)) * 100) 
    : 0;

  return (
    <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl shadow-xl space-y-6 text-left">
      <div className="flex justify-between items-start">
        <div>
          <span className="px-2 py-0.5 text-[9px] font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full uppercase tracking-wider">
            Stylist Roster Performance
          </span>
          <h3 className="text-lg font-black text-white mt-1.5">{metrics.name}</h3>
          <p className="text-xs text-slate-500 font-bold">{metrics.role}</p>
        </div>
        <div className="w-12 h-12 rounded-2xl bg-emerald-950/40 border border-emerald-900/30 flex items-center justify-center text-xl">
          📈
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-950/40 border border-slate-850 p-4 rounded-2xl">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Average Rating</span>
          <span className="text-xl font-black text-white block mt-1">{metrics.averageRating.toFixed(1)} ★</span>
          <span className="text-[9px] text-slate-500 font-bold uppercase block mt-0.5">Based on reviews</span>
        </div>

        <div className="bg-slate-950/40 border border-slate-850 p-4 rounded-2xl">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Completion Rate</span>
          <span className="text-xl font-black text-white block mt-1">{completionRate}%</span>
          <span className="text-[9px] text-slate-500 font-bold uppercase block mt-0.5">Jobs completed</span>
        </div>

        <div className="bg-slate-950/40 border border-slate-850 p-4 rounded-2xl">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Completed</span>
          <span className="text-xl font-black text-white block mt-1">{metrics.completedAppointments}</span>
          <span className="text-[9px] text-emerald-500 font-bold uppercase block mt-0.5">Confirmed bookings</span>
        </div>

        <div className="bg-slate-950/40 border border-slate-850 p-4 rounded-2xl">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Cancelled</span>
          <span className="text-xl font-black text-red-400 block mt-1">{metrics.cancelledAppointments}</span>
          <span className="text-[9px] text-slate-500 font-bold uppercase block mt-0.5">No-shows/cancellations</span>
        </div>
      </div>
    </div>
  );
};

export default PerformanceCard;
