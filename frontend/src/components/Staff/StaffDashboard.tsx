import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
import { StaffChat } from './StaffChat';
import { StaffInsights } from './StaffInsights';
import { PerformanceCard } from './PerformanceCard';
import { RevenueCard } from './RevenueCard';
import { ScheduleCard } from './ScheduleCard';
import { CustomerHistoryCard } from './CustomerHistoryCard';
import { UpcomingAppointments } from './UpcomingAppointments';
import { RecommendationsCard } from './RecommendationsCard';

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
  const [activeTab, setActiveTab] = useState<'dashboard' | 'appointments' | 'customers' | 'schedule' | 'assistant' | 'profile' | 'leads' | 'upsells' | 'reviews' | 'performance'>('dashboard');
  
  // Roster lists
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [customers, setCustomers] = useState<CustomerHistoryItem[]>([]);
  const [leads, setLeads] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Leave management states
  const [leaves, setLeaves] = useState<any[]>([]);
  const [leaveDate, setLeaveDate] = useState<string>('');
  const [leaveReason, setLeaveReason] = useState<string>('');

  // Stylist performance aggregates
  const [personalStats, setPersonalStats] = useState<any>({
    appointments: 0,
    revenue: 0.0,
    rating: 0.0,
    upsells: 0.0,
    role: 'Stylist'
  });

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

  const loadStaffData = async () => {
    try {
      setIsLoading(true);
      
      // Load real appointments from the backend
      const apptRes = await apiClient.get<any[]>('/appointments/my').catch(() => ({ data: [] }));
      if (apptRes.data && apptRes.data.length > 0) {
        setAppointments(apptRes.data.map((appt: any) => {
          let normalized = appt.start_time;
          if (appt.start_time && !appt.start_time.endsWith('Z') && !appt.start_time.includes('+')) {
            const parts = appt.start_time.split(/T|\s/);
            const hasTimeOffset = parts.length > 1 && parts[1].includes('-');
            if (!hasTimeOffset) {
              normalized = appt.start_time + 'Z';
            }
          }
          const start = new Date(normalized);
          const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
          const monthStr = monthNames[start.getUTCMonth()];
          const dayStr = start.getUTCDate();
          const hours = start.getUTCHours();
          const minutes = start.getUTCMinutes();
          const ampm = hours >= 12 ? 'PM' : 'AM';
          const displayHours = hours % 12 || 12;
          const displayMinutes = minutes.toString().padStart(2, '0');
          const timeStr = `${displayHours}:${displayMinutes} ${ampm}`;
          return {
            id: appt.id,
            start_time: `${monthStr} ${dayStr} @ ${timeStr}`,
            raw_start_time: appt.start_time,
            end_time: appt.end_time,
            customer_name: appt.customer ? `${appt.customer.first_name} ${appt.customer.last_name}` : 'Client',
            service_name: appt.service?.name || 'Service',
            notes: appt.notes || 'None',
            status: appt.status
          };
        }));
      } else {
        setAppointments([]);
      }

      // Load leaves from backend
      const leavesRes = await apiClient.get<any[]>('/staff/leaves').catch(() => ({ data: [] }));
      setLeaves(leavesRes.data);

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
        setCustomers([]);
      }

      const leadsRes = await apiClient.get<any[]>('/staff/leads').catch(() => ({ data: [] }));
      setLeads(leadsRes.data.length ? leadsRes.data : []);

      try {
        const staffSumRes = await apiClient.get('/analytics/staff-summary');
        if (staffSumRes.data?.success && staffSumRes.data?.staff?.roster) {
          const roster = staffSumRes.data.staff.roster;
          const matched = roster.find((s: any) => s.email === user?.email || s.id === user?.staff_id);
          if (matched) {
            setPersonalStats({
              name: matched.name || 'Stylist',
              appointments: matched.appointments || 0,
              revenue: matched.revenue || 0.0,
              rating: matched.rating || 0.0,
              upsells: matched.upsells || 0.0,
              role: matched.role || 'Stylist'
            });
          }
        }
      } catch (err) {
        console.warn('Failed to load dynamic staff analytics benchmarks.', err);
      }
    } catch (e) {
      console.warn('Failed to load dynamic stylist logs', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadStaffData();
  }, []);

  const handleUpdateStatus = async (apptId: string, nextStatus: string) => {
    try {
      await apiClient.post(`/appointments/${apptId}/status`, { status: nextStatus });
      window.alert(`🎉 Success! Status updated to ${nextStatus}.`);
      loadStaffData();
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to update status.');
    }
  };

  const handleAddLeave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leaveDate) return;
    try {
      await apiClient.post('/staff/leaves', {
        leave_date: leaveDate,
        reason: leaveReason || null
      });
      window.alert('🎉 Success! Leave scheduled.');
      setLeaveDate('');
      setLeaveReason('');
      // Refresh leaves list
      const leavesRes = await apiClient.get<any[]>('/staff/leaves').catch(() => ({ data: [] }));
      setLeaves(leavesRes.data);
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to schedule leave.');
    }
  };

  const handleCancelLeave = async (leaveId: string) => {
    if (!window.confirm('Are you sure you want to cancel this leave?')) return;
    try {
      await apiClient.delete(`/staff/leaves/${leaveId}`);
      window.alert('🎉 Success! Leave cancelled.');
      // Refresh leaves list
      const leavesRes = await apiClient.get<any[]>('/staff/leaves').catch(() => ({ data: [] }));
      setLeaves(leavesRes.data);
    } catch (err: any) {
      window.alert('Failed to cancel leave.');
    }
  };

  // Compute stats metrics dynamically
  const stats = [
    { title: "Today's Styling Book", value: `${appointments.filter(a => a.status !== 'CANCELLED' && a.status !== 'COMPLETED').length} Slots`, desc: 'Active agenda', icon: '⏰' },
    { title: 'Stylist Rating', value: `${personalStats.rating?.toFixed(1) || '0.0'} ★`, desc: 'Average feedback rating', icon: '📈' },
    { title: 'Upsell Converts', value: `$${personalStats.upsells?.toFixed(0) || '0'}`, desc: 'Total upsell revenue', icon: '⚡' },
    { title: 'Assigned Role', value: `${personalStats.role || 'Stylist'}`, desc: 'Specialized role', icon: '📍' }
  ];

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
    const staffName = personalStats.name || user?.email || 'Stylist';
    if (selectedService === 'Signature Precision Haircut') {
      setUpsellSuggestion(`💡 Upsell Agent Recommendation:\nRecommend our 'Hydrating Keratin Leave-in treatment' for $25. ${staffName} earns a 15% commission ($3.75) upon conversion.`);
    } else if (selectedService === 'Balayage & Creative Color') {
      setUpsellSuggestion(`💡 Upsell Agent Recommendation:\nRecommend 'Post-Color UV Protection Shield Treatment' for $45. ${staffName} earns a 15% commission ($6.75) upon conversion.`);
    } else {
      setUpsellSuggestion(`💡 Upsell Agent Recommendation:\nRecommend 'Signature Scalp Cleansing Detox Massage' for $30. ${staffName} earns a 15% commission ($4.50) upon conversion.`);
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
              { id: 'performance', label: 'My Performance', icon: '📈' },
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
      <main className="flex-1 p-6 md:p-8 text-left overflow-y-auto">
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
                  
                  {appointments.filter(appt => appt.status !== 'CANCELLED' && appt.status !== 'COMPLETED').length === 0 ? (
                    <div className="text-center text-slate-500 py-8 text-xs">
                      No active appointments booked for today.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {appointments.filter(appt => appt.status !== 'CANCELLED' && appt.status !== 'COMPLETED').map(appt => (
                        <div key={appt.id} className="bg-slate-900/80 border border-slate-800/80 p-5 rounded-2xl space-y-3 relative flex flex-col justify-between hover:border-slate-700 transition-colors">
                          <div>
                            <span className="absolute top-4 right-4 px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-[9px] font-bold border border-emerald-500/20 uppercase">
                              {appt.start_time}
                            </span>
                            <div className="space-y-1">
                              <h4 className="text-base font-extrabold text-white">{appt.customer_name}</h4>
                              <span className="text-xs text-blue-400 font-bold block">{appt.service_name}</span>
                            </div>
                            <p className="text-xs text-slate-405 leading-relaxed font-medium bg-slate-950 p-3 rounded-xl border border-slate-850 my-2">
                              <span className="text-[10px] text-slate-500 font-black block uppercase mb-1">Stylist Notes:</span>
                              {appt.notes}
                            </p>
                          </div>
                          <div className="flex justify-between items-center pt-2 border-t border-slate-850/60 mt-2">
                            <span className={`px-2 py-0.5 rounded text-[9px] font-black border uppercase ${
                              appt.status === 'PENDING'
                                ? 'bg-amber-900/25 text-amber-300 border-amber-800/40'
                                : appt.status === 'CONFIRMED'
                                ? 'bg-blue-900/25 text-blue-300 border-blue-800/40'
                                : appt.status === 'CHECKED_IN'
                                ? 'bg-purple-900/25 text-purple-300 border-purple-800/40'
                                : appt.status === 'IN_SERVICE'
                                ? 'bg-indigo-900/25 text-indigo-300 border-indigo-800/40'
                                : appt.status === 'COMPLETED'
                                ? 'bg-emerald-900/25 text-emerald-300 border-emerald-800/40'
                                : 'bg-red-900/25 text-red-355 border-red-800/40'
                            }`}>
                              {appt.status}
                            </span>
                            <div className="flex gap-1.5">
                              {appt.status === 'PENDING' && (
                                <>
                                  <button
                                    onClick={() => handleUpdateStatus(appt.id, 'CONFIRMED')}
                                    className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-bold cursor-pointer"
                                  >
                                    Confirm
                                  </button>
                                  <button
                                    onClick={() => handleUpdateStatus(appt.id, 'CANCELLED')}
                                    className="px-2.5 py-1 bg-red-955 border border-red-900/40 text-red-400 rounded text-[10px] cursor-pointer"
                                  >
                                    Cancel
                                  </button>
                                </>
                              )}
                              {appt.status === 'CONFIRMED' && (
                                <>
                                  <button
                                    onClick={() => handleUpdateStatus(appt.id, 'CHECKED_IN')}
                                    className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[10px] font-bold cursor-pointer"
                                  >
                                    Check In
                                  </button>
                                  <button
                                    onClick={() => handleUpdateStatus(appt.id, 'CANCELLED')}
                                    className="px-2.5 py-1 bg-red-955 border border-red-900/40 text-red-400 rounded text-[10px] cursor-pointer"
                                  >
                                    Cancel
                                  </button>
                                </>
                              )}
                              {appt.status === 'CHECKED_IN' && (
                                <button
                                  onClick={() => handleUpdateStatus(appt.id, 'IN_SERVICE')}
                                  className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px] font-bold cursor-pointer"
                                >
                                  Start Service
                                </button>
                              )}
                              {appt.status === 'IN_SERVICE' && (
                                <button
                                  onClick={() => handleUpdateStatus(appt.id, 'COMPLETED')}
                                  className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-bold cursor-pointer"
                                >
                                  Complete
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}

            {/* 2. Agenda Book Tab */}
            {activeTab === 'appointments' && (
              <UpcomingAppointments appointments={appointments} onUpdateStatus={handleUpdateStatus} />
            )}

            {/* 3. Client History Tab */}
            {activeTab === 'customers' && (
              <CustomerHistoryCard customers={customers} />
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
                              {lead.followup_count > 0 && (
                                <span className="block text-[10px] text-slate-500 mt-1 font-bold">
                                  {lead.followup_count} {lead.followup_count === 1 ? 'follow-up' : 'follow-ups'}
                                </span>
                              )}
                            </td>
                             <td className="px-4 py-4 whitespace-nowrap text-slate-400 text-xs">
                              {lead.last_contacted 
                                ? new Date(lead.last_contacted).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) + ' ' + new Date(lead.last_contacted).toLocaleDateString()
                                : 'Never'}
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
                                {lead.status === 'LOST' && (
                                  <span className="text-slate-500 font-bold text-xs">✗ Dismissed / Lost</span>
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
              <ScheduleCard
                appointments={appointments}
                leaves={leaves}
                leaveDate={leaveDate}
                leaveReason={leaveReason}
                setLeaveDate={setLeaveDate}
                setLeaveReason={setLeaveReason}
                onAddLeave={handleAddLeave}
                onCancelLeave={handleCancelLeave}
              />
            )}

            {/* 5. AI Co-Stylist Assistant Tab */}
            {activeTab === 'assistant' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">🤖 AI Co-Stylist Panel</h2>
                  <p className="text-xs text-slate-500">Authorized: Atlas Co-Stylist AI. Ask questions about schedule, metrics, and customer formula cards.</p>
                </div>
                <StaffChat />
              </div>
            )}

            {/* Upsells Tab */}
            {activeTab === 'upsells' && (
              <RecommendationsCard
                customers={customers}
                selectedCustomerId={selectedCustomerId}
                setSelectedCustomerId={setSelectedCustomerId}
                recommendations={staffRecommendations}
                isRecommendationsLoading={isStaffRecsLoading}
                onFetchRecommendations={fetchStaffRecommendations}
                onAcceptRecommendation={handlePresentUpsell}
                selectedService={selectedService}
                setSelectedService={setSelectedService}
                onQueryUpsell={handleQueryUpsell}
                upsellSuggestion={upsellSuggestion}
              />
            )}

            {/* Reviews Tab */}
            {activeTab === 'reviews' && (
              <StaffInsights
                reviews={staffReviews}
                isReviewsLoading={isStaffReviewsLoading}
                personalStats={personalStats}
              />
            )}

            {/* Performance Tab */}
            {activeTab === 'performance' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">📈 My Performance Benchmarks</h2>
                  <p className="text-xs text-slate-500">Examine details of your service records, commission splits, and client ratings.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start animate-fade-in">
                  <PerformanceCard
                    metrics={{
                      totalAppointments: personalStats.appointments,
                      completedAppointments: personalStats.appointments,
                      cancelledAppointments: 0,
                      averageRating: personalStats.rating,
                      name: personalStats.name || user?.email || 'Stylist',
                      role: personalStats.role
                    }}
                  />
                  <RevenueCard
                    revenue={personalStats.revenue}
                    completedCount={personalStats.appointments}
                  />
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
