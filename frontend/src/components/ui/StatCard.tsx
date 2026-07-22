/**
 * Shared KPI stat-tile primitive.
 *
 * Admin, Staff, and Customer dashboards each hand-rolled their own version
 * of this card with matching Tailwind classes (bg-slate-900/60
 * backdrop-blur-xl border rounded-2xl, same title/value/desc type scale) —
 * consolidating into one component keeps that visual language in sync by
 * construction instead of by convention across three separate files.
 */
import React from 'react';

export interface StatCardProps {
  title: string;
  value: React.ReactNode;
  desc?: string;
  icon?: React.ReactNode;
  /** Tailwind text-color utility class applied to the value, e.g. 'text-emerald-400'. */
  color?: string;
  onClick?: () => void;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, desc, icon, color = 'text-white', onClick }) => {
  const interactive = typeof onClick === 'function';

  return (
    <div
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
      className={`bg-slate-900/60 backdrop-blur-xl border border-slate-800/80 p-5 rounded-2xl shadow-md space-y-1.5 transition-all duration-300 group ${
        icon ? 'flex items-center space-x-4 space-y-0' : ''
      } ${
        interactive
          ? 'cursor-pointer hover:scale-[1.02] hover:border-blue-500/50 hover:bg-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500'
          : ''
      }`}
    >
      {icon && (
        <div className="w-12 h-12 rounded-xl bg-slate-850 flex items-center justify-center text-2xl flex-shrink-0">
          {icon}
        </div>
      )}
      <div>
        <span className="block text-[10px] font-black text-slate-450 uppercase tracking-wider group-hover:text-blue-400 transition-colors">
          {title}
        </span>
        <span className={`font-black block ${icon ? 'text-lg mt-0.5' : 'text-2xl'} ${color}`}>{value}</span>
        {desc && <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">{desc}</span>}
      </div>
    </div>
  );
};

export default StatCard;
