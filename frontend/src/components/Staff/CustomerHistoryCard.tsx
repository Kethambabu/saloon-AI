import React, { useState } from 'react';

interface CustomerHistoryItem {
  id: string;
  name: string;
  email: string;
  last_service: string;
  last_date: string;
  notes: string;
}

interface CustomerHistoryCardProps {
  customers: CustomerHistoryItem[];
}

export const CustomerHistoryCard: React.FC<CustomerHistoryCardProps> = ({ customers }) => {
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filtered = customers.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    c.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6 text-left">
      <div className="border-b border-slate-800 pb-3 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-xl font-black">👥 Historical Customer Logs</h2>
          <p className="text-xs text-slate-500">Examine details, formulas, and contact cards across the customer base.</p>
        </div>
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search customer by name or email..."
          className="w-full md:max-w-xs px-4 py-2 bg-slate-905 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.length === 0 ? (
          <div className="col-span-2 text-center text-slate-550 py-12 text-xs font-bold bg-slate-900/10 border border-slate-850/60 rounded-3xl">
            No customer profiles found.
          </div>
        ) : (
          filtered.map(c => (
            <div key={c.id} className="bg-slate-900/40 border border-slate-800/80 p-5 rounded-2xl flex flex-col justify-between gap-3 hover:border-slate-700 transition-all">
              <div className="flex justify-between items-start gap-2 text-xs">
                <div>
                  <h4 className="font-extrabold text-white text-sm">{c.name}</h4>
                  <span className="text-slate-500 text-[11px] block mt-0.5">{c.email}</span>
                </div>
                <div className="text-right">
                  <span className="text-emerald-450 font-bold block">{c.last_service}</span>
                  <span className="text-[10px] text-slate-550 font-bold block">{c.last_date}</span>
                </div>
              </div>
              <div className="text-xs text-slate-350 bg-slate-950/60 p-3.5 border border-slate-850 rounded-xl">
                <span className="text-[9px] text-slate-500 font-black block uppercase tracking-wider mb-1">Color/Styling Formula Preference:</span>
                <p className="italic font-medium leading-relaxed">{c.notes}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default CustomerHistoryCard;
