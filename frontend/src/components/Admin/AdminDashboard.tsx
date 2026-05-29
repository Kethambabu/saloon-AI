import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
import { AnalyticsDashboard } from '../analytics';
import { AgentChat } from '../AgentChat/AgentChat';

interface UserRecord {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  staff_id: string | null;
  customer_id: string | null;
}

interface AppointmentRecord {
  id: string;
  start_time: string;
  status: string;
  notes: string | null;
  service: { name: string; price: number };
  customer: { first_name: string; last_name: string; email: string } | null;
  staff: { first_name: string; last_name: string } | null;
}

interface StaffRecord {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  role: string;
  is_active: boolean;
}

interface LeadRecord {
  id: string;
  name: string;
  email: string;
  phone: string;
  source: string;
  status: string;
  last_contact: string;
}

interface ReviewRecord {
  id: string;
  customer_name: string;
  rating: number;
  comment: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  ai_response: string | null;
}

export const AdminDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  
  // Navigation State
  const [activeTab, setActiveTab] = useState<'dashboard' | 'analytics' | 'staff' | 'customers' | 'leads' | 'reports' | 'agents' | 'settings'>('dashboard');
  
  // Sub-tab state for AI Agents
  const [activeAgentTab, setActiveAgentTab] = useState<'receptionist' | 'bi' | 'reputation' | 'lead' | 'upsell'>('receptionist');
  // Sub-tab state for Settings
  const [activeSettingsTab, setActiveSettingsTab] = useState<'users' | 'services' | 'system'>('users');

  // Data States
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [staff, setStaff] = useState<StaffRecord[]>([]);
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  
  // Interactive Simulator States
  const [biQuery, setBiQuery] = useState<string>('');
  const [biAnswer, setBiAnswer] = useState<string>('');
  const [isBiLoading, setIsBiLoading] = useState<boolean>(false);
  const [upsellRule, setUpsellRule] = useState<string>('If client books Balayage, offer Hydrating Facial with 20% discount.');
  const [rules, setRules] = useState<string[]>([
    'If client books Balayage, offer Hydrating Facial with 20% discount.',
    'Send $10 birthday voucher to clients with over 3 completed bookings.'
  ]);
  const [newRuleInput, setNewRuleInput] = useState<string>('');

  // Service Management States
  const [services, setServices] = useState([
    { id: '1', name: 'Signature Precision Haircut', price: 85, duration: 60 },
    { id: '2', name: 'Balayage & Creative Color', price: 220, duration: 150 },
    { id: '3', name: 'Hydrating Deep Facial', price: 120, duration: 75 },
    { id: '4', name: 'Himalayan Hot Stone Massage', price: 150, duration: 90 }
  ]);
  const [editingServiceId, setEditingServiceId] = useState<string | null>(null);
  const [editPrice, setEditPrice] = useState<number>(0);

  useEffect(() => {
    const fetchAllData = async () => {
      try {
        setIsLoading(true);
        // Attempt dynamic load or fallback
        const [usersRes, apptsRes] = await Promise.all([
          apiClient.get<UserRecord[]>('/auth/users').catch(() => ({ data: [] })),
          apiClient.get<AppointmentRecord[]>('/appointments/my').catch(() => ({ data: [] }))
        ]);

        setUsers(usersRes.data.length ? usersRes.data : [
          { id: '8c3f1d64-1', email: 'owner@salonai.com', role: 'Admin', is_active: true, staff_id: null, customer_id: null },
          { id: '8c3f1d64-2', email: 'marcus@salonai.com', role: 'Staff', is_active: true, staff_id: '1', customer_id: null },
          { id: '8c3f1d64-3', email: 'customer@example.com', role: 'User', is_active: true, staff_id: null, customer_id: '1' }
        ]);

        setAppointments([
          { id: 'appt-1', start_time: new Date(Date.now() + 3600000).toISOString(), status: 'CONFIRMED', notes: 'Wants quiet experience', service: { name: 'Signature Precision Haircut', price: 85 }, customer: { first_name: 'Sarah', last_name: 'Jenkins', email: 'sarah.j@example.com' }, staff: { first_name: 'Marcus', last_name: 'Johnson' } },
          { id: 'appt-2', start_time: new Date(Date.now() + 7200000).toISOString(), status: 'CONFIRMED', notes: 'First time client', service: { name: 'Balayage & Creative Color', price: 220 }, customer: { first_name: 'Emily', last_name: 'Davis', email: 'emily.d@example.com' }, staff: { first_name: 'Marcus', last_name: 'Johnson' } }
        ]);

        setStaff([
          { id: 'staff-1', first_name: 'Marcus', last_name: 'Johnson', email: 'marcus@salonai.com', phone: '+1 (555) 0122', role: 'Senior Stylist', is_active: true },
          { id: 'staff-2', first_name: 'Alexandra', last_name: 'Chen', email: 'alexandra@salonai.com', phone: '+1 (555) 0133', role: 'Color Expert', is_active: true }
        ]);

        setLeads([
          { id: 'lead-1', name: 'Brittany Meyers', email: 'britt.m@example.com', phone: '+1 (555) 0244', source: 'Facebook Ad', status: 'Follow-up Sent', last_contact: '2026-05-29' },
          { id: 'lead-2', name: 'Jonathan Ross', email: 'jross@example.com', phone: '+1 (555) 0255', source: 'Google Search', status: 'Pending Clara Agent', last_contact: '2026-05-28' }
        ]);

        setReviews([
          { id: 'rev-1', customer_name: 'Sarah Jenkins', rating: 5, comment: 'Clara booked me instantly with Marcus. The Signature Precision Haircut was spectacular!', status: 'APPROVED', sentiment: 'POSITIVE', ai_response: 'Thank you Sarah! We are thrilled Marcus delivered a spectacular style for you. Look forward to seeing you again!' },
          { id: 'rev-2', customer_name: 'Michael Miller', rating: 2, comment: 'The haircut was fine but my appointment started 15 minutes late.', status: 'PENDING', sentiment: 'NEGATIVE', ai_response: null }
        ]);

      } catch (err) {
        console.warn('Failed to load operations dashboard databases', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchAllData();
  }, []);

  const handleToggleActive = (userId: string) => {
    setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: !u.is_active } : u));
  };

  const handleCancelAppointment = (id: string) => {
    if (window.confirm('Cancel this active client appointment?')) {
      setAppointments(prev => prev.map(a => a.id === id ? { ...a, status: 'CANCELLED' } : a));
    }
  };

  const handleTriggerBIQuery = () => {
    if (!biQuery.trim()) return;
    setIsBiLoading(true);
    setBiAnswer('');
    setTimeout(() => {
      setIsBiLoading(false);
      const queryLower = biQuery.toLowerCase();
      if (queryLower.includes('revenue') || queryLower.includes('sales')) {
        setBiAnswer("📊 Atlas BI Agent Analysis:\nTotal Revenue for May 2026 reached $24,850 (an increase of 14% month-over-month). 'Balayage & Color' represented 54% of sales volume, while Downtown Elite was our most active branch, yielding $12,400 in total sales.");
      } else if (queryLower.includes('performance') || queryLower.includes('stylist')) {
        setBiAnswer("📈 Atlas BI Agent Analysis:\nSenior Stylist Marcus Johnson is leading platform throughput with a 99% satisfaction rate across 45 appointments, earning $3,825. Alexandra Chen has successfully converted 12 upsell recommendations, boosting color session tickets by $480.");
      } else {
        setBiAnswer("💡 Atlas BI Agent Analysis:\nQuery successfully executed across active database tables. Found 3 correlating clusters: booking frequency is highest on Fridays between 2:00 PM and 6:00 PM; automated Clara conversations successfully resolved 88% of scheduler pipelines without stylist intervention.");
      }
    }, 1500);
  };

  const handleModerateReview = (reviewId: string, action: 'APPROVED' | 'REJECTED') => {
    setReviews(prev => prev.map(r => r.id === reviewId ? { ...r, status: action } : r));
  };

  const handleGenerateReviewResponse = (reviewId: string) => {
    setReviews(prev => prev.map(r => {
      if (r.id === reviewId) {
        return {
          ...r,
          ai_response: `Hi ${r.customer_name}, we appreciate your honest feedback. We sincerely apologize for the delay. We are aligning with our staff to ensure timely sessions. Thank you!`
        };
      }
      return r;
    }));
  };

  const handleAddRule = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRuleInput.trim()) return;
    setRules(prev => [...prev, newRuleInput]);
    setNewRuleInput('');
  };

  const handleSavePrice = (id: string) => {
    setServices(prev => prev.map(s => s.id === id ? { ...s, price: editPrice } : s));
    setEditingServiceId(null);
  };

  // Quick stats computed helper
  const stats = [
    { title: 'Global Revenue', value: '$24,850.00', desc: 'Month to Date (+14%)', icon: '💰' },
    { title: 'Stylist Roster', value: `${staff.length} Active`, desc: 'Across 3 Branches', icon: '💇' },
    { title: 'Happy Guests', value: '184 Clients', desc: 'Average rating 4.8★', icon: '👤' },
    { title: 'AI Automation', value: '100% Online', desc: 'AutoGen Core active', icon: '🤖' }
  ];

  return (
    <div className="flex flex-col md:flex-row min-h-[85vh] bg-slate-950 text-white rounded-3xl overflow-hidden border border-slate-800/80 shadow-2xl font-sans">
      
      {/* Sidebar Navigation */}
      <aside className="w-full md:w-64 bg-slate-900 border-r border-slate-800/80 p-6 flex flex-col justify-between">
        <div className="space-y-6">
          <div className="text-left border-b border-slate-800 pb-4">
            <h2 className="text-xl font-black bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              SalonAI Control
            </h2>
            <span className="inline-flex items-center px-2 py-0.5 mt-1 rounded text-[9px] font-black bg-purple-500/10 text-purple-400 border border-purple-500/20 uppercase tracking-widest">
              Root Administrator
            </span>
          </div>

          <nav className="flex flex-col gap-2">
            {[
              { id: 'dashboard', label: 'Dashboard', icon: '🏠' },
              { id: 'analytics', label: 'Analytics', icon: '📈' },
              { id: 'staff', label: 'Staff Roster', icon: '💇' },
              { id: 'customers', label: 'Customers', icon: '👥' },
              { id: 'leads', label: 'Lead Management', icon: '🎯' },
              { id: 'reports', label: 'Reports & Logs', icon: '📜' },
              { id: 'agents', label: 'AI Agent Grid', icon: '🤖' },
              { id: 'settings', label: 'Settings Panel', icon: '⚙️' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl text-xs font-bold text-left transition-all cursor-pointer ${
                  activeTab === tab.id
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
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
            <span className="block text-[9px] font-black text-slate-500 uppercase tracking-widest">Global Admin</span>
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

      {/* Main Operations Container */}
      <main className="flex-1 p-6 md:p-8 text-left overflow-y-auto max-h-[85vh]">
        {isLoading ? (
          <div className="py-24 text-center text-slate-500 font-bold animate-pulse">
            Establishing Secure Admin Session...
          </div>
        ) : (
          <div className="animate-fade-in space-y-6">
            
            {/* 1. Dashboard Tab */}
            {activeTab === 'dashboard' && (
              <div className="space-y-6">
                
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

                {/* Appointment monitoring table */}
                <section className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-black text-white">📅 Active Appointment Monitoring</h3>
                      <p className="text-xs text-slate-500">Live operational log of all bookings across platform branches.</p>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-800 text-sm">
                      <thead>
                        <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                          <th className="px-4 py-3 text-left">Time / Date</th>
                          <th className="px-4 py-3 text-left">Client Name</th>
                          <th className="px-4 py-3 text-left">Stylist</th>
                          <th className="px-4 py-3 text-left">Service Requested</th>
                          <th className="px-4 py-3 text-center">Status</th>
                          <th className="px-4 py-3 text-center">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {appointments.map((appt) => (
                          <tr key={appt.id} className="hover:bg-slate-850/30 transition-colors">
                            <td className="px-4 py-4 whitespace-nowrap text-blue-400 font-bold text-xs">
                              {new Date(appt.start_time).toLocaleString()}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap font-semibold text-white">
                              {appt.customer ? `${appt.customer.first_name} ${appt.customer.last_name}` : 'Unknown'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-350">
                              {appt.staff ? `${appt.staff.first_name} ${appt.staff.last_name}` : 'Auto Assigned'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-400 font-medium">
                              {appt.service.name}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[9px] font-bold ${
                                appt.status === 'CONFIRMED' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                              }`}>
                                {appt.status}
                              </span>
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              {appt.status === 'CONFIRMED' && (
                                <button
                                  onClick={() => handleCancelAppointment(appt.id)}
                                  className="px-2.5 py-1 bg-red-950/40 hover:bg-red-900/40 border border-red-900/40 text-red-400 rounded-lg text-xs transition-all cursor-pointer"
                                >
                                  Cancel Booking
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            )}

            {/* 2. Analytics Tab */}
            {activeTab === 'analytics' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">📈 Enterprise Analytics Engine</h2>
                  <p className="text-xs text-slate-500">Live graphical tracking of revenue, performance, and retention index.</p>
                </div>
                {/* Renders the full pre-built AnalyticsDashboard component */}
                <AnalyticsDashboard />
              </div>
            )}

            {/* 3. Staff Roster Tab */}
            {activeTab === 'staff' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
                  <div>
                    <h2 className="text-xl font-black">💇 Staff Operations Hub</h2>
                    <p className="text-xs text-slate-500">Review commission metrics, styling capacity, and stylist profiles.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {staff.map(s => (
                    <div key={s.id} className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl flex flex-col justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <h4 className="text-base font-extrabold text-white">{s.first_name} {s.last_name}</h4>
                          <span className="px-2 py-0.5 text-[9px] font-bold bg-blue-900/40 text-blue-300 border border-blue-800/40 rounded">
                            {s.role}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 space-y-1">
                          <p>📧 Email: {s.email}</p>
                          <p>📞 Phone: {s.phone || 'No phone'}</p>
                        </div>
                      </div>
                      <div className="mt-4 pt-4 border-t border-slate-800/60 flex items-center justify-between text-xs">
                        <span className="text-slate-500">Weekly Target: 40 hrs</span>
                        <span className="text-emerald-400 font-bold">Uptime 99%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 4. Customers Tab */}
            {activeTab === 'customers' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">👤 Customer Insights</h2>
                  <p className="text-xs text-slate-500">Inspect client catalog, historical booking metrics, and preferences.</p>
                </div>

                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl">
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-800 text-sm">
                      <thead>
                        <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                          <th className="px-4 py-3 text-left">Customer Name</th>
                          <th className="px-4 py-3 text-left">Email</th>
                          <th className="px-4 py-3 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        <tr className="hover:bg-slate-850/30 transition-colors">
                          <td className="px-4 py-4 whitespace-nowrap font-semibold text-white">Sarah Jenkins</td>
                          <td className="px-4 py-4 whitespace-nowrap text-slate-400">sarah.j@example.com</td>
                          <td className="px-4 py-4 whitespace-nowrap text-center">
                            <span className="px-2 py-0.5 rounded-full text-[9px] bg-emerald-500/10 text-emerald-400 font-bold">Active</span>
                          </td>
                        </tr>
                        <tr className="hover:bg-slate-850/30 transition-colors">
                          <td className="px-4 py-4 whitespace-nowrap font-semibold text-white">Michael Miller</td>
                          <td className="px-4 py-4 whitespace-nowrap text-slate-400">m.miller@example.com</td>
                          <td className="px-4 py-4 whitespace-nowrap text-center">
                            <span className="px-2 py-0.5 rounded-full text-[9px] bg-emerald-500/10 text-emerald-400 font-bold">Active</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 5. Leads Tab */}
            {activeTab === 'leads' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">🎯 Lead Follow-up campaigns</h2>
                  <p className="text-xs text-slate-500">Autonomous campaign supervisor for customer acquisition funnel.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 text-center">
                    <span className="text-2xl block">📈</span>
                    <span className="block text-xs font-black text-slate-400 uppercase mt-2">Conversion Rate</span>
                    <span className="text-xl font-black block mt-1">32.4%</span>
                  </div>
                  <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 text-center">
                    <span className="text-2xl block">💬</span>
                    <span className="block text-xs font-black text-slate-400 uppercase mt-2">Active Chats</span>
                    <span className="text-xl font-black block mt-1">12 Funnels</span>
                  </div>
                  <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 text-center">
                    <span className="text-2xl block">⚡</span>
                    <span className="block text-xs font-black text-slate-400 uppercase mt-2">Leads Captured</span>
                    <span className="text-xl font-black block mt-1">45 Leads</span>
                  </div>
                </div>

                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                  <h3 className="text-sm font-extrabold text-white">Lead Catalog</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-800 text-sm">
                      <thead>
                        <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                          <th className="px-4 py-3 text-left">Lead Name</th>
                          <th className="px-4 py-3 text-left">Source Campaign</th>
                          <th className="px-4 py-3 text-center">Funnel State</th>
                          <th className="px-4 py-3 text-right">Captured</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {leads.map(lead => (
                          <tr key={lead.id} className="hover:bg-slate-850/30 transition-colors">
                            <td className="px-4 py-4 whitespace-nowrap font-bold text-white">{lead.name}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-400">{lead.source}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              <span className="px-2.5 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-bold uppercase">
                                {lead.status}
                              </span>
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-right text-slate-500 text-xs">{lead.last_contact}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 6. Reports Tab */}
            {activeTab === 'reports' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">📜 Reports & Operational Logs</h2>
                  <p className="text-xs text-slate-500">Platform telemetry logs, session tokens, and business audits.</p>
                </div>

                <div className="bg-slate-900/60 p-5 rounded-3xl border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <h3 className="text-sm font-extrabold text-white">System Logs</h3>
                    <span className="px-2 py-0.5 text-[9px] font-bold bg-emerald-500/10 text-emerald-400 rounded">HEALTHY</span>
                  </div>
                  <div className="font-mono text-xs text-slate-400 space-y-2 max-h-60 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-850">
                    <p className="text-slate-500">[2026-05-29 23:30:12] INFO: Supabase connection pooling initialized successfully.</p>
                    <p className="text-blue-400">[2026-05-29 23:30:14] DEBUG: Lazy loading AutoGen ReceptionistAgent singleton...</p>
                    <p className="text-slate-500">[2026-05-29 23:30:16] INFO: ReceptionistAgent bound tools: 9 verified tools registered.</p>
                    <p className="text-emerald-400">[2026-05-29 23:31:01] SUCCESS: Token issued for owner@salonai.com [Admin role].</p>
                    <p className="text-slate-500">[2026-05-29 23:32:05] INFO: SQLite dialect detected. Falling back to strftime logic safely.</p>
                  </div>
                </div>
              </div>
            )}

            {/* 7. AI Agent Grid Tab */}
            {activeTab === 'agents' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">🤖 AI Agent Operations Panel</h2>
                  <p className="text-xs text-slate-500">Configure, monitor, and query specialized agents in the active SalonAI network.</p>
                </div>

                {/* Sub navigation for agents */}
                <div className="flex flex-wrap gap-2 border-b border-slate-900 pb-3">
                  {[
                    { id: 'receptionist', label: 'Clara Receptionist', icon: '📞' },
                    { id: 'bi', label: 'Atlas BI Analytics', icon: '📊' },
                    { id: 'reputation', label: 'Reputation Shield', icon: '🛡️' },
                    { id: 'lead', label: 'Lead Follow-up', icon: '🎯' },
                    { id: 'upsell', label: 'Upsell Engine', icon: '⚡' }
                  ].map(agent => (
                    <button
                      key={agent.id}
                      onClick={() => setActiveAgentTab(agent.id as any)}
                      className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer border ${
                        activeAgentTab === agent.id
                          ? 'bg-blue-600 border-blue-500 text-white shadow-md'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      <span>{agent.icon}</span>
                      <span>{agent.label}</span>
                    </button>
                  ))}
                </div>

                {/* Agent Detail Views */}
                {activeAgentTab === 'receptionist' && (
                  <div className="space-y-4">
                    <div className="bg-slate-900/60 p-5 border border-slate-800 rounded-3xl space-y-4">
                      <div>
                        <h4 className="text-base font-extrabold text-white">📞 Clara Receptionist Console</h4>
                        <p className="text-xs text-slate-500">Runs Microsoft AutoGen on our database schema. Allowed roles: Admin, Staff, User.</p>
                      </div>
                      <AgentChat />
                    </div>
                  </div>
                )}

                {activeAgentTab === 'bi' && (
                  <div className="bg-slate-900/60 p-6 border border-slate-800 rounded-3xl space-y-6">
                    <div>
                      <h4 className="text-base font-extrabold text-white">📊 Atlas Business Intelligence Agent</h4>
                      <p className="text-xs text-slate-500">Authorized: Admin Only. Atlas executes dialect-aware SQL analyses across transaction databases.</p>
                    </div>

                    <div className="space-y-4 max-w-xl">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Ask Atlas BI Agent</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={biQuery}
                            onChange={e => setBiQuery(e.target.value)}
                            placeholder="e.g. 'Show me revenue performance for Marcus Johnson'..."
                            className="flex-1 px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <button
                            onClick={handleTriggerBIQuery}
                            disabled={isBiLoading}
                            className="px-5 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-xs font-bold rounded-xl transition-all cursor-pointer uppercase tracking-wider"
                          >
                            {isBiLoading ? 'Synthesizing...' : 'Query'}
                          </button>
                        </div>
                      </div>

                      {biAnswer && (
                        <div className="bg-slate-950 p-4 border border-slate-850 rounded-xl font-medium text-xs leading-relaxed text-slate-200 whitespace-pre-wrap animate-fade-in text-left">
                          {biAnswer}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {activeAgentTab === 'reputation' && (
                  <div className="bg-slate-900/60 p-6 border border-slate-800 rounded-3xl space-y-6">
                    <div>
                      <h4 className="text-base font-extrabold text-white">🛡️ Reputation Shield Agent</h4>
                      <p className="text-xs text-slate-500">Authorized: Admin Only. Monitors scores, performs sentiment screening, and generates replies.</p>
                    </div>

                    {/* NPS Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      <div className="bg-slate-950 p-4 rounded-xl border border-slate-850 text-center">
                        <span className="block text-[10px] font-black text-slate-400 uppercase">Average Rating</span>
                        <span className="text-2xl font-black block mt-1 text-amber-450">4.8 ★</span>
                      </div>
                      <div className="bg-slate-950 p-4 rounded-xl border border-slate-850 text-center">
                        <span className="block text-[10px] font-black text-slate-400 uppercase">NPS Score</span>
                        <span className="text-2xl font-black block mt-1 text-blue-450">92</span>
                      </div>
                      <div className="bg-slate-950 p-4 rounded-xl border border-slate-850 text-center">
                        <span className="block text-[10px] font-black text-slate-400 uppercase">Positive Reviews</span>
                        <span className="text-2xl font-black block mt-1 text-emerald-450">96.2%</span>
                      </div>
                      <div className="bg-slate-950 p-4 rounded-xl border border-slate-850 text-center">
                        <span className="block text-[10px] font-black text-slate-400 uppercase">Awaiting Moderation</span>
                        <span className="text-2xl font-black block mt-1 text-amber-500">1 Review</span>
                      </div>
                    </div>

                    {/* Reviews list */}
                    <div className="space-y-4">
                      <h5 className="text-sm font-extrabold text-white">Client Reviews Ledger</h5>
                      
                      <div className="space-y-4">
                        {reviews.map(rev => (
                          <div key={rev.id} className="bg-slate-950 border border-slate-850 p-5 rounded-2xl space-y-3">
                            <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
                              <div className="flex items-center gap-2">
                                <span className="font-extrabold text-white">{rev.customer_name}</span>
                                <span className="text-amber-450 font-bold">{'★'.repeat(rev.rating)}</span>
                              </div>
                              <div className="flex gap-2">
                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                                  rev.sentiment === 'POSITIVE' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                                }`}>
                                  {rev.sentiment}
                                </span>
                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                                  rev.status === 'APPROVED' ? 'bg-blue-500/10 text-blue-450' : 'bg-yellow-500/10 text-yellow-450'
                                }`}>
                                  {rev.status}
                                </span>
                              </div>
                            </div>

                            <p className="text-xs text-slate-350 italic font-medium leading-relaxed">"{rev.comment}"</p>

                            {rev.ai_response ? (
                              <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800 text-xs text-slate-400 mt-2 font-medium">
                                <span className="text-indigo-400 font-extrabold block mb-0.5">Reputation Agent Response:</span>
                                {rev.ai_response}
                              </div>
                            ) : (
                              <div className="flex gap-2 pt-2">
                                <button
                                  onClick={() => handleGenerateReviewResponse(rev.id)}
                                  className="px-3 py-1.5 bg-indigo-950/40 hover:bg-indigo-900/40 border border-indigo-800/40 text-indigo-400 rounded-lg text-[10px] font-bold uppercase transition-all cursor-pointer"
                                >
                                  Generate AI Response
                                </button>
                                <button
                                  onClick={() => handleModerateReview(rev.id, 'APPROVED')}
                                  className="px-3 py-1.5 bg-emerald-950/40 hover:bg-emerald-900/40 border border-emerald-800/40 text-emerald-400 rounded-lg text-[10px] font-bold uppercase transition-all cursor-pointer"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => handleModerateReview(rev.id, 'REJECTED')}
                                  className="px-3 py-1.5 bg-red-950/40 hover:bg-red-900/40 border border-red-800/40 text-red-450 rounded-lg text-[10px] font-bold uppercase transition-all cursor-pointer"
                                >
                                  Reject
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {activeAgentTab === 'lead' && (
                  <div className="bg-slate-900/60 p-6 border border-slate-800 rounded-3xl space-y-6">
                    <div>
                      <h4 className="text-base font-extrabold text-white">🎯 Lead Follow-up Agent Console</h4>
                      <p className="text-xs text-slate-500">Authorized: Admin Only. Integrates email, SMS, and WhatsApp triggers to convert lost funnels.</p>
                    </div>

                    <div className="bg-slate-950 border border-slate-850 p-5 rounded-2xl space-y-4 font-mono text-xs">
                      <div className="flex justify-between text-slate-500 border-b border-slate-850 pb-2">
                        <span>Campaign State</span>
                        <span className="text-emerald-400 font-bold uppercase">Automated Trigger Online</span>
                      </div>
                      <div className="space-y-2 text-left">
                        <p className="text-slate-400">⚡ [Lead Captured] Brittany Meyers (Facebook Ad) captured. Triggering funnel...</p>
                        <p className="text-indigo-400">💬 [SMS Sent] "Hi Brittany! Clara noticed you were interested in Balayage. We have a 10% coupon for slots tomorrow. Reply book to reserve!"</p>
                        <p className="text-emerald-400">🎉 [Success] Brittany Meyers converted! Booking registered at Downtown Elite.</p>
                      </div>
                    </div>
                  </div>
                )}

                {activeAgentTab === 'upsell' && (
                  <div className="bg-slate-900/60 p-6 border border-slate-800 rounded-3xl space-y-6">
                    <div>
                      <h4 className="text-base font-extrabold text-white">⚡ Upsell Agent Engine Configuration</h4>
                      <p className="text-xs text-slate-500">Authorized: Admin & Staff. Generates matching recommendations based on styling selections.</p>
                    </div>

                    <form onSubmit={handleAddRule} className="space-y-4 max-w-xl">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">New Recommendation Rule</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={newRuleInput}
                            onChange={e => setNewRuleInput(e.target.value)}
                            placeholder="e.g. 'If user books Facial, recommend Deep Hydration mask for $15'..."
                            className="flex-1 px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <button
                            type="submit"
                            className="px-5 py-3 bg-blue-600 hover:bg-blue-500 text-xs font-bold rounded-xl transition-all cursor-pointer uppercase tracking-wider"
                          >
                            Add Rule
                          </button>
                        </div>
                      </div>
                    </form>

                    <div className="space-y-3">
                      <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Active Recommendation Rules</h5>
                      {rules.map((rule, idx) => (
                        <div key={idx} className="bg-slate-950 p-4 border border-slate-850 rounded-xl flex items-center justify-between gap-4">
                          <span className="text-xs text-slate-200 leading-relaxed font-semibold">{rule}</span>
                          <span className="px-2 py-0.5 rounded text-[8px] font-black bg-blue-500/10 text-blue-450 border border-blue-500/20 uppercase">Rule Enabled</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 8. Settings Panel Tab */}
            {activeTab === 'settings' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">⚙️ Security & System Configurations</h2>
                  <p className="text-xs text-slate-500">Edit active services catalog, credential privileges, and platform settings.</p>
                </div>

                {/* Settings Sub-nav */}
                <div className="flex gap-2 border-b border-slate-900 pb-3">
                  <button
                    onClick={() => setActiveSettingsTab('users')}
                    className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer border ${
                      activeSettingsTab === 'users'
                        ? 'bg-blue-600 border-blue-500 text-white shadow-md'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    👥 User Roster
                  </button>
                  <button
                    onClick={() => setActiveSettingsTab('services')}
                    className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer border ${
                      activeSettingsTab === 'services'
                        ? 'bg-blue-600 border-blue-500 text-white shadow-md'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    💇 Catalog editor
                  </button>
                </div>

                {/* Sub tab contents */}
                {activeSettingsTab === 'users' && (
                  <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                    <h3 className="text-sm font-extrabold text-white">Supervised Accounts</h3>
                    
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-800 text-sm">
                        <thead>
                          <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                            <th className="px-4 py-3 text-left">Email Address</th>
                            <th className="px-4 py-3 text-left">Security Role</th>
                            <th className="px-4 py-3 text-center">Status</th>
                            <th className="px-4 py-3 text-center">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60">
                          {users.map(u => (
                            <tr key={u.id} className="hover:bg-slate-850/30 transition-colors">
                              <td className="px-4 py-4 whitespace-nowrap font-bold text-white">{u.email}</td>
                              <td className="px-4 py-4 whitespace-nowrap">
                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${
                                  u.role === 'Admin'
                                    ? 'bg-purple-900/30 text-purple-300 border-purple-800/40'
                                    : u.role === 'Staff'
                                    ? 'bg-emerald-900/30 text-emerald-300 border-emerald-800/40'
                                    : 'bg-blue-900/30 text-blue-300 border-blue-800/40'
                                }`}>
                                  {u.role}
                                </span>
                              </td>
                              <td className="px-4 py-4 whitespace-nowrap text-center">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-[9px] font-bold ${
                                  u.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                                }`}>
                                  <span className={`w-1 h-1 rounded-full mr-1 ${u.is_active ? 'bg-emerald-400' : 'bg-red-400'}`} />
                                  {u.is_active ? 'Active' : 'Suspended'}
                                </span>
                              </td>
                              <td className="px-4 py-4 whitespace-nowrap text-center">
                                <button
                                  onClick={() => handleToggleActive(u.id)}
                                  className={`px-2.5 py-1 rounded text-xs font-bold border transition-all cursor-pointer ${
                                    u.is_active
                                      ? 'bg-red-950/30 border-red-900/30 text-red-400 hover:bg-red-900/30'
                                      : 'bg-emerald-950/30 border-emerald-900/30 text-emerald-400 hover:bg-emerald-900/30'
                                  }`}
                                >
                                  {u.is_active ? 'Suspend' : 'Activate'}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {activeSettingsTab === 'services' && (
                  <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                    <h3 className="text-sm font-extrabold text-white">High-Value Catalog Editor</h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {services.map(s => (
                        <div key={s.id} className="bg-slate-950 p-4 border border-slate-850 rounded-2xl flex items-center justify-between">
                          <div>
                            <h4 className="text-xs font-black text-white">{s.name}</h4>
                            <span className="text-[10px] text-slate-500 font-bold block mt-1">⏱️ {s.duration} min</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {editingServiceId === s.id ? (
                              <div className="flex gap-2 items-center">
                                <input
                                  type="number"
                                  value={editPrice}
                                  onChange={e => setEditPrice(Number(e.target.value))}
                                  className="w-16 px-2 py-1 bg-slate-900 border border-slate-800 rounded text-xs text-white"
                                />
                                <button
                                  onClick={() => handleSavePrice(s.id)}
                                  className="px-2 py-1 bg-emerald-600 text-white rounded text-xs cursor-pointer"
                                >
                                  💾
                                </button>
                              </div>
                            ) : (
                              <div className="flex items-center gap-3">
                                <span className="text-xs font-black text-blue-400">${s.price}</span>
                                <button
                                  onClick={() => {
                                    setEditingServiceId(s.id);
                                    setEditPrice(s.price);
                                  }}
                                  className="p-1 bg-slate-900 hover:bg-slate-850 rounded text-xs cursor-pointer border border-slate-800"
                                >
                                  ✏️
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </div>
            )}

          </div>
        )}
      </main>
    </div>
  );
};
