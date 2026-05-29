import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
import { AgentChat } from '../AgentChat/AgentChat';

interface AppointmentRecord {
  id: string;
  start_time: string;
  end_time: string;
  customer_name: string;
  service_name: string;
  notes: string;
}

interface CustomerHistoryItem {
  id: string;
  name: string;
  email: string;
  last_service: string;
  last_date: string;
  notes: string;
}

interface StaffDashboardProps {
  onToggleChat?: () => void;
}

export const StaffDashboard: React.FC<StaffDashboardProps> = ({ onToggleChat }) => {
  const { user, logout } = useAuth();
  
  // Navigation state
  const [activeTab, setActiveTab] = useState<'dashboard' | 'appointments' | 'customers' | 'schedule' | 'assistant' | 'profile'>('dashboard');
  
  // Roster lists
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [customers, setCustomers] = useState<CustomerHistoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Upsell Agent helper
  const [upsellSuggestion, setUpsellSuggestion] = useState<string>('');
  const [selectedService, setSelectedService] = useState<string>('Signature Precision Haircut');

  useEffect(() => {
    const loadStaffData = async () => {
      try {
        setIsLoading(true);
        // Simulate loading database data
        setAppointments([
          { id: 'appt-s1', start_time: '10:00 AM - 11:00 AM', end_time: '11:00 AM', customer_name: 'Alice Smith', service_name: 'Signature Precision Haircut', notes: 'Requests layering, prefers organic hair products' },
          { id: 'appt-s2', start_time: '01:30 PM - 03:00 PM', end_time: '03:00 PM', customer_name: 'David Jones', service_name: 'Balayage & Creative Color', notes: 'First session, wants subtle cool blonde highlights' }
        ]);

        setCustomers([
          { id: 'c-1', name: 'Alice Smith', email: 'alice.s@example.com', last_service: 'Signature Precision Haircut', last_date: '2026-05-10', notes: 'Always prefers Alexandra or Marcus. Prefers quiet session.' },
          { id: 'c-2', name: 'David Jones', email: 'david.j@example.com', last_service: 'Beard Trim & Clean Shave', last_date: '2026-04-18', notes: 'Wants strong moisturizers post-shave.' },
          { id: 'c-3', name: 'Emily Davis', email: 'emily.d@example.com', last_service: 'Balayage & Creative Color', last_date: '2026-05-02', notes: 'Sensitive scalp, color should stay off root line.' }
        ]);
      } catch (e) {
        console.warn('Failed to load dynamic stylist logs', e);
      } finally {
        setIsLoading(false);
      }
    };
    loadStaffData();
  }, []);

  // Compute stats metrics
  const stats = [
    { title: "Today's Styling Book", value: `${appointments.length} Slots`, desc: 'Starting 10:00 AM', icon: '⏰' },
    { title: 'Stylist Rating', value: '4.95 ★', desc: 'Top tier precision rating', icon: '📈' },
    { title: 'Upsell Converts', value: '14 successful', desc: 'Commission bonus active', icon: '⚡' },
    { title: 'Branch Location', value: 'Downtown Elite', desc: 'Assigned Stylist', icon: '📍' }
  ];

  // Search filtered customers
  const filteredCustomers = customers.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    c.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Trigger Upsell recommendation mock matching standard agent rules
  const handleQueryUpsell = () => {
    if (selectedService === 'Signature Precision Haircut') {
      setUpsellSuggestion("💡 Upsell Agent Recommendation:\nRecommend our 'Hydrating Keratin Leave-in treatment' for $25. Marcus earns a 15% commission ($3.75) upon conversion.");
    } else if (selectedService === 'Balayage & Creative Color') {
      setUpsellSuggestion("💡 Upsell Agent Recommendation:\nRecommend 'Post-Color UV Protection Shield Treatment' for $45. Marcus earns a 15% commission ($6.75) upon conversion.");
    } else {
      setUpsellSuggestion("💡 Upsell Agent Recommendation:\nRecommend 'Signature Scalp Cleansing Detox Massage' for $30. Marcus earns a 15% commission ($4.50) upon conversion.");
    }
  };

  return (
    <div className="flex flex-col md:flex-row min-h-[85vh] bg-slate-950 text-white rounded-3xl overflow-hidden border border-slate-800/80 shadow-2xl font-sans">
      
      {/* Sidebar Navigation */}
      <aside className="w-full md:w-64 bg-slate-900 border-r border-slate-800/80 p-6 flex flex-col justify-between">
        <div className="space-y-6">
          <div className="text-left border-b border-slate-800 pb-4">
            <h2 className="text-xl font-black bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
              Stylist Hub
            </h2>
            <span className="inline-flex items-center px-2 py-0.5 mt-1 rounded text-[9px] font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase tracking-widest">
              Stylist Staff
            </span>
          </div>

          <nav className="flex flex-col gap-2">
            {[
              { id: 'dashboard', label: 'My Dashboard', icon: '🏠' },
              { id: 'appointments', label: 'Agenda Book', icon: '📅' },
              { id: 'customers', label: 'Client History', icon: '👥' },
              { id: 'schedule', label: 'My Calendar', icon: '🗓️' },
              { id: 'assistant', label: 'AI Co-Stylist', icon: '🤖' },
              { id: 'profile', label: 'Stylist Profile', icon: '👤' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl text-xs font-bold text-left transition-all cursor-pointer ${
                  activeTab === tab.id
                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <span className="text-lg">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="mt-8 text-left border-t border-slate-800 pt-4 flex items-center justify-between">
          <div className="overflow-hidden">
            <span className="block text-[9px] font-black text-slate-500 uppercase tracking-widest">Stylist Account</span>
            <span className="block text-xs font-bold text-slate-350 truncate">{user?.email}</span>
          </div>
          <button
            onClick={logout}
            className="p-2 bg-red-650/15 border border-red-500/25 hover:bg-red-650/25 text-red-400 rounded-lg transition-all cursor-pointer text-xs"
            title="Log Out"
          >
            🚪
          </button>
        </div>
      </aside>

      {/* Main Stylist Operations Panel */}
      <main className="flex-1 p-6 md:p-8 text-left overflow-y-auto max-h-[85vh]">
        {isLoading ? (
          <div className="py-24 text-center text-slate-500 font-bold animate-pulse">
            Establishing Creative Session...
          </div>
        ) : (
          <div className="animate-fade-in space-y-6">
            
            {/* 1. Dashboard Tab */}
            {activeTab === 'dashboard' && (
              <div className="space-y-6">
                
                {/* Welcome Banner */}
                <section className="bg-gradient-to-r from-emerald-950/60 via-slate-900/60 to-slate-900/60 rounded-3xl p-6 border border-slate-800/80 flex flex-col md:flex-row items-center justify-between gap-4">
                  <div className="space-y-2">
                    <span className="px-2.5 py-0.5 text-[9px] font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full uppercase tracking-widest">
                      Professional Suite
                    </span>
                    <h2 className="text-2xl font-black">My Creative Board</h2>
                    <p className="text-xs text-slate-400 max-w-xl">
                      Review today's style book, check client preferences before they arrive, and configure Upsell matches.
                    </p>
                  </div>
                  {onToggleChat && (
                    <button
                      onClick={onToggleChat}
                      className="px-5 py-3 bg-blue-600 hover:bg-blue-500 text-xs font-bold rounded-xl transition-all shadow-lg shadow-blue-500/10 whitespace-nowrap cursor-pointer"
                    >
                      💬 Quick Clara Assistant
                    </button>
                  )}
                </section>

                {/* Stats Grid */}
                <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {stats.map((stat, idx) => (
                    <div key={idx} className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                      <div className="w-12 h-12 rounded-xl bg-slate-850 flex items-center justify-center text-2xl">
                        {stat.icon}
                      </div>
                      <div>
                        <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">{stat.title}</span>
                        <span className="text-lg font-black text-white block mt-0.5">{stat.value}</span>
                        <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">{stat.desc}</span>
                      </div>
                    </div>
                  ))}
                </section>

                {/* Today's Agenda list */}
                <section className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                  <h3 className="text-sm font-extrabold text-slate-400 uppercase tracking-wider">Today's Appointment Ledger</h3>
                  
                  {appointments.length === 0 ? (
                    <div className="text-center text-slate-500 py-8 text-xs">
                      No appointments booked for today.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {appointments.map(appt => (
                        <div key={appt.id} className="bg-slate-900/80 border border-slate-800/80 p-5 rounded-2xl space-y-3 relative">
                          <span className="absolute top-4 right-4 px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-[9px] font-bold border border-emerald-500/20 uppercase">
                            {appt.start_time}
                          </span>
                          <div className="space-y-1">
                            <h4 className="text-base font-extrabold text-white">{appt.customer_name}</h4>
                            <span className="text-xs text-blue-400 font-bold block">{appt.service_name}</span>
                          </div>
                          <p className="text-xs text-slate-400 leading-relaxed font-medium bg-slate-950 p-3 rounded-xl border border-slate-850">
                            <span className="text-[10px] text-slate-500 font-black block uppercase mb-1">Stylist Notes:</span>
                            {appt.notes}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}

            {/* 2. Agenda Book Tab */}
            {activeTab === 'appointments' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">📅 Assigned Agenda & Roster</h2>
                  <p className="text-xs text-slate-500">Supervise details, instructions, and customer files assigned directly to your chair.</p>
                </div>

                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl">
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-800 text-sm">
                      <thead>
                        <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                          <th className="px-4 py-3 text-left">Time Slot</th>
                          <th className="px-4 py-3 text-left">Client Name</th>
                          <th className="px-4 py-3 text-left">Requested Service</th>
                          <th className="px-4 py-3 text-left">Client Special Notes</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {appointments.map(appt => (
                          <tr key={appt.id} className="hover:bg-slate-850/30 transition-colors">
                            <td className="px-4 py-4 whitespace-nowrap text-blue-400 font-bold text-xs">{appt.start_time}</td>
                            <td className="px-4 py-4 whitespace-nowrap font-bold text-white">{appt.customer_name}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-350">{appt.service_name}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-400 italic text-xs">{appt.notes}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 3. Client History Tab */}
            {activeTab === 'customers' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3 space-y-2">
                  <h2 className="text-xl font-black">👥 Historical Customer Logs</h2>
                  <p className="text-xs text-slate-500">Examine details, historical styles, and formula preferences across your client base.</p>
                  
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    placeholder="Search customer name or email..."
                    className="max-w-md px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white focus:outline-none"
                  />
                </div>

                <div className="space-y-4">
                  {filteredCustomers.map(c => (
                    <div key={c.id} className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl space-y-3">
                      <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
                        <div>
                          <h4 className="font-extrabold text-white">{c.name}</h4>
                          <span className="text-slate-500">{c.email}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-blue-400 font-bold block">{c.last_service}</span>
                          <span className="text-[10px] text-slate-500 font-bold block">{c.last_date}</span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-350 leading-relaxed font-medium bg-slate-950 p-3 rounded-xl border border-slate-850">
                        <span className="text-[9px] text-slate-500 font-black block uppercase mb-1">Color/Styling Formula Preference:</span>
                        {c.notes}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 4. Calendar Tab */}
            {activeTab === 'schedule' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">🗓️ Stylist Weekly Planner</h2>
                  <p className="text-xs text-slate-500">Visual schedule planner and slot allocations.</p>
                </div>

                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl">
                  <div className="grid grid-cols-5 gap-4 text-center">
                    {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map((day, idx) => (
                      <div key={idx} className="bg-slate-950 p-4 rounded-xl border border-slate-850 space-y-3">
                        <span className="block text-[10px] font-black text-slate-400 uppercase tracking-widest">{day}</span>
                        <div className="space-y-1.5">
                          {idx === 0 || idx === 4 ? (
                            <span className="px-2 py-1 bg-emerald-500/10 text-emerald-400 rounded text-[9px] font-bold block border border-emerald-500/20">
                              2 Bookings
                            </span>
                          ) : (
                            <span className="px-2 py-1 bg-slate-900 text-slate-500 rounded text-[9px] font-bold block">
                              Off-duty / Empty
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 5. AI Co-Stylist Assistant Tab */}
            {activeTab === 'assistant' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">🤖 AI Co-Stylist Panel</h2>
                  <p className="text-xs text-slate-500">Authorized: Clara Receptionist & Upsell Agent. Upsell matches recommendations with your clients in real-time.</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                  {/* Clara Chat integration */}
                  <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-5 space-y-4">
                    <h3 className="text-sm font-extrabold text-white">📞 Clara Chat Receptionist</h3>
                    <AgentChat />
                  </div>

                  {/* Upsell Agent Matching Tool */}
                  <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6 space-y-6 text-left">
                    <div>
                      <h3 className="text-sm font-extrabold text-white">⚡ Upsell Recommendation Generator</h3>
                      <p className="text-xs text-slate-500">Select the service to query the Upsell Agent rules in real-time.</p>
                    </div>

                    <div className="space-y-4">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Select Client Service</label>
                        <div className="flex gap-2">
                          <select
                            value={selectedService}
                            onChange={e => setSelectedService(e.target.value)}
                            className="flex-1 px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none"
                          >
                            <option value="Signature Precision Haircut">Signature Precision Haircut</option>
                            <option value="Balayage & Creative Color">Balayage & Creative Color</option>
                            <option value="Himalayan Hot Stone Massage">Himalayan Hot Stone Massage</option>
                          </select>
                          <button
                            onClick={handleQueryUpsell}
                            className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 text-xs font-bold rounded-xl transition-all cursor-pointer uppercase tracking-wider"
                          >
                            Match
                          </button>
                        </div>
                      </div>

                      {upsellSuggestion && (
                        <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl font-medium text-xs leading-relaxed text-slate-200 whitespace-pre-wrap animate-fade-in">
                          {upsellSuggestion}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 6. Profile Tab */}
            {activeTab === 'profile' && (
              <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-3xl max-w-md mx-auto space-y-6">
                <h3 className="text-base font-extrabold text-white text-center">👤 Stylist Profile Card</h3>
                
                <div className="space-y-4">
                  <div className="flex justify-between border-b border-slate-800 pb-2 text-xs">
                    <span className="text-slate-500 font-bold">Stylist ID</span>
                    <span className="text-white font-mono text-[10px]">staff-6a3e2b64-004c</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800 pb-2 text-xs">
                    <span className="text-slate-500 font-bold">Email Address</span>
                    <span className="text-white font-extrabold">{user?.email}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800 pb-2 text-xs">
                    <span className="text-slate-500 font-bold">Privilege Tier</span>
                    <span className="text-emerald-400 font-black tracking-wider uppercase">{user?.role}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800 pb-2 text-xs">
                    <span className="text-slate-500 font-bold">Duty Assignment</span>
                    <span className="text-slate-200 font-bold">Downtown Elite Branch</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800 pb-2 text-xs">
                    <span className="text-slate-500 font-bold">Duty Status</span>
                    <span className="text-emerald-400 font-extrabold">Active Stylist</span>
                  </div>
                </div>
              </div>
            )}

          </div>
        )}
      </main>
    </div>
  );
};
