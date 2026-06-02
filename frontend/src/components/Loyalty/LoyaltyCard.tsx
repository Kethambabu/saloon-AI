import React from 'react';

interface LoyaltyCardProps {
  loyaltyPoints: number;
  memberRank: string;
  isLoading?: boolean;
  onRefresh?: () => void;
}

/**
 * Display component for loyalty points and member rank
 * Used in dashboard and other sections
 */
export const LoyaltyCard: React.FC<LoyaltyCardProps> = ({
  loyaltyPoints,
  memberRank,
  isLoading = false,
  onRefresh,
}) => {
  // Determine rank color
  const getRankColor = (rank: string): string => {
    switch (rank) {
      case 'Platinum':
        return 'text-purple-300';
      case 'Gold Elite':
        return 'text-yellow-300';
      case 'Gold':
        return 'text-yellow-400';
      case 'Silver':
        return 'text-slate-300';
      default:
        return 'text-orange-400';
    }
  };

  // Determine rank icon
  const getRankIcon = (rank: string): string => {
    switch (rank) {
      case 'Platinum':
        return '👑';
      case 'Gold Elite':
        return '✨';
      case 'Gold':
        return '⭐';
      case 'Silver':
        return '🌟';
      default:
        return '🎯';
    }
  };

  return (
    <div className="grid grid-cols-2 gap-4 bg-slate-950/60 p-4.5 rounded-2xl border border-slate-800">
      {/* Loyalty Points Section */}
      <div className="text-left px-3">
        <span className="block text-[8px] text-slate-500 font-bold uppercase tracking-widest">
          Loyalty Points
        </span>
        <div className="flex items-center justify-between mt-1">
          <span className="block text-xl font-black text-blue-400">
            {isLoading ? '...' : loyaltyPoints}
          </span>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="ml-2 text-slate-400 hover:text-blue-400 disabled:opacity-50 transition-colors"
              title="Refresh loyalty data"
            >
              <svg
                className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>
          )}
        </div>
        <span className="block text-[9px] text-slate-400 mt-0.5">
          {isLoading ? 'Loading...' : `${loyaltyPoints} available`}
        </span>
      </div>

      {/* Member Rank Section */}
      <div className="text-left px-3 border-l border-slate-800">
        <span className="block text-[8px] text-slate-500 font-bold uppercase tracking-widest">
          Member Rank
        </span>
        <span className={`block text-xl font-black mt-1 ${getRankColor(memberRank)}`}>
          {getRankIcon(memberRank)} {isLoading ? '...' : memberRank}
        </span>
        <span className="block text-[9px] text-slate-400 mt-0.5">
          {memberRank === 'Platinum' && 'Elite member'}
          {memberRank === 'Gold Elite' && 'Top tier'}
          {memberRank === 'Gold' && 'Premium status'}
          {memberRank === 'Silver' && 'Active member'}
          {memberRank === 'Bronze' && 'Get started'}
        </span>
      </div>
    </div>
  );
};

export default LoyaltyCard;
