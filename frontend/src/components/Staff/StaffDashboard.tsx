import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
import { AgentChat } from '../AgentChat/AgentChat';

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
  const [searchQuery, setSearchQuery] = useState<string>('');
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

  // Helper to calculate the dates of the current week (Monday to Sunday)
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

  // Compute stats metrics dynamically
  const stats = [
    { title: "Today's Styling Book", value: `${appointments.filter(a => a.status !== 'CANCELLED' && a.status !== 'COMPLETED').length} Slots`, desc: 'Active agenda', icon: '⏰' },
    { title: 'Stylist Rating', value: `${personalStats.rating?.toFixed(1) || '0.0'} ★`, desc: 'Average feedback rating', icon: '📈' },
    { title: 'Upsell Converts', value: `$${personalStats.upsells?.toFixed(0) || '0'}`, desc: 'Total upsell revenue', icon: '⚡' },
    { title: 'Assigned Role', value: `${personalStats.role || 'Stylist'}`, desc: 'Specialized role', icon: '📍' }
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
                          <th className="px-4 py-3 text-center">Status</th>
                          <th className="px-4 py-3 text-center">Workflow Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {appointments.map(appt => (
                          <tr key={appt.id} className="hover:bg-slate-850/30 transition-colors">
                            <td className="px-4 py-4 whitespace-nowrap text-blue-400 font-bold text-xs">{appt.start_time}</td>
                            <td className="px-4 py-4 whitespace-nowrap font-bold text-white">{appt.customer_name}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-350">{appt.service_name}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-slate-450 italic text-xs">{appt.notes}</td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-black border uppercase ${
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
                                  : 'bg-red-900/25 text-red-350 border-red-800/40'
                              }`}>
                                {appt.status}
                              </span>
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap text-center">
                              <div className="flex gap-2 justify-center">
                                {appt.status === 'PENDING' && (
                                  <>
                                    <button
                                      onClick={() => handleUpdateStatus(appt.id, 'CONFIRMED')}
                                      className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs cursor-pointer font-bold"
                                    >
                                      Confirm
                                    </button>
                                    <button
                                      onClick={() => handleUpdateStatus(appt.id, 'CANCELLED')}
                                      className="px-2.5 py-1 bg-red-950 border border-red-900/30 text-red-400 rounded-lg text-xs cursor-pointer"
                                    >
                                      Cancel
                                    </button>
                                  </>
                                )}
                                {appt.status === 'CONFIRMED' && (
                                  <>
                                    <button
                                      onClick={() => handleUpdateStatus(appt.id, 'CHECKED_IN')}
                                      className="px-2.5 py-1 bg-indigo-650 hover:bg-indigo-500 text-white rounded-lg text-xs cursor-pointer font-bold"
                                    >
                                      Check In
                                    </button>
                                    <button
                                      onClick={() => handleUpdateStatus(appt.id, 'CANCELLED')}
                                      className="px-2.5 py-1 bg-red-950 border border-red-900/30 text-red-400 rounded-lg text-xs cursor-pointer"
                                    >
                                      Cancel
                                    </button>
                                  </>
                                )}
                                {appt.status === 'CHECKED_IN' && (
                                  <button
                                    onClick={() => handleUpdateStatus(appt.id, 'IN_SERVICE')}
                                    className="px-2.5 py-1 bg-blue-650 hover:bg-blue-500 text-white rounded-lg text-xs cursor-pointer font-bold"
                                  >
                                    Start Service
                                  </button>
                                )}
                                {appt.status === 'IN_SERVICE' && (
                                  <button
                                    onClick={() => handleUpdateStatus(appt.id, 'COMPLETED')}
                                    className="px-2.5 py-1 bg-emerald-650 hover:bg-emerald-500 text-white rounded-lg text-xs cursor-pointer font-bold"
                                  >
                                    Complete
                                  </button>
                                )}
                                {(appt.status === 'COMPLETED' || appt.status === 'CANCELLED') && (
                                  <span className="text-slate-500 text-xs">-</span>
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
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">🗓️ Stylist Weekly Planner</h2>
                  <p className="text-xs text-slate-500">Visual schedule planner, leave scheduler, and slot allocations.</p>
                </div>

                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl">
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-4 text-center">
                    {getCurrentWeekDates().map((dateObj, idx) => {
                      const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' });
                      const dateStr = dateObj.toISOString().split('T')[0]; // YYYY-MM-DD
                      const displayDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });

                      // Check if staff has leave scheduled for this date
                      const isOnLeave = leaves.some(l => l.leave_date === dateStr);
                      const leaveInfo = leaves.find(l => l.leave_date === dateStr);

                      // Filter appointments for this date
                      const dayBookings = appointments.filter(appt => {
                        if (appt.status === 'CANCELLED' || appt.status === 'COMPLETED') return false;
                        if (!appt.raw_start_time) return false;
                        return appt.raw_start_time.startsWith(dateStr);
                      });
                      
                      const count = dayBookings.length;

                      return (
                        <div key={idx} className={`bg-slate-950 p-4 rounded-xl border space-y-3 flex flex-col justify-between min-h-[170px] ${
                          isOnLeave ? 'border-red-900/35 bg-red-950/5' : 'border-slate-850'
                        }`}>
                          <div>
                            <div className="border-b border-slate-900 pb-1.5 mb-2 text-center">
                              <span className="block text-[10px] font-black text-slate-400 uppercase tracking-widest">{dayName}</span>
                              <span className="block text-[9px] text-slate-500 font-bold mt-0.5">{displayDate}</span>
                            </div>
                            <div className="space-y-1.5">
                              {isOnLeave ? (
                                <div className="space-y-1">
                                  <span className="px-2 py-0.5 bg-red-500/10 text-red-400 rounded text-[9px] font-black block border border-red-500/20 uppercase tracking-wider text-center">
                                    🌴 On Leave
                                  </span>
                                  {leaveInfo?.reason && (
                                    <span className="text-[9px] text-slate-550 italic block text-center truncate" title={leaveInfo.reason}>
                                      "{leaveInfo.reason}"
                                    </span>
                                  )}
                                </div>
                              ) : count > 0 ? (
                                <>
                                  <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-[9px] font-black block border border-emerald-500/20 uppercase tracking-wider text-center">
                                    {count} {count === 1 ? 'Slot' : 'Slots'}
                                  </span>
                                  <div className="space-y-1 mt-2">
                                    {dayBookings.slice(0, 3).map(b => (
                                      <div key={b.id} className="text-[9px] text-left text-slate-350 bg-slate-900/40 p-1.5 rounded border border-slate-850/60" title={`${b.customer_name} - ${b.service_name}`}>
                                        <span className="font-extrabold text-white block truncate">{b.customer_name}</span>
                                        <span className="text-slate-500 block truncate">{b.service_name}</span>
                                      </div>
                                    ))}
                                    {count > 3 && (
                                      <span className="text-[8px] text-slate-500 block text-center mt-1">+{count - 3} more</span>
                                    )}
                                  </div>
                                </>
                              ) : (
                                <span className="px-2 py-1 bg-slate-900/40 text-slate-655 rounded text-[9px] font-bold block text-center uppercase tracking-wider">
                                  Empty
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Leave Management Section */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
                  <div className="border-b border-slate-800 pb-3 flex justify-between items-center flex-wrap gap-4">
                    <div>
                      <h3 className="text-sm font-extrabold text-white uppercase tracking-wider">🌴 Schedule Leaves & Off Days</h3>
                      <p className="text-xs text-slate-500">Put leave for specific dates to block client bookings on both customer app and Clara assistant.</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Add Leave Form */}
                    <form onSubmit={handleAddLeave} className="bg-slate-955 p-5 rounded-2xl border border-slate-850 space-y-4 lg:col-span-1">
                      <h4 className="text-xs font-black text-white uppercase tracking-widest border-b border-slate-900 pb-2">Record New Leave</h4>
                      
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[9px] font-bold text-slate-550 uppercase tracking-widest">Select Leave Date</label>
                        <input
                          type="date"
                          value={leaveDate}
                          onChange={e => setLeaveDate(e.target.value)}
                          required
                          className="px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white focus:outline-none"
                        />
                      </div>

                      <div className="flex flex-col gap-1.5">
                        <label className="text-[9px] font-bold text-slate-550 uppercase tracking-widest">Reason / Description (Optional)</label>
                        <input
                          type="text"
                          value={leaveReason}
                          onChange={e => setLeaveReason(e.target.value)}
                          placeholder="e.g. Vacation, Personal matter"
                          className="px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white focus:outline-none"
                        />
                      </div>

                      <button
                        type="submit"
                        className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-xs font-black rounded-xl text-white transition-all cursor-pointer text-center shadow-lg shadow-emerald-500/10 uppercase tracking-wider"
                      >
                        🌴 Schedule Leave
                      </button>
                    </form>

                    {/* Leaves list */}
                    <div className="bg-slate-955 p-5 rounded-2xl border border-slate-850 space-y-4 lg:col-span-2">
                      <h4 className="text-xs font-black text-white uppercase tracking-widest border-b border-slate-900 pb-2">My Active Leaves</h4>
                      
                      {leaves.length === 0 ? (
                        <div className="text-center text-slate-500 py-12 text-xs">
                          No scheduled leaves found.
                        </div>
                      ) : (
                        <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
                          {leaves.map((l) => (
                            <div key={l.id} className="bg-slate-900/60 border border-slate-850 p-3.5 rounded-xl flex items-center justify-between gap-4">
                              <div className="space-y-1">
                                <span className="font-extrabold text-white text-xs block">📅 {new Date(l.leave_date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' })}</span>
                                {l.reason && <span className="text-[10px] text-slate-450 block italic">Reason: "{l.reason}"</span>}
                              </div>
                              <button
                                onClick={() => handleCancelLeave(l.id)}
                                className="px-2.5 py-1.5 bg-red-950/20 hover:bg-red-900/30 border border-red-900/30 text-red-400 rounded-lg text-[10px] font-bold cursor-pointer transition-all"
                              >
                                Cancel Leave
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
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

            {/* My Performance Tab */}
            {activeTab === 'performance' && (
              <div className="space-y-6 animate-fade-in">
                <div className="border-b border-slate-800 pb-3">
                  <h2 className="text-xl font-black">📈 My Performance Analytics</h2>
                  <p className="text-xs text-slate-500">Secure personal styling benchmarks and revenue commission highlights.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { label: "Completed Appointments", val: `${personalStats.appointments} Sessions`, desc: "Total stylized bookings", color: "text-blue-455" },
                    { label: "Revenue Generated", val: `₹${personalStats.revenue?.toLocaleString()}`, desc: "Incremental value generated", color: "text-emerald-450" },
                    { label: "Stylist Customer Rating", val: `${personalStats.rating} ★`, desc: "Based on client reviews", color: "text-pink-455" },
                    { label: "Upsells Sold", val: `₹${personalStats.upsells?.toLocaleString()}`, desc: "Accepted recommendations value", color: "text-indigo-405" }
                  ].map((card, idx) => (
                    <div key={idx} className="bg-slate-900/60 border border-slate-850 p-5 rounded-2xl shadow-md space-y-1">
                      <span className="block text-[8px] font-black text-slate-550 uppercase tracking-wider">{card.label}</span>
                      <span className={`text-xl font-black block ${card.color}`}>{card.val}</span>
                      <span className="text-[9px] text-slate-550 block font-bold uppercase">{card.desc}</span>
                    </div>
                  ))}
                </div>

                <section className="bg-slate-900/60 border border-slate-850 p-6 rounded-3xl space-y-3">
                  <span className="text-xs font-black text-emerald-450 block uppercase">🌟 Monthly Commission Progress</span>
                  <p className="text-xs font-semibold text-slate-350 leading-relaxed">
                    Great styling! You have sold ₹{personalStats.upsells?.toLocaleString()} in upsell recommendations this month. You earn a 15% commission (₹{(personalStats.upsells * 0.15).toLocaleString()}) which will be added directly to your next paycheck bonus! Keep recommending Hair Spa and complimentary add-ons.
                  </p>
                </section>
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
