import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';
import { AgentChat } from '../AgentChat/AgentChat';
import { useLoyalty } from '../../hooks/useLoyalty';
import { LoyaltyCard } from '../Loyalty/LoyaltyCard';
import { loyaltySyncService } from '../../services/LoyaltySyncService';

interface AppointmentRecord {
  id: string;
  start_time: string;
  end_time: string;
  status: string;
  notes: string | null;
  service: {
    name: string;
    price: number;
    duration_minutes: number;
  };
  staff: {
    id?: string;
    first_name: string;
    last_name: string;
  } | null;
  branch: {
    id?: string;
    name: string;
    city: string;
  };
}

interface ServiceItem {
  id: string;
  name: string;
  description: string;
  price: number;
  duration_minutes: number;
}

interface BranchItem {
  id: string;
  name: string;
  city: string;
}

interface StaffItem {
  id: string;
  first_name: string;
  last_name: string;
  role: string;
}

interface NotificationItem {
  id: string;
  type: 'success' | 'info' | 'warning';
  title: string;
  message: string;
  timestamp: string;
}

/**
 * Format ISO datetime string in UTC without browser timezone conversion.
 * Converts "2026-06-07T13:00:00Z" to "June 7, 2026 at 1:00 PM" (UTC)
 */
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
    // Use UTC methods to avoid timezone conversion
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth();
    const day = date.getUTCDate();
    const hours = date.getUTCHours();
    const minutes = date.getUTCMinutes();
    
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'];
    
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    const displayMinutes = minutes.toString().padStart(2, '0');
    
    return `${monthNames[month]} ${day}, ${year} at ${displayHours}:${displayMinutes} ${ampm}`;
  } catch (err) {
    return 'Invalid date';
  }
};

/**
 * Format ISO date string to YYYY-MM-DD in UTC without browser timezone conversion.
 */
const formatUTCDate = (isoString: string): string => {
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
    const month = (date.getUTCMonth() + 1).toString().padStart(2, '0');
    const day = date.getUTCDate().toString().padStart(2, '0');
    return `${year}-${month}-${day}`;
  } catch (err) {
    return 'Invalid date';
  }
};

/**
 * Extract date and time from ISO string for pre-populating inputs.
 */
const getInitialDateTimeForReschedule = (isoString: string) => {
  if (!isoString) return { date: '', time: '' };
  try {
    let normalized = isoString;
    if (isoString && !isoString.endsWith('Z') && !isoString.includes('+')) {
      const parts = isoString.split(/T|\s/);
      const hasTimeOffset = parts.length > 1 && parts[1].includes('-');
      if (!hasTimeOffset) {
        normalized = isoString + 'Z';
      }
    }
    const dateObj = new Date(normalized);
    const year = dateObj.getUTCFullYear();
    const month = (dateObj.getUTCMonth() + 1).toString().padStart(2, '0');
    const day = dateObj.getUTCDate().toString().padStart(2, '0');
    const hours = dateObj.getUTCHours().toString().padStart(2, '0');
    const minutes = dateObj.getUTCMinutes().toString().padStart(2, '0');
    return {
      date: `${year}-${month}-${day}`,
      time: `${hours}:${minutes}`
    };
  } catch (err) {
    return { date: '', time: '' };
  }
};

