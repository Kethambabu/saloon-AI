import React from 'react';

interface LandingPageProps {
  onNavigateToLogin: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigateToLogin }) => {
  return (
    <div className="min-h-screen bg-slate-950 text-white font-sans overflow-x-hidden relative">
      {/* Background Animated Gradient Orbs */}
      <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none animate-pulse duration-[8s]" />
      <div className="absolute top-1/3 right-1/4 w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-[140px] pointer-events-none animate-pulse duration-[10s]" />
      <div className="absolute bottom-10 left-1/3 w-[450px] h-[450px] bg-cyan-500/5 rounded-full blur-[100px] pointer-events-none" />

      {/* Header */}
      <header className="border-b border-slate-900 sticky top-0 z-50 backdrop-blur-md bg-slate-950/80">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 shadow-lg text-white">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <span className="text-xl font-black bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
              SalonAI
            </span>
          </div>

          <div className="flex items-center space-x-4">
            <a href="#services" className="text-xs font-bold text-slate-400 hover:text-white transition-all hidden md:inline">Services</a>
            <a href="#agents" className="text-xs font-bold text-slate-400 hover:text-white transition-all hidden md:inline">AI Agents</a>
            <a href="#testimonials" className="text-xs font-bold text-slate-400 hover:text-white transition-all hidden md:inline">Testimonials</a>
            <button
              onClick={onNavigateToLogin}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-xs font-bold rounded-xl transition-all shadow-lg shadow-blue-500/20 cursor-pointer"
            >
              Sign In
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative min-h-[90vh] flex items-center justify-center px-6">
        <div className="max-w-4xl text-center space-y-6 z-10">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase tracking-widest">
            ✨ Premium Salon workforce solution
          </span>
          <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-none bg-gradient-to-b from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            SalonAI Workforce Platform
          </h1>
          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            AI-Powered Salon Management & Appointment Automation
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <button
              onClick={onNavigateToLogin}
              className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-xs font-bold rounded-xl transition-all shadow-xl shadow-blue-500/20 cursor-pointer uppercase tracking-wider"
            >
              Sign In
            </button>
            <a
              href="#features"
              className="w-full sm:w-auto px-8 py-4 bg-slate-900 hover:bg-slate-850 border border-slate-800 rounded-xl text-xs font-bold text-slate-300 hover:text-white transition-all text-center cursor-pointer uppercase tracking-wider"
            >
              Learn More
            </a>
          </div>
        </div>
      </section>

      {/* Feature Cards Grid */}
      <section id="features" className="py-24 px-6 max-w-7xl mx-auto space-y-12">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-black md:text-4xl">Platform Capabilities</h2>
          <p className="text-xs text-slate-500 uppercase tracking-widest font-black">Powered by Enterprise Agents</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { title: 'Automated Booking', desc: 'Clara handles natural language appointments natively via chat without friction.', icon: '📅' },
            { title: 'BI Business Analytics', desc: 'Deep charts tracking retention, revenue and branch benchmarks in real-time.', icon: '📈' },
            { title: 'Reputation Shield', desc: 'Autonomous monitoring and review moderation ensuring customer satisfaction.', icon: '🛡️' }
          ].map((f, idx) => (
            <div key={idx} className="bg-slate-900/40 border border-slate-800/80 p-6 rounded-2xl space-y-3">
              <span className="text-3xl block">{f.icon}</span>
              <h3 className="text-base font-extrabold">{f.title}</h3>
              <p className="text-xs text-slate-400 leading-relaxed font-medium">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* AI Agents Showcase */}
      <section id="agents" className="py-24 bg-slate-900/20 border-t border-b border-slate-900 px-6">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-6 text-left">
            <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Autonomous Avatars</span>
            <h2 className="text-3xl md:text-4xl font-black">Meet Clara & The AI Workforce</h2>
            <p className="text-xs text-slate-400 leading-relaxed font-medium">
              We employ a dynamic network of specialized AI Agents that handle receptionist booking, lead generation follow-ups, reputation shielding, and deep business analytics completely autonomously.
            </p>
            <div className="space-y-3">
              <div className="flex items-center space-x-3 bg-slate-900/60 p-3.5 rounded-xl border border-slate-850">
                <span className="text-xl">🤖</span>
                <div>
                  <h4 className="text-xs font-bold">Clara - AI Receptionist</h4>
                  <p className="text-[10px] text-slate-400">Processes bookings, cancels, and reschedules in real-time.</p>
                </div>
              </div>
              <div className="flex items-center space-x-3 bg-slate-900/60 p-3.5 rounded-xl border border-slate-850">
                <span className="text-xl">📊</span>
                <div>
                  <h4 className="text-xs font-bold">Atlas - BI Analytics specialist</h4>
                  <p className="text-[10px] text-slate-400">Synthesizes raw tables into premium graphs and reports.</p>
                </div>
              </div>
            </div>
          </div>
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-3xl p-6 shadow-2xl relative">
            <div className="absolute top-4 right-4 flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
              <span className="text-[9px] font-bold text-emerald-400 uppercase">Clara Online</span>
            </div>
            <div className="space-y-4 text-left">
              <div className="border-b border-slate-800 pb-3">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Agent Console Simulator</span>
              </div>
              <div className="space-y-3 text-xs leading-relaxed">
                <p className="bg-slate-950/60 p-3 rounded-xl border border-slate-850 font-medium">
                  <span className="text-blue-400 font-bold">Client:</span> Can I schedule a hot stone massage tomorrow afternoon at Downtown Elite?
                </p>
                <p className="bg-blue-600/10 p-3 rounded-xl border border-blue-500/20 text-slate-200 font-medium">
                  <span className="text-indigo-400 font-bold">Clara:</span> Hello! I searched for available hot stone massage slots at Downtown Elite tomorrow. We have openings at 2:00 PM, 3:30 PM, and 5:00 PM. Which works best for you?
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Services and Pricing Section */}
      <section id="services" className="py-24 px-6 max-w-7xl mx-auto space-y-12">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-black md:text-4xl">Premium Offerings</h2>
          <p className="text-xs text-slate-500 uppercase tracking-widest font-black">High-Value Service Catalog</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            { name: 'Signature Precision Haircut', price: 85, duration: 60, icon: '💇' },
            { name: 'Balayage & Creative Color', price: 220, duration: 150, icon: '🎨' },
            { name: 'Hydrating Deep Facial', price: 120, duration: 75, icon: '🧖‍♀️' },
            { name: 'Himalayan Hot Stone Massage', price: 150, duration: 90, icon: '🪨' }
          ].map((s, idx) => (
            <div key={idx} className="bg-slate-900/40 border border-slate-800/80 p-6 rounded-2xl flex flex-col justify-between hover:border-slate-700 transition-all text-left">
              <div className="space-y-2">
                <span className="text-3xl block">{s.icon}</span>
                <h3 className="text-sm font-extrabold text-white">{s.name}</h3>
              </div>
              <div className="flex items-center justify-between border-t border-slate-800/60 pt-4 mt-6 text-xs">
                <span className="text-slate-500">⏱️ {s.duration} min</span>
                <span className="text-blue-400 text-sm font-black">${s.price}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className="py-24 bg-slate-900/20 border-t border-slate-900 px-6">
        <div className="max-w-7xl mx-auto space-y-12">
          <div className="text-center space-y-2">
            <h2 className="text-3xl font-black md:text-4xl">Client Commendations</h2>
            <p className="text-xs text-slate-500 uppercase tracking-widest font-black">Loved by thousands</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {[
              { text: "The booking experience with Clara was seamless. I asked for a haircut next Tuesday and it was booked instantly with Marcus!", author: "Sarah Jenkins", role: "Frequent Guest" },
              { text: "Our staff performance increased dramatically since introducing the SalonAI workforce analytics dashboards.", author: "Alexander Chen", role: "Downtown Elite Senior Stylist" }
            ].map((t, idx) => (
              <div key={idx} className="bg-slate-900/40 border border-slate-850 p-6 rounded-2xl text-left space-y-4">
                <p className="text-slate-300 text-xs italic leading-relaxed font-medium">"{t.text}"</p>
                <div>
                  <h4 className="text-xs font-bold text-white">{t.author}</h4>
                  <span className="text-[10px] text-slate-500 uppercase font-black tracking-wider">{t.role}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="py-24 px-6 max-w-4xl mx-auto text-center space-y-6">
        <h2 className="text-3xl font-black">Connect With Our Lounge</h2>
        <p className="text-slate-400 text-xs max-w-lg mx-auto leading-relaxed">
          Questions about our automated agents or platform deployments? Get in touch with our operations center.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4 text-xs font-bold">
          <span>📧 contact@salonai.com</span>
          <span className="hidden sm:inline">•</span>
          <span>📞 +1 (212) 555-0100</span>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6 text-xs text-slate-500">
          <div className="flex items-center space-x-2">
            <span>&copy; {new Date().getFullYear()} SalonAI Platform. All rights reserved.</span>
          </div>
          <div className="flex space-x-4">
            <a href="#services" className="hover:text-white transition-all">Privacy Policy</a>
            <a href="#services" className="hover:text-white transition-all">Terms of Service</a>
          </div>
        </div>
      </footer>
    </div>
  );
};
