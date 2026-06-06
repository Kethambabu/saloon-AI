import React from 'react';

interface RecommendationItem {
  id: string;
  service_id: string;
  name: string;
  description: string;
  price: number;
  confidence_score: number;
  reason: string;
  appointment_id?: string;
}

interface CustomerHistoryItem {
  id: string;
  name: string;
  email: string;
}

interface RecommendationsCardProps {
  customers: CustomerHistoryItem[];
  selectedCustomerId: string;
  setSelectedCustomerId: (val: string) => void;
  recommendations: RecommendationItem[];
  isRecommendationsLoading: boolean;
  onFetchRecommendations: (customerId: string) => void;
  onAcceptRecommendation: (rec: RecommendationItem) => void;
  selectedService: string;
  setSelectedService: (val: string) => void;
  onQueryUpsell: () => void;
  upsellSuggestion: string;
}

export const RecommendationsCard: React.FC<RecommendationsCardProps> = ({
  customers,
  selectedCustomerId,
  setSelectedCustomerId,
  recommendations,
  isRecommendationsLoading,
  onFetchRecommendations,
  onAcceptRecommendation,
  selectedService,
  setSelectedService,
  onQueryUpsell,
  upsellSuggestion
}) => {

  const handleCustomerChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const cid = e.target.value;
    setSelectedCustomerId(cid);
    if (cid) {
      onFetchRecommendations(cid);
    }
  };

  return (
    <div className="space-y-6 text-left">
      <div className="border-b border-slate-800 pb-3">
        <h2 className="text-xl font-black">⚡ Real-time Upsell Engine</h2>
        <p className="text-xs text-slate-500">Query and apply high-value add-on service recommendations based on customer history.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        
        {/* Upsell matcher by service */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 space-y-4">
          <div>
            <h3 className="text-sm font-extrabold text-white">⚡ Upsell Rule Query</h3>
            <p className="text-[11px] text-slate-500">Choose a service catalog category to preview rule matching recommendations.</p>
          </div>

          <div className="space-y-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Core Booked Service</label>
              <div className="flex gap-2">
                <select
                  value={selectedService}
                  onChange={e => setSelectedService(e.target.value)}
                  className="flex-1 px-4 py-2.5 bg-slate-950 border border-slate-850 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="Signature Precision Haircut">Signature Precision Haircut</option>
                  <option value="Balayage & Creative Color">Balayage & Creative Color</option>
                  <option value="Himalayan Hot Stone Massage">Himalayan Hot Stone Massage</option>
                </select>
                <button
                  onClick={onQueryUpsell}
                  className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition-all cursor-pointer uppercase tracking-wider"
                >
                  Match
                </button>
              </div>
            </div>

            {upsellSuggestion && (
              <div className="bg-emerald-950/20 border border-emerald-900/30 p-4 rounded-2xl text-xs text-emerald-450 leading-relaxed font-semibold">
                {upsellSuggestion}
              </div>
            )}
          </div>
        </div>

        {/* Live Customer Recommendations lookup */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 space-y-4">
          <div>
            <h3 className="text-sm font-extrabold text-white">👤 Live Client Profiler Upsells</h3>
            <p className="text-[11px] text-slate-500">Select an active client profile to compile dynamic database recommendations.</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Active Client Session</label>
            <select
              value={selectedCustomerId}
              onChange={handleCustomerChange}
              className="w-full px-4 py-2.5 bg-slate-950 border border-slate-850 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
            >
              <option value="">-- Choose Client --</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          <div className="space-y-3 pt-2">
            {isRecommendationsLoading ? (
              <p className="text-center text-xs text-slate-500 py-4 font-bold animate-pulse">Compiling analytics metrics...</p>
            ) : selectedCustomerId && recommendations.length === 0 ? (
              <p className="text-center text-xs text-slate-550 py-4 font-semibold">No upsell recommendations compiled for this client.</p>
            ) : (
              <div className="space-y-2.5">
                {recommendations.map((rec) => (
                  <div key={rec.id} className="bg-slate-950/60 border border-slate-855 p-4 rounded-xl flex items-center justify-between gap-3">
                    <div className="text-left">
                      <h4 className="font-bold text-white text-xs">{rec.name}</h4>
                      <span className="text-emerald-450 font-bold block mt-0.5">${rec.price}</span>
                      <p className="text-[10px] text-slate-500 mt-1 leading-relaxed">{rec.reason}</p>
                    </div>
                    <button
                      onClick={() => onAcceptRecommendation(rec)}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[10px] font-bold whitespace-nowrap cursor-pointer"
                    >
                      Apply Add-on
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default RecommendationsCard;
