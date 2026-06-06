import React from 'react';

interface ReviewItem {
  id: string;
  rating: number;
  comment: string;
  sentiment: string;
  created_at: string;
  customer_name?: string;
}

interface StaffInsightsProps {
  reviews: ReviewItem[];
  isReviewsLoading: boolean;
  personalStats: {
    appointments: number;
    revenue: number;
    rating: number;
    upsells: number;
    role: string;
  };
}

export const StaffInsights: React.FC<StaffInsightsProps> = ({ reviews, isReviewsLoading, personalStats }) => {
  
  // Dynamic AI coaching insights generator
  const getCoachingTip = () => {
    const rating = personalStats.rating || 0;
    const upsells = personalStats.upsells || 0;
    
    if (rating < 4.2 && rating > 0) {
      return {
        title: "🎯 Focus Area: Client Relationship & Details",
        tip: "Your average rating is currently below our 4.5 baseline. Make sure to conduct a thorough style consultation before starting services and pay extra attention to client notes and comfort.",
        badge: "Customer Relations"
      };
    } else if (upsells < 50) {
      return {
        title: "⚡ Focus Area: Automated Upselling",
        tip: "You have generated low add-on revenues this month. Use the AI Co-Stylist suggestion presets to pitch complementary treatments (e.g., matching a Hair Spa treatment with a Precision Haircut).",
        badge: "Revenue Boost"
      };
    } else {
      return {
        title: "🏆 Excellence Path: Leadership & Mentoring",
        tip: "Outstanding metrics! You are exceeding targets in both customer ratings and upsell conversions. Keep sharing your formula cards and upselling pitches with the rest of the styling roster.",
        badge: "Top Performer"
      };
    }
  };

  const coaching = getCoachingTip();

  return (
    <div className="space-y-6 text-left">
      <div className="border-b border-slate-800 pb-3">
        <h2 className="text-xl font-black">📈 AI Performance Coach & Insights</h2>
        <p className="text-xs text-slate-500">Access personalized operational guidance and read real-time customer feedback.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        
        {/* Coach tip */}
        <div className="lg:col-span-1 bg-slate-900/60 border border-slate-800 p-6 rounded-3xl shadow-xl space-y-4 flex flex-col justify-between h-full min-h-[300px]">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="px-2 py-0.5 text-[9px] font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full uppercase tracking-wider">
                {coaching.badge}
              </span>
              <span className="text-xl">🎓</span>
            </div>
            
            <div className="space-y-2">
              <h3 className="text-sm font-extrabold text-white uppercase tracking-wider">{coaching.title}</h3>
              <p className="text-xs text-slate-400 leading-relaxed font-medium">
                {coaching.tip}
              </p>
            </div>
          </div>
          
          <div className="border-t border-slate-850 pt-4 mt-4 text-[10px] text-slate-500 font-bold uppercase tracking-wider">
            Updated daily by Atlas Coach
          </div>
        </div>

        {/* Reviews Ledger Feed */}
        <div className="lg:col-span-2 bg-slate-900/40 border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
          <h3 className="text-sm font-extrabold text-white uppercase tracking-wider">⭐ Client Feedback Ledger</h3>
          
          {isReviewsLoading ? (
            <p className="text-center text-xs text-slate-500 py-8 font-bold animate-pulse">Loading feedback reviews...</p>
          ) : reviews.length === 0 ? (
            <p className="text-center text-xs text-slate-500 py-8 font-semibold">No feedback reviews registered for your sessions.</p>
          ) : (
            <div className="space-y-3 max-h-[350px] overflow-y-auto custom-scrollbar pr-1">
              {reviews.map((rev) => (
                <div key={rev.id} className="bg-slate-950/60 border border-slate-850 p-4 rounded-xl space-y-2 relative">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-white">{rev.customer_name || 'Anonymous Client'}</span>
                    <span className="text-emerald-400 font-bold block">{rev.rating} ★</span>
                  </div>
                  <p className="text-xs text-slate-350 leading-relaxed font-medium italic">"{rev.comment || 'No comment provided'}"</p>
                  <div className="flex justify-between items-center text-[9px] text-slate-500 font-black uppercase tracking-wider pt-1">
                    <span>Sentiment: <strong className={rev.sentiment === 'POSITIVE' ? 'text-emerald-555' : 'text-slate-400'}>{rev.sentiment}</strong></span>
                    <span>{new Date(rev.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default StaffInsights;