export const UserDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  
  // Navigation & active views
  const [activeTab, setActiveTab] = useState<'dashboard' | 'book' | 'my-appointments' | 'history' | 'assistant' | 'services' | 'notifications' | 'profile' | 'recommendations' | 'reviews'>('dashboard');
  
  // Data loading states
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [staff, setStaff] = useState<StaffItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Loyalty Points State - using custom hook
  const { loyaltyPoints, memberRank, isLoading: loyaltyLoading, refreshLoyalty } = useLoyalty();

  // Recommendations state variables
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState<boolean>(false);
  const [justBookedAppt, setJustBookedAppt] = useState<{ id: string; serviceName: string } | null>(null);

  // Reviews state variables
  const [customerReviews, setCustomerReviews] = useState<any[]>([]);
  const [isReviewsLoading, setIsReviewsLoading] = useState<boolean>(false);

  // My Appointments Tab state
  const [appointmentTab, setAppointmentTab] = useState<'upcoming' | 'completed' | 'cancelled'>('upcoming');

  // Reschedule state
  const [reschedulingAppt, setReschedulingAppt] = useState<AppointmentRecord | null>(null);
  const [newRescheduleDate, setNewRescheduleDate] = useState<string>('');
  const [newRescheduleTime, setNewRescheduleTime] = useState<string>('');

  // Review submission state
  const [reviewingAppt, setReviewingAppt] = useState<AppointmentRecord | null>(null);
  const [ratingValue, setRatingValue] = useState<number>(5);
  const [reviewComment, setReviewComment] = useState<string>('');

  // Step-by-Step Booking Wizard states
  const [bookingStep, setBookingStep] = useState<number>(1);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [selectedService, setSelectedService] = useState<string>('');
  const [selectedStylist, setSelectedStylist] = useState<string>('any');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [selectedTime, setSelectedTime] = useState<string>('');
  const [bookingNotes, setBookingNotes] = useState<string>('');
  const [isUpsellAccepted, setIsUpsellAccepted] = useState<boolean>(false);
  const [isBookingSubmitting, setIsBookingSubmitting] = useState<boolean>(false);

  // User Profile Preferences state
  const [prefBranch, setPrefBranch] = useState<string>('');
  const [prefStylist, setPrefStylist] = useState<string>('');
  const [prefService, setPrefService] = useState<string>('');

  // Notification center alerts
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [activeLead, setActiveLead] = useState<any>(null);

  // Load backend data
  const fetchData = async (silent = false) => {
    try {
      if (!silent) setIsLoading(true);
      
      // Loyalty points are now fetched via useLoyalty hook
      // No need to fetch here anymore
      refreshLoyalty();
      
      // Load services & branches
      const srvRes = await apiClient.get<ServiceItem[]>('/services');
      setServices(srvRes.data);

      const branchRes = await apiClient.get<BranchItem[]>('/branches');
      setBranches(branchRes.data);

      // Load client's appointments
      const apptRes = await apiClient.get<AppointmentRecord[]>('/appointments/my');
      setAppointments(apptRes.data);

      // Load notifications dynamically
      const notifRes = await apiClient.get<any[]>('/notifications').catch(() => ({ data: [] }));
      if (notifRes.data && notifRes.data.length > 0) {
        setNotifications(notifRes.data.map((n: any) => ({
          id: n.id,
          type: n.is_read ? 'info' : 'warning',
          title: n.title,
          message: n.message,
          timestamp: new Date(n.created_at).toLocaleTimeString() + ' ' + new Date(n.created_at).toLocaleDateString()
        })));
      } else {
        setNotifications([]);
      }

      // Load active lead
      try {
        const leadRes = await apiClient.get('/leads/active');
        setActiveLead(leadRes.data || null);
      } catch (err) {
        setActiveLead(null);
      }
    } catch (err) {
      console.warn('Backend offline or not returning customer data');
      setNotifications([]);
      setServices([]);
      setBranches([]);
      setAppointments([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Load local storage preferences if available
    setPrefBranch(localStorage.getItem('pref_branch') || '');
    setPrefStylist(localStorage.getItem('pref_stylist') || '');
    setPrefService(localStorage.getItem('pref_service') || '');
  }, []);

  // Handle staff loading when branch changes
  useEffect(() => {
    const fetchStaff = async () => {
      if (!selectedBranch) return;
      try {
        const staffRes = await apiClient.get<StaffItem[]>(`/branches/${selectedBranch}/staff`);
        setStaff(staffRes.data);
      } catch (err) {
        console.warn('Failed to load branch stylists');
        setStaff([]);
      }
    };
    fetchStaff();
  }, [selectedBranch]);

  // Synchronize manual booking drafts to the backend Lead Recovery System
  useEffect(() => {
    // We only want to save a draft if the user has selected at least one option
    if (!selectedBranch && !selectedService && selectedStylist === 'any' && !selectedDate && !selectedTime) {
      return;
    }
    
    // Do not save draft if they are currently submitting/finalizing
    if (isBookingSubmitting) {
      return;
    }

    const saveDraftLead = async () => {
      try {
        await apiClient.post('/leads/draft', {
          branch_id: selectedBranch || null,
          service_id: selectedService || null,
          staff_id: selectedStylist === 'any' ? null : selectedStylist,
          date: selectedDate || null,
          time: selectedTime || null,
          notes: bookingNotes || null
        });
      } catch (err) {
        console.warn('Failed to update lead draft on backend:', err);
      }
    };

    // Debounce the draft save to avoid spamming the backend
    const timeoutId = setTimeout(saveDraftLead, 1000);
    return () => clearTimeout(timeoutId);
  }, [selectedBranch, selectedService, selectedStylist, selectedDate, selectedTime, bookingNotes]);

  const showToast = (text: string, type: 'success' | 'error') => {
    setToastMessage({ text, type });
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  const fetchRecommendations = async () => {
    if (!user?.customer_id) return;
    try {
      setIsRecommendationsLoading(true);
      const res = await apiClient.get(`/recommendations/${user.customer_id}`);
      if (res.data && res.data.success) {
        setRecommendations(res.data.recommendations);
      }
    } catch (err) {
      console.error('Failed to fetch recommendations:', err);
    } finally {
      setIsRecommendationsLoading(false);
    }
  };

  const handleAcceptRecommendation = async (rec: any) => {
    if (!user?.customer_id) return;
    try {
      const res = await apiClient.post('/recommendations/accept', {
        customer_id: user.customer_id,
        service_id: rec.service_id,
        appointment_id: rec.appointment_id || (justBookedAppt ? justBookedAppt.id : null)
      });
      if (res.data && res.data.success) {
        showToast(res.data.message || 'Recommendation accepted successfully!', 'success');
        fetchData(true);
        fetchRecommendations();
      }
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to accept recommendation.', 'error');
    } finally {
      if (justBookedAppt) setJustBookedAppt(null);
    }
  };

  const handleRejectRecommendation = async (rec: any) => {
    if (!user?.customer_id) return;
    try {
      await apiClient.post('/recommendations/reject', {
        customer_id: user.customer_id,
        service_id: rec.service_id,
        appointment_id: rec.appointment_id || (justBookedAppt ? justBookedAppt.id : null)
      });
      fetchRecommendations();
    } catch (err: any) {
      console.warn('Failed to dismiss recommendation in database:', err);
    } finally {
      if (justBookedAppt) setJustBookedAppt(null);
    }
  };

  useEffect(() => {
    if (activeTab === 'recommendations') {
      fetchRecommendations();
    }
  }, [activeTab]);

  const fetchCustomerReviews = async () => {
    try {
      setIsReviewsLoading(true);
      const res = await apiClient.get('/reviews');
      if (res.data && res.data.success) {
        setCustomerReviews(res.data.reviews);
      }
    } catch (err) {
      console.error('Failed to load reviews:', err);
    } finally {
      setIsReviewsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'reviews') {
      fetchCustomerReviews();
    }
  }, [activeTab]);

  // Perform Smart Rebooking in one click
  const handleSmartRebook = (lastService: string, lastStylist: string, lastBranch: string) => {
    const foundService = services.find(s => s.name === lastService || s.id === lastService);
    const foundBranch = branches.find(b => b.name === lastBranch || b.id === lastBranch);
    
    if (foundBranch) setSelectedBranch(foundBranch.id);
    if (foundService) setSelectedService(foundService.id);
    setSelectedStylist(lastStylist || 'any');
    
    // Set to tomorrow at 5pm automatically
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    setSelectedDate(tomorrowStr);
    setSelectedTime('17:00');
    setBookingNotes('One-click smart rebooked session');
    
    // Move to confirm step
    setBookingStep(5);
    setActiveTab('book');
  };

  // Reschedule logic
  const handleRescheduleSubmit = async () => {
    if (!reschedulingAppt || !newRescheduleDate || !newRescheduleTime) return;
    
    const newStartTime = `${newRescheduleDate}T${newRescheduleTime}:00Z`;
    
    // Check if the selected date and time is in the future
    const now = new Date();
    const selectedDateTime = new Date(newStartTime);
    if (selectedDateTime <= now) {
      showToast('Appointments must be in the future.', 'error');
      return;
    }
    
    try {
      await apiClient.post(`/appointments/${reschedulingAppt.id}/reschedule`, {
        new_start_time: newStartTime
      });
      showToast('Appointment rescheduled successfully!', 'success');
      setReschedulingAppt(null);
      fetchData(true);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Rescheduling failed. Slot might be unavailable.';
      showToast(errorMsg, 'error');
    }
  };

  // Cancel logic
  const handleCancelAppointment = async (apptId: string) => {
    if (!window.confirm('Are you sure you want to cancel this booking?')) return;
    try {
      await apiClient.delete(`/appointments/${apptId}`);
      showToast('Booking cancelled successfully.', 'success');
      // Trigger loyalty refresh when appointment is cancelled
      loyaltySyncService.emit('appointment_cancelled');
      fetchData(true);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to cancel booking.', 'error');
    }
  };

  // Review submission logic
  const handleReviewSubmit = async () => {
    if (!reviewingAppt) return;
    try {
      await apiClient.post('/reviews', {
        appointment_id: reviewingAppt.id,
        rating: ratingValue,
        comment: reviewComment
      });
      showToast('Review submitted successfully! Thank you.', 'success');
      setReviewingAppt(null);
      setReviewComment('');
      setRatingValue(5);
      // Trigger loyalty refresh when review is submitted
      loyaltySyncService.emit('review_submitted');
      fetchData(true);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to submit review.', 'error');
    }
  };

  // Resume booking from active lead
  const handleResumeBooking = async () => {
    let currentServices = services;
    if (services.length === 0) {
      try {
        const srvRes = await apiClient.get<ServiceItem[]>('/services');
        setServices(srvRes.data);
        currentServices = srvRes.data;
      } catch (e) {
        console.warn('Failed to load services on resume booking', e);
      }
    }
    
    try {
      const res = await apiClient.get<any>('/leads/active');
      if (res.data) {
        const lead = res.data;
        if (lead.branch_id) {
          setSelectedBranch(lead.branch_id);
          // Pre-fetch staff immediately to ensure it's loaded in state for step 4/5 stylist name lookup
          try {
            const staffRes = await apiClient.get<StaffItem[]>(`/branches/${lead.branch_id}/staff`);
            setStaff(staffRes.data);
          } catch (e) {
            console.warn('Failed to pre-fetch branch staff', e);
          }
        }
        
        let matchedServiceId = '';
        if (lead.service_name) {
          const matchedService = currentServices.find(s => s.name === lead.service_name);
          if (matchedService) {
            setSelectedService(matchedService.id);
            matchedServiceId = matchedService.id;
          }
        }
        
        if (lead.assigned_staff) setSelectedStylist(lead.assigned_staff);
        if (lead.preferred_date) setSelectedDate(lead.preferred_date);
        if (lead.preferred_time) {
          // Format preferred_time (HH:MM or HH:MM:SS) to HH:MM
          const timeStr = lead.preferred_time.substring(0, 5);
          setSelectedTime(timeStr);
        }
        
        // Navigate based on details populated
        if (lead.branch_id && matchedServiceId && lead.preferred_date && lead.preferred_time) {
          setBookingStep(5);
        } else if (lead.branch_id && matchedServiceId && lead.assigned_staff) {
          setBookingStep(4);
        } else if (lead.branch_id && matchedServiceId) {
          setBookingStep(3);
        } else if (lead.branch_id) {
          setBookingStep(2);
        } else {
          setBookingStep(1);
        }
      } else {
        setBookingStep(1);
      }
    } catch (err) {
      console.warn('Failed to fetch active lead details, falling back to step 1', err);
      setBookingStep(1);
    }
    setActiveTab('book');
  };

  // Booking submit logic
  const handleFinalizeBooking = async () => {
    if (!selectedBranch || !selectedService || !selectedDate || !selectedTime) {
      showToast('Please complete all wizard steps.', 'error');
      return;
    }

    const startTime = `${selectedDate}T${selectedTime}:00Z`;

    // Check if the selected date and time is in the future
    const now = new Date();
    const selectedDateTime = new Date(startTime);
    if (selectedDateTime <= now) {
      showToast('Appointments must be in the future.', 'error');
      return;
    }

    setIsBookingSubmitting(true);
    const finalNotes = isUpsellAccepted 
      ? `${bookingNotes ? bookingNotes + ' | ' : ''}Accepted Special head-massage upsell bundle ($25)` 
      : bookingNotes;

    try {
      const res = await apiClient.post('/appointments', {
        branch_id: selectedBranch,
        service_id: selectedService,
        start_time: startTime,
        staff_id: selectedStylist === 'any' ? null : selectedStylist,
        notes: finalNotes || null
      });
      
      showToast('Styling session booked successfully!', 'success');
      
      const newApptId = res.data.appointment_id;
      const serviceName = res.data.service_name || services.find(s => s.id === selectedService)?.name || '';

      // Reset wizard
      setBookingStep(1);
      setSelectedBranch('');
      setSelectedService('');
      setSelectedStylist('any');
      setSelectedDate('');
      setSelectedTime('');
      setBookingNotes('');
      setIsUpsellAccepted(false);
      
      // Navigate back to My Appointments
      setActiveTab('my-appointments');
      setAppointmentTab('upcoming');
      // Trigger loyalty refresh after successful booking
      loyaltySyncService.emit('appointment_completed');
      fetchData(true);

      // Open recommendations fetch popup immediately
      if (newApptId && user?.customer_id) {
        setJustBookedAppt({ id: newApptId, serviceName });
        // Fetch recommendations directly so they are immediately visible
        const recRes = await apiClient.get(`/recommendations/${user.customer_id}`);
        if (recRes.data && recRes.data.success) {
          setRecommendations(recRes.data.recommendations);
        }
      }
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Double booking error: Client or Stylist is busy at this slot.', 'error');
    } finally {
      setIsBookingSubmitting(false);
    }
  };

  // Preference update logic
  const savePreferences = () => {
    localStorage.setItem('pref_branch', prefBranch);
    localStorage.setItem('pref_stylist', prefStylist);
    localStorage.setItem('pref_service', prefService);
    showToast('Dashboard style preferences updated successfully.', 'success');
  };

  // Filter list helper
  const getFilteredAppointments = (tab: 'upcoming' | 'completed' | 'cancelled') => {
    return appointments.filter(appt => {
      const status = appt.status.toUpperCase();
      if (tab === 'upcoming') return status === 'CONFIRMED' || status === 'PENDING';
      if (tab === 'completed') return status === 'COMPLETED';
      return status === 'CANCELLED' || status === 'CANCELED';
    });
  };

  return (
    <div className="flex flex-col lg:flex-row min-h-screen bg-slate-950 text-white font-sans">
      
      {/* ============================================================================
          SIDEBAR NAVIGATION BAR
          ============================================================================ */}
      <aside className="w-full lg:w-72 bg-slate-900 border-b lg:border-b-0 lg:border-r border-slate-800/80 p-6 flex flex-col justify-between">
        <div className="space-y-8">
          {/* Custom Salon Brand Header */}
          <div className="text-left pb-4 border-b border-slate-800">
            <h2 className="text-2xl font-black bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              SalonAI Elite
            </h2>
            <span className="block text-[8px] tracking-widest text-slate-500 uppercase font-black -mt-0.5">Customer Experience Portal</span>
          </div>

          {/* Navigation Links */}
          <nav className="flex flex-col gap-1.5">
            {[
              { id: 'dashboard', label: 'Dashboard Home', icon: '🏠' },
              { id: 'recommendations', label: 'Recommended For You', icon: '💡' },
              { id: 'book', label: 'Book Appointment', icon: '📅' },
              { id: 'my-appointments', label: 'My Appointments', icon: '⏰' },
              { id: 'reviews', label: 'My Feedback Reviews', icon: '⭐' },
              { id: 'history', label: 'Booking History', icon: '📜' },
              { id: 'assistant', label: 'AI Receptionist', icon: '🤖' },
              { id: 'services', label: 'Services Catalog', icon: '💇' },
              { id: 'notifications', label: 'Notifications Center', icon: '🔔', badge: notifications.filter(n => n.type === 'warning').length },
              { id: 'profile', label: 'Profile Settings', icon: '👤' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id as any);
                  setBookingStep(1); // Reset booking wizard whenever switching
                }}
                className={`flex items-center justify-between px-4 py-3 rounded-2xl text-xs font-bold text-left transition-all duration-300 cursor-pointer ${
                  activeTab === tab.id
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
                }`}
              >
                <div className="flex items-center space-x-3.5">
                  <span className="text-lg">{tab.icon}</span>
                  <span>{tab.label}</span>
                </div>
                {tab.badge !== undefined && tab.badge > 0 ? (
                  <span className="px-2 py-0.5 text-[9px] font-black bg-red-500 text-white rounded-full animate-pulse">
                    {tab.badge}
                  </span>
                ) : null}
              </button>
            ))}
          </nav>
        </div>

        {/* Logged in User Profile Footer */}
        <div className="mt-8 pt-4 border-t border-slate-800 text-left space-y-3">
          <div>
            <span className="block text-[9px] font-black text-slate-500 uppercase tracking-widest">Client Session</span>
            <span className="block text-xs font-extrabold text-slate-300 truncate mt-0.5">{user?.email}</span>
            <span className="inline-block mt-1 px-2.5 py-0.5 rounded-full text-[8px] font-black bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase tracking-widest">
              🥇 Gold Tier Member
            </span>
          </div>
          <button
            onClick={logout}
            className="w-full py-2.5 bg-red-950/20 hover:bg-red-900/30 border border-red-900/20 text-red-400 hover:text-red-300 rounded-xl text-xs font-bold tracking-wider transition-all duration-300 cursor-pointer text-center"
          >
            🚪 Logout Securely
          </button>
        </div>
      </aside>

      {/* ============================================================================
          MAIN BODY VIEWPORTS
          ============================================================================ */}
      <main className="flex-1 p-6 lg:p-10 text-left overflow-y-auto max-h-screen">
        
        {/* Toast Alerts Banner */}
        {toastMessage && (
          <div className={`fixed top-6 right-6 z-50 px-5 py-4 rounded-2xl shadow-2xl text-xs font-bold animate-fade-in border ${
            toastMessage.type === 'success' 
              ? 'bg-emerald-950/90 border-emerald-500/30 text-emerald-400 shadow-emerald-950/40' 
              : 'bg-red-950/90 border-red-500/30 text-red-400 shadow-red-950/40'
          }`}>
            <span className="flex items-center space-x-2">
              <span>{toastMessage.type === 'success' ? '✓' : '⚠'}</span>
              <span>{toastMessage.text}</span>
            </span>
          </div>
        )}

        {isLoading ? (
          <div className="h-[60vh] flex flex-col items-center justify-center space-y-4">
            <div className="w-10 h-10 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
            <span className="text-xs font-black text-slate-500 uppercase tracking-widest animate-pulse">Syncing client portfolio context...</span>
          </div>
        ) : (
          <div className="space-y-8 animate-fade-in">

            {/* ============================================================================
                VIEW 1: DASHBOARD HOME
                ============================================================================ */}
            {activeTab === 'dashboard' && (
              <div className="space-y-8">
                
                {/* Gold Tier Lounge Banner */}
                <section className="bg-gradient-to-r from-blue-900/40 to-indigo-950/40 rounded-3xl p-6 lg:p-8 border border-slate-800/80 flex flex-col lg:flex-row items-center justify-between gap-6">
                  <div className="space-y-3">
                    <span className="px-3 py-1 text-[9px] font-black bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full uppercase tracking-widest">
                      Member Welcome
                    </span>
                    <h2 className="text-3xl font-black tracking-tight text-white">Your Zenoti Styling Lounge</h2>
                    <p className="text-xs text-slate-400 max-w-xl leading-relaxed">
                      Enjoy elite membership rewards. Check out your real-time styling parameters, active upcoming reservations, or launch a booking instantly.
                    </p>
                  </div>
                  
                  {/* Loyalty Points Metrics Grid - using new LoyaltyCard component */}
                  <LoyaltyCard 
                    loyaltyPoints={loyaltyPoints}
                    memberRank={memberRank}
                    isLoading={loyaltyLoading}
                    onRefresh={refreshLoyalty}
                  />
                </section>

                {/* ─── LEAD FOLLOW-UP BANNER (shown when staff has contacted the customer or they have a draft) ─── */}
                {activeLead && (activeLead.status === 'CONTACTED' || activeLead.status === 'NEW') && (
                  <div className="bg-gradient-to-r from-amber-950/60 to-orange-950/60 border border-amber-500/30 rounded-2xl p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
                    <div className="space-y-1">
                      <span className="text-[9px] font-black text-amber-400 uppercase tracking-widest animate-pulse">
                        {activeLead.status === 'CONTACTED' ? '💬 Our Team Reached Out' : '✏️ Unfinished Booking'}
                      </span>
                      <h4 className="text-sm font-extrabold text-white">
                        {activeLead.status === 'CONTACTED'
                          ? `You have an unfinished booking for ${activeLead.service_name || 'a salon service'}`
                          : `Resume your booking for ${activeLead.service_name || 'a salon service'}`}
                      </h4>
                      <p className="text-xs text-slate-400">
                        {activeLead.status === 'CONTACTED'
                          ? 'Pick up where you left off — your preferences are saved.'
                          : 'You were in the middle of scheduling. Click continue to finish.'}
                      </p>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={handleResumeBooking}
                        className="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 text-black text-xs font-black rounded-xl transition-all cursor-pointer whitespace-nowrap shadow-lg shadow-amber-500/20"
                      >
                        ▶ Continue Booking
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            await apiClient.post('/leads/active/dismiss');
                            setActiveLead(null);
                            fetchData(true);
                            showToast('Follow-up reminder dismissed.', 'success');
                          } catch (err) {
                            console.warn('Failed to dismiss active lead:', err);
                            showToast('Failed to dismiss reminder.', 'error');
                          }
                        }}
                        className="px-4 py-2.5 border border-slate-700 hover:bg-slate-800 text-slate-350 hover:text-white text-xs font-bold rounded-xl transition-all cursor-pointer whitespace-nowrap"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                )}

                {/* Main Dashboard Interactive Split Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  
                  {/* Left Column - Appointments Context & Smart Rebooking */}
                  <div className="lg:col-span-2 space-y-6">
                    
                    {/* Active reservation */}
                    <div className="space-y-4">
                      <h3 className="text-sm font-extrabold text-slate-400 uppercase tracking-widest">Your Next Confirmed Styling Session</h3>
                      {appointments.filter(a => a.status === 'CONFIRMED' || a.status === 'PENDING').length === 0 ? (
                        <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-8 text-center text-slate-500 text-xs">
                          No upcoming sessions booked. Need a refresh? Reserve a custom slot in our wizard.
                        </div>
                      ) : (
                        (() => {
                          const active = appointments.filter(a => a.status === 'CONFIRMED' || a.status === 'PENDING')[0];
                          return (
                            <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-3xl relative overflow-hidden flex flex-col justify-between">
                              <div className="absolute top-0 right-0 px-4 py-1.5 bg-emerald-500/10 border-l border-b border-emerald-500/20 text-emerald-400 text-[10px] font-black rounded-bl-2xl uppercase tracking-wider">
                                {active.status}
                              </div>
                              <div className="space-y-2.5">
                                <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Confirmed Appointment</span>
                                <h4 className="text-xl font-black text-white">{active.service.name}</h4>
                                <div className="flex flex-wrap items-center text-xs text-slate-400 gap-4 mt-2">
                                  <span>📍 {active.branch.name}</span>
                                  <span>•</span>
                                  <span>💇 {active.staff ? `${active.staff.first_name} ${active.staff.last_name}` : 'Professional assigned'}</span>
                                  <span>•</span>
                                  <span>⏱️ {active.service.duration_minutes} min</span>
                                </div>
                                <p className="text-xs font-bold text-slate-300 mt-2 bg-slate-950/40 p-3 rounded-xl border border-slate-850">
                                  📅 {formatUTCDateTime(active.start_time)}
                                </p>
                              </div>
                              <div className="mt-5 pt-4 border-t border-slate-800/80 flex items-center justify-between">
                                <span className="text-lg font-black text-blue-400">${active.service.price}</span>
                                <div className="flex items-center space-x-2">
                                  <button
                                    onClick={() => {
                                      const { date, time } = getInitialDateTimeForReschedule(active.start_time);
                                      setNewRescheduleDate(date);
                                      setNewRescheduleTime(time);
                                      setReschedulingAppt(active);
                                    }}
                                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-[11px] font-bold rounded-xl transition-all cursor-pointer"
                                  >
                                    🕒 Reschedule
                                  </button>
                                  <button
                                    onClick={() => handleCancelAppointment(active.id)}
                                    className="px-4 py-2 bg-red-950/40 hover:bg-red-900/30 border border-red-900/30 text-red-400 text-[11px] font-bold rounded-xl transition-all cursor-pointer"
                                  >
                                    🗑️ Cancel
                                  </button>
                                </div>
                              </div>
                            </div>
                          );
                        })()
                      )}
                    </div>

                    {/* Smart Rebooking Shortcut Card */}
                    <div className="space-y-4">
                      <h3 className="text-sm font-extrabold text-slate-400 uppercase tracking-widest">Smart Quick-Rebook Co-Pilot</h3>
                      {appointments.filter(a => a.status === 'COMPLETED').length === 0 ? (
                        <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-8 text-center text-slate-500 text-xs">
                          Complete a styling session with us to enable smart quick re-booking parameters.
                        </div>
                      ) : (
                        (() => {
                          const last = appointments.filter(a => a.status === 'COMPLETED')[0];
                          return (
                            <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-3xl flex flex-col md:flex-row items-center justify-between gap-6 text-left">
                              <div className="space-y-1.5">
                                <span className="px-2.5 py-0.5 text-[8px] font-black bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-full uppercase tracking-widest">
                                  Based on your last visit
                                </span>
                                <h4 className="text-base font-extrabold text-white">Repeat styling with {last.staff ? last.staff.first_name : 'stylist'}?</h4>
                                <p className="text-xs text-slate-400">
                                  Quickly book a **{last.service.name}** at our **{last.branch.name}** lounge.
                                </p>
                              </div>
                              <button
                                onClick={() => handleSmartRebook(
                                  last.service.name, 
                                  last.staff?.id || 'any', 
                                  last.branch.name
                                )}
                                className="w-full md:w-auto px-5 py-3 bg-gradient-to-tr from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-xs font-bold rounded-xl transition-all cursor-pointer whitespace-nowrap shadow-md shadow-blue-500/10"
                              >
                                ⚡ One-Click Rebook
                              </button>
                            </div>
                          );
                        })()
                      )}
                    </div>

                  </div>

                  {/* Right Column - Preferences Memorized */}
                  <div className="space-y-6">
                    <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-3xl space-y-5">
                      <h3 className="text-sm font-extrabold text-slate-400 uppercase tracking-widest border-b border-slate-800 pb-3">My Styling Profile</h3>
                      
                      <div className="space-y-3.5 text-xs">
                        <div className="flex justify-between border-b border-slate-850 pb-2">
                          <span className="text-slate-500 font-bold">Preferred Lounge</span>
                          <span className="text-slate-300 font-extrabold">{prefBranch || 'Not Set'}</span>
                        </div>
                        <div className="flex justify-between border-b border-slate-850 pb-2">
                          <span className="text-slate-500 font-bold">Preferred Artist</span>
                          <span className="text-slate-300 font-extrabold">{prefStylist || 'Not Set'}</span>
                        </div>
                        <div className="flex justify-between border-b border-slate-850 pb-2">
                          <span className="text-slate-500 font-bold">Preferred Treatment</span>
                          <span className="text-slate-300 font-extrabold">{prefService || 'Not Set'}</span>
                        </div>
                      </div>

                      <button
                        onClick={() => setActiveTab('profile')}
                        className="w-full py-2.5 bg-slate-800 hover:bg-slate-750 text-[11px] font-bold rounded-xl transition-all cursor-pointer text-center"
                      >
                        ⚙ Customize Styling Preferences
                      </button>
                    </div>
                  </div>

                </div>

              </div>
            )}

            {/* ============================================================================
                VIEW 2: STEP-BY-STEP BOOKING WIZARD
                ============================================================================ */}
            {activeTab === 'book' && (
              <div className="bg-slate-900/40 border border-slate-800 p-6 lg:p-8 rounded-3xl max-w-2xl mx-auto space-y-8 relative">
                
                {/* Wizard Header */}
                <div className="text-center space-y-1">
                  <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest">Styling Wizard</span>
                  <h3 className="text-2xl font-black text-white">📅 Reserve Premium Styling Session</h3>
                  
                  {/* Steps Progress Indicator */}
                  <div className="flex items-center justify-center space-x-2 mt-4">
                    {[1, 2, 3, 4, 5].map(step => (
                      <div 
                        key={step} 
                        className={`h-1.5 w-10 rounded-full transition-all duration-300 ${
                          bookingStep >= step ? 'bg-blue-500' : 'bg-slate-800'
                        }`} 
                      />
                    ))}
                  </div>
                </div>

                {/* STEP 1: BRANCH SELECTION */}
                {bookingStep === 1 && (
                  <div className="space-y-4">
                    <label className="block text-xs font-black text-slate-400 uppercase tracking-wider text-left">Step 1: Choose Lounge Location</label>
                    <div className="grid grid-cols-1 gap-3.5">
                      {branches.map(b => (
                        <div 
                          key={b.id} 
                          onClick={() => {
                            setSelectedBranch(b.id);
                            setBookingStep(2);
                          }}
                          className={`p-4 rounded-2xl border text-left cursor-pointer transition-all duration-200 ${
                            selectedBranch === b.id 
                              ? 'bg-blue-600/10 border-blue-500' 
                              : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                          }`}
                        >
                          <span className="inline-block text-[9px] font-black bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full uppercase tracking-wider">{b.city}</span>
                          <h4 className="text-base font-extrabold text-white mt-1.5">{b.name}</h4>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* STEP 2: SERVICE SELECTION */}
                {bookingStep === 2 && (
                  <div className="space-y-4">
                    <label className="block text-xs font-black text-slate-400 uppercase tracking-wider text-left">Step 2: Choose Styling Treatment</label>
                    <div className="grid grid-cols-1 gap-3">
                      {services.map(s => (
                        <div 
                          key={s.id} 
                          onClick={() => {
                            setSelectedService(s.id);
                            setBookingStep(3);
                          }}
                          className={`p-4 rounded-2xl border text-left cursor-pointer transition-all duration-200 flex justify-between items-center ${
                            selectedService === s.id 
                              ? 'bg-blue-600/10 border-blue-500' 
                              : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                          }`}
                        >
                          <div className="space-y-1">
                            <h4 className="text-sm font-extrabold text-white">{s.name}</h4>
                            <p className="text-xs text-slate-400 leading-relaxed font-medium max-w-md">{s.description}</p>
                            <span className="block text-[10px] text-slate-500">⏱️ {s.duration_minutes} minutes duration</span>
                          </div>
                          <span className="text-base font-black text-blue-400">${s.price}</span>
                        </div>
                      ))}
                    </div>
                    <button 
                      onClick={() => setBookingStep(1)} 
                      className="px-4 py-2 border border-slate-800 rounded-xl text-xs font-bold text-slate-400 hover:text-white cursor-pointer mt-4"
                    >
                      ← Back to Location
                    </button>
                  </div>
                )}

                {/* STEP 3: STYLIST / STAFF SELECTION */}
                {bookingStep === 3 && (
                  <div className="space-y-4">
                    <label className="block text-xs font-black text-slate-400 uppercase tracking-wider text-left">Step 3: Choose Professional Artist</label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                      <div 
                        onClick={() => {
                          setSelectedStylist('any');
                          setBookingStep(4);
                        }}
                        className={`p-4 rounded-2xl border text-left cursor-pointer transition-all duration-200 ${
                          selectedStylist === 'any' 
                            ? 'bg-blue-600/10 border-blue-500' 
                            : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        <span className="text-3xl block">👥</span>
                        <h4 className="text-sm font-extrabold text-white mt-2">Auto-Assign Best Available</h4>
                        <p className="text-[11px] text-slate-400 mt-1">We will allocate the top artist available for your time slot.</p>
                      </div>
                      
                      {staff.map(st => (
                        <div 
                          key={st.id} 
                          onClick={() => {
                            setSelectedStylist(st.id);
                            setBookingStep(4);
                          }}
                          className={`p-4 rounded-2xl border text-left cursor-pointer transition-all duration-200 ${
                            selectedStylist === st.id 
                              ? 'bg-blue-600/10 border-blue-500' 
                              : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                          }`}
                        >
                          <span className="text-3xl block">👩‍🎨</span>
                          <h4 className="text-sm font-extrabold text-white mt-2">{st.first_name} {st.last_name}</h4>
                          <span className="inline-block text-[9px] font-black bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full uppercase tracking-widest mt-1">{st.role}</span>
                        </div>
                      ))}
                    </div>
                    <button 
                      onClick={() => setBookingStep(2)} 
                      className="px-4 py-2 border border-slate-800 rounded-xl text-xs font-bold text-slate-400 hover:text-white cursor-pointer mt-4"
                    >
                      ← Back to Services
                    </button>
                  </div>
                )}

                {/* STEP 4: DATE & TIME SELECTOR */}
                {bookingStep === 4 && (
                  <div className="space-y-6">
                    <label className="block text-xs font-black text-slate-400 uppercase tracking-wider text-left">Step 4: Select Scheduling slot</label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Select Day</label>
                        <input 
                          type="date" 
                          value={selectedDate}
                          onChange={e => setSelectedDate(e.target.value)}
                          required
                          className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none"
                        />
                      </div>
                      
                      <div className="flex flex-col gap-1.5">
                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Select Available Time</label>
                        <select 
                          value={selectedTime}
                          onChange={e => setSelectedTime(e.target.value)}
                          required
                          className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none"
                        >
                          <option value="">Choose slot...</option>
                          <option value="10:00">10:00 AM</option>
                          <option value="11:30">11:30 AM</option>
                          <option value="13:00">1:00 PM</option>
                          <option value="14:30">2:30 PM</option>
                          <option value="16:00">4:00 PM</option>
                          <option value="17:00">5:00 PM</option>
                          <option value="18:30">6:30 PM</option>
                          <option value="20:00">8:00 PM</option>
                        </select>
                      </div>
                    </div>
                    
                    <div className="flex flex-col gap-1.5 text-left">
                      <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Special Requests / Notes</label>
                      <textarea 
                        value={bookingNotes}
                        onChange={e => setBookingNotes(e.target.value)}
                        placeholder="Add special requirements or styling preferences..."
                        className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none h-20 resize-none"
                      />
                    </div>

                    <div className="flex justify-between mt-4">
                      <button 
                        onClick={() => setBookingStep(3)} 
                        className="px-4 py-2 border border-slate-800 rounded-xl text-xs font-bold text-slate-400 hover:text-white cursor-pointer"
                      >
                        ← Back to Stylist
                      </button>
                      <button 
                        disabled={!selectedDate || !selectedTime}
                        onClick={() => setBookingStep(5)} 
                        className="px-5 py-2.5 bg-blue-600 disabled:opacity-50 text-xs font-bold rounded-xl text-white cursor-pointer hover:bg-blue-500"
                      >
                        Continue to Confirm →
                      </button>
                    </div>
                  </div>
                )}

                {/* STEP 5: UPSELL SUGGESTIONS & CONFIRMATION */}
                {bookingStep === 5 && (
                  <div className="space-y-6 text-left">
                    <label className="block text-xs font-black text-slate-400 uppercase tracking-wider">Step 5: Verify Details & Confirm Booking</label>
                    
                    {/* Real-time details review */}
                    <div className="bg-slate-950/50 rounded-2xl border border-slate-850 p-5 space-y-3.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-500 font-bold">Lounge Location:</span>
                        <span className="text-white font-extrabold">{branches.find(b => b.id === selectedBranch)?.name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500 font-bold">Styling Service:</span>
                        <span className="text-white font-extrabold">{services.find(s => s.id === selectedService)?.name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500 font-bold">Artist Stylist:</span>
                        <span className="text-white font-extrabold">{selectedStylist === 'any' ? 'Best Available Assign' : staff.find(st => st.id === selectedStylist)?.first_name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500 font-bold">Time Slot:</span>
                        <span className="text-blue-400 font-black">{selectedDate} at {selectedTime}</span>
                      </div>
                    </div>

                    {/* Dynamic AI Receptionist Upsell Suggestion Card */}
                    <div className="bg-gradient-to-r from-blue-950/60 to-indigo-950/60 border border-blue-500/30 rounded-2xl p-5 space-y-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-base">✨</span>
                        <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Clara's Upsell Bundle Suggestion</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed font-semibold">
                        Add a luxurious nourishing **Head Massage & Deep Hair Conditioning** treatment to your schedule for only **$25** (normally $55)!
                      </p>
                      
                      <div className="flex items-center space-x-3 pt-2">
                        <button
                          type="button"
                          onClick={() => setIsUpsellAccepted(true)}
                          className={`px-4.5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                            isUpsellAccepted 
                              ? 'bg-blue-600 text-white shadow-lg' 
                              : 'bg-slate-900 border border-slate-800 text-slate-300 hover:text-white'
                          }`}
                        >
                          {isUpsellAccepted ? '✓ Bundle Added' : 'Add to Booking (+$25)'}
                        </button>
                        {isUpsellAccepted && (
                          <button 
                            type="button" 
                            onClick={() => setIsUpsellAccepted(false)}
                            className="text-[10px] text-red-400 font-bold hover:underline cursor-pointer"
                          >
                            Remove Upsell
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Final Cost & Booking Action */}
                    <div className="flex items-center justify-between border-t border-slate-800/80 pt-4 mt-6">
                      <div>
                        <span className="block text-[9px] font-bold text-slate-500 uppercase tracking-widest">Total Styling Fee</span>
                        <span className="text-2xl font-black text-blue-400">
                          ${(services.find(s => s.id === selectedService)?.price || 0) + (isUpsellAccepted ? 25 : 0)}
                        </span>
                      </div>

                      <div className="flex space-x-3">
                        <button 
                          onClick={() => setBookingStep(4)} 
                          className="px-4 py-2 border border-slate-800 rounded-xl text-xs font-bold text-slate-400 hover:text-white cursor-pointer"
                        >
                          ← Back
                        </button>
                        <button 
                          disabled={isBookingSubmitting}
                          onClick={handleFinalizeBooking} 
                          className="px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-xs font-black rounded-xl text-white shadow-lg cursor-pointer"
                        >
                          {isBookingSubmitting ? 'Confirming with Supabase...' : 'Confirm Booking Slot'}
                        </button>
                      </div>
                    </div>

                  </div>
                )}

              </div>
            )}

            {/* ============================================================================
                VIEW 3: MY APPOINTMENTS (UPCOMING, COMPLETED, CANCELLED TABS)
                ============================================================================ */}
            {activeTab === 'my-appointments' && (
              <div className="space-y-6">
                
                {/* View Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="text-left">
                    <h3 className="text-xl font-black">⏰ Real-Time Scheduled Sessions</h3>
                    <p className="text-xs text-slate-500">Track active bookings, view historical logs, and submit stylist reviews.</p>
                  </div>
                  
                  {/* Filter Tabs */}
                  <div className="flex bg-slate-900 border border-slate-800 p-1.5 rounded-2xl">
                    {[
                      { id: 'upcoming', label: 'Active Scheduled' },
                      { id: 'completed', label: 'Completed' },
                      { id: 'cancelled', label: 'Cancelled' }
                    ].map(tab => (
                      <button
                        key={tab.id}
                        onClick={() => setAppointmentTab(tab.id as any)}
                        className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                          appointmentTab === tab.id 
                            ? 'bg-blue-600 text-white shadow-md' 
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Appointments List Grid */}
                {getFilteredAppointments(appointmentTab).length === 0 ? (
                  <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-12 text-center text-slate-500 text-xs">
                    No {appointmentTab} appointments found.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {getFilteredAppointments(appointmentTab).map(appt => (
                      <div key={appt.id} className="bg-slate-900/60 border border-slate-800/80 p-5 rounded-2xl relative overflow-hidden flex flex-col justify-between text-left">
                        
                        {/* Status Tag */}
                        <div className={`absolute top-0 right-0 px-3.5 py-1 text-[9px] font-black rounded-bl-xl border-l border-b uppercase tracking-widest ${
                          appt.status.toUpperCase() === 'COMPLETED' 
                            ? 'bg-blue-500/10 border-blue-500/25 text-blue-400' 
                            : appt.status.toUpperCase() === 'CANCELLED' || appt.status.toUpperCase() === 'CANCELED'
                              ? 'bg-red-500/10 border-red-500/25 text-red-400' 
                              : 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
                        }`}>
                          {appt.status}
                        </div>

                        <div className="space-y-3">
                          <span className="block text-[9px] font-bold text-slate-500 uppercase tracking-wider">{appt.branch.name}</span>
                          <h4 className="text-base font-black text-white">{appt.service.name}</h4>
                          <p className="text-[11px] text-slate-400 font-bold bg-slate-950/40 p-2.5 rounded-xl border border-slate-850">
                            📅 {formatUTCDateTime(appt.start_time)}
                          </p>
                          <div className="flex items-center space-x-2 text-xs text-slate-400">
                            <span>Stylist:</span>
                            <span className="text-slate-200 font-bold">{appt.staff ? `${appt.staff.first_name} ${appt.staff.last_name}` : 'Professional assigns'}</span>
                          </div>
                          {appt.notes && (
                            <p className="text-[11px] text-slate-400 italic bg-slate-950/20 p-2 rounded-lg border border-slate-850">Notes: "{appt.notes}"</p>
                          )}
                        </div>

                        {/* Interactive Action Buttons */}
                        <div className="mt-5 pt-4 border-t border-slate-800/60 flex items-center justify-between">
                          <span className="text-base font-black text-blue-400">${appt.service.price}</span>
                          
                          <div className="flex space-x-2">
                            {appointmentTab === 'upcoming' && (
                              <>
                                <button
                                  onClick={() => {
                                    const { date, time } = getInitialDateTimeForReschedule(appt.start_time);
                                    setNewRescheduleDate(date);
                                    setNewRescheduleTime(time);
                                    setReschedulingAppt(appt);
                                  }}
                                  className="px-3 py-2 bg-slate-800 hover:bg-slate-750 text-xs font-bold rounded-xl text-slate-300 cursor-pointer transition-all"
                                >
                                  Reschedule
                                </button>
                                <button
                                  onClick={() => handleCancelAppointment(appt.id)}
                                  className="px-3 py-2 bg-red-950/15 hover:bg-red-900/20 border border-red-900/30 text-red-400 text-xs font-bold rounded-xl cursor-pointer transition-all"
                                >
                                  Cancel Booking
                                </button>
                              </>
                            )}
                            
                            {appointmentTab === 'completed' && (
                              <button
                                onClick={() => setReviewingAppt(appt)}
                                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-xs font-bold rounded-xl text-white cursor-pointer transition-all shadow-md shadow-blue-500/10"
                              >
                                ★ Submit Review
                              </button>
                            )}
                          </div>
                        </div>

                      </div>
                    ))}
                  </div>
                )}

                {/* ============================================================================
                    MODAL: SUBMIT RATING & REVIEW FOR COMPLETED SESSION
                    ============================================================================ */}
                {reviewingAppt && (
                  <div className="fixed inset-0 bg-slate-950/75 flex items-center justify-center p-6 z-50 transition-opacity">
                    <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 lg:p-8 w-full max-w-md space-y-6 shadow-2xl relative">
                      <button 
                        onClick={() => setReviewingAppt(null)}
                        className="absolute top-4 right-4 text-slate-400 hover:text-white text-base cursor-pointer"
                      >
                        ✕
                      </button>
                      
                      <div className="text-center space-y-1">
                        <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest">Share experience</span>
                        <h4 className="text-lg font-black text-white">Rate Your Styling Treatment</h4>
                        <p className="text-xs text-slate-450 mt-1">Reviewing **{reviewingAppt.service.name}** with **{reviewingAppt.staff?.first_name}**</p>
                      </div>

                      {/* Interactive Stars Selection */}
                      <div className="flex items-center justify-center space-x-2.5 py-2">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            onClick={() => setRatingValue(star)}
                            className={`text-2xl cursor-pointer hover:scale-115 transition-transform ${
                              star <= ratingValue ? 'text-amber-400' : 'text-slate-600'
                            }`}
                          >
                            {star <= ratingValue ? '★' : '☆'}
                          </button>
                        ))}
                      </div>

                      <div className="flex flex-col gap-1.5 text-left">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Styling Comments</label>
                        <textarea
                          value={reviewComment}
                          onChange={e => setReviewComment(e.target.value)}
                          placeholder="Tell us about the stylist's precision, salon atmosphere, or premium products..."
                          className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none h-24 resize-none"
                        />
                      </div>

                      <div className="flex justify-between items-center pt-2">
                        <button
                          onClick={() => setReviewingAppt(null)}
                          className="px-4 py-2.5 border border-slate-800 rounded-xl text-xs font-bold text-slate-400 hover:text-white cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleReviewSubmit}
                          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-xs font-black rounded-xl text-white cursor-pointer shadow-lg shadow-blue-500/10"
                        >
                          Commit Review
                        </button>
                      </div>

                    </div>
                  </div>
                )}

                {/* ============================================================================
                    MODAL: RESCHEDULE SCHEDULING TIME
                    ============================================================================ */}
                {reschedulingAppt && (
                  <div className="fixed inset-0 bg-slate-950/75 flex items-center justify-center p-6 z-50 transition-opacity">
                    <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 lg:p-8 w-full max-w-md space-y-6 shadow-2xl relative">
                      <button 
                        onClick={() => setReschedulingAppt(null)}
                        className="absolute top-4 right-4 text-slate-400 hover:text-white text-base cursor-pointer"
                      >
                        ✕
                      </button>
                      
                      <div className="text-center space-y-1">
                        <span className="text-[9px] font-black text-indigo-400 uppercase tracking-widest">Modify booking</span>
                        <h4 className="text-lg font-black text-white">Reschedule Your Session</h4>
                        <p className="text-xs text-slate-450">Moving **{reschedulingAppt.service.name}** reservation.</p>
                      </div>

                      <div className="grid grid-cols-1 gap-4 text-left">
                        <div className="flex flex-col gap-1.5">
                          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Select New Date</label>
                          <input
                            type="date"
                            value={newRescheduleDate}
                            onChange={e => setNewRescheduleDate(e.target.value)}
                            required
                            className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none"
                          />
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Select New Time Slot</label>
                          <select
                            value={newRescheduleTime}
                            onChange={e => setNewRescheduleTime(e.target.value)}
                            required
                            className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none"
                          >
                            <option value="">Choose slot...</option>
                            <option value="10:00">10:00 AM</option>
                            <option value="11:30">11:30 AM</option>
                            <option value="13:00">1:00 PM</option>
                            <option value="14:30">2:30 PM</option>
                            <option value="16:00">4:00 PM</option>
                            <option value="17:00">5:00 PM</option>
                            <option value="18:30">6:30 PM</option>
                            <option value="20:00">8:00 PM</option>
                          </select>
                        </div>
                      </div>

                      <div className="flex justify-between items-center pt-2">
                        <button
                          onClick={() => setReschedulingAppt(null)}
                          className="px-4 py-2.5 border border-slate-800 rounded-xl text-xs font-bold text-slate-400 hover:text-white cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleRescheduleSubmit}
                          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-xs font-black rounded-xl text-white cursor-pointer shadow-lg shadow-blue-500/10"
                        >
                          Submit Reschedule
                        </button>
                      </div>

                    </div>
                  </div>
                )}

              </div>
            )}

            {/* ============================================================================
                VIEW 4: APPOINTMENT HISTORY LOG
                ============================================================================ */}
            {activeTab === 'history' && (
              <div className="space-y-6">
                <div className="text-left">
                  <h3 className="text-xl font-black">📜 Historical Archive</h3>
                  <p className="text-xs text-slate-500 font-bold uppercase tracking-widest mt-1">Archived Styling Sessions</p>
                </div>

                {appointments.length === 0 ? (
                  <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-12 text-center text-slate-500 text-xs">
                    No historical logs found in our database.
                  </div>
                ) : (
                  <div className="bg-slate-900/40 rounded-3xl border border-slate-800 overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left border-collapse">
                        <thead>
                          <tr className="bg-slate-900 border-b border-slate-850 text-slate-500 font-black uppercase tracking-wider">
                            <th className="px-6 py-4">Treatment / Service</th>
                            <th className="px-6 py-4">Lounge Location</th>
                            <th className="px-6 py-4">Stylist Artist</th>
                            <th className="px-6 py-4">Completion Date</th>
                            <th className="px-6 py-4">Price paid</th>
                            <th className="px-6 py-4">Session Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-850 text-slate-350">
                          {appointments.map(appt => (
                            <tr key={appt.id} className="hover:bg-slate-900/45 transition-colors">
                              <td className="px-6 py-4.5 font-bold text-white">{appt.service.name}</td>
                              <td className="px-6 py-4.5">{appt.branch.name}</td>
                              <td className="px-6 py-4.5 font-semibold text-slate-300">{appt.staff ? `${appt.staff.first_name} ${appt.staff.last_name}` : 'Auto Assigned'}</td>
                              <td className="px-6 py-4.5">{formatUTCDate(appt.start_time)}</td>
                              <td className="px-6 py-4.5 text-blue-400 font-black">${appt.service.price}</td>
                              <td className="px-6 py-4.5">
                                <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold border ${
                                  appt.status.toUpperCase() === 'COMPLETED' 
                                    ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' 
                                    : appt.status.toUpperCase() === 'CANCELLED' || appt.status.toUpperCase() === 'CANCELED'
                                      ? 'bg-red-500/10 border-red-500/20 text-red-400' 
                                      : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                                }`}>
                                  {appt.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ============================================================================
                VIEW 5: CONVERSATIONAL AI ASSISTANT (CLARA FULLSCREEN VIEWPORT)
                ============================================================================ */}
            {activeTab === 'assistant' && (
              <div className="space-y-6">
                <div className="text-left border-b border-slate-800 pb-4">
                  <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest">Conversational Assistant</span>
                  <h3 className="text-xl font-black text-white">🤖 Clara - Automated Salon Receptionist</h3>
                  <p className="text-xs text-slate-500 mt-1">Book schedules, cancel bookings, check slot times using plain natural language.</p>
                </div>
                
                {/* Full screen render wrapper for Clara chat */}
                <div className="bg-slate-900/30 rounded-3xl border border-slate-800 overflow-hidden shadow-2xl relative custom-fullscreen-agentchat-container">
                  <AgentChat onRefreshAppointments={() => fetchData(true)} />
                </div>

                <style>{`
                  .custom-fullscreen-agentchat-container .w-full.max-w-7xl {
                    max-width: 100% !important;
                    height: 65vh !important;
                    border: none !important;
                    box-shadow: none !important;
                  }
                `}</style>
              </div>
            )}

            {/* ============================================================================
                VIEW 6: COMPREHENSIVE SERVICE OFFERINGS CATALOG
                ============================================================================ */}
            {activeTab === 'services' && (
              <div className="space-y-6">
                <div className="text-left">
                  <h3 className="text-xl font-black">💆 Styling & Spa Catalog</h3>
                  <p className="text-xs text-slate-550 font-bold uppercase tracking-widest mt-1">Zenoti Premium High-Value Services</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {services.map(s => (
                    <div key={s.id} className="bg-slate-900/60 border border-slate-800 p-6 rounded-3xl flex flex-col justify-between hover:border-blue-500/40 hover:bg-slate-900/80 transition-all duration-300 group">
                      <div className="space-y-2">
                        <div className="w-12 h-12 rounded-2xl bg-blue-900/30 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
                          {s.name.includes('Massage') ? '🪨' : s.name.includes('Hair') || s.name.includes('Cut') ? '💇' : s.name.includes('Facial') ? '🧖‍♀️' : s.name.includes('Pedi') ? '👣' : s.name.includes('Mani') ? '💅' : '🎨'}
                        </div>
                        <h4 className="text-base font-extrabold text-white mt-3">{s.name}</h4>
                        <p className="text-xs text-slate-450 leading-relaxed font-medium mt-1">{s.description}</p>
                      </div>
                      
                      <div className="flex items-center justify-between border-t border-slate-800/60 pt-4 mt-6 text-xs">
                        <span className="text-slate-500 font-bold">⏱️ {s.duration_minutes} minutes duration</span>
                        <span className="text-blue-400 text-sm font-black">${s.price}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ============================================================================
                VIEW 7: NOTIFICATIONS CENTER
                ============================================================================ */}
            {activeTab === 'notifications' && (
              <div className="space-y-6">
                <div className="text-left flex justify-between items-center border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-xl font-black">🔔 Notifications Alert Console</h3>
                    <p className="text-xs text-slate-500 mt-1">Real-time scheduling commits and special promotional updates.</p>
                  </div>
                  
                  <button 
                    onClick={async () => {
                      try {
                        await apiClient.post('/notifications/read-all');
                        setNotifications([]);
                        showToast('Notification logs cleared.', 'success');
                      } catch (err) {
                        console.warn('Failed to clear notifications in DB, clearing locally', err);
                        setNotifications([]);
                        showToast('Notification logs cleared.', 'success');
                      }
                    }}
                    className="px-3.5 py-2 border border-slate-800 hover:text-white rounded-xl text-xs font-bold text-slate-400 cursor-pointer"
                  >
                    Clear All Alerts
                  </button>
                </div>

                {notifications.length === 0 ? (
                  <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-12 text-center text-slate-500 text-xs">
                    No active notifications logs.
                  </div>
                ) : (
                  <div className="space-y-3 max-w-2xl mx-auto">
                    {notifications.map(n => (
                      <div key={n.id} className={`bg-slate-900/50 border p-4.5 rounded-2xl flex items-start space-x-4 text-left hover:border-slate-750 transition-colors ${
                        n.message.toLowerCase().includes("unfinished booking") 
                          ? 'border-amber-500/20 bg-gradient-to-r from-slate-900/50 to-amber-950/10' 
                          : 'border-slate-800'
                      }`}>
                        <span className="text-lg mt-0.5 text-slate-400">
                          {n.message.toLowerCase().includes("unfinished booking") 
                            ? '💬' 
                            : n.type === 'success' ? '✓' : n.type === 'warning' ? '⚠' : 'ℹ'}
                        </span>
                        <div className="flex-1 space-y-1">
                          <div className="flex justify-between items-center">
                            <h4 className={`text-xs font-black ${n.message.toLowerCase().includes("unfinished booking") ? 'text-amber-400' : 'text-slate-200'}`}>{n.title}</h4>
                            <div className="flex items-center space-x-3.5">
                              <span className="text-[10px] text-slate-500 font-medium">{n.timestamp}</span>
                              <button
                                onClick={async () => {
                                  try {
                                    await apiClient.post(`/notifications/${n.id}/read`);
                                    fetchData(true);
                                    showToast('Notification cleared.', 'success');
                                  } catch (err) {
                                    console.warn('Failed to clear notification:', err);
                                  }
                                }}
                                className="text-slate-500 hover:text-red-400 text-xs font-bold transition-colors cursor-pointer"
                                title="Clear notification"
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                          <p className="text-xs text-slate-400 leading-relaxed font-semibold">{n.message}</p>
                          {n.message.toLowerCase().includes("unfinished booking") && (
                            <button
                              onClick={handleResumeBooking}
                              className="mt-2.5 px-4.5 py-2 bg-amber-500 hover:bg-amber-400 text-black text-[10px] font-black uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-amber-500/25 cursor-pointer"
                            >
                              Continue Booking
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ============================================================================
                VIEW 8: PREFERRED PROFILE PAGE
                ============================================================================ */}
            {activeTab === 'profile' && (
              <div className="bg-slate-900/40 border border-slate-800 p-6 lg:p-8 rounded-3xl max-w-xl mx-auto space-y-6">
                <div className="text-center space-y-1.5 border-b border-slate-800 pb-5">
                  <h3 className="text-xl font-black">👤 Custom Styling Parameters</h3>
                  <p className="text-xs text-slate-450">Save preferred parameters for a personalized dashboard and AI receptionist profile memory.</p>
                </div>

                <div className="space-y-5 text-left">
                  
                  {/* Account detail overview */}
                  <div className="bg-slate-950/60 p-4.5 rounded-2xl border border-slate-850 space-y-2.5 text-xs">
                    <span className="block text-[8px] font-black text-slate-550 uppercase tracking-widest border-b border-slate-850 pb-2">Client Details</span>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-bold">Email Address:</span>
                      <span className="text-white font-extrabold">{user?.email}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500 font-bold">Privilege Membership Rank:</span>
                      <span className="text-blue-400 font-black">Gold Member Elite</span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Preferred Lounge Branch</label>
                    <select
                      value={prefBranch}
                      onChange={e => setPrefBranch(e.target.value)}
                      className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none"
                    >
                      <option value="">Select branch...</option>
                      {branches.map(b => (
                        <option key={b.id} value={b.name}>{b.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Preferred Styling Specialist</label>
                    <select
                      value={prefStylist}
                      onChange={e => setPrefStylist(e.target.value)}
                      className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none"
                    >
                      <option value="">Select stylist...</option>
                      {staff.map(st => (
                        <option key={st.id} value={`${st.first_name} ${st.last_name}`}>{st.first_name} {st.last_name} ({st.role})</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Preferred styling Treatment</label>
                    <select
                      value={prefService}
                      onChange={e => setPrefService(e.target.value)}
                      className="px-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none"
                    >
                      <option value="">Select service...</option>
                      {services.map(s => (
                        <option key={s.id} value={s.name}>{s.name}</option>
                      ))}
                    </select>
                  </div>

                  <button
                    onClick={savePreferences}
                    className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 text-xs font-black rounded-xl text-white transition-all cursor-pointer shadow-lg shadow-blue-500/10 mt-3"
                  >
                    Save Preference Memory
                  </button>

                </div>
              </div>
            )}

            {activeTab === 'reviews' && (
              <div className="space-y-6 animate-fade-in">
                <div className="text-left border-b border-slate-800 pb-4">
                  <h3 className="text-xl font-black">⭐ My Feedback Reviews</h3>
                  <p className="text-xs text-slate-550 font-bold uppercase tracking-wider mt-1">Submit styling ratings, share comments, and view official replies</p>
                </div>

                {/* Sub-section 1: Rate Completed Services */}
                <div className="space-y-4">
                  <h4 className="text-sm font-extrabold text-slate-400 uppercase tracking-widest text-left">Rate Completed Services</h4>
                  
                  {appointments.filter(appt => appt.status.toUpperCase() === 'COMPLETED' && !customerReviews.some(r => r.appointment_id === appt.id)).length === 0 ? (
                    <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-8 text-center text-slate-500 text-xs font-semibold">
                      All your completed appointments have been successfully rated! Thank you for supporting our stylists.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {appointments.filter(appt => appt.status.toUpperCase() === 'COMPLETED' && !customerReviews.some(r => r.appointment_id === appt.id)).map(appt => (
                        <div key={appt.id} className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl flex justify-between items-center text-left hover:border-blue-500/25 transition-all">
                          <div>
                            <h5 className="text-xs font-black text-white">{appt.service.name}</h5>
                            <span className="block text-[10px] text-slate-550 font-bold mt-0.5">Stylist: {appt.staff ? `${appt.staff.first_name} ${appt.staff.last_name}` : 'Salon Artist'}</span>
                            <span className="block text-[9px] text-blue-400 font-bold mt-1">Completed on {formatUTCDate(appt.start_time)}</span>
                          </div>
                          <button
                            onClick={() => {
                              setReviewingAppt(appt);
                              setRatingValue(5);
                              setReviewComment('');
                            }}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-[10px] font-black uppercase tracking-wider rounded-xl text-white transition-all shadow-lg cursor-pointer whitespace-nowrap"
                          >
                            ⭐ Rate Stylist
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="border-t border-slate-850 my-6" />

                {/* Sub-section 2: Review History */}
                <div className="space-y-4">
                  <h4 className="text-sm font-extrabold text-slate-400 uppercase tracking-widest text-left">My Review History</h4>
                  
                  {isReviewsLoading ? (
                    <div className="h-32 flex flex-col items-center justify-center space-y-2">
                      <div className="w-6 h-6 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Loading review history...</span>
                    </div>
                  ) : customerReviews.length === 0 ? (
                    <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-12 text-center text-slate-500 text-xs">
                      No review logs found. Rate a service above to leave your first review!
                    </div>
                  ) : (
                    <div className="space-y-4 max-w-3xl">
                      {customerReviews.map((rev) => (
                        <div key={rev.id} className="bg-slate-900/50 border border-slate-800 p-5 rounded-2xl text-left space-y-3 hover:border-slate-750 transition-colors">
                          <div className="flex justify-between items-start flex-wrap gap-2">
                            <div>
                              <h5 className="text-xs font-black text-white">{rev.branch_name || 'Salon Branch'}</h5>
                              <span className="text-[10px] text-slate-500 block font-semibold">{rev.created_at ? rev.created_at.split('T')[0] : 'Just now'}</span>
                            </div>
                            <div className="flex text-amber-400 text-sm">
                              {'★'.repeat(rev.rating)}{'☆'.repeat(5 - rev.rating)}
                            </div>
                          </div>
                          
                          <p className="text-xs text-slate-300 leading-relaxed font-semibold bg-slate-950/60 p-3 rounded-xl border border-slate-850">
                            {rev.review_text || rev.comment}
                          </p>

                          {rev.ai_response && (
                            <div className="bg-blue-950/20 border border-blue-900/20 p-3.5 rounded-xl space-y-1 mt-2.5 ml-4 border-l-2 border-l-blue-500">
                              <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest block">💬 Official Salon Reply</span>
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

            {activeTab === 'recommendations' && (
              <div className="space-y-6">
                <div className="text-left border-b border-slate-800 pb-4">
                  <h3 className="text-xl font-black">💡 Recommended For You</h3>
                  <p className="text-xs text-slate-500 mt-1">Personalized premium treatments and add-on services curated by SalonAI Upsell Agent.</p>
                </div>

                {isRecommendationsLoading ? (
                  <div className="h-48 flex flex-col items-center justify-center space-y-3">
                    <div className="w-8 h-8 border-3 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                    <span className="text-xs text-slate-500 font-bold uppercase tracking-widest animate-pulse">Running purchase history RAG analysis...</span>
                  </div>
                ) : recommendations.length === 0 ? (
                  <div className="bg-slate-900/30 rounded-2xl border border-slate-800 p-12 text-center text-slate-500 text-xs">
                    No recommendations found. Book an appointment first to see suggestions!
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {recommendations.map((rec) => (
                      <div key={rec.id} className="bg-slate-900/60 border border-slate-800 p-6 rounded-3xl flex flex-col justify-between hover:border-blue-500/40 hover:bg-slate-900/80 transition-all duration-300 group">
                        <div className="space-y-3">
                          <div className="flex justify-between items-start">
                            <div className="w-12 h-12 rounded-2xl bg-blue-900/30 flex items-center justify-center text-2xl group-hover:scale-110 transition-transform">
                              {rec.name.includes('Spa') ? '🧖‍♂️' : rec.name.includes('Massage') ? '🪨' : rec.name.includes('Cut') || rec.name.includes('Trim') ? '💇' : rec.name.includes('Facial') ? '🧖‍♀️' : '✨'}
                            </div>
                            <span className="px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/25 rounded-full text-[9px] font-black uppercase tracking-wider">
                              {(rec.confidence_score * 100).toFixed(0)}% Match
                            </span>
                          </div>
                          <h4 className="text-base font-extrabold text-white mt-2">{rec.name}</h4>
                          <p className="text-xs text-slate-455 leading-relaxed font-medium mt-1">{rec.description}</p>
                          <div className="bg-blue-950/30 rounded-xl p-3 border border-blue-900/20 mt-3">
                            <span className="block text-[8px] font-bold text-blue-400 uppercase tracking-widest">Why you'll love it</span>
                            <p className="text-[11px] text-slate-300 mt-1 font-semibold leading-relaxed">{rec.reason}</p>
                          </div>
                        </div>
                        
                        <div className="border-t border-slate-800/60 pt-4 mt-6">
                          <div className="flex items-center justify-between text-xs mb-4">
                            <span className="text-slate-550 font-bold">⏱️ {rec.duration_minutes} mins</span>
                            <span className="text-blue-400 text-sm font-black">${rec.price}</span>
                          </div>
                          
                          <div className="grid grid-cols-2 gap-3">
                            <button
                              onClick={() => handleRejectRecommendation(rec)}
                              className="w-full py-2.5 bg-slate-950 hover:bg-slate-900 border border-slate-800 text-slate-400 hover:text-white rounded-xl text-xs font-bold transition-all cursor-pointer text-center"
                            >
                              Dismiss
                            </button>
                            <button
                              onClick={() => handleAcceptRecommendation(rec)}
                              className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-xs font-black rounded-xl text-white transition-all cursor-pointer text-center shadow-lg shadow-blue-500/10"
                            >
                              Add Service
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ============================================================================
                MODAL: NEW APPOINTMENT CONFIRMED - DYNAMIC UPSELL OPPORTUNITIES
                ============================================================================ */}
            {justBookedAppt && (
              <div className="fixed inset-0 bg-slate-950/75 flex items-center justify-center p-6 z-50 transition-opacity">
                <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 lg:p-8 w-full max-w-lg space-y-6 shadow-2xl relative">
                  <button 
                    onClick={() => setJustBookedAppt(null)}
                    className="absolute top-4 right-4 text-slate-400 hover:text-white text-base cursor-pointer"
                  >
                    ✕
                  </button>
                  
                  <div className="text-center space-y-1">
                    <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center text-3xl mx-auto mb-3">
                      🎉
                    </div>
                    <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">Appointment Confirmed!</span>
                    <h4 className="text-lg font-black text-white">Your styling session is booked</h4>
                    <p className="text-xs text-slate-450 mt-1">Booked: **{justBookedAppt.serviceName}**</p>
                  </div>

                  <div className="border-t border-slate-800/80 my-4" />

                  <div className="space-y-4">
                    <div className="text-left">
                      <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest block">💡 Recommended For You</span>
                      <p className="text-xs text-slate-400 mt-0.5">Combine your booking with one of these matching treatments to maximize your results!</p>
                    </div>

                    {isRecommendationsLoading ? (
                      <div className="h-32 flex flex-col items-center justify-center space-y-2">
                        <div className="w-6 h-6 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Generating matching add-ons...</span>
                      </div>
                    ) : recommendations.length === 0 ? (
                      <div className="bg-slate-950/40 rounded-2xl border border-slate-850 p-6 text-center text-slate-500 text-xs">
                        No matching recommendations generated for this slot.
                      </div>
                    ) : (
                      <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                        {recommendations.slice(0, 2).map((rec) => (
                          <div key={rec.id} className="bg-slate-950/50 border border-slate-850 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 text-left hover:border-slate-800 transition-colors">
                            <div className="space-y-1.5 flex-1">
                              <div className="flex items-center space-x-2">
                                <h5 className="text-xs font-black text-white">{rec.name}</h5>
                                <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded-full text-[8px] font-bold uppercase">
                                  {(rec.confidence_score * 100).toFixed(0)}% Match
                                </span>
                              </div>
                              <p className="text-[11px] text-slate-450 leading-relaxed font-semibold">{rec.reason}</p>
                              <div className="flex items-center space-x-3 text-[10px] text-slate-500">
                                <span>⏱️ {rec.duration_minutes} mins</span>
                                <span>•</span>
                                <span className="text-blue-400 font-bold">${rec.price}</span>
                              </div>
                            </div>
                            <div className="flex sm:flex-col gap-2 min-w-[100px]">
                              <button
                                onClick={() => handleAcceptRecommendation(rec)}
                                className="flex-1 sm:flex-none px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-[10px] font-black rounded-lg text-white transition-all text-center cursor-pointer"
                              >
                                Add Service
                              </button>
                              <button
                                onClick={() => handleRejectRecommendation(rec)}
                                className="flex-1 sm:flex-none px-3.5 py-2 border border-slate-800 hover:text-white text-[10px] font-bold rounded-lg text-slate-400 transition-all text-center cursor-pointer"
                              >
                                Dismiss
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex justify-center pt-2 border-t border-slate-850">
                    <button
                      onClick={() => setJustBookedAppt(null)}
                      className="px-6 py-2.5 bg-slate-850 hover:bg-slate-800 rounded-xl text-xs font-bold text-slate-300 hover:text-white cursor-pointer"
                    >
                      No thanks, view my dashboard
                    </button>
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
