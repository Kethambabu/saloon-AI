/**
 * useAnalytics Hook - Real-time analytics data fetcher
 * Provides auto-polling, loading states, and error handling for dashboard data.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { analyticsService } from '../api/analyticsService';
import type { DashboardOverview } from '../types/analytics';

const POLL_INTERVAL_MS = 30000; // 30 seconds

interface UseAnalyticsReturn {
  data: DashboardOverview | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
}

export function useAnalytics(): UseAnalyticsReturn {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(prev => prev ? true : false); // Don't flash loading on refresh
      const result = await analyticsService.getOverview();
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-polling for real-time updates
  useEffect(() => {
    intervalRef.current = setInterval(fetchData, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  return { data, loading, error, lastUpdated, refresh: fetchData };
}

export default useAnalytics;
