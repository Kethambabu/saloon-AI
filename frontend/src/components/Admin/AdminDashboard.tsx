import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
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
const formatUTCDateTime = (isoString: string): string => {
  try {
    let normalized = isoString;
    if (isoString && !isoString.endsWith('Z') && !isoString.includes('+')) {
      const parts = isoString.split(/T|\s/);
      const hasTimeOffset = parts.length > 1 && parts[1].includes('-');
      if (!hasTimeOffset) {
        normalized = isoString + 'Z';
      }
    }
    const date = new Date(normalized);
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth();
    const day = date.getUTCDate();
    const hours = date.getUTCHours();
    const minutes = date.getUTCMinutes();
    
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    const displayMinutes = minutes.toString().padStart(2, '0');
    
    return `${monthNames[month]} ${day}, ${year} at ${displayHours}:${displayMinutes} ${ampm}`;
  } catch (err) {
    return 'Invalid date';
  }
};
interface ReviewRecord {
  id: string;
  customer_name: string;
  rating: number;
  comment: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE' | 'CRITICAL';
  ai_response: string | null;
  escalation_required: boolean;
  responded: boolean;
  created_at: string;
  review_text?: string;
  staff_name?: string;
}

export const AdminDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  
  // Redesigned Zenoti-Style Navigation State
  const [activeTab, setActiveTab] = useState<
    | 'dashboard'
    | 'revenue'
    | 'customer-intelligence'
    | 'staff-intelligence'
    | 'lead-intelligence'
    | 'upsell-intelligence'
    | 'reputation-intelligence'
    | 'forecast'
    | 'business-assistant'
    | 'settings'
  >('dashboard');

  // Interactive Review moderation state
  const [replyingReviewId, setReplyingReviewId] = useState<string | null>(null);
  const [responseText, setResponseText] = useState<string>('');
  const [reputationFilter, setReputationFilter] = useState<'ALL' | 'NEGATIVE' | 'CRITICAL'>('ALL');
  
  // Interactive Settings catalog state
  const [activeSettingsTab, setActiveSettingsTab] = useState<'users' | 'services'>('users');
  const [editingServiceId, setEditingServiceId] = useState<string | null>(null);
  const [editPrice, setEditPrice] = useState<number>(0);
  
  // Add Service Form State
  const [newServiceName, setNewServiceName] = useState('');
  const [newServiceDescription, setNewServiceDescription] = useState('');
  const [newServicePrice, setNewServicePrice] = useState<number>(0);
  const [newServiceDuration, setNewServiceDuration] = useState<number>(30);
  const [isAddingService, setIsAddingService] = useState(false);

  // Operational Data States
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [leads, setLeads] = useState<any[]>([]);
  const [leadSearch, setLeadSearch] = useState<string>('');
  const [leadStatusFilter, setLeadStatusFilter] = useState<string>('ALL');
  const [leadSortBy, setLeadSortBy] = useState<string>('score-desc');
  const [topRecoverableLeads, setTopRecoverableLeads] = useState<any[]>([]);
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // --- BI Agent State Trackers with Premium Fallback Defaults ---
  const [dashboardSummary, setDashboardSummary] = useState<any>({
    revenue_today: 0,
    appointments_today: 0,
    new_customers: 0,
    lead_conversion_rate: 0.0,
    average_rating: 0.0,
    upsell_revenue: 0.0
  });

  const [revenueSummary, setRevenueSummary] = useState<any>({
    cards: {
      today_revenue: 0.0,
      weekly_revenue: 0.0,
      monthly_revenue: 0.0,
      yearly_revenue: 0.0
    },
    charts: {
      labels: [],
      revenue_over_time: [],
      by_service: {},
      by_branch: {},
      by_staff: {}
    }
  });

  const [customerSummary, setCustomerSummary] = useState<any>({
    total_customers: 0,
    returning_customers: 0,
    inactive_customers: 0,
    vip_customers: 0,
    customer_lifetime_value: 0.0
  });

  const [staffSummary, setStaffSummary] = useState<any>({
    top_performer: "None",
    top_revenue: 0.0,
    top_appointments: 0,
    top_rating: 0.0,
    top_upsells: 0.0,
    lowest_performer: "None",
    roster: []
  });

  const [leadSummary, setLeadSummary] = useState<any>({
    new_leads: 0,
    converted_leads: 0,
    lost_leads: 0,
    pending_leads: 0,
    conversion_rate: 0.0
  });

  const [reviewSummary, setReviewSummary] = useState<any>({
    total_reviews: 0,
    average_rating: 0.0,
    positive_reviews: 0,
    neutral_reviews: 0,
    negative_reviews: 0,
    critical_complaints: 0,
    primary_complaint: "None"
  });

  const [upsellSummary, setUpsellSummary] = useState<any>({
    upsell_revenue: 0.0,
    acceptance_rate: 0.0,
    accepted_count: 0,
    total_offers: 0,
    most_accepted: "None"
  });

  const [aiInsights, setAiInsights] = useState<string[]>([]);

  const [forecastSummary, setForecastSummary] = useState<any>({
    expected_revenue: 0.0,
    expected_appointments: 0,
    expected_leads: 0,
    expected_conversion: 0.0,
    expected_upsell_revenue: 0.0,
    growth_rate_pct: 0.0
  });

  const [isBIDataLoading, setIsBIDataLoading] = useState<boolean>(false);

  const [services, setServices] = useState<any[]>([]);

  // --- Fetch BI Data from Backend Analytics ---
  const fetchBIData = async () => {
    try {
      setIsBIDataLoading(true);
      const [
        dashRes,
        revRes,
        custRes,
        staffRes,
        leadAnalyticsRes,
        reviewRes,
        upsellRes,
        insightsRes,
        forecastRes
      ] = await Promise.all([
        apiClient.get('/analytics/dashboard-summary').catch(() => ({ data: { success: false, summary: null } })),
        apiClient.get('/analytics/revenue-summary').catch(() => ({ data: { success: false, revenue: null } })),
        apiClient.get('/analytics/customer-summary').catch(() => ({ data: { success: false, customers: null } })),
        apiClient.get('/analytics/staff-summary').catch(() => ({ data: { success: false, staff: null } })),
        apiClient.get('/leads/analytics').catch(() => ({ data: null })),
        apiClient.get('/analytics/review-summary').catch(() => ({ data: { success: false, reviews: null } })),
        apiClient.get('/analytics/upsell-summary').catch(() => ({ data: { success: false, upsells: null } })),
        apiClient.get('/analytics/ai-insights').catch(() => ({ data: { success: false, insights: [] } })),
        apiClient.get('/analytics/forecast-metrics').catch(() => ({ data: { success: false, forecast: null } }))
      ]);

      if (dashRes.data?.success && dashRes.data?.summary) setDashboardSummary(dashRes.data.summary);
      if (revRes.data?.success && revRes.data?.revenue) setRevenueSummary(revRes.data.revenue);
      if (custRes.data?.success && custRes.data?.customers) setCustomerSummary(custRes.data.customers);
      if (staffRes.data?.success && staffRes.data?.staff) setStaffSummary(staffRes.data.staff);
      
      if (leadAnalyticsRes.data) {
        const la = leadAnalyticsRes.data;
        setLeadSummary({
          new_leads: la.new_leads || 0,
          converted_leads: la.converted_leads || 0,
          lost_leads: la.lost_leads || 0,
          pending_leads: (la.contacted_leads || 0) + (la.interested_leads || 0),
          conversion_rate: la.conversion_rate || 0.0
        });
        setTopRecoverableLeads(la.top_recoverable_leads || []);
      }
      if (reviewRes.data?.success && reviewRes.data?.reviews) setReviewSummary(reviewRes.data.reviews);
      if (upsellRes.data?.success && upsellRes.data?.upsells) setUpsellSummary(upsellRes.data.upsells);
      if (insightsRes.data?.success && insightsRes.data?.insights?.length) setAiInsights(insightsRes.data.insights);
      if (forecastRes.data?.success && forecastRes.data?.forecast) setForecastSummary(forecastRes.data.forecast);
    } catch (err) {
      console.warn('Failed to load dynamic BI telemetry logs, utilizing preloaded fallbacks.', err);
    } finally {
      setIsBIDataLoading(false);
    }
  };

  // --- Initial database seeding load ---
  useEffect(() => {
    const fetchAllData = async () => {
      try {
        setIsLoading(true);
        const [usersRes, apptsRes, leadsRes, reviewsRes, servicesRes] = await Promise.all([
          apiClient.get<UserRecord[]>('/auth/users').catch(() => ({ data: [] })),
          apiClient.get<AppointmentRecord[]>('/appointments/my').catch(() => ({ data: [] })),
          apiClient.get<any[]>('/leads').catch(() => ({ data: [] })),
          apiClient.get<any>('/reviews').catch(() => ({ data: { success: false, reviews: [] } })),
          apiClient.get<any[]>('/services?active_only=false').catch(() => ({ data: [] }))
        ]);

        setUsers(usersRes.data || []);
        setAppointments(apptsRes.data || []);
        setLeads(leadsRes.data || []);
        const reviewArray = reviewsRes.data?.reviews || reviewsRes.data || [];
        setReviews(reviewArray);
        setServices((servicesRes.data || []).map((s: any) => ({
          ...s,
          duration: s.duration_minutes || s.duration
        })));

        await fetchBIData();
      } catch (err) {
        console.warn('Failed to compile operations ledger', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchAllData();
  }, []);

  const handleToggleActive = async (userId: string) => {
    try {
      const res = await apiClient.post(`/auth/users/${userId}/toggle`);
      if (res.data && res.data.success) {
        setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: res.data.is_active } : u));
      }
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to update user status.');
    }
  };

  const handleCancelAppointment = (id: string) => {
    if (window.confirm('Cancel this active client appointment?')) {
      setAppointments(prev => prev.map(a => a.id === id ? { ...a, status: 'CANCELLED' } : a));
    }
  };

  const handleRespondToReview = async (reviewId: string, text: string) => {
    if (!text.trim()) return;
    try {
      const res = await apiClient.post('/reviews/respond', {
        review_id: reviewId,
        custom_response: text
      });
      if (res.data && res.data.success) {
        window.alert('Response registered successfully!');
        setReplyingReviewId(null);
        setResponseText('');
        // reload reviews
        const reviewsRes = await apiClient.get('/reviews').catch(() => ({ data: [] }));
        const reviewArray = reviewsRes.data?.reviews || reviewsRes.data || [];
        if (reviewArray.length) setReviews(reviewArray);
      }
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to submit response.');
    }
  };

  const handleEscalateReview = async (reviewId: string) => {
    try {
      const res = await apiClient.post('/reviews/escalate', {
        review_id: reviewId
      });
      if (res.data && res.data.success) {
        window.alert('Review escalated to manager successfully!');
        // reload
        const reviewsRes = await apiClient.get('/reviews').catch(() => ({ data: [] }));
        const reviewArray = reviewsRes.data?.reviews || reviewsRes.data || [];
        if (reviewArray.length) setReviews(reviewArray);
      }
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to escalate review.');
    }
  };

  const handleSavePrice = async (id: string) => {
    try {
      await apiClient.put(`/services/${id}`, { price: editPrice });
      setServices(prev => prev.map(s => s.id === id ? { ...s, price: editPrice } : s));
      setEditingServiceId(null);
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to update service price.');
    }
  };

  const handleAddService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newServiceName.trim() || newServicePrice <= 0 || newServiceDuration <= 0) {
      window.alert('Please fill out all required fields with valid values.');
      return;
    }
    try {
      setIsAddingService(true);
      const res = await apiClient.post('/services', {
        name: newServiceName,
        description: newServiceDescription || undefined,
        price: newServicePrice,
        duration_minutes: newServiceDuration
      });
      if (res.data) {
        const addedService = {
          ...res.data,
          duration: res.data.duration_minutes
        };
        setServices(prev => [...prev, addedService]);
        setNewServiceName('');
        setNewServiceDescription('');
        setNewServicePrice(0);
        setNewServiceDuration(30);
        window.alert('New service added successfully!');
      }
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to add new service.');
    } finally {
      setIsAddingService(false);
    }
  };

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

          <nav className="flex flex-col gap-1.5">
            {[
              { id: 'dashboard', label: 'Executive Overview', icon: '🏠' },
              { id: 'revenue', label: 'Revenue Intelligence', icon: '💰' },
              { id: 'customer-intelligence', label: 'Customer Intelligence', icon: '👥' },
              { id: 'staff-intelligence', label: 'Staff Intelligence', icon: '💇' },
              { id: 'lead-intelligence', label: 'Lead Intelligence', icon: '🎯' },
              { id: 'upsell-intelligence', label: 'Upsell Intelligence', icon: '⚡' },
              { id: 'reputation-intelligence', label: 'Reputation Intelligence', icon: '🛡️' },
              { id: 'forecast', label: 'Forecast Intelligence', icon: '🔮' },
              { id: 'business-assistant', label: 'AI Business Assistant', icon: '🤖' },
              { id: 'settings', label: 'Settings Panel', icon: '⚙️' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-3 px-4 py-2.5 rounded-xl text-xs font-bold text-left transition-all cursor-pointer ${
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
        {isLoading || isBIDataLoading ? (
          <div className="py-24 text-center text-slate-500 font-bold animate-pulse">
            Establishing Secure Admin Session & BI Telemetry logs...
          </div>
        ) : (
          <div className="animate-fade-in space-y-6">
            
            {/* ── 1. Executive Overview Subpage ── */}
            {activeTab === 'dashboard' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3 flex justify-between items-center">
                  <div>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Dashboard</span>
                    <h2 className="text-xl font-black mt-0.5 text-white">Good Morning, Balu</h2>
                  </div>
                  <button 
                    onClick={fetchBIData}
                    className="px-3.5 py-1.5 bg-slate-900 border border-slate-800 hover:text-white rounded-xl text-xs font-bold text-slate-450 hover:bg-slate-850 transition-all cursor-pointer"
                  >
                    🔄 Sync Analytics
                  </button>
                </div>

                {/* Indicated Metrics Cards Grid */}
                <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {[
                    { title: "Revenue Today", value: `₹${dashboardSummary?.revenue_today?.toLocaleString()}`, desc: "Reflects completed bookings today", color: "text-emerald-400" },
                    { title: "Appointments Today", value: dashboardSummary?.appointments_today, desc: "Total scheduled guest visits", color: "text-blue-400" },
                    { title: "New Customers", value: dashboardSummary?.new_customers, desc: "First-time registered users", color: "text-purple-400" },
                    { title: "Lead Conversion Rate", value: `${dashboardSummary?.lead_conversion_rate}%`, desc: "CRM pipeline conversion score", color: "text-amber-400" },
                    { title: "Average Rating", value: `${dashboardSummary?.average_rating} ★`, desc: "Based on verified approved reviews", color: "text-pink-400" },
                    { title: "Upsell Revenue Today", value: `₹${dashboardSummary?.upsell_revenue?.toLocaleString()}`, desc: "Yield from accepted add-ons", color: "text-indigo-400" }
                  ].map((item, idx) => (
                    <div key={idx} className="bg-slate-900/60 backdrop-blur-xl border border-slate-850/80 p-5 rounded-2xl shadow-md space-y-1.5">
                      <span className="block text-[10px] font-black text-slate-550 uppercase tracking-wider">{item.title}</span>
                      <span className={`text-2xl font-black block ${item.color}`}>{item.value}</span>
                      <span className="text-[9px] text-slate-500 block font-bold uppercase">{item.desc}</span>
                    </div>
                  ))}
                </section>

                {/* AI Insights Card */}
                <section className="bg-slate-900/60 backdrop-blur-xl border border-slate-850 p-6 rounded-3xl space-y-4">
                  <div className="flex items-center space-x-2">
                    <span className="text-xl">🧠</span>
                    <div>
                      <h3 className="text-sm font-black text-white uppercase tracking-wider">Today's AI Insights</h3>
                      <p className="text-[10px] text-slate-500">Autonomous business analysis generated by Atlas BI Agent.</p>
                    </div>
                  </div>
                  <ul className="space-y-3 pt-2">
                    {aiInsights.map((insight, idx) => (
                      <li key={idx} className="flex items-start space-x-3 text-xs text-slate-350 font-semibold">
                        <span className="text-emerald-400 font-extrabold mt-0.5">✦</span>
                        <span>{insight}</span>
                      </li>
                    ))}
                  </ul>
                </section>

                {/* Appointments Table */}
                <section className="bg-slate-900/40 border border-slate-850 rounded-3xl p-6 shadow-xl space-y-4">
                  <div>
                    <h3 className="text-sm font-black text-white flex items-center gap-2">📅 Active Appointment Monitoring</h3>
                    <p className="text-xs text-slate-500">Live operational ledger of active scheduler pipelines.</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-850 text-xs font-semibold">
                      <thead>
                        <tr className="text-slate-500 uppercase tracking-wider text-[9px] font-black">
                          <th className="px-4 py-3 text-left">Time / Date</th>
                          <th className="px-4 py-3 text-left">Client Name</th>
                          <th className="px-4 py-3 text-left">Assigned Stylist</th>
                          <th className="px-4 py-3 text-left">Service Requested</th>
                          <th className="px-4 py-3 text-center">Status</th>
                          <th className="px-4 py-3 text-center">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-855 text-slate-300">
                        {appointments.map((appt) => (
                          <tr key={appt.id} className="hover:bg-slate-850/20 transition-colors">
                            <td className="px-4 py-3.5 whitespace-nowrap text-blue-400">
                              {formatUTCDateTime(appt.start_time)}
                            </td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-white">
                              {appt.customer ? `${appt.customer.first_name} ${appt.customer.last_name}` : 'Anonymous Guest'}
                            </td>
                            <td className="px-4 py-3.5 whitespace-nowrap">
                              {appt.staff ? `${appt.staff.first_name} ${appt.staff.last_name}` : 'Auto Assigned'}
                            </td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-slate-400">
                              {appt.service.name}
                            </td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-center">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase ${
                                appt.status === 'CONFIRMED' || appt.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-450' : 'bg-red-500/10 text-red-450'
                              }`}>
                                {appt.status}
                              </span>
                            </td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-center">
                              {appt.status === 'CONFIRMED' && (
                                <button
                                  onClick={() => handleCancelAppointment(appt.id)}
                                  className="px-2.5 py-1 bg-red-955/20 border border-red-900/30 text-red-400 hover:bg-red-900/30 rounded-lg text-[10px] transition-all cursor-pointer font-bold"
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

            {/* ── 2. Revenue Intelligence Subpage ── */}
            {activeTab === 'revenue' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Finance Analytics</span>
                  <h2 className="text-xl font-black mt-0.5">💰 Revenue Intelligence</h2>
                  <p className="text-xs text-slate-500">Global salon aggregates and performance charts.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { label: "Today's Revenue", val: `₹${revenueSummary?.cards?.today_revenue?.toLocaleString()}`, color: "text-emerald-450" },
                    { label: "Weekly Revenue", val: `₹${revenueSummary?.cards?.weekly_revenue?.toLocaleString()}`, color: "text-blue-400" },
                    { label: "Monthly Revenue", val: `₹${revenueSummary?.cards?.monthly_revenue?.toLocaleString()}`, color: "text-purple-400" },
                    { label: "Yearly Revenue", val: `₹${revenueSummary?.cards?.yearly_revenue?.toLocaleString()}`, color: "text-amber-400" }
                  ].map((card, idx) => (
                    <div key={idx} className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                      <span className="block text-[9px] font-black text-slate-500 uppercase tracking-wider">{card.label}</span>
                      <span className={`text-xl font-black block mt-1 ${card.color}`}>{card.val}</span>
                    </div>
                  ))}
                </div>

                {/* HTML Line/Bar Chart for Revenue Trend */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-slate-900/40 border border-slate-850 p-6 rounded-3xl">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider mb-4">📈 Revenue Trend Over Time</h3>
                    <div className="flex items-end justify-between h-40 gap-2.5 pt-6">
                      {revenueSummary?.charts?.revenue_over_time?.map((val: number, idx: number) => {
                        const max = Math.max(...revenueSummary.charts.revenue_over_time, 1);
                        const pct = Math.round((val / max) * 100);
                        return (
                          <div key={idx} className="flex-1 flex flex-col items-center gap-2 group h-full justify-end">
                            <span className="text-[8px] text-emerald-400 font-bold opacity-0 group-hover:opacity-100 transition-opacity">₹{val.toLocaleString()}</span>
                            <div className="w-full bg-gradient-to-t from-blue-600 to-indigo-500 rounded-t-md hover:from-blue-500 hover:to-indigo-400 transition-all cursor-pointer" style={{ height: `${pct}%` }} />
                            <span className="text-[8px] text-slate-500 font-bold">{revenueSummary.charts.labels[idx]?.split("-")?.slice(1)?.join("/")}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Revenue by Service Progressive Bars */}
                  <div className="bg-slate-900/40 border border-slate-850 p-6 rounded-3xl space-y-4">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">💇 Revenue Share by Service</h3>
                    <div className="space-y-3 pt-2">
                      {Object.entries(revenueSummary?.charts?.by_service || {}).map(([service, amount]: [string, any]) => {
                        const total = Object.values(revenueSummary.charts.by_service).reduce((a: any, b: any) => a + b, 0) as number;
                        const pct = Math.round((amount / (total || 1)) * 100);
                        return (
                          <div key={service} className="space-y-1 text-xs">
                            <div className="flex justify-between font-bold">
                              <span className="text-slate-350">{service}</span>
                              <span className="text-blue-400">₹{amount?.toLocaleString()} ({pct}%)</span>
                            </div>
                            <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-855">
                              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Revenue by Staff Leaderboard & Branch */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-slate-900/40 border border-slate-850 p-6 rounded-3xl space-y-3.5">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">🌟 Revenue contribution by Branch</h3>
                    <div className="space-y-3 pt-1">
                      {Object.entries(revenueSummary?.charts?.by_branch || {}).map(([branch, amount]: [string, any]) => (
                        <div key={branch} className="flex justify-between items-center text-xs font-bold bg-slate-950/45 p-3 border border-slate-855 rounded-xl">
                          <span className="text-slate-300">{branch}</span>
                          <span className="text-emerald-450">₹{amount?.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="bg-slate-900/40 border border-slate-850 p-6 rounded-3xl space-y-3.5">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">🏆 Top Staff Revenue Contributors</h3>
                    <div className="space-y-3 pt-1">
                      {Object.entries(revenueSummary?.charts?.by_staff || {}).map(([st, amount]: [string, any]) => (
                        <div key={st} className="flex justify-between items-center text-xs font-bold bg-slate-950/45 p-3 border border-slate-855 rounded-xl">
                          <span className="text-slate-300">{st}</span>
                          <span className="text-indigo-400">₹{amount?.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* AI Insights Card */}
                <section className="bg-slate-900/60 backdrop-blur-xl border border-slate-850 p-5 rounded-2xl space-y-2">
                  <span className="text-xs font-black text-indigo-455 block">💡 Revenue AI Insight</span>
                  <p className="text-xs font-semibold text-slate-350 leading-relaxed">
                    {aiInsights && aiInsights.length > 0 
                      ? `${aiInsights[0]} ${aiInsights[1] || ''}` 
                      : 'Retrieving live revenue analytics...'}
                  </p>
                </section>
              </div>
            )}

            {/* ── 3. Customer Intelligence Subpage ── */}
            {activeTab === 'customer-intelligence' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">CRM Telemetry</span>
                  <h2 className="text-xl font-black mt-0.5">👥 Customer Intelligence</h2>
                  <p className="text-xs text-slate-500">Cohort retention metrics and LTV benchmarking.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                  {[
                    { label: "Total Customers", val: customerSummary?.total_customers, color: "text-blue-450" },
                    { label: "Returning Cohort", val: customerSummary?.returning_customers, color: "text-emerald-450" },
                    { label: "VIP Cohort", val: customerSummary?.vip_customers, color: "text-purple-450" },
                    { label: "Inactive Customers (90d)", val: customerSummary?.inactive_customers, color: "text-red-450" },
                    { label: "Customer LTV Avg", val: `₹${customerSummary?.customer_lifetime_value?.toLocaleString()}`, color: "text-amber-400" }
                  ].map((card, idx) => (
                    <div key={idx} className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl text-center">
                      <span className="block text-[8px] font-black text-slate-500 uppercase tracking-wider">{card.label}</span>
                      <span className={`text-xl font-black block mt-1 ${card.color}`}>{card.val}</span>
                    </div>
                  ))}
                </div>

                {/* AI Insight */}
                <section className="bg-slate-900/60 border border-slate-850 p-5 rounded-3xl space-y-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-lg">📢</span>
                    <h4 className="text-xs font-black uppercase text-indigo-400 tracking-wider">Cohort Attrition Alert</h4>
                  </div>
                  <p className="text-xs font-semibold text-slate-350 leading-relaxed">
                    {customerSummary?.total_customers > 0 
                      ? `${Math.round((customerSummary?.inactive_customers / customerSummary?.total_customers) * 100)}% of our registered customers (${customerSummary?.inactive_customers} out of {customerSummary?.total_customers}) have not booked an appointment in the last 90 days. We recommend launching a targeted re-engagement campaign.`
                      : 'No customer cohort attrition detected.'}
                  </p>
                </section>
              </div>
            )}

            {/* ── 4. Staff Intelligence Subpage ── */}
            {activeTab === 'staff-intelligence' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Roster Management</span>
                  <h2 className="text-xl font-black mt-0.5">💇 Staff Intelligence</h2>
                  <p className="text-xs text-slate-500">Stylist productivity leaderboards and ratings benchmarks.</p>
                </div>

                {/* Staff Intelligence Indicators */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Top Performer</span>
                    <span className="text-sm font-black text-emerald-450 block mt-1">{staffSummary?.top_performer}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Highest Styling Volume</span>
                    <span className="text-sm font-black text-blue-400 block mt-1">{staffSummary?.top_appointments} sessions</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Top Rating Score</span>
                    <span className="text-sm font-black text-pink-400 block mt-1">{staffSummary?.top_rating} ★</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Top Upsells Sold</span>
                    <span className="text-sm font-black text-indigo-400 block mt-1">₹{staffSummary?.top_upsells?.toLocaleString()}</span>
                  </div>
                </div>

                {/* Stylist Leaderboard table */}
                <section className="bg-slate-900/40 border border-slate-850 rounded-3xl p-6 shadow-xl space-y-4">
                  <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">Stylist Productivity Roster</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-850 text-xs font-semibold">
                      <thead>
                        <tr className="text-slate-500 uppercase tracking-wider text-[9px] font-black">
                          <th className="px-4 py-3 text-left">Stylist Name</th>
                          <th className="px-4 py-3 text-left">Security Role</th>
                          <th className="px-4 py-3 text-center">Appointments</th>
                          <th className="px-4 py-3 text-center">Revenue Generated</th>
                          <th className="px-4 py-3 text-center">Average Rating</th>
                          <th className="px-4 py-3 text-right">Upsells Logged</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-855 text-slate-350">
                        {staffSummary?.roster?.map((st: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-850/20 transition-colors">
                            <td className="px-4 py-3.5 whitespace-nowrap text-white font-bold">{st.name}</td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-slate-450">{st.role}</td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-center text-blue-400">{st.appointments}</td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-center text-emerald-450">₹{st.revenue?.toLocaleString()}</td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-center text-pink-400">{st.rating} ★</td>
                            <td className="px-4 py-3.5 whitespace-nowrap text-right text-indigo-405">₹{st.upsells?.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                <section className="bg-slate-900/60 border border-slate-855 p-5 rounded-2xl text-xs font-semibold text-slate-350">
                  <span className="text-indigo-400 font-black block mb-1">💡 Performance AI Insight</span>
                  {aiInsights && aiInsights.length > 4 
                    ? aiInsights[4] 
                    : 'No stylist transactions completed yet today.'}
                </section>
              </div>
            )}

            {/* ── 5. Lead Intelligence Subpage ── */}
            {activeTab === 'lead-intelligence' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3 flex justify-between items-center">
                  <div>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">CRM Pipeline</span>
                    <h2 className="text-xl font-black mt-0.5">🎯 Lead Intelligence</h2>
                    <p className="text-xs text-slate-500">Autonomous campaign conversions and pipeline indicators.</p>
                  </div>
                  <button 
                    onClick={fetchBIData}
                    className="px-3.5 py-1.5 bg-slate-900 border border-slate-800 hover:text-white rounded-xl text-xs font-bold text-slate-450 hover:bg-slate-850 transition-all cursor-pointer"
                  >
                    🔄 Refresh Leads
                  </button>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="bg-slate-900/50 border border-slate-855 p-4.5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">New Leads</span>
                    <span className="text-xl font-black text-blue-400 block mt-1">{leadSummary?.new_leads}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-855 p-4.5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Contacted</span>
                    <span className="text-xl font-black text-purple-400 block mt-1">{leadSummary?.pending_leads}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-855 p-4.5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Converted</span>
                    <span className="text-xl font-black text-emerald-450 block mt-1">{leadSummary?.converted_leads}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-855 p-4.5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Lost Pipeline</span>
                    <span className="text-xl font-black text-red-450 block mt-1">{leadSummary?.lost_leads}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-855 p-4.5 rounded-2xl text-center col-span-2 md:col-span-1">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Conversion Rate</span>
                    <span className="text-xl font-black text-indigo-400 block mt-1">{leadSummary?.conversion_rate}%</span>
                  </div>
                </div>

                <section className="bg-slate-900/60 border border-slate-850 p-5 rounded-3xl space-y-2">
                  <span className="text-xs font-black text-amber-400 block uppercase">💬 CRM Funnel Bottleneck Detected</span>
                  <p className="text-xs font-semibold text-slate-350 leading-relaxed">
                    {aiInsights && aiInsights.length > 2 
                      ? `${aiInsights[2]} We recommend optimizing styling and scheduling response speeds during peak bottleneck hours.`
                      : 'No active CRM funnel bottlenecks detected.'}
                  </p>
                </section>

                {/* Search, Filter, Sort Controls */}
                <div className="bg-slate-900/40 border border-slate-850 rounded-3xl p-5 flex flex-col md:flex-row gap-4 items-center justify-between">
                  <div className="w-full md:w-1/3 relative">
                    <input 
                      type="text" 
                      placeholder="Search leads name, email, phone, service..." 
                      value={leadSearch}
                      onChange={e => setLeadSearch(e.target.value)}
                      className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none placeholder-slate-500"
                    />
                  </div>
                  <div className="flex flex-wrap gap-3 w-full md:w-auto justify-end">
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-black text-slate-500 uppercase">Status:</span>
                      <select
                        value={leadStatusFilter}
                        onChange={e => setLeadStatusFilter(e.target.value)}
                        className="px-3 py-2 bg-slate-955 border border-slate-800 rounded-xl text-xs text-white focus:outline-none cursor-pointer"
                      >
                        <option value="ALL">All Statuses</option>
                        <option value="NEW">New</option>
                        <option value="CONTACTED">Contacted</option>
                        <option value="INTERESTED">Interested</option>
                        <option value="CONVERTED">Converted</option>
                        <option value="LOST">Lost</option>
                      </select>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-black text-slate-500 uppercase">Sort By:</span>
                      <select
                        value={leadSortBy}
                        onChange={e => setLeadSortBy(e.target.value)}
                        className="px-3 py-2 bg-slate-955 border border-slate-800 rounded-xl text-xs text-white focus:outline-none cursor-pointer"
                      >
                        <option value="score-desc">Highest Score First</option>
                        <option value="score-asc">Lowest Score First</option>
                        <option value="date-desc">Newest First</option>
                        <option value="date-asc">Oldest First</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* ─── Top Recoverable Leads (Prioritized Scoring Grid) ─── */}
                {topRecoverableLeads.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <span>🔥 High Priority Recoverable Leads</span>
                      <span className="px-1.5 py-0.5 rounded-full text-[8px] bg-red-500/10 text-red-400 font-black animate-pulse">Top Scoring</span>
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {topRecoverableLeads.slice(0, 3).map((lead) => (
                        <div key={lead.id} className="bg-gradient-to-tr from-slate-900/60 to-amber-955/10 border border-slate-850 hover:border-amber-500/30 p-5 rounded-2xl shadow-lg relative overflow-hidden flex flex-col justify-between transition-all group">
                          <div className="absolute top-0 right-0 px-3 py-1 bg-amber-500/10 border-l border-b border-amber-500/20 text-amber-400 text-[10px] font-black rounded-bl-xl uppercase tracking-wider">
                            Score: {lead.lead_score}
                          </div>
                          <div className="space-y-3">
                            <span className="text-[9px] font-black text-slate-550 uppercase tracking-widest block">{lead.source || 'AI Receptionist'}</span>
                            <div>
                              <h4 className="text-sm font-extrabold text-white">{lead.customer_name}</h4>
                              <p className="text-[11px] text-slate-400 font-semibold">{lead.customer_email || lead.email}</p>
                              {lead.customer_phone && <p className="text-[10px] text-slate-500 font-bold mt-0.5">{lead.customer_phone}</p>}
                            </div>
                            <div className="bg-slate-950/45 border border-slate-855 p-3 rounded-xl space-y-1">
                              <span className="block text-[8px] font-bold text-slate-500 uppercase">Target Treatment</span>
                              <span className="text-xs font-extrabold text-white block truncate">{lead.service_name || 'General Inquiry'}</span>
                            </div>
                          </div>
                          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[10px]">
                            <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase ${
                              lead.status === 'NEW' 
                                ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' 
                                : lead.status === 'CONTACTED' 
                                  ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' 
                                  : lead.status === 'INTERESTED'
                                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            }`}>{lead.status}</span>
                            <span className="text-slate-500 font-bold">Captured {lead.created_at ? new Date(lead.created_at).toLocaleDateString() : 'Today'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Lead Catalog Table */}
                <section className="bg-slate-900/40 border border-slate-855 rounded-3xl p-6 shadow-xl space-y-4">
                  <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">
                    All CRM Leads Table ({
                      leads.filter(l => {
                        const q = leadSearch.toLowerCase();
                        const matchesSearch = !leadSearch.trim() || 
                          (l.customer_name && l.customer_name.toLowerCase().includes(q)) ||
                          (l.customer_email && l.customer_email.toLowerCase().includes(q)) ||
                          (l.customer_phone && l.customer_phone.toLowerCase().includes(q)) ||
                          (l.service_name && l.service_name.toLowerCase().includes(q)) ||
                          (l.source && l.source.toLowerCase().includes(q));
                        const matchesStatus = leadStatusFilter === 'ALL' || l.status === leadStatusFilter;
                        return matchesSearch && matchesStatus;
                      }).length
                    })
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-850 text-xs font-semibold">
                      <thead>
                        <tr className="text-slate-500 uppercase tracking-wider text-[9px] font-black">
                          <th className="px-4 py-3 text-left">Customer Name</th>
                          <th className="px-4 py-3 text-left">Service Name</th>
                          <th className="px-4 py-3 text-center">Status</th>
                          <th className="px-4 py-3 text-center">Source</th>
                          <th className="px-4 py-3 text-center">Follow-ups</th>
                          <th className="px-4 py-3 text-center">Score</th>
                          <th className="px-4 py-3 text-right">Captured Date</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-855 text-slate-350">
                        {(() => {
                          const q = leadSearch.toLowerCase();
                          const list = leads.filter(l => {
                            const matchesSearch = !leadSearch.trim() || 
                              (l.customer_name && l.customer_name.toLowerCase().includes(q)) ||
                              (l.customer_email && l.customer_email.toLowerCase().includes(q)) ||
                              (l.customer_phone && l.customer_phone.toLowerCase().includes(q)) ||
                              (l.service_name && l.service_name.toLowerCase().includes(q)) ||
                              (l.source && l.source.toLowerCase().includes(q));
                            const matchesStatus = leadStatusFilter === 'ALL' || l.status === leadStatusFilter;
                            return matchesSearch && matchesStatus;
                          });

                          list.sort((a, b) => {
                            if (leadSortBy === 'score-desc') return (b.lead_score || 0) - (a.lead_score || 0);
                            if (leadSortBy === 'score-asc') return (a.lead_score || 0) - (b.lead_score || 0);
                            if (leadSortBy === 'date-desc') return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
                            if (leadSortBy === 'date-asc') return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
                            return 0;
                          });

                          if (list.length === 0) {
                            return (
                              <tr>
                                <td colSpan={7} className="px-4 py-8 text-center text-slate-500 font-bold">
                                  No leads match the current filters.
                                </td>
                              </tr>
                            );
                          }

                          return list.map((lead) => (
                            <tr key={lead.id} className="hover:bg-slate-850/20 transition-colors">
                              <td className="px-4 py-3.5 whitespace-nowrap text-white font-bold">
                                {lead.customer_name}
                                <span className="block text-[10px] text-slate-500 font-semibold">{lead.customer_email || lead.email}</span>
                              </td>
                              <td className="px-4 py-3.5 whitespace-nowrap text-slate-450">{lead.service_name || 'General Inquiry'}</td>
                              <td className="px-4 py-3.5 whitespace-nowrap text-center">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-[8px] font-black uppercase ${
                                  lead.status === 'NEW' 
                                    ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' 
                                    : lead.status === 'CONTACTED' 
                                      ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' 
                                      : lead.status === 'INTERESTED' 
                                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' 
                                        : lead.status === 'CONVERTED' 
                                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                                          : 'bg-slate-800 text-slate-500'
                                }`}>
                                  {lead.status}
                                </span>
                              </td>
                              <td className="px-4 py-3.5 whitespace-nowrap text-center text-slate-450">{lead.source || 'AI Chat'}</td>
                              <td className="px-4 py-3.5 whitespace-nowrap text-center text-slate-350">{lead.followup_count} reminder(s)</td>
                              <td className="px-4 py-3.5 whitespace-nowrap text-center text-red-400 font-bold">{lead.lead_score || 0} pts</td>
                              <td className="px-4 py-3.5 whitespace-nowrap text-right text-slate-450">{lead.created_at ? new Date(lead.created_at).toLocaleDateString() : 'Unknown'}</td>
                            </tr>
                          ));
                        })()}
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            )}

            {/* ── 6. Upsell Intelligence Subpage ── */}
            {activeTab === 'upsell-intelligence' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Incremental Growth</span>
                  <h2 className="text-xl font-black mt-0.5">⚡ Upsell Intelligence</h2>
                  <p className="text-xs text-slate-500">Cross-sell and upgrade yields generated by Upsell Agent.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Upsell Revenue</span>
                    <span className="text-xl font-black text-emerald-450 block mt-1">₹{upsellSummary?.upsell_revenue?.toLocaleString()}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Acceptance Conversion</span>
                    <span className="text-xl font-black text-blue-400 block mt-1">{upsellSummary?.acceptance_rate}%</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Conversions Logged</span>
                    <span className="text-xl font-black text-purple-400 block mt-1">{upsellSummary?.accepted_count} times</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Total Offers Presented</span>
                    <span className="text-xl font-black text-amber-400 block mt-1">{upsellSummary?.total_offers} offers</span>
                  </div>
                </div>

                <section className="bg-slate-900/60 border border-slate-850 p-5 rounded-3xl space-y-2">
                  <span className="text-xs font-black text-indigo-400 block">💡 Upsell AI Insight</span>
                  <p className="text-xs font-semibold text-slate-350 leading-relaxed">
                    {aiInsights && aiInsights.length > 1 
                      ? `${aiInsights[1]} Recommending high-performing services dynamically to customers helps maximize overall ticket sizes.`
                      : 'Retrieving live upsell analytics...'}
                  </p>
                </section>
              </div>
            )}

            {/* ── 7. Reputation Intelligence Subpage ── */}
            {activeTab === 'reputation-intelligence' && (
              <div className="space-y-6 animate-fade-in">
                <div className="border-b border-slate-850 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Brand Protection</span>
                  <h2 className="text-xl font-black mt-0.5">🛡️ Reputation Intelligence</h2>
                  <p className="text-xs text-slate-500">Autonomous reviews sentiment classification and NPS scorecards.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                  <div className="bg-slate-900/60 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Average Rating</span>
                    <span className="text-2xl font-black block mt-1 text-amber-450">{reviewSummary?.average_rating} ★</span>
                  </div>
                  <div className="bg-slate-900/60 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Total Review Logs</span>
                    <span className="text-2xl font-black block mt-1 text-blue-400">{reviewSummary?.total_reviews}</span>
                  </div>
                  <div className="bg-slate-900/60 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Positive Reviews</span>
                    <span className="text-2xl font-black block mt-1 text-emerald-450">{reviewSummary?.positive_reviews}</span>
                  </div>
                  <div className="bg-slate-900/60 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Critical complaints</span>
                    <span className="text-2xl font-black block mt-1 text-purple-400">{reviewSummary?.critical_complaints} logs</span>
                  </div>
                </div>

                <section className="bg-slate-900/60 border border-slate-850 p-5 rounded-3xl text-xs font-semibold text-slate-350">
                  <span className="text-indigo-400 font-black block mb-1">💡 Reputation AI Insight</span>
                  {aiInsights && aiInsights.length > 3 
                    ? aiInsights[3] 
                    : 'No waiting-time complaints recorded today.'}
                </section>

                {/* Review Feed Scoped list */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-5 text-left">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-850/60 pb-4">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-wider">Client Reviews Ledger</h3>
                    <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-850 text-xs">
                      {[
                        { id: 'ALL', label: 'All Reviews' },
                        { id: 'NEGATIVE', label: 'Negative Feedback' },
                        { id: 'CRITICAL', label: 'Critical Escalations' }
                      ].map((subTab) => (
                        <button
                          key={subTab.id}
                          onClick={() => setReputationFilter(subTab.id as any)}
                          className={`px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer ${
                            reputationFilter === subTab.id
                              ? 'bg-blue-600 text-white shadow-md'
                              : 'text-slate-400 hover:text-white'
                          }`}
                        >
                          {subTab.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-4">
                    {reviews
                      .filter((rev) => {
                        if (reputationFilter === 'NEGATIVE') return rev.sentiment === 'NEGATIVE' || rev.rating <= 2;
                        if (reputationFilter === 'CRITICAL') return rev.sentiment === 'CRITICAL' || rev.escalation_required;
                        return true;
                      })
                      .map((rev) => (
                        <div key={rev.id} className="bg-slate-950 border border-slate-850 p-5 rounded-2xl space-y-3 relative hover:border-slate-800 transition-colors">
                          <div className="flex justify-between items-start flex-wrap gap-2 text-xs">
                            <div className="space-y-0.5">
                              <h4 className="font-extrabold text-white flex items-center gap-2">
                                <span>{rev.customer_name}</span>
                                {rev.staff_name && (
                                  <span className="px-2 py-0.5 bg-slate-900 border border-slate-850 text-slate-400 rounded text-[9px] font-medium">
                                    Stylist: {rev.staff_name}
                                  </span>
                                )}
                              </h4>
                              <span className="text-[10px] text-slate-500 block font-semibold">{rev.created_at ? rev.created_at.split('T')[0] : 'Just now'}</span>
                            </div>
                            
                            <div className="flex items-center gap-2">
                              <div className="flex text-amber-400 text-sm mr-2">
                                {'★'.repeat(rev.rating)}{'☆'.repeat(5 - rev.rating)}
                              </div>
                              <span className={`px-2 py-0.5 rounded text-[8px] font-black border tracking-wider uppercase ${
                                rev.sentiment === 'POSITIVE'
                                  ? 'bg-emerald-950/20 text-emerald-450 border-emerald-900/35'
                                  : rev.sentiment === 'NEUTRAL'
                                  ? 'bg-blue-900/20 text-blue-350 border-blue-800/40'
                                  : 'bg-red-955/20 text-red-400 border-red-900/35'
                              }`}>
                                {rev.sentiment}
                              </span>
                            </div>
                          </div>

                          <p className="text-xs text-slate-300 leading-relaxed font-semibold bg-slate-950/40 p-3.5 rounded-xl border border-slate-850">
                            {rev.review_text || rev.comment}
                          </p>

                          {/* Action button rows */}
                          <div className="flex flex-wrap items-center justify-between gap-4 pt-2.5 border-t border-slate-850/65 mt-4">
                            <div className="flex gap-2">
                              {rev.escalation_required ? (
                                <span className="px-2.5 py-1 bg-purple-950/40 border border-purple-900/45 text-purple-405 rounded-lg text-[9px] font-black uppercase flex items-center gap-1 shadow-md">
                                  🚨 Escalated To Manager
                                </span>
                              ) : (
                                <button
                                  onClick={() => handleEscalateReview(rev.id)}
                                  className="px-3 py-1.5 bg-slate-900 hover:bg-slate-850 border border-slate-850 hover:border-slate-750 text-slate-400 hover:text-white rounded-lg text-[9px] font-black uppercase transition-all cursor-pointer"
                                >
                                  Escalate To Manager
                                </button>
                              )}
                            </div>

                            <div className="flex gap-2">
                              {rev.ai_response && replyingReviewId !== rev.id && (
                                <span className="text-[9px] text-slate-550 font-black bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-850 uppercase">
                                  Reply Registered
                                </span>
                              )}
                              {replyingReviewId !== rev.id && (
                                <button
                                  onClick={() => {
                                    setReplyingReviewId(rev.id);
                                    setResponseText(rev.ai_response || '');
                                  }}
                                  className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[9px] font-black uppercase transition-all cursor-pointer"
                                >
                                  {rev.ai_response ? 'Edit Response' : 'Write Response'}
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Inline response editor */}
                          {replyingReviewId === rev.id && (
                            <div className="bg-slate-900 p-4 border border-slate-850 rounded-2xl space-y-3.5 mt-3 animate-fade-in text-left">
                              <div className="flex flex-col gap-1.5">
                                <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Salon Reply Draft</label>
                                <textarea
                                  value={responseText}
                                  onChange={(e) => setResponseText(e.target.value)}
                                  placeholder="Write your review reply or use dynamic Brand Guidelines..."
                                  rows={3}
                                  className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500 font-semibold"
                                />
                              </div>
                              <div className="flex justify-end gap-2 text-xs">
                                <button
                                  onClick={() => setReplyingReviewId(null)}
                                  className="px-3.5 py-1.5 border border-slate-800 text-slate-400 hover:text-white rounded-lg font-bold cursor-pointer"
                                >
                                  Cancel
                                </button>
                                <button
                                  onClick={() => handleRespondToReview(rev.id, responseText)}
                                  className="px-4.5 py-1.5 bg-blue-650 hover:bg-blue-500 text-white rounded-lg font-black shadow-md cursor-pointer"
                                >
                                  Send Response
                                </button>
                              </div>
                            </div>
                          )}

                          {/* Official Reply block */}
                          {rev.ai_response && replyingReviewId !== rev.id && (
                            <div className="bg-blue-950/20 border border-blue-900/20 p-4 rounded-xl space-y-1 mt-3 ml-4 border-l-2 border-l-blue-500 animate-fade-in">
                              <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest block">💬 Official Salon Reply</span>
                              <p className="text-xs text-slate-400 font-semibold leading-relaxed">{rev.ai_response}</p>
                            </div>
                          )}
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── 8. Forecast Intelligence Subpage ── */}
            {activeTab === 'forecast' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Predictive Models</span>
                  <h2 className="text-xl font-black mt-0.5">🔮 Forecast Intelligence</h2>
                  <p className="text-xs text-slate-500">Expectation curves and seasonal salon forecasts.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Expected Revenue</span>
                    <span className="text-xl font-black text-emerald-450 block mt-1">₹{forecastSummary?.expected_revenue?.toLocaleString()}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Expected Booking Volume</span>
                    <span className="text-xl font-black text-blue-450 block mt-1">{forecastSummary?.expected_appointments}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Expected Leads Captured</span>
                    <span className="text-xl font-black text-purple-450 block mt-1">{forecastSummary?.expected_leads}</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Expected Conversion Rate</span>
                    <span className="text-xl font-black text-amber-400 block mt-1">{forecastSummary?.expected_conversion}%</span>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-850 p-5 rounded-2xl text-center">
                    <span className="block text-[8px] font-black text-slate-500 uppercase">Growth Predictor</span>
                    <span className="text-xl font-black text-indigo-400 block mt-1">+{forecastSummary?.growth_rate_pct}%</span>
                  </div>
                </div>

                <section className="bg-slate-900/60 border border-slate-850 p-5 rounded-3xl text-xs font-semibold text-slate-350 leading-relaxed">
                  <span className="text-indigo-400 font-black block mb-1">🔮 Statistical Forecasting Rationale</span>
                  Predictive regression algorithms calculate a {forecastSummary?.growth_rate_pct}% net growth forecast next month across appointments volume and upsells ticket sizes, yielding an estimated monthly corporate output of ₹{forecastSummary?.expected_revenue?.toLocaleString()}.
                </section>
              </div>
            )}

            {/* ── 9. AI Business Assistant Subpage ── */}
            {activeTab === 'business-assistant' && (
              <div className="space-y-6">
                <div className="border-b border-slate-850 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">AutoGen Multi-Agent Workspace</span>
                  <h2 className="text-xl font-black mt-0.5">🤖 AI Business Assistant</h2>
                  <p className="text-xs text-slate-500">Converse directly with Atlas the Business Intelligence Analyst Co-pilot.</p>
                </div>

                <div className="bg-slate-900/60 border border-slate-850 p-5 rounded-3xl">
                  <AgentChat intentOverride="business_intelligence" />
                </div>
              </div>
            )}

            {/* ── 10. Settings Subpage ── */}
            {activeTab === 'settings' && (
              <div className="space-y-6">
                <div className="border-b border-slate-800 pb-3">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Admin security</span>
                  <h2 className="text-xl font-black mt-0.5">⚙️ Settings Panel</h2>
                  <p className="text-xs text-slate-500">Edit credential privileges and high-value styling catalogs.</p>
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
                                      ? 'bg-red-955 border-red-900/30 text-red-400 hover:bg-red-900/30'
                                      : 'bg-emerald-955 border-emerald-900/30 text-emerald-400 hover:bg-emerald-900/30'
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
                  <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
                    <h3 className="text-sm font-extrabold text-white">High-Value Catalog Editor</h3>

                    {/* Add New Service Form */}
                    <form onSubmit={handleAddService} className="bg-slate-950/40 border border-slate-800 p-5 rounded-2xl space-y-4 text-left">
                      <h4 className="text-xs font-black text-indigo-400 uppercase tracking-widest">Add New Catalog Service</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-[10px] font-bold text-slate-550 uppercase tracking-wider mb-1">Service Name *</label>
                          <input
                            type="text"
                            value={newServiceName}
                            onChange={e => setNewServiceName(e.target.value)}
                            placeholder="e.g. Luxury Keratin Treatment"
                            className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-bold text-slate-550 uppercase tracking-wider mb-1">Price (₹) *</label>
                          <input
                            type="number"
                            value={newServicePrice || ''}
                            onChange={e => setNewServicePrice(Number(e.target.value))}
                            placeholder="Price"
                            className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                            min="1"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-bold text-slate-550 uppercase tracking-wider mb-1">Duration (minutes) *</label>
                          <input
                            type="number"
                            value={newServiceDuration || ''}
                            onChange={e => setNewServiceDuration(Number(e.target.value))}
                            placeholder="Duration"
                            className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                            min="1"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-555 uppercase tracking-wider mb-1">Description</label>
                        <textarea
                          value={newServiceDescription}
                          onChange={e => setNewServiceDescription(e.target.value)}
                          placeholder="Brief description of the service..."
                          rows={2}
                          className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                        />
                      </div>
                      <div className="flex justify-end">
                        <button
                          type="submit"
                          disabled={isAddingService}
                          className="px-4 py-2 bg-blue-650/15 border border-blue-500/25 hover:bg-blue-650/25 text-blue-400 font-bold rounded-xl text-xs transition-all cursor-pointer disabled:opacity-50"
                        >
                          {isAddingService ? 'Adding Service...' : '➕ Add Service to Catalog'}
                        </button>
                      </div>
                    </form>

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
                                <span className="text-xs font-black text-blue-400">₹{s.price}</span>
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

export default AdminDashboard;
