/**
 * Analytics API Service
 * Connects to backend BI endpoints with fallback to realistic mock data.
 * Supports real-time polling for live dashboard updates.
 */

import { apiClient } from './client';
import type {
  DashboardOverview,
  RevenueAnalytics,
  StaffAnalytics,
  RetentionAnalytics,
  ServiceAnalytics,
} from '../types/analytics';

// ── Mock Data Generator ────────────────────────────────────────────
// Provides realistic salon data when backend is unavailable

function generateMockRevenueData(): RevenueAnalytics {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const revenueData = [4200, 5100, 4800, 6200, 7100, 6800, 7500, 8200, 7900, 8600, 9100, 9800];

  return {
    success: true,
    metrics: {
      total_revenue: 85400,
      total_bookings: 1247,
      average_ticket: 68.48,
    },
    revenue_by_service: {
      'Haircut & Style': 28500,
      'Color Treatment': 22100,
      'Keratin Treatment': 15800,
      'Bridal Package': 12000,
      'Spa & Facial': 7000,
    },
    revenue_by_branch: {
      'Downtown Studio': 38200,
      'Midtown Salon': 28700,
      'Uptown Luxe': 18500,
    },
    charts: {
      revenue_over_time: {
        labels: months,
        datasets: [{
          label: 'Monthly Revenue ($)',
          data: revenueData,
        }],
      },
    },
  };
}

function generateMockStaffData(): StaffAnalytics {
  const staffMembers = [
    { staff_id: '1', name: 'Sophia Martinez', role: 'Senior Stylist', completed_bookings: 186, revenue_generated: 18200, utilization_rate_pct: 92.5, average_rating: 4.9 },
    { staff_id: '2', name: 'James Chen', role: 'Color Specialist', completed_bookings: 154, revenue_generated: 15800, utilization_rate_pct: 87.3, average_rating: 4.8 },
    { staff_id: '3', name: 'Olivia Brown', role: 'Stylist', completed_bookings: 142, revenue_generated: 12400, utilization_rate_pct: 78.6, average_rating: 4.7 },
    { staff_id: '4', name: 'Liam Patel', role: 'Junior Stylist', completed_bookings: 128, revenue_generated: 9800, utilization_rate_pct: 72.1, average_rating: 4.5 },
    { staff_id: '5', name: 'Emma Wilson', role: 'Spa Therapist', completed_bookings: 98, revenue_generated: 8600, utilization_rate_pct: 65.4, average_rating: 4.9 },
  ];

  return {
    success: true,
    staff_metrics: staffMembers,
    charts: {
      staff_revenue: {
        labels: staffMembers.map(s => s.name),
        datasets: [{ label: 'Revenue Generated ($)', data: staffMembers.map(s => s.revenue_generated) }],
      },
      staff_ratings: {
        labels: staffMembers.map(s => s.name),
        datasets: [{ label: 'Average Rating', data: staffMembers.map(s => s.average_rating) }],
      },
    },
  };
}

function generateMockRetentionData(): RetentionAnalytics {
  return {
    success: true,
    retention_metrics: {
      total_registered_customers: 842,
      total_transacting_customers: 624,
      one_time_visitors: 218,
      repeat_visitors: 406,
      loyal_visitors_3plus: 187,
      retention_rate_pct: 65.1,
    },
    top_customers_by_ltv: [
      { customer_name: 'Sarah Johnson', ltv: 2840 },
      { customer_name: 'Michael Roberts', ltv: 2450 },
      { customer_name: 'Jessica Lee', ltv: 2180 },
      { customer_name: 'David Kim', ltv: 1920 },
      { customer_name: 'Amanda Torres', ltv: 1750 },
      { customer_name: 'Ryan Mitchell', ltv: 1580 },
      { customer_name: 'Nicole Adams', ltv: 1420 },
      { customer_name: 'Brandon Clark', ltv: 1280 },
    ],
    charts: {
      retention_distribution: {
        labels: ['One-Time Visitors', 'Repeat Customers (2+)'],
        datasets: [{ label: 'Customer Count', data: [218, 406] }],
      },
    },
  };
}

function generateMockServiceData(): ServiceAnalytics {
  const services = [
    { service_name: 'Haircut & Style', total_bookings: 412, total_revenue: 28500 },
    { service_name: 'Color Treatment', total_bookings: 284, total_revenue: 22100 },
    { service_name: 'Keratin Treatment', total_bookings: 156, total_revenue: 15800 },
    { service_name: 'Bridal Package', total_bookings: 48, total_revenue: 12000 },
    { service_name: 'Spa & Facial', total_bookings: 178, total_revenue: 7000 },
    { service_name: 'Beard Trim', total_bookings: 169, total_revenue: 4200 },
  ];

  return {
    success: true,
    services,
    charts: {
      service_bookings: {
        labels: services.map(s => s.service_name),
        datasets: [{ label: 'Bookings Count', data: services.map(s => s.total_bookings) }],
      },
      service_revenue_share: {
        labels: services.map(s => s.service_name),
        datasets: [{ label: 'Revenue Share ($)', data: services.map(s => s.total_revenue) }],
      },
    },
  };
}

// ── API Fetcher with Graceful Fallback ─────────────────────────────
async function fetchWithFallback<T>(endpoint: string, fallbackFn: () => T): Promise<T> {
  try {
    const response = await apiClient.get(endpoint);
    return response.data as T;
  } catch {
    console.warn(`[Analytics] Backend unavailable for ${endpoint}, using demo data`);
    return fallbackFn();
  }
}

// ── Exported Analytics API ─────────────────────────────────────────
export const analyticsService = {
  getOverview: (): Promise<DashboardOverview> =>
    fetchWithFallback<DashboardOverview>('/analytics/overview', () => ({
      success: true,
      revenue: generateMockRevenueData(),
      staff: generateMockStaffData(),
      retention: generateMockRetentionData(),
      services: generateMockServiceData(),
    })),

  getRevenue: (startDate?: string, endDate?: string, branchId?: string): Promise<RevenueAnalytics> => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    if (branchId) params.set('branch_id', branchId);
    const query = params.toString() ? `?${params.toString()}` : '';
    return fetchWithFallback(`/analytics/revenue${query}`, generateMockRevenueData);
  },

  getStaff: (branchId?: string): Promise<StaffAnalytics> => {
    const query = branchId ? `?branch_id=${branchId}` : '';
    return fetchWithFallback(`/analytics/staff${query}`, generateMockStaffData);
  },

  getRetention: (): Promise<RetentionAnalytics> =>
    fetchWithFallback('/analytics/retention', generateMockRetentionData),

  getServices: (): Promise<ServiceAnalytics> =>
    fetchWithFallback('/analytics/services', generateMockServiceData),
};

export default analyticsService;
