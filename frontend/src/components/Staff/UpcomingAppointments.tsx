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

interface UpcomingAppointmentsProps {
  appointments: AppointmentRecord[];
  onUpdateStatus: (apptId: string, nextStatus: string) => void;
}

export const UpcomingAppointments: React.FC<UpcomingAppointmentsProps> = ({ appointments, onUpdateStatus }) => {
  const activeAppts = appointments.filter(a => a.status !== 'CANCELLED' && a.status !== 'COMPLETED');

  return (
    <div className="space-y-6 text-left">
      <div className="border-b border-slate-800 pb-3">
        <h2 className="text-xl font-black">📅 Today's Styling Ledger</h2>
        <p className="text-xs text-slate-500">Track and update the live status of appointments assigned to your chair.</p>
      </div>

      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
        {activeAppts.length === 0 ? (
          <div className="text-center text-slate-500 py-12 text-xs font-bold">
            No active appointments scheduled for today.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activeAppts.map(appt => (
              <div key={appt.id} className="bg-slate-900/80 border border-slate-800/80 p-5 rounded-2xl flex flex-col justify-between relative hover:border-slate-700 transition-colors">
                <div>
                  <span className="absolute top-4 right-4 px-2 py-0.5 bg-emerald-500/10 text-emerald-450 rounded text-[9px] font-bold border border-emerald-500/20 uppercase tracking-wide">
                    {appt.start_time}
                  </span>
                  <div className="space-y-1 text-left">
                    <h4 className="text-base font-extrabold text-white">{appt.customer_name}</h4>
                    <span className="text-xs text-emerald-450 font-bold block">{appt.service_name}</span>
                  </div>
                  <p className="text-xs text-slate-350 leading-relaxed font-medium bg-slate-950 p-3.5 rounded-xl border border-slate-850 my-3 text-left">
                    <span className="text-[10px] text-slate-500 font-black block uppercase tracking-wider mb-1">Stylist Notes:</span>
                    {appt.notes}
                  </p>
                </div>
                
                <div className="flex justify-between items-center pt-2.5 border-t border-slate-850/60 mt-1">
                  <span className={`px-2.5 py-0.5 rounded text-[9px] font-black border uppercase tracking-wider ${
                    appt.status === 'PENDING'
                      ? 'bg-amber-900/20 text-amber-300 border-amber-800/40'
                      : appt.status === 'CONFIRMED'
                      ? 'bg-blue-900/20 text-blue-300 border-blue-800/40'
                      : appt.status === 'CHECKED_IN'
                      ? 'bg-purple-900/20 text-purple-300 border-purple-800/40'
                      : appt.status === 'IN_SERVICE'
                      ? 'bg-indigo-900/20 text-indigo-300 border-indigo-800/40'
                      : 'bg-slate-900 text-slate-500 border-slate-800'
                  }`}>
                    {appt.status}
                  </span>

                  <div className="flex gap-1.5">
                    {appt.status === 'PENDING' && (
                      <>
                        <button
                          onClick={() => onUpdateStatus(appt.id, 'CONFIRMED')}
                          className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow-md shadow-emerald-500/10"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => onUpdateStatus(appt.id, 'CANCELLED')}
                          className="px-3 py-1 bg-slate-950 border border-slate-800 hover:border-red-900/40 text-slate-450 hover:text-red-400 rounded-lg text-[10px] font-bold cursor-pointer transition-all"
                        >
                          Cancel
                        </button>
                      </>
                    )}
                    {appt.status === 'CONFIRMED' && (
                      <>
                        <button
                          onClick={() => onUpdateStatus(appt.id, 'CHECKED_IN')}
                          className="px-3 py-1 bg-blue-650 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow-md shadow-blue-500/10"
                        >
                          Check In
                        </button>
                        <button
                          onClick={() => onUpdateStatus(appt.id, 'CANCELLED')}
                          className="px-3 py-1 bg-slate-950 border border-slate-800 hover:border-red-900/40 text-slate-455 hover:text-red-400 rounded-lg text-[10px] font-bold cursor-pointer transition-all"
                        >
                          Cancel
                        </button>
                      </>
                    )}
                    {appt.status === 'CHECKED_IN' && (
                      <button
                        onClick={() => onUpdateStatus(appt.id, 'IN_SERVICE')}
                        className="px-3 py-1 bg-purple-650 hover:bg-purple-500 text-white rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow-md shadow-purple-500/10"
                      >
                        Start Service
                      </button>
                    )}
                    {appt.status === 'IN_SERVICE' && (
                      <button
                        onClick={() => onUpdateStatus(appt.id, 'COMPLETED')}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[10px] font-bold cursor-pointer transition-all shadow-md shadow-emerald-500/10"
                      >
                        Complete Job
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default UpcomingAppointments;
