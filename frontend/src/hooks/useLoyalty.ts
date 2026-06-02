import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../api/client';
import { loyaltySyncService } from '../services/LoyaltySyncService';
import type { LoyaltyEventType } from '../services/LoyaltySyncService';

export interface LoyaltyTransactionItem {
  id: string;
  type: string;
  points_change: number;
  new_balance: number;
  description: string;
  created_at: string;
}

export interface LoyaltySummary {
  customer_id: string;
  current_balance: number;
  completed_appointments: number;
  reviews_submitted: number;
  average_rating: number;
  recent_transactions: LoyaltyTransactionItem[];
}

interface UseLoyaltyReturn {
  loyaltyPoints: number;
  memberRank: string;
  summary: LoyaltySummary | null;
  isLoading: boolean;
  error: string | null;
  refreshLoyalty: () => Promise<void>;
}

/**
 * Custom hook to manage customer loyalty points
 * Handles fetching, caching, and refreshing loyalty data
 * Automatically refreshes when loyalty-related events occur
 */
export const useLoyalty = (): UseLoyaltyReturn => {
  const [loyaltyPoints, setLoyaltyPoints] = useState<number>(0);
  const [memberRank, setMemberRank] = useState<string>('Bronze');
  const [summary, setSummary] = useState<LoyaltySummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Calculate member rank tier based on points
  const calculateMemberRank = (points: number): string => {
    if (points >= 500) return 'Platinum';
    if (points >= 300) return 'Gold Elite';
    if (points >= 150) return 'Gold';
    if (points >= 50) return 'Silver';
    return 'Bronze';
  };

  // Fetch loyalty data from backend
  const refreshLoyalty = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Try primary endpoint: dedicated loyalty endpoint
      try {
        const response = await apiClient.get<LoyaltySummary>('/customer/loyalty/balance');
        setSummary(response.data);
        setLoyaltyPoints(response.data.current_balance);
        setMemberRank(calculateMemberRank(response.data.current_balance));
        return;
      } catch (err) {
        // Fallback to dashboard endpoint if loyalty endpoint fails
        console.warn('Loyalty endpoint failed, trying dashboard endpoint');
      }

      // Fallback: Get loyalty points from dashboard
      const dashboardRes = await apiClient.get<any>('/customer/dashboard');
      setLoyaltyPoints(dashboardRes.data.loyalty_points || 0);
      setMemberRank(calculateMemberRank(dashboardRes.data.loyalty_points || 0));

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch loyalty data';
      setError(errorMessage);
      console.error('Error fetching loyalty data:', err);
      
      // Set default fallback values
      setLoyaltyPoints(0);
      setMemberRank('Bronze');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle loyalty sync events
  const handleLoyaltyEvent = useCallback((eventType: LoyaltyEventType) => {
    console.log(`Loyalty event triggered: ${eventType}`);
    refreshLoyalty();
  }, [refreshLoyalty]);

  // Initial load on mount
  useEffect(() => {
    refreshLoyalty();
  }, [refreshLoyalty]);

  // Subscribe to loyalty sync events
  useEffect(() => {
    const unsubscribe = loyaltySyncService.subscribe(handleLoyaltyEvent);
    return unsubscribe;
  }, [handleLoyaltyEvent]);

  return {
    loyaltyPoints,
    memberRank,
    summary,
    isLoading,
    error,
    refreshLoyalty,
  };
};
