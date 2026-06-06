import React from 'react';

interface AppointmentRecord {
  id: string;
  start_time: string;
  raw_start_time: string;
  end_time: string;
  customer_name: string;
  service_name: string;
  notes: string;
  status: string;
}

interface LeaveItem {
  id: string;
  leave_date: string;
  reason: string | null;
}

interface ScheduleCardProps {
  appointments: AppointmentRecord[];
  leaves: LeaveItem[];
  leaveDate: string;
  leaveReason: string;
  setLeaveDate: (val: string) => void;
  setLeaveReason: (val: string) => void;
  onAddLeave: (e: React.FormEvent) => void;
  onCancelLeave: (leaveId: string) => void;
}

export const ScheduleCard: React.FC<ScheduleCardProps> = ({
  appointments,
  leaves,
  leaveDate,
  leaveReason,
  setLeaveDate,
  setLeaveReason,
  onAddLeave,
  onCancelLeave
}) => {

  const getCurrentWeekDates = () => {
    const now = new Date();
    const currentDay = now.getUTCDay(); // 0 is Sunday, 1 is Monday, etc.
    const distanceToMonday = currentDay === 0 ? -6 : 1 - currentDay;
    
    const monday = new Date(now);
    monday.setUTCDate(now.getUTCDate() + distanceToMonday);
    
    const weekDates = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setUTCDate(monday.getUTCDate() + i);
      weekDates.push(d);
    }
    return weekDates;
  };

  const weekDates = getCurrentWeekDates();

  return (
    <div className="space-y-6 text-left">
      <div className="border-b border-slate-800 pb-3">
        <h2 className="text-xl font-black">🗓️ Weekly Stylist Roster Calendar</h2>
        <p className="text-xs text-slate-500">Track your weekly shifts, active hours, and leave schedules.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Calendar Grid */}
        <div className="lg:col-span-2 bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
          <h3 className="text-sm font-extrabold text-white uppercase tracking-wider"> Roster Matrix</h3>
          <div className="grid grid-cols-7 gap-2">
            {weekDates.map((date, idx) => {
              const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
              const dayNum = date.getUTCDate();
              const dateStr = date.toISOString().split('T')[0];
              
              const dayAppts = appointments.filter(a => {
                if (!a.raw_start_time) return false;
                return a.raw_start_time.startsWith(dateStr) && a.status !== 'CANCELLED';
              });
              
              const isOnLeave = leaves.some(l => l.leave_date === dateStr);
              const leaveInfo = leaves.find(l => l.leave_date === dateStr);

              return (
                <div 
                  key={idx} 
                  className={`p-3 rounded-xl border flex flex-col justify-between min-h-[120px] transition-all ${
                    isOnLeave 
                      ? 'bg-amber-950/10 border-amber-900/30 text-amber-500'
                      : dayAppts.length > 0
                      ? 'bg-slate-900 border-emerald-800/40 text-emerald-400'
                      : 'bg-slate-950/80 border-slate-850 text-slate-400 hover:border-slate-800'
                  }`}
                >
                  <div>
                    <span className="block text-[10px] font-black uppercase tracking-wider opacity-60">{dayName}</span>
                    <span className="text-base font-black text-white">{dayNum}</span>
                  </div>
                  
                  <div className="mt-2 text-left">
                    {isOnLeave ? (
                      <span className="text-[9px] font-bold uppercase tracking-wider block bg-amber-550/10 border border-amber-500/20 px-1 py-0.5 rounded text-amber-500" title={leaveInfo?.reason || "On Leave"}>
                        🏖️ Leave
                      </span>
                    ) : dayAppts.length > 0 ? (
                      <span className="text-[9px] font-black uppercase tracking-wider block bg-emerald-500/10 border border-emerald-500/20 px-1 py-0.5 rounded text-emerald-400">
                        ⚡ {dayAppts.length} Booking{dayAppts.length > 1 ? 's' : ''}
                      </span>
                    ) : (
                      <span className="text-[8px] font-bold text-slate-500 uppercase tracking-widest block">
                        Free Slot
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Leaves Request Panel */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl flex flex-col justify-between gap-6">
          <div className="space-y-4">
            <h3 className="text-sm font-extrabold text-white uppercase tracking-wider">🌴 Schedule Leave & Off Days</h3>
            <form onSubmit={onAddLeave} className="space-y-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Target Leave Date</label>
                <input
                  type="date"
                  value={leaveDate}
                  onChange={e => setLeaveDate(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 bg-slate-950 border border-slate-850 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Reason / Note</label>
                <input
                  type="text"
                  value={leaveReason}
                  onChange={e => setLeaveReason(e.target.value)}
                  placeholder="e.g. personal, family event"
                  className="w-full px-4 py-2.5 bg-slate-950 border border-slate-850 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <button
                type="submit"
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition-all cursor-pointer uppercase tracking-wider mt-1"
              >
                Schedule Leave
              </button>
            </form>
          </div>

          <div className="space-y-3">
            <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-850 pb-2">My Active Leaves</h4>
            {leaves.length === 0 ? (
              <p className="text-left text-slate-500 text-xs py-2">No scheduled leaves found.</p>
            ) : (
              <div className="space-y-2 max-h-[150px] overflow-y-auto custom-scrollbar">
                {leaves.map((l) => (
                  <div key={l.id} className="bg-slate-950/60 border border-slate-850 px-3.5 py-2.5 rounded-xl flex items-center justify-between gap-2 text-xs">
                    <div>
                      <span className="font-bold text-white block">{l.leave_date}</span>
                      <span className="text-[10px] text-slate-500 font-semibold italic">{l.reason || 'No note provided'}</span>
                    </div>
                    <button
                      onClick={() => onCancelLeave(l.id)}
                      className="text-[10px] text-red-400 hover:text-red-500 cursor-pointer font-bold uppercase tracking-wider"
                    >
                      Cancel
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default ScheduleCard;
