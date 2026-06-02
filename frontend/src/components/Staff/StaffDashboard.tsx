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
  const [activeTab, setActiveTab] = useState<'dashboard' | 'appointments' | 'customers' | 'schedule' | 'assistant' | 'profile' | 'leads' | 'upsells' | 'reviews'>('dashboard');
  
  // Roster lists
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [customers, setCustomers] = useState<CustomerHistoryItem[]>([]);
  const [leads, setLeads] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Upsell Agent helper
  const [upsellSuggestion, setUpsellSuggestion] = useState<string>('');
  const [selectedService, setSelectedService] = useState<string>('Signature Precision Haircut');

  // Live Upsell Agent states
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');
  const [staffRecommendations, setStaffRecommendations] = useState<any[]>([]);
  const [isStaffRecsLoading, setIsStaffRecsLoading] = useState<boolean>(false);

  // Reviews state variables
  const [staffReviews, setStaffReviews] = useState<any[]>([]);
  const [isStaffReviewsLoading, setIsStaffReviewsLoading] = useState<boolean>(false);

  useEffect(() => {
    const loadStaffData = async () => {
      try {
        setIsLoading(true);
        // Simulate loading database data
        setAppointments([
          { id: 'appt-s1', start_time: '10:00 AM - 11:00 AM', end_time: '11:00 AM', customer_name: 'Alice Smith', service_name: 'Signature Precision Haircut', notes: 'Requests layering, prefers organic hair products' },
          { id: 'appt-s2', start_time: '01:30 PM - 03:00 PM', end_time: '03:00 PM', customer_name: 'David Jones', service_name: 'Balayage & Creative Color', notes: 'First session, wants subtle cool blonde highlights' }
        ]);

        const custRes = await apiClient.get<any[]>('/customers').catch(() => ({ data: [] }));
        if (custRes.data && custRes.data.length > 0) {
          setCustomers(custRes.data.map((c: any) => ({
            id: c.id,
            name: `${c.first_name} ${c.last_name}`,
            email: c.email,
            last_service: c.phone || 'No Phone',
            last_date: 'Active',
            notes: c.is_active ? 'Active Profile' : 'Inactive Profile'
          })));
        } else {
          setCustomers([
            { id: 'c-1', name: 'Alice Smith', email: 'alice.s@example.com', last_service: 'Signature Precision Haircut', last_date: '2026-05-10', notes: 'Always prefers Alexandra or Marcus. Prefers quiet session.' },
            { id: 'c-2', name: 'David Jones', email: 'david.j@example.com', last_service: 'Beard Trim & Clean Shave', last_date: '2026-04-18', notes: 'Wants strong moisturizers post-shave.' },
            { id: 'c-3', name: 'Emily Davis', email: 'emily.d@example.com', last_service: 'Balayage & Creative Color', last_date: '2026-05-02', notes: 'Sensitive scalp, color should stay off root line.' }
          ]);
        }

        const leadsRes = await apiClient.get<any[]>('/staff/leads').catch(() => ({ data: [] }));
        setLeads(leadsRes.data.length ? leadsRes.data : [
          { id: 'lead-s1', customer_name: 'Balu', customer_email: 'balu@example.com', customer_phone: '+919999999999', service_name: 'Hair Spa', status: 'NEW', lead_score: 80, last_contacted: null, created_at: new Date().toISOString() },
          { id: 'lead-s2', customer_name: 'Vamsi Krishna', customer_email: 'vamsi@example.com', customer_phone: '+918888888888', service_name: 'Balayage & Creative Color', status: 'CONTACTED', lead_score: 60, last_contacted: new Date().toISOString(), created_at: new Date().toISOString() }
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

  const fetchStaffRecommendations = async (customerId: string) => {
    if (!customerId) return;
    try {
      setIsStaffRecsLoading(true);
      const res = await apiClient.get(`/recommendations/${customerId}`);
      if (res.data && res.data.success) {
        setStaffRecommendations(res.data.recommendations);
      }
    } catch (err) {
      console.error('Failed to load customer recommendations:', err);
      setStaffRecommendations([]);
    } finally {
      setIsStaffRecsLoading(false);
    }
  };

  const handlePresentUpsell = async (rec: any) => {
    if (!selectedCustomerId) return;
    try {
      const res = await apiClient.post('/recommendations/accept', {
        customer_id: selectedCustomerId,
        service_id: rec.service_id,
        appointment_id: rec.appointment_id || null
      });
      if (res.data && res.data.success) {
        window.alert(`🎉 Success! Accepted ${rec.name} for this customer booking!`);
        fetchStaffRecommendations(selectedCustomerId);
      }
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to accept recommendation.');
    }
  };

  const fetchStaffReviews = async () => {
    try {
      setIsStaffReviewsLoading(true);
      const res = await apiClient.get('/reviews');
      if (res.data && res.data.success) {
        setStaffReviews(res.data.reviews);
      }
    } catch (err) {
      console.error('Failed to fetch staff reviews:', err);
    } finally {
      setIsStaffReviewsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'reviews') {
      fetchStaffReviews();
    }
  }, [activeTab]);

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

  const handleCallCustomer = (name: string, phone: string) => {
    window.alert(`📞 Calling ${name} at ${phone}...`);
  };

  const handleSendWhatsApp = (name: string, phone: string, service: string) => {
    const text = encodeURIComponent(`Hi ${name}, we noticed you were interested in our ${service} at SalonAI. Appointments are still available tomorrow! Would you like to lock in your slot?`);
    window.open(`https://wa.me/${phone.replace(/[^0-9]/g, '')}?text=${text}`, '_blank');
  };

  const handleMarkContacted = async (leadId: string) => {
    try {
      await apiClient.post('/leads/followup', { lead_id: leadId });
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: 'CONTACTED', followup_count: (l.followup_count || 0) + 1, last_contacted: new Date().toISOString() } : l));
      window.alert("✉️ Follow-up message sent! Lead status updated to CONTACTED.");
    } catch (err) {
      console.error(err);
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: 'CONTACTED', last_contacted: new Date().toISOString() } : l));
      window.alert("✉️ Follow-up message sent (local update)!");
    }
  };

  const handleConvertToAppointment = async (leadId: string) => {
    try {
      await apiClient.post('/leads/convert', { lead_id: leadId });
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: 'CONVERTED', converted: true, converted_at: new Date().toISOString() } : l));
      window.alert("🎉 Lead successfully converted to confirmed appointment!");
    } catch (err) {
      console.error(err);
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: 'CONVERTED' } : l));
      window.alert("🎉 Lead successfully converted to confirmed appointment (local update)!");
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
              { id: 'leads', label: 'My Leads', icon: '🎯' },
              { id: 'upsells', label: 'Upsell Opportunities', icon: '⚡' },
              { id: 'reviews', label: 'My Reviews', icon: '⭐' },
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

            {/* My Leads Tab */}
            {activeTab === 'leads' && (
              <div className="space-y-6 animate-fade-in">
                <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
                  <div>
                    <h2 className="text-xl font-black">🎯 My Assigned Leads</h2>
                    <p className="text-xs text-slate-500">Contact, follow-up, and convert potential customers into bookings.</p>
                  </div>
                </div>

                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-800 text-sm">
                      <thead>
                        <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                          <th className="px-4 py-3 text-left">Customer Name</th>
                          <th className="px-4 py-3 text-left">Interested Service</th>
                          <th className="px-4 py-3 text-center">Score</th>
                          <th className="px-4 py-3 text-center">Status</th>
                          <th className="px-4 py-3 text-left">Last Contacted</th>
                          <th className="px-4 py-3 text-center">Outreach / Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {leads.map(lead => (
                          <tr key={lead.id} className="hover:bg-slate-850/30 transition-colors">
                            <td className="px-4 py-4 whitespace-nowrap font-bold text-white">
                              {lead.customer_name}
                              <span className="block text-[10px] text-slate-500 font-semibold">{lead.customer_phone}</span>
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-350 font-bold">{lead.service_name}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-center font-black">
                              <span className={`px-2 py-0.5 rounded text-[10px] ${
                                lead.lead_score >= 80 ? 'bg-red-500/10 text-red-400' : 'bg-slate-800 text-slate-450'
                              }`}>
                                {lead.lead_score} pts
                              </span>
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              <span className={`px-2 py-0.5 rounded text-[9px] font-bold border uppercase ${
                                lead.status === 'NEW'
                                  ? 'bg-purple-900/20 text-purple-300 border-purple-800/40'
                                  : lead.status === 'CONTACTED'
                                  ? 'bg-blue-900/20 text-blue-300 border-blue-800/40'
                                  : lead.status === 'CONVERTED'
                                  ? 'bg-emerald-900/20 text-emerald-300 border-emerald-800/40'
                                  : 'bg-slate-900 text-slate-500 border-slate-800'
                              }`}>
                                {lead.status}
                              </span>
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-400 text-xs">
                              {lead.last_contacted ? new Date(lead.last_contacted).toLocaleDateString() : 'Never'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              <div className="flex gap-2 justify-center">
                                {lead.status !== 'CONVERTED' && lead.status !== 'LOST' && (
                                  <>
                                    <button
                                      onClick={() => handleCallCustomer(lead.customer_name, lead.customer_phone)}
                                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs cursor-pointer border border-slate-700"
                                      title="Call Customer"
                                    >
                                      📞 Call
                                    </button>
                                    <button
                                      onClick={() => handleSendWhatsApp(lead.customer_name, lead.customer_phone, lead.service_name)}
                                      className="px-2.5 py-1 bg-emerald-950 hover:bg-emerald-900 border border-emerald-900 text-emerald-400 rounded-lg text-xs cursor-pointer"
                                      title="WhatsApp"
                                    >
                                      💬 WhatsApp
                                    </button>
                                    <button
                                      onClick={() => handleMarkContacted(lead.id)}
                                      className="px-2.5 py-1 bg-blue-950 hover:bg-blue-900 border border-blue-800 text-blue-400 rounded-lg text-xs cursor-pointer"
                                      title="Mark Contacted"
                                    >
                                      ✉️ Contacted
                                    </button>
                                    <button
                                      onClick={() => handleConvertToAppointment(lead.id)}
                                      className="px-2.5 py-1 bg-indigo-650 hover:bg-indigo-500 text-white rounded-lg text-xs cursor-pointer font-bold shadow-md shadow-indigo-500/20"
                                      title="Convert to Appointment"
                                    >
                                      🎉 Convert
                                    </button>
                                  </>
                                )}
                                {lead.status === 'CONVERTED' && (
                                  <span className="text-emerald-400 font-bold text-xs">✓ Booking Confirmed</span>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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

            {activeTab === 'upsells' && (
              <div className="space-y-6 animate-fade-in">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">⚡ Automated Upsell & Recommendations</h2>
                  <p className="text-xs text-slate-500">Select an active client to analyze historical preferences and prompt live pairing recommendations.</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                  
                  {/* Left Column: Customers List */}
                  <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-5 space-y-4 lg:col-span-1">
                    <h3 className="text-sm font-extrabold text-white">👥 Customers Likely To Buy</h3>
                    <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
                      {customers.map(c => (
                        <button
                          key={c.id}
                          onClick={() => {
                            setSelectedCustomerId(c.id);
                            fetchStaffRecommendations(c.id);
                          }}
                          className={`w-full text-left p-3.5 rounded-2xl border transition-all cursor-pointer flex flex-col space-y-1 ${
                            selectedCustomerId === c.id
                              ? 'bg-emerald-950/40 border-emerald-500/35 text-white'
                              : 'bg-slate-950/40 border-slate-850 hover:border-slate-750 text-slate-400 hover:text-white'
                          }`}
                        >
                          <span className="text-xs font-black block">{c.name}</span>
                          <span className="text-[10px] text-slate-500 font-semibold">{c.email}</span>
                          <span className="text-[9px] text-emerald-400 font-bold uppercase mt-1">{c.notes || 'Active Profile'}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Right Column: Recommendations & Actions */}
                  <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-5 space-y-4 lg:col-span-2">
                    <h3 className="text-sm font-extrabold text-white">💡 Recommended Services</h3>
                    
                    {!selectedCustomerId ? (
                      <div className="bg-slate-950/30 rounded-2xl border border-slate-850 p-12 text-center text-slate-500 text-xs font-medium">
                        Select a customer from the left list to query recommendations.
                      </div>
                    ) : isStaffRecsLoading ? (
                      <div className="h-48 flex flex-col items-center justify-center space-y-3">
                        <div className="w-6 h-6 border-2 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin" />
                        <span className="text-xs text-slate-500 font-bold uppercase tracking-widest animate-pulse">Consulting purchase history RAG engine...</span>
                      </div>
                    ) : staffRecommendations.length === 0 ? (
                      <div className="bg-slate-950/30 rounded-2xl border border-slate-850 p-12 text-center text-slate-500 text-xs font-semibold">
                        No automated upsell matching recommendations for this client today.
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="bg-emerald-950/20 border border-emerald-500/10 p-4 rounded-2xl">
                          <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest block">⚡ Live Pairing Recommendation Available</span>
                          <p className="text-xs text-slate-450 mt-1 leading-relaxed">
                            These services pair perfectly with this client's booking pattern or explicit rules. Pitch them to the customer during their appointment today!
                          </p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {staffRecommendations.map((rec) => (
                            <div key={rec.id} className="bg-slate-950 border border-slate-850 p-5 rounded-2xl flex flex-col justify-between hover:border-slate-750 transition-all">
                              <div className="space-y-2">
                                <div className="flex justify-between items-center text-xs">
                                  <h4 className="font-extrabold text-white">{rec.name}</h4>
                                  <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-450 rounded text-[9px] font-bold">
                                    {(rec.confidence_score * 100).toFixed(0)}% Match
                                  </span>
                                </div>
                                <p className="text-xs text-slate-450 leading-relaxed font-semibold">{rec.description}</p>
                                <p className="text-[11px] text-emerald-450 bg-emerald-950/20 border border-emerald-900/10 p-2.5 rounded-xl font-bold">
                                  💡 Pitch reason: {rec.reason}
                                </p>
                              </div>

                              <div className="border-t border-slate-850/60 pt-4 mt-5">
                                <div className="flex items-center justify-between text-xs mb-3 font-semibold">
                                  <span className="text-slate-500">⏱️ {rec.duration_minutes} mins</span>
                                  <span className="text-emerald-400 text-sm font-black">${rec.price}</span>
                                </div>
                                <button
                                  onClick={() => handlePresentUpsell(rec)}
                                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-xs font-black rounded-xl text-white transition-all cursor-pointer text-center shadow-lg shadow-emerald-500/10 uppercase tracking-wider"
                                >
                                  Present Upsell
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* 6. Profile Tab */}

            {activeTab === 'reviews' && (
              <div className="space-y-6 animate-fade-in">
                <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
                  <div>
                    <h2 className="text-xl font-black">⭐ My Stylist Ratings & Feedback</h2>
                    <p className="text-xs text-slate-500">Monitor your professional rating score, analyze client feedback, and review performance insights.</p>
                  </div>
                  <button
                    onClick={fetchStaffReviews}
                    className="px-4 py-2 border border-slate-800 hover:text-white rounded-xl text-xs font-bold text-slate-400 cursor-pointer"
                  >
                    🔄 Refresh Feed
                  </button>
                </div>

                {isStaffReviewsLoading ? (
                  <div className="py-24 text-center text-slate-500 font-bold animate-pulse">
                    Aggregating your ratings log...
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Metrics Summary Row */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/15 flex items-center justify-center text-2xl text-amber-400">
                          🏆
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Average Rating</span>
                          <span className="text-2xl font-black text-white block mt-0.5">
                            {staffReviews.length > 0
                              ? (staffReviews.reduce((sum, r) => sum + r.rating, 0) / staffReviews.length).toFixed(1)
                              : '5.0'} / 5.0
                          </span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Based on {staffReviews.length} reviews</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/15 flex items-center justify-center text-2xl text-emerald-400">
                          💚
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Positive Feedback</span>
                          <span className="text-2xl font-black text-white block mt-0.5">
                            {staffReviews.filter(r => r.sentiment === 'POSITIVE').length}
                          </span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Happy clients served</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/15 flex items-center justify-center text-2xl text-red-400">
                          ⚠️
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Needs Attention</span>
                          <span className="text-2xl font-black text-white block mt-0.5">
                            {staffReviews.filter(r => r.sentiment === 'NEGATIVE' || r.sentiment === 'CRITICAL').length}
                          </span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Negative/Critical complaints</span>
                        </div>
                      </div>
                    </div>

                    {/* Review Feed */}
                    <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4 text-left">
                      <h3 className="text-sm font-extrabold text-slate-400 uppercase tracking-wider">Recent Client Testimonials</h3>
                      
                      {staffReviews.length === 0 ? (
                        <div className="text-center text-slate-500 py-12 text-xs font-semibold">
                          No customer reviews logged for you yet. Deliver great styles to earn feedback!
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {staffReviews.map((rev) => (
                            <div key={rev.id} className="bg-slate-955 border border-slate-850 p-5 rounded-2xl space-y-3 hover:border-slate-800 transition-colors">
                              <div className="flex justify-between items-start flex-wrap gap-2 text-xs">
                                <div>
                                  <h4 className="font-extrabold text-white">{rev.customer_name}</h4>
                                  <span className="text-slate-550 block font-bold">Booking: {rev.branch_name || 'Downtown Branch'}</span>
                                </div>
                                <div className="text-right flex flex-col items-end">
                                  <div className="flex text-amber-400 text-sm mb-1">
                                    {'★'.repeat(rev.rating)}{'☆'.repeat(5 - rev.rating)}
                                  </div>
                                  <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase border ${
                                    rev.sentiment === 'POSITIVE'
                                      ? 'bg-emerald-950/20 text-emerald-450 border-emerald-900/20'
                                      : rev.sentiment === 'NEUTRAL'
                                      ? 'bg-slate-900 text-slate-400 border-slate-800'
                                      : 'bg-red-950/20 text-red-450 border-red-900/20'
                                  }`}>
                                    {rev.sentiment}
                                  </span>
                                </div>
                              </div>

                              <p className="text-xs text-slate-300 leading-relaxed font-semibold bg-slate-900/30 p-3.5 rounded-xl border border-slate-850">
                                {rev.review_text || rev.comment}
                              </p>

                              {rev.ai_response && (
                                <div className="bg-emerald-950/15 border border-emerald-900/10 p-3.5 rounded-xl space-y-1 ml-4 border-l-2 border-l-emerald-500">
                                  <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest block">💬 Official Response Sent</span>
                                  <p className="text-xs text-slate-400 font-semibold leading-relaxed">{rev.ai_response}</p>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
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
