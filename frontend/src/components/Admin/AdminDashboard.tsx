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
  const [activeTab, setActiveTab] = useState<'dashboard' | 'analytics' | 'staff' | 'customers' | 'leads' | 'reports' | 'agents' | 'settings' | 'upsell-analytics' | 'reputation'>('dashboard');
  
  // Live Upsell Analytics states
  const [upsellStats, setUpsellStats] = useState<any>({
    generated: 0,
    accepted: 0,
    revenue: 0,
    acceptance_rate: 0,
    top_addons: []
  });
  const [isUpsellStatsLoading, setIsUpsellStatsLoading] = useState<boolean>(false);

  // Live Reputation Analytics states
  const [reputationStats, setReputationStats] = useState<any>({
    total_reviews: 0,
    average_rating: 0.0,
    sentiment_distribution: { positive: 0, neutral: 0, negative: 0, critical: 0 },
    ratings_distribution: { "1_star": 0, "2_star": 0, "3_star": 0, "4_star": 0, "5_star": 0 },
    top_complaints: [],
    most_praised: [],
    escalated_count: 0,
    responded_count: 0
  });
  const [isReputationStatsLoading, setIsReputationStatsLoading] = useState<boolean>(false);
  const [reputationReviews, setReputationReviews] = useState<any[]>([]);
  const [isReputationReviewsLoading, setIsReputationReviewsLoading] = useState<boolean>(false);
  const [reputationFilter, setReputationFilter] = useState<'ALL' | 'NEGATIVE' | 'CRITICAL'>('ALL');
  const [replyingReviewId, setReplyingReviewId] = useState<string | null>(null);
  const [responseText, setResponseText] = useState<string>('');
  
  // Sub-tab state for AI Agents
  const [activeAgentTab, setActiveAgentTab] = useState<'receptionist' | 'bi' | 'reputation' | 'lead' | 'upsell'>('receptionist');
  // Sub-tab state for Settings
  const [activeSettingsTab, setActiveSettingsTab] = useState<'users' | 'services' | 'system'>('users');

  // Data States
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [staff, setStaff] = useState<StaffRecord[]>([]);
  const [leads, setLeads] = useState<any[]>([]);
  const [leadAnalytics, setLeadAnalytics] = useState<any>({
    total_leads: 200,
    new_leads: 45,
    converted_leads: 120,
    lost_leads: 35,
    conversion_rate: 60.0,
    top_recoverable_leads: []
  });
  const [leadsSearch, setLeadsSearch] = useState<string>('');
  const [leadsFilter, setLeadsFilter] = useState<string>('ALL');
  const [leadsSort, setLeadsSort] = useState<string>('SCORE');
  const [reviews, setReviews] = useState<ReviewRecord[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  
  // Interactive Simulator States
  const [biQuery, setBiQuery] = useState<string>('');
  const [biAnswer, setBiAnswer] = useState<string>('');
  const [isBiLoading, setIsBiLoading] = useState<boolean>(false);
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
        const [usersRes, _apptsRes] = await Promise.all([
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

        try {
          const [leadsRes, analyticsRes] = await Promise.all([
            apiClient.get<any[]>('/leads'),
            apiClient.get<any>('/leads/analytics')
          ]);
          setLeads(leadsRes.data);
          setLeadAnalytics(analyticsRes.data);
        } catch (err) {
          console.warn('API Leads offline, falling back to mock dashboard content', err);
          setLeads([
            { id: 'lead-1', customer_name: 'Balu', customer_email: 'balu@example.com', customer_phone: '+919999999999', service_name: 'Hair Spa', source: 'Website', status: 'NEW', lead_score: 80, last_contacted: null, created_at: new Date().toISOString() },
            { id: 'lead-2', customer_name: 'Vamsi Krishna', customer_email: 'vamsi@example.com', customer_phone: '+918888888888', service_name: 'Balayage & Creative Color', source: 'Facebook Ad', status: 'CONTACTED', lead_score: 60, last_contacted: new Date().toISOString(), created_at: new Date().toISOString() },
            { id: 'lead-3', customer_name: 'Jennifer Taylor', customer_email: 'jennifer@example.com', customer_phone: '+1-212-555-6001', service_name: 'Hydrating Deep-Cleansing Facial', source: 'Instagram Ad', status: 'CONVERTED', lead_score: 100, last_contacted: new Date().toISOString(), created_at: new Date().toISOString() }
          ]);
          setLeadAnalytics({
            total_leads: 3,
            new_leads: 1,
            contacted_leads: 1,
            interested_leads: 0,
            converted_leads: 1,
            lost_leads: 0,
            conversion_rate: 33.3,
            top_recoverable_leads: []
          });
        }

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

  const fetchUpsellStats = async () => {
    try {
      setIsUpsellStatsLoading(true);
      const res = await apiClient.get('/recommendations/analytics/stats');
      if (res.data && res.data.success) {
        setUpsellStats(res.data.analytics);
      }
    } catch (err) {
      console.error('Failed to load upsell analytics:', err);
      setUpsellStats({
        generated: 500,
        accepted: 120,
        revenue: 75000,
        acceptance_rate: 24,
        top_addons: [
          { name: 'Hair Spa', count: 100, revenue: 50000 },
          { name: 'Beard Trim', count: 15, revenue: 2250 },
          { name: 'Head Massage', count: 5, revenue: 1500 }
        ]
      });
    } finally {
      setIsUpsellStatsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'upsell-analytics') {
      fetchUpsellStats();
    }
  }, [activeTab]);

  const fetchReputationData = async () => {
    try {
      setIsReputationStatsLoading(true);
      setIsReputationReviewsLoading(true);
      const [statsRes, reviewsRes] = await Promise.all([
        apiClient.get('/reviews/analytics/stats'),
        apiClient.get('/reviews')
      ]);
      if (statsRes.data && statsRes.data.success) {
        setReputationStats(statsRes.data.analytics);
      }
      if (reviewsRes.data && reviewsRes.data.success) {
        setReputationReviews(reviewsRes.data.reviews);
      }
    } catch (err) {
      console.error('Failed to load reputation data:', err);
      // Fallback mocks
      setReputationStats({
        total_reviews: 800,
        average_rating: 4.6,
        sentiment_distribution: { positive: 700, neutral: 50, negative: 42, critical: 8 },
        ratings_distribution: { "1_star": 10, "2_star": 20, "3_star": 70, "4_star": 200, "5_star": 500 },
        top_complaints: [
          { category: "Waiting Time", count: 25 },
          { category: "Staff Availability", count: 12 },
          { category: "Pricing", count: 5 }
        ],
        most_praised: [
          { category: "Hair Styling", count: 450 },
          { category: "Customer Service", count: 210 },
          { category: "Cleanliness", count: 40 }
        ],
        escalated_count: 3,
        responded_count: 785
      });
      setReputationReviews([
        { id: 'rev-1', customer_name: 'Sarah Jenkins', rating: 5, comment: 'Clara booked me instantly with Marcus. The Signature Precision Haircut was spectacular!', status: 'APPROVED', sentiment: 'POSITIVE', ai_response: 'Thank you Sarah! We are thrilled Marcus delivered a spectacular style for you. Look forward to seeing you again!', escalation_required: false, responded: true, created_at: new Date().toISOString() },
        { id: 'rev-2', customer_name: 'Michael Miller', rating: 2, comment: 'The haircut was fine but my appointment started 45 minutes late. Very disappointed.', status: 'PENDING', sentiment: 'NEGATIVE', ai_response: null, escalation_required: false, responded: false, created_at: new Date().toISOString() },
        { id: 'rev-3', customer_name: 'David Jones', rating: 1, comment: 'Staff behavior was rude and I believe they tried to overcharge/scam me!', status: 'PENDING', sentiment: 'CRITICAL', ai_response: null, escalation_required: true, responded: false, created_at: new Date().toISOString() }
      ]);
    } finally {
      setIsReputationStatsLoading(false);
      setIsReputationReviewsLoading(false);
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
        fetchReputationData();
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
        fetchReputationData();
      }
    } catch (err: any) {
      window.alert(err.response?.data?.detail || 'Failed to escalate review.');
    }
  };

  useEffect(() => {
    if (activeTab === 'reputation') {
      fetchReputationData();
    }
  }, [activeTab]);

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
              { id: 'upsell-analytics', label: 'Upsell Analytics', icon: '⚡' },
              { id: 'reputation', label: 'Reputation Management', icon: '🛡️' },
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
            {activeTab === 'leads' && (() => {
              const filteredLeads = leads
                .filter(l => {
                  const s = leadsSearch.toLowerCase();
                  const matchSearch = 
                    (l.customer_name || '').toLowerCase().includes(s) ||
                    (l.customer_email || '').toLowerCase().includes(s) ||
                    (l.customer_phone || '').toLowerCase().includes(s) ||
                    (l.service_name || '').toLowerCase().includes(s) ||
                    (l.source || '').toLowerCase().includes(s);
                  
                  if (leadsFilter === 'ALL') return matchSearch;
                  return matchSearch && l.status === leadsFilter;
                })
                .sort((a, b) => {
                  if (leadsSort === 'SCORE') return (b.lead_score || 0) - (a.lead_score || 0);
                  if (leadsSort === 'DATE') return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
                  if (leadsSort === 'NAME') return (a.customer_name || '').localeCompare(b.customer_name || '');
                  return 0;
                });

              const topRecoverable = [...leads]
                .filter(l => l.status === 'NEW' || l.status === 'CONTACTED' || l.status === 'INTERESTED')
                .sort((a, b) => (b.lead_score || 0) - (a.lead_score || 0))
                .slice(0, 5);

              return (
                <div className="space-y-6 animate-fade-in">
                  <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
                    <div>
                      <h2 className="text-xl font-black">🎯 Lead Follow-up Management</h2>
                      <p className="text-xs text-slate-500">Autonomous campaign supervisor for customer acquisition funnel.</p>
                    </div>
                  </div>

                  {/* Analytics Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="bg-slate-900/60 p-4.5 rounded-2xl border border-slate-800 text-center">
                      <span className="text-xl block">🎯</span>
                      <span className="block text-[10px] font-black text-slate-400 uppercase mt-1">Total Leads</span>
                      <span className="text-lg font-black block mt-0.5">{leadAnalytics.total_leads}</span>
                    </div>
                    <div className="bg-slate-900/60 p-4.5 rounded-2xl border border-slate-800 text-center">
                      <span className="text-xl block">✨</span>
                      <span className="block text-[10px] font-black text-slate-400 uppercase mt-1">New Leads</span>
                      <span className="text-lg font-black block mt-0.5">{leadAnalytics.new_leads}</span>
                    </div>
                    <div className="bg-slate-900/60 p-4.5 rounded-2xl border border-slate-800 text-center">
                      <span className="text-xl block">🎉</span>
                      <span className="block text-[10px] font-black text-slate-400 uppercase mt-1">Converted</span>
                      <span className="text-lg font-black block mt-0.5 text-emerald-400">{leadAnalytics.converted_leads}</span>
                    </div>
                    <div className="bg-slate-900/60 p-4.5 rounded-2xl border border-slate-800 text-center">
                      <span className="text-xl block">🛑</span>
                      <span className="block text-[10px] font-black text-slate-400 uppercase mt-1">Lost Leads</span>
                      <span className="text-lg font-black block mt-0.5 text-red-400">{leadAnalytics.lost_leads}</span>
                    </div>
                    <div className="bg-slate-900/60 p-4.5 rounded-2xl border border-slate-800 text-center col-span-2 md:col-span-1">
                      <span className="text-xl block">📈</span>
                      <span className="block text-[10px] font-black text-slate-400 uppercase mt-1">Conversion Rate</span>
                      <span className="text-lg font-black block mt-0.5 text-blue-400">{leadAnalytics.conversion_rate}%</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Main Lead Table */}
                    <div className="lg:col-span-2 space-y-4">
                      {/* Search & Filters */}
                      <div className="bg-slate-900/40 p-4 border border-slate-800 rounded-2xl flex flex-col sm:flex-row gap-3 justify-between items-center">
                        <input
                          type="text"
                          value={leadsSearch}
                          onChange={e => setLeadsSearch(e.target.value)}
                          placeholder="Search name, phone, service..."
                          className="w-full sm:max-w-xs px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs focus:outline-none"
                        />
                        <div className="flex gap-2 w-full sm:w-auto">
                          <select
                            value={leadsFilter}
                            onChange={e => setLeadsFilter(e.target.value)}
                            className="flex-1 sm:flex-none px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none"
                          >
                            <option value="ALL">All Statuses</option>
                            <option value="NEW">New</option>
                            <option value="CONTACTED">Contacted</option>
                            <option value="INTERESTED">Interested</option>
                            <option value="CONVERTED">Converted</option>
                            <option value="LOST">Lost</option>
                          </select>
                          <select
                            value={leadsSort}
                            onChange={e => setLeadsSort(e.target.value)}
                            className="flex-1 sm:flex-none px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none"
                          >
                            <option value="SCORE">Sort by Score</option>
                            <option value="DATE">Sort by Date</option>
                            <option value="NAME">Sort by Name</option>
                          </select>
                        </div>
                      </div>

                      {/* Lead Table card */}
                      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4 text-left">
                        <h3 className="text-sm font-extrabold text-white">Lead Catalog ({filteredLeads.length})</h3>
                        <div className="overflow-x-auto">
                          <table className="min-w-full divide-y divide-slate-800 text-sm">
                            <thead>
                              <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                                <th className="px-4 py-3 text-left">Lead Details</th>
                                <th className="px-4 py-3 text-left">Interested Service</th>
                                <th className="px-4 py-3 text-center">Score</th>
                                <th className="px-4 py-3 text-center">Status</th>
                                <th className="px-4 py-3 text-right">Acquisition</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/60">
                              {filteredLeads.map(lead => (
                                <tr key={lead.id} className="hover:bg-slate-850/30 transition-colors">
                                  <td className="px-4 py-4 whitespace-nowrap font-bold text-white">
                                    {lead.customer_name}
                                    <span className="block text-[10px] text-slate-500 font-semibold">{lead.customer_email || lead.email}</span>
                                  </td>
                                  <td className="px-4 py-4 whitespace-nowrap text-slate-300 font-medium">{lead.service_name || 'General Inquiry'}</td>
                                  <td className="px-4 py-4 whitespace-nowrap text-center font-black">
                                    <span className={`px-2 py-0.5 rounded text-[10px] ${
                                      (lead.lead_score || 0) >= 80 ? 'bg-red-500/10 text-red-400 font-bold' : 'bg-slate-800 text-slate-400'
                                    }`}>
                                      {lead.lead_score || 0} pts
                                    </span>
                                  </td>
                                  <td className="px-4 py-4 whitespace-nowrap text-center">
                                    <span className={`px-2.5 py-0.5 rounded text-[9px] font-bold border uppercase ${
                                      lead.status === 'NEW'
                                        ? 'bg-purple-500/10 border-purple-500/20 text-purple-400'
                                        : lead.status === 'CONTACTED'
                                        ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                                        : lead.status === 'INTERESTED'
                                        ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                                        : lead.status === 'CONVERTED'
                                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                                        : 'bg-slate-900 border-slate-800 text-slate-500'
                                    }`}>
                                      {lead.status}
                                    </span>
                                  </td>
                                  <td className="px-4 py-4 whitespace-nowrap text-right text-slate-500 text-xs">
                                    {lead.source || 'Website'}
                                    <span className="block text-[9px] text-slate-600 mt-0.5">{lead.created_at ? new Date(lead.created_at).toLocaleDateString() : ''}</span>
                                  </td>
                                </tr>
                              ))}
                              {filteredLeads.length === 0 && (
                                <tr>
                                  <td colSpan={5} className="text-center py-12 text-slate-500 text-xs font-semibold">
                                    No leads matched your search query or filters.
                                  </td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>

                    {/* Top Recoverable Leads Sidebar */}
                    <div className="space-y-4">
                      <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-5 shadow-xl space-y-4 text-left">
                        <div className="space-y-1">
                          <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                            <span>🔥</span> Top Recoverable Leads
                          </h3>
                          <p className="text-[11px] text-slate-500">Unconverted leads with the highest customer intent scores.</p>
                        </div>

                        <div className="space-y-3">
                          {topRecoverable.map(lead => (
                            <div key={lead.id} className="bg-slate-950/60 p-4 border border-slate-850 rounded-2xl flex items-center justify-between gap-3 hover:border-blue-500/30 transition-colors">
                              <div className="space-y-1 overflow-hidden">
                                <h4 className="text-xs font-extrabold text-white truncate">{lead.customer_name}</h4>
                                <span className="text-[10px] text-blue-400 block font-semibold truncate">{lead.service_name}</span>
                                <span className="inline-flex text-[9px] font-black bg-purple-500/10 text-purple-400 px-1.5 py-0.2 rounded uppercase mt-0.5">{lead.status}</span>
                              </div>
                              <div className="text-right">
                                <span className="text-xs font-black text-red-400 block">{lead.lead_score} pts</span>
                                <span className="text-[9px] text-slate-600 block mt-0.5 font-bold uppercase">{lead.source || 'Ad'}</span>
                              </div>
                            </div>
                          ))}
                          {topRecoverable.length === 0 && (
                            <div className="text-center py-8 text-slate-600 text-xs font-semibold">
                              All leads successfully converted!
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}

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

            {activeTab === 'upsell-analytics' && (
              <div className="space-y-6 animate-fade-in">
                <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
                  <div>
                    <h2 className="text-xl font-black">⚡ Automated Upsell & Revenue Analytics</h2>
                    <p className="text-xs text-slate-500">Live operational throughput, acceptance conversions, and total incremental yield generated by Upsell Agent.</p>
                  </div>
                  <button
                    onClick={fetchUpsellStats}
                    className="px-4 py-2 border border-slate-800 hover:text-white rounded-xl text-xs font-bold text-slate-400 cursor-pointer"
                  >
                    🔄 Refresh Stats
                  </button>
                </div>

                {isUpsellStatsLoading ? (
                  <div className="py-24 text-center text-slate-500 font-bold animate-pulse">
                    Aggregating upsell yield ledger...
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* 4 KPI Metrics Cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-blue-900/10 border border-blue-500/15 flex items-center justify-center text-2xl text-blue-400">
                          📢
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Recommendations Generated</span>
                          <span className="text-2xl font-black text-white block mt-0.5">{upsellStats.generated}</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Total offers presented</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-emerald-900/10 border border-emerald-500/15 flex items-center justify-center text-2xl text-emerald-400">
                          🎯
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Recommendations Accepted</span>
                          <span className="text-2xl font-black text-white block mt-0.5">{upsellStats.accepted}</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Conversions logged</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-amber-900/10 border border-amber-500/15 flex items-center justify-center text-2xl text-amber-400">
                          💰
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Total Revenue Generated</span>
                          <span className="text-2xl font-black text-amber-400 block mt-0.5">${upsellStats.revenue.toLocaleString()}</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Incremental booking yield</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-purple-900/10 border border-purple-500/15 flex items-center justify-center text-2xl text-purple-400">
                          📈
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Acceptance Rate</span>
                          <span className="text-2xl font-black text-white block mt-0.5">{upsellStats.acceptance_rate}%</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Conversion efficiency</span>
                        </div>
                      </div>
                    </div>

                    {/* Top Add-ons Table */}
                    <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                      <div className="flex justify-between items-center">
                        <h3 className="text-sm font-extrabold text-slate-400 uppercase tracking-wider">🏆 Top Add-on Services</h3>
                        <span className="px-2 py-0.5 bg-blue-500/10 text-blue-450 border border-blue-500/20 rounded text-[9px] font-black uppercase tracking-widest">
                          Best Performing Services
                        </span>
                      </div>
                      
                      {(!upsellStats.top_addons || upsellStats.top_addons.length === 0) ? (
                        <div className="text-center text-slate-500 py-8 text-xs font-semibold">
                          No add-on services converted yet.
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="min-w-full divide-y divide-slate-800 text-sm">
                            <thead>
                              <tr className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                                <th className="px-4 py-3 text-left">Recommended Service Name</th>
                                <th className="px-4 py-3 text-center">Conversions Count</th>
                                <th className="px-4 py-3 text-right">Revenue Generated</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/60">
                              {upsellStats.top_addons.map((addon: any, idx: number) => (
                                <tr key={idx} className="hover:bg-slate-850/30 transition-colors">
                                  <td className="px-4 py-4 whitespace-nowrap font-bold text-white flex items-center space-x-2">
                                    <span className="text-slate-500 font-black">#{idx + 1}</span>
                                    <span>{addon.name}</span>
                                  </td>
                                  <td className="px-4 py-4 whitespace-nowrap text-center text-slate-300 font-extrabold">
                                    {addon.count} times
                                  </td>
                                  <td className="px-4 py-4 whitespace-nowrap text-right text-emerald-400 font-black">
                                    ${addon.revenue.toLocaleString()}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'reputation' && (
              <div className="space-y-6 animate-fade-in">
                <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
                  <div>
                    <h2 className="text-xl font-black">🛡️ Reputation Shield & Review Management</h2>
                    <p className="text-xs text-slate-500">Autonomous sentiment moderator, rating scorecard, and manual manager feedback responder.</p>
                  </div>
                  <button
                    onClick={fetchReputationData}
                    className="px-4 py-2 border border-slate-800 hover:text-white rounded-xl text-xs font-bold text-slate-400 cursor-pointer"
                  >
                    🔄 Refresh Stats
                  </button>
                </div>

                {isReputationStatsLoading ? (
                  <div className="py-24 text-center text-slate-500 font-bold animate-pulse">
                    Aggregating brand reputation scorecard...
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* 4 KPI Scorecard Cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-blue-900/10 border border-blue-500/15 flex items-center justify-center text-2xl text-blue-400">
                          📊
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Total Reviews</span>
                          <span className="text-2xl font-black text-white block mt-0.5">{reputationStats.total_reviews}</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">All submitted feedback</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-amber-900/10 border border-amber-500/15 flex items-center justify-center text-2xl text-amber-400">
                          🏆
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Average Rating</span>
                          <span className="text-2xl font-black text-white block mt-0.5">{reputationStats.average_rating} ★</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Out of 5.0 stars</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-red-900/10 border border-red-500/15 flex items-center justify-center text-2xl text-red-400">
                          ⚠️
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Negative Reviews</span>
                          <span className="text-2xl font-black text-red-400 block mt-0.5">{reputationStats.sentiment_distribution?.negative || 0}</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Rating &lt;= 2 stars</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
                        <div className="w-12 h-12 rounded-xl bg-purple-900/10 border border-purple-500/15 flex items-center justify-center text-2xl text-purple-400">
                          🚨
                        </div>
                        <div>
                          <span className="block text-[10px] font-black text-slate-400 uppercase tracking-wider">Critical Reviews</span>
                          <span className="text-2xl font-black text-purple-400 block mt-0.5">{reputationStats.escalated_count}</span>
                          <span className="text-[9px] text-slate-500 block mt-0.5 font-bold uppercase">Escalated to Manager</span>
                        </div>
                      </div>
                    </div>

                    {/* Analytics panels */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                      
                      {/* Ratings Distribution Bar list */}
                      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                        <h3 className="text-sm font-extrabold text-white flex items-center gap-2">⭐ Ratings Distribution</h3>
                        <div className="space-y-3 pt-2">
                          {[5, 4, 3, 2, 1].map((stars) => {
                            const count = reputationStats.ratings_distribution?.[`${stars}_star`] || 0;
                            const total = reputationStats.total_reviews || 1;
                            const pct = Math.round((count / total) * 100);
                            return (
                              <div key={stars} className="flex items-center gap-3 text-xs">
                                <span className="w-10 text-slate-400 font-bold whitespace-nowrap text-left">{stars} ★</span>
                                <div className="flex-1 h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-850">
                                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                                </div>
                                <span className="w-8 text-slate-500 text-right font-semibold">{count}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Top Complaints Card */}
                      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                        <h3 className="text-sm font-extrabold text-white flex items-center gap-2">👎 Top Complaints</h3>
                        <div className="space-y-3 pt-2">
                          {reputationStats.top_complaints?.length === 0 ? (
                            <p className="text-xs text-slate-500 py-4 font-semibold text-center">No complaints flagged. Great job stylist team!</p>
                          ) : (
                            reputationStats.top_complaints?.map((comp: any, idx: number) => (
                              <div key={idx} className="bg-slate-955 border border-slate-850 p-3.5 rounded-2xl flex items-center justify-between">
                                <span className="text-xs font-bold text-slate-350">{comp.category}</span>
                                <span className="px-2 py-0.5 bg-red-950/40 border border-red-900/40 text-red-400 rounded text-[10px] font-black">{comp.count} mentions</span>
                              </div>
                            ))
                          )}
                        </div>
                      </div>

                      {/* Most Praised Card */}
                      <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
                        <h3 className="text-sm font-extrabold text-white flex items-center gap-2">👍 Most Praised Aspects</h3>
                        <div className="space-y-3 pt-2">
                          {reputationStats.most_praised?.length === 0 ? (
                            <p className="text-xs text-slate-500 py-4 font-semibold text-center">Praise comments are still processing...</p>
                          ) : (
                            reputationStats.most_praised?.map((praise: any, idx: number) => (
                              <div key={idx} className="bg-slate-955 border border-slate-850 p-3.5 rounded-2xl flex items-center justify-between">
                                <span className="text-xs font-bold text-slate-350">{praise.category}</span>
                                <span className="px-2 py-0.5 bg-emerald-950/40 border border-emerald-900/45 text-emerald-400 rounded text-[10px] font-black">+{praise.count} mentions</span>
                              </div>
                            ))
                          )}
                        </div>
                      </div>

                    </div>

                    {/* Review Feed Scoped list */}
                    <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-5 text-left">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-850 pb-4">
                        <h3 className="text-sm font-extrabold text-white">Client Reviews Ledger</h3>
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

                      {isReputationReviewsLoading ? (
                        <div className="py-12 text-center text-slate-500 font-bold animate-pulse text-xs">
                          Fetching latest feedback feed...
                        </div>
                      ) : (
                        (() => {
                          const filtered = reputationReviews.filter((rev) => {
                            if (reputationFilter === 'NEGATIVE') return rev.sentiment === 'NEGATIVE' || rev.rating <= 2;
                            if (reputationFilter === 'CRITICAL') return rev.sentiment === 'CRITICAL' || rev.escalation_required;
                            return true;
                          });

                          return (
                            <div className="space-y-4">
                              {filtered.length === 0 ? (
                                <p className="text-xs text-slate-500 py-12 font-semibold text-center">No customer reviews matching this status filter.</p>
                              ) : (
                                filtered.map((rev) => (
                                  <div key={rev.id} className="bg-slate-950 border border-slate-850 p-5 rounded-2xl space-y-3 relative hover:border-slate-800 transition-colors">
                                    <div className="flex justify-between items-start flex-wrap gap-2 text-xs">
                                      <div className="space-y-0.5">
                                        <h4 className="font-extrabold text-white flex items-center gap-2">
                                          <span>{rev.customer_name}</span>
                                          {rev.staff_name && (
                                            <span className="px-2 py-0.5 bg-slate-900 border border-slate-850 text-slate-450 rounded text-[9px] font-medium font-sans">Stylist: {rev.staff_name}</span>
                                          )}
                                        </h4>
                                        <span className="text-[10px] text-slate-500 block font-semibold">{rev.created_at ? rev.created_at.split('T')[0] : 'Just now'}</span>
                                      </div>
                                      
                                      <div className="flex items-center gap-2">
                                        <div className="flex text-amber-400 text-sm mr-2">
                                          {'★'.repeat(rev.rating)}{'☆'.repeat(5 - rev.rating)}
                                        </div>
                                        <span className={`px-2 py-0.5 rounded text-[9px] font-black border tracking-wider ${
                                          rev.sentiment === 'POSITIVE'
                                            ? 'bg-emerald-950/20 text-emerald-450 border-emerald-900/35'
                                            : rev.sentiment === 'NEUTRAL'
                                            ? 'bg-blue-900/20 text-blue-350 border-blue-800/40'
                                            : rev.sentiment === 'NEGATIVE'
                                            ? 'bg-red-950/20 text-red-400 border-red-900/35'
                                            : 'bg-purple-950/30 text-purple-400 border-purple-900/35'
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
                                          <span className="px-2.5 py-1 bg-purple-950/40 border border-purple-900/45 text-purple-400 rounded-lg text-[10px] font-black uppercase flex items-center gap-1 shadow-md shadow-purple-950/15">
                                            🚨 Escalated To Manager
                                          </span>
                                        ) : (
                                          <button
                                            onClick={() => handleEscalateReview(rev.id)}
                                            className="px-3 py-1.5 bg-slate-900 hover:bg-slate-850 border border-slate-850 hover:border-slate-750 text-slate-400 hover:text-white rounded-lg text-[10px] font-extrabold uppercase transition-all cursor-pointer animate-fade-in"
                                          >
                                            Escalate To Manager
                                          </button>
                                        )}
                                      </div>

                                      <div className="flex gap-2">
                                        {rev.ai_response && replyingReviewId !== rev.id && (
                                          <span className="text-[10px] text-slate-500 font-bold bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-850">
                                            Response Registered
                                          </span>
                                        )}
                                        {replyingReviewId !== rev.id && (
                                          <button
                                            onClick={() => {
                                              setReplyingReviewId(rev.id);
                                              setResponseText(rev.ai_response || '');
                                            }}
                                            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-black uppercase transition-all shadow-md shadow-blue-500/10 cursor-pointer"
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
                                          <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Salon Reply Draft</label>
                                          <textarea
                                            value={responseText}
                                            onChange={(e) => setResponseText(e.target.value)}
                                            placeholder="Write your review reply or use dynamic Brand Guidelines guidelines..."
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
                                ))
                              )}
                            </div>
                          );
                        })()
                      )}
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
