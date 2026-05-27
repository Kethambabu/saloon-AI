/**
 * Analytics Dashboard Type Definitions
 * Typed interfaces for all BI analytics data structures
 */

// ── Revenue Analytics ──────────────────────────────────────────────
export interface RevenueMetrics {
  total_revenue: number;
  total_bookings: number;
  average_ticket: number;
}

export interface ChartDataset {
  label: string;
  data: number[];
}

export interface ChartData {
  labels: string[];
  datasets: ChartDataset[];
}

export interface RevenueAnalytics {
  success: boolean;
  metrics: RevenueMetrics;
  revenue_by_service: Record<string, number>;
  revenue_by_branch: Record<string, number>;
  charts: {
    revenue_over_time: ChartData;
  };
}

// ── Staff Performance ──────────────────────────────────────────────
export interface StaffMember {
  staff_id: string;
  name: string;
  role: string;
  completed_bookings: number;
  revenue_generated: number;
  utilization_rate_pct: number;
  average_rating: number;
}

export interface StaffAnalytics {
  success: boolean;
  staff_metrics: StaffMember[];
  charts: {
    staff_revenue: ChartData;
    staff_ratings: ChartData;
  };
}

// ── Retention Analytics ────────────────────────────────────────────
export interface RetentionMetrics {
  total_registered_customers: number;
  total_transacting_customers: number;
  one_time_visitors: number;
  repeat_visitors: number;
  loyal_visitors_3plus: number;
  retention_rate_pct: number;
}

export interface TopCustomer {
  customer_name: string;
  ltv: number;
}

export interface RetentionAnalytics {
  success: boolean;
  retention_metrics: RetentionMetrics;
  top_customers_by_ltv: TopCustomer[];
  charts: {
    retention_distribution: ChartData;
  };
}

// ── Service Popularity ─────────────────────────────────────────────
export interface ServicePopularity {
  service_name: string;
  total_bookings: number;
  total_revenue: number;
}

export interface ServiceAnalytics {
  success: boolean;
  services: ServicePopularity[];
  charts: {
    service_bookings: ChartData;
    service_revenue_share: ChartData;
  };
}

// ── Aggregated Dashboard ───────────────────────────────────────────
export interface DashboardOverview {
  success: boolean;
  revenue: RevenueAnalytics | null;
  staff: StaffAnalytics | null;
  retention: RetentionAnalytics | null;
  services: ServiceAnalytics | null;
}

// ── Time Range Filter ──────────────────────────────────────────────
export type TimeRange = '7d' | '30d' | '90d' | '12m' | 'all';
