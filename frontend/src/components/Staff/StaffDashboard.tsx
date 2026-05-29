import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';

interface PersonalRoster {
  id: string;
  customer_name: string;
  service_name: string;
  start_time: string;
  notes: string;
}

interface StaffDashboardProps {
  onToggleChat: () => void;
}

export const StaffDashboard: React.FC<StaffDashboardProps> = ({ onToggleChat }) => {
  const { user, logout } = useAuth();
  const [schedule, setSchedule] = useState<PersonalRoster[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Personal metrics
  const stats = [
    { title: 'Today Schedule', value: '1 Appointment', desc: 'Starting at 10:00 AM', icon: '⏰' },
    { title: 'My Performance', value: '99% Score', desc: 'Top ratings on haircut styling', icon: '📈' },
    { title: 'Commission Earned', value: '$85.00', desc: '1 completed styling session', icon: '💰' }
  ];

  useEffect(() => {
    const fetchPersonalSchedule = async () => {
      try {
        setSchedule([
          { id: '0e3f1b64-444c-4c6e-0342-cf0e985c0df1', customer_name: 'Alice Smith', service_name: 'Signature Precision Haircut', start_time: '10:00 AM - 11:00 AM', notes: 'Prefers layers haircut' }
        ]);
      } catch (err) {
        console.warn('Failed to load dynamic stylist roster');
      } finally {
        setIsLoading(false);
      }
    };
    fetchPersonalSchedule();
  }, []);

  return (
    <div className="space-y-8 text-left animate-fade-in">
      
      {/* Welcome banner */}
      <section className="bg-gradient-to-r from-emerald-900 via-slate-800 to-indigo-950 text-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-800 relative overflow-hidden flex flex-col md:flex-row items-center justify-between">
        <div className="absolute top-0 right-0 w-80 h-80 bg-emerald-600/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none" />
        
        <div className="space-y-2 z-10">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            💇 Stylist & Professional Hub
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight">
            My Creative Workspace
          </h1>
          <p className="text-slate-300 text-sm max-w-xl leading-relaxed">
            Welcome back, <span className="text-white font-bold">{user?.email}</span>. Review your daily appointment book, check client preferences, track commissions, and work with Clara.
          </p>
        </div>
        
        <div className="mt-4 md:mt-0 z-10 flex space-x-3">
          <button
            onClick={onToggleChat}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl shadow-md transition-all cursor-pointer"
          >
            💬 Open Clara Assistant
          </button>
          <button
            onClick={logout}
            className="px-4 py-2 bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-xl transition-all cursor-pointer"
          >
            Logout
          </button>
        </div>
      </section>

      {/* Stylist Stats Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-slate-850 flex items-center justify-center text-2xl">
              {stat.icon}
            </div>
            <div>
              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider">{stat.title}</span>
              <span className="text-lg font-extrabold text-white block mt-0.5">{stat.value}</span>
              <span className="text-[10px] text-slate-500 block mt-0.5 font-medium">{stat.desc}</span>
            </div>
          </div>
        ))}
      </section>

      {/* Schedule list */}
      <section className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
        <div>
          <h3 className="text-lg font-extrabold text-white">My Agenda Today</h3>
          <p className="text-xs text-slate-500">Examine details, times, and preferences for your client appointments.</p>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-slate-500 font-semibold animate-pulse">Loading daily agenda...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800 text-sm">
              <thead>
                <tr className="text-slate-400 font-bold uppercase tracking-wider text-xs">
                  <th className="px-4 py-3 text-left">Time Slot</th>
                  <th className="px-4 py-3 text-left">Customer</th>
                  <th className="px-4 py-3 text-left">Requested Service</th>
                  <th className="px-4 py-3 text-left">Special Instructions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {schedule.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-850/30 transition-colors">
                    <td className="px-4 py-4 whitespace-nowrap text-blue-400 font-bold">{s.start_time}</td>
                    <td className="px-4 py-4 whitespace-nowrap font-semibold text-white">{s.customer_name}</td>
                    <td className="px-4 py-4 whitespace-nowrap text-slate-350">{s.service_name}</td>
                    <td className="px-4 py-4 whitespace-nowrap text-slate-400 italic">{s.notes || 'No notes specified.'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

    </div>
  );
};
