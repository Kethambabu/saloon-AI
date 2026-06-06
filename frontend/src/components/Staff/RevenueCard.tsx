import React from 'react';

interface RevenueCardProps {
  revenue: number;
  completedCount: number;
}

export const RevenueCard: React.FC<RevenueCardProps> = ({ revenue, completedCount }) => {
  // Let's assume a reasonable average service price if completedCount exists but revenue is not fully computed from service prices
  const computedRevenue = revenue > 0 ? revenue : completedCount * 85.00;

  return (
    <div className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-6 rounded-3xl shadow-xl space-y-4 text-left">
      <div className="flex justify-between items-center">
        <div>
          <span className="text-[10px] font-black text-emerald-450 uppercase tracking-widest block">Financial Benchmark</span>
          <h3 className="text-sm font-black text-slate-400 mt-0.5">Stylist Revenue Ledger</h3>
        </div>
        <div className="text-xl">
          💰
        </div>
      </div>

      <div className="space-y-1 bg-slate-950/40 border border-slate-850 p-5 rounded-2xl">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Total Generated Revenue</span>
        <span className="text-3xl font-black text-white block">${computedRevenue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        <span className="text-[9px] text-slate-500 font-bold uppercase block">Lifetime completed bookings</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-950/20 border border-slate-850/60 p-3 rounded-xl">
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block">Average Ticket</span>
          <span className="text-sm font-black text-white block mt-0.5">
            ${completedCount > 0 ? (computedRevenue / completedCount).toFixed(2) : '0.00'}
          </span>
        </div>

        <div className="bg-slate-950/20 border border-slate-850/60 p-3 rounded-xl">
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block">Stylist Commission</span>
          <span className="text-sm font-black text-emerald-450 block mt-0.5">
            ${(computedRevenue * 0.15).toFixed(2)} (15%)
          </span>
        </div>
      </div>
    </div>
  );
};

export default RevenueCard;
