import React, { useState } from 'react';
import { AgentChat } from '../AgentChat/AgentChat';

interface LandingPageProps {
  onNavigateToLogin: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigateToLogin }) => {
  const [isChatOpen, setIsChatOpen] = useState(false);

  const services = [
    { name: 'Signature Precision Haircut', price: '$85', duration: '60 min', icon: '💇', desc: 'Crafted haircut with custom styling tailored to your face structure.' },
    { name: 'Balayage & Creative Color', price: '$220', duration: '150 min', icon: '🎨', desc: 'Premium hand-painted high-definition balayage with high-shine seal.' },
    { name: 'Hydrating Deep Facial', price: '$120', duration: '75 min', icon: '🧖‍♀️', desc: 'Multi-layer organic moisture fusion with cooling oxygen infusion.' },
    { name: 'Himalayan Hot Stone Massage', price: '$150', duration: '90 min', icon: '🪨', desc: 'Aromatic therapeutic massage utilizing smooth volcanic hot stones.' },
    { name: 'Luxury Spa Pedicure', price: '$75', duration: '50 min', icon: '👣', desc: 'Exfoliating sea salt scrub, hot stone foot massage, and gel polish.' },
    { name: 'Elite Gel Manicure', price: '$65', duration: '45 min', icon: '💅', desc: 'Precision cuticle care, nourishing hand massage, and long-wear gel coat.' }
  ];

  const stylists = [
    { name: 'Alexandra Chen', role: 'Senior Stylist & Hair Artist', specialty: 'Precision Shag, Pixies & Balayage', experience: '8 Years', avatar: '👩‍🎨' },
    { name: 'Marcus Johnson', role: 'Master Color Specialist', specialty: 'Pastel Blends, Highlights & Correction', experience: '10 Years', avatar: '👨‍🎨' }
  ];

  const branches = [
    { city: 'Vijayawada', location: 'Benz Circle Hub', phone: '+91 866 555 0192', address: '4th Floor, Grand Plaza, Benz Circle' },
    { city: 'Hyderabad', location: 'Jubilee Hills Elite', phone: '+91 40 555 0183', address: 'Road No. 36, Beside Metro Station, Jubilee Hills' },
    { city: 'Bengaluru', location: 'Indiranagar Premium', phone: '+91 80 555 0174', address: '100 Feet Road, Indiranagar, Opp. Sports Club' }
  ];

  const testimonials = [
    { text: "The booking experience with Clara was seamless. I asked for a haircut next Tuesday and it was booked instantly with Marcus!", author: "Sarah Jenkins", role: "Frequent Guest" },
    { text: "SalonAI matches Zenoti's luxury standards. Beautiful design, real-time availability, and outstanding service catalogs.", author: "Rajesh Kumar", role: "Gold Member" }
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white font-sans overflow-x-hidden relative">
      {/* Background Animated Premium Light Effects */}
      <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-blue-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute top-1/3 right-1/4 w-[600px] h-[600px] bg-indigo-500/10 rounded-full blur-[140px] pointer-events-none animate-pulse duration-[8s]" />
      <div className="absolute bottom-10 left-1/3 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[120px] pointer-events-none" />

      {/* Header / Navbar */}
      <header className="border-b border-slate-900 sticky top-0 z-50 backdrop-blur-md bg-slate-950/80">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 shadow-lg text-white">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <div>
              <span className="text-xl font-black bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                SalonAI
              </span>
              <span className="block text-[8px] tracking-widest text-blue-400 font-bold uppercase -mt-1">Luxury Lounge</span>
            </div>
          </div>

          <div className="flex items-center space-x-6">
            <a href="#services" className="text-xs font-bold text-slate-400 hover:text-white transition-all hidden md:inline">Services</a>
            <a href="#stylists" className="text-xs font-bold text-slate-400 hover:text-white transition-all hidden md:inline">Stylists</a>
            <a href="#locations" className="text-xs font-bold text-slate-400 hover:text-white transition-all hidden md:inline">Locations</a>
            <a href="#testimonials" className="text-xs font-bold text-slate-400 hover:text-white transition-all hidden md:inline">Testimonials</a>
            <button
              onClick={onNavigateToLogin}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-xs font-bold rounded-xl transition-all shadow-lg shadow-blue-500/20 cursor-pointer"
            >
              Sign In
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative min-h-[85vh] flex items-center justify-center px-6">
        <div className="max-w-4xl text-center space-y-6 z-10">
          <span className="inline-flex items-center px-4 py-1.5 rounded-full text-[10px] font-black bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase tracking-widest">
            ✨ Autonomous Zenoti-Inspired Platform
          </span>
          <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-none bg-gradient-to-b from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            SalonAI Luxury Spa & Salon
          </h1>
          <p className="text-base md:text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Experience high-definition grooming and stress-free schedules. Connect with our elite, AI-driven booking hub to lock in perfect styling sessions effortlessly.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <button
              onClick={onNavigateToLogin}
              className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-xs font-bold rounded-xl transition-all shadow-xl shadow-blue-500/20 cursor-pointer uppercase tracking-wider"
            >
              📅 Book Appointment Now
            </button>
            <a
              href="#services"
              className="w-full sm:w-auto px-8 py-4 bg-slate-900 hover:bg-slate-850 border border-slate-800 rounded-xl text-xs font-bold text-slate-300 hover:text-white transition-all text-center cursor-pointer uppercase tracking-wider"
            >
              Explore Catalog
            </a>
          </div>
        </div>
      </section>

      {/* Services Grid Section */}
      <section id="services" className="py-24 px-6 max-w-7xl mx-auto space-y-12 border-t border-slate-900">
        <div className="text-center space-y-2">
          <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Grooming & Wellness</span>
          <h2 className="text-3xl font-black md:text-4xl">Premium Offerings</h2>
          <div className="h-1 w-12 bg-blue-500 mx-auto rounded-full mt-2" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {services.map((s, idx) => (
            <div key={idx} className="bg-slate-900/40 border border-slate-800/80 p-6 rounded-2xl flex flex-col justify-between hover:border-blue-500/50 hover:bg-slate-900/60 transition-all duration-300 text-left group">
              <div className="space-y-3">
                <span className="text-4xl block group-hover:scale-110 transition-transform duration-300 w-fit">{s.icon}</span>
                <h3 className="text-base font-extrabold text-white group-hover:text-blue-400 transition-colors">{s.name}</h3>
                <p className="text-xs text-slate-400 leading-relaxed font-medium">{s.desc}</p>
              </div>
              <div className="flex items-center justify-between border-t border-slate-800/60 pt-4 mt-6 text-xs">
                <span className="text-slate-500 font-bold">⏱️ {s.duration}</span>
                <span className="text-blue-400 text-sm font-black">{s.price}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Featured Stylists Section */}
      <section id="stylists" className="py-24 bg-slate-900/20 border-t border-b border-slate-900 px-6">
        <div className="max-w-7xl mx-auto space-y-12">
          <div className="text-center space-y-2">
            <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Master Artists</span>
            <h2 className="text-3xl font-black md:text-4xl">Featured Staff Stylists</h2>
            <div className="h-1 w-12 bg-blue-500 mx-auto rounded-full mt-2" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {stylists.map((stylist, idx) => (
              <div key={idx} className="bg-slate-900/50 border border-slate-800/80 rounded-3xl p-6 flex items-center space-x-6 hover:border-blue-500/40 transition-all duration-300 text-left">
                <div className="w-20 h-20 rounded-2xl bg-blue-900/40 border border-blue-800/60 flex items-center justify-center text-4xl shadow-inner">
                  {stylist.avatar}
                </div>
                <div className="space-y-1.5 flex-1">
                  <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded-full">{stylist.experience} Experience</span>
                  <h3 className="text-lg font-black text-white">{stylist.name}</h3>
                  <p className="text-xs font-bold text-slate-300">{stylist.role}</p>
                  <p className="text-xs text-slate-400 font-medium">Specialty: {stylist.specialty}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Locations Section */}
      <section id="locations" className="py-24 px-6 max-w-7xl mx-auto space-y-12">
        <div className="text-center space-y-2">
          <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Our Lounges</span>
          <h2 className="text-3xl font-black md:text-4xl">Luxury Branches</h2>
          <div className="h-1 w-12 bg-blue-500 mx-auto rounded-full mt-2" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {branches.map((b, idx) => (
            <div key={idx} className="bg-slate-900/40 border border-slate-800/80 p-6 rounded-2xl text-left space-y-4 hover:border-blue-500/30 transition-all duration-300">
              <div>
                <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 rounded-full">{b.city}</span>
                <h3 className="text-lg font-black text-white mt-2">{b.location}</h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">{b.address}</p>
              </div>
              <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs font-bold">
                <span className="text-slate-500">📞 Support</span>
                <span className="text-slate-300">{b.phone}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className="py-24 bg-slate-900/20 border-t border-slate-900 px-6">
        <div className="max-w-7xl mx-auto space-y-12">
          <div className="text-center space-y-2">
            <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Loved by guests</span>
            <h2 className="text-3xl font-black md:text-4xl">Client Commendations</h2>
            <div className="h-1 w-12 bg-blue-500 mx-auto rounded-full mt-2" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {testimonials.map((t, idx) => (
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

      {/* Business Details Section */}
      <section className="py-24 px-6 max-w-4xl mx-auto text-center space-y-8 border-t border-slate-900">
        <div className="space-y-2">
          <h2 className="text-3xl font-black">Elite Salon Operation Details</h2>
          <p className="text-slate-400 text-xs max-w-lg mx-auto leading-relaxed">
            Open daily. Experience luxurious Zenoti-standard styling across all active branches.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-xs font-bold max-w-2xl mx-auto">
          <div className="bg-slate-900/40 border border-slate-850 p-4 rounded-xl">
            <span className="block text-slate-500 uppercase tracking-wider text-[9px] mb-1">Opening Hours</span>
            <span className="text-white text-sm">9:00 AM - 9:00 PM</span>
          </div>
          <div className="bg-slate-900/40 border border-slate-850 p-4 rounded-xl">
            <span className="block text-slate-500 uppercase tracking-wider text-[9px] mb-1">Corporate Email</span>
            <span className="text-white text-sm">contact@salonai.com</span>
          </div>
          <div className="bg-slate-900/40 border border-slate-850 p-4 rounded-xl">
            <span className="block text-slate-500 uppercase tracking-wider text-[9px] mb-1">Main Phone</span>
            <span className="text-white text-sm">+1 (212) 555-0100</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-12 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6 text-xs text-slate-500">
          <div>
            <span>&copy; {new Date().getFullYear()} SalonAI Platform. All rights reserved.</span>
          </div>
          <div className="flex space-x-6">
            <a href="#services" className="hover:text-white transition-all">Privacy Policy</a>
            <a href="#services" className="hover:text-white transition-all">Terms of Service</a>
          </div>
        </div>
      </footer>

      {/* ============================================================================
          FLOATING AI RECEPTIONIST CHAT WIDGET
          ============================================================================ */}
      <div className="fixed bottom-6 right-6 z-50">
        {!isChatOpen ? (
          <button
            onClick={() => setIsChatOpen(true)}
            className="w-14 h-14 bg-gradient-to-tr from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-full flex items-center justify-center shadow-2xl shadow-blue-500/30 hover:scale-105 transition-all duration-300 cursor-pointer relative group border border-blue-400/20"
          >
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 border-2 border-slate-950 rounded-full animate-pulse" />
            <svg className="w-6 h-6 text-white group-hover:rotate-12 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span className="absolute right-16 bg-slate-900 border border-slate-800 text-[10px] text-white px-2.5 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap font-bold shadow-md">
              Chat with Clara
            </span>
          </button>
        ) : (
          <div className="bg-white border border-slate-200 shadow-2xl rounded-2xl overflow-hidden w-[92vw] sm:w-[480px] h-[550px] flex flex-col animate-fade-in border-slate-300">
            {/* Widget Mini-Header */}
            <div className="bg-slate-900 px-4 py-3 flex items-center justify-between text-white border-b border-slate-800">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-full bg-blue-100 border border-blue-200 flex items-center justify-center font-bold text-blue-600 shadow-sm text-sm">
                  C
                </div>
                <div className="text-left">
                  <h4 className="text-xs font-bold">Clara AI Receptionist</h4>
                  <span className="text-[9px] text-emerald-400 font-bold block -mt-0.5">● Online & Ready</span>
                </div>
              </div>
              <button
                onClick={() => setIsChatOpen(false)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-all cursor-pointer"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* Nesting the AgentChat component within a customized box */}
            <div className="flex-1 overflow-hidden relative nested-agent-chat-wrapper">
              <AgentChat />
            </div>
          </div>
        )}
      </div>

      {/* Global CSS Overrides to adjust AgentChat styles for the popup widget */}
      <style>{`
        .nested-agent-chat-wrapper .w-full.max-w-7xl {
          max-width: 100% !important;
          height: 100% !important;
          min-height: unset !important;
          border: none !important;
          border-radius: 0px !important;
          box-shadow: none !important;
        }
        .nested-agent-chat-wrapper header {
          display: none !important;
        }
      `}</style>

    </div>
  );
};
