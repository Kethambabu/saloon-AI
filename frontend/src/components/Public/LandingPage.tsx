import React, { useState } from 'react';
import { AgentChat } from '../AgentChat/AgentChat';

interface LandingPageProps {
  onNavigateToLogin: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigateToLogin }) => {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  const categories = [
    { label: 'Hair Styling', icon: '💇' },
    { label: 'Hair Coloring', icon: '🎨' },
    { label: 'Facials & Skincare', icon: '🧖‍♀️' },
    { label: 'Massage Therapy', icon: '🪨' },
    { label: 'Manicure', icon: '💅' },
    { label: 'Pedicure', icon: '👣' }
  ];

  const services = [
    { name: 'Signature Precision Haircut', price: '$85', duration: '60 min', icon: '💇', desc: 'Crafted haircut with custom styling tailored to your face structure.', category: 'Hair Styling' },
    { name: 'Balayage & Creative Color', price: '$220', duration: '150 min', icon: '🎨', desc: 'Premium hand-painted high-definition balayage with high-shine seal.', category: 'Hair Coloring' },
    { name: 'Hydrating Deep Facial', price: '$120', duration: '75 min', icon: '🧖‍♀️', desc: 'Multi-layer organic moisture fusion with cooling oxygen infusion.', category: 'Facials & Skincare' },
    { name: 'Himalayan Hot Stone Massage', price: '$150', duration: '90 min', icon: '🪨', desc: 'Aromatic therapeutic massage utilizing smooth volcanic hot stones.', category: 'Massage Therapy' },
    { name: 'Luxury Spa Pedicure', price: '$75', duration: '50 min', icon: '👣', desc: 'Exfoliating sea salt scrub, hot stone foot massage, and gel polish.', category: 'Pedicure' },
    { name: 'Elite Gel Manicure', price: '$65', duration: '45 min', icon: '💅', desc: 'Precision cuticle care, nourishing hand massage, and long-wear gel coat.', category: 'Manicure' }
  ];

  const benefits = [
    { title: 'Easy Online Booking', desc: 'Reserve appointments in under 30 seconds with real-time slot verification.', icon: '⚡' },
    { title: 'Master Stylists', desc: 'Highly trained professionals specializing in custom cuts, colors, and spa treatments.', icon: '🏆' },
    { title: 'AI Co-Stylist Clara', desc: 'An intelligent beauty agent recommending style configurations based on your history.', icon: '🤖' },
    { title: 'Premium Lounges', desc: 'Sit back and enjoy luxury services in our modern, state-of-the-art branch facilities.', icon: '✨' }
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
    <div className={`min-h-screen font-sans overflow-x-hidden relative transition-colors duration-350 ${
      isDarkMode ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-900'
    }`}>
      
      {/* Background Animated Premium Light Effects */}
      {isDarkMode ? (
        <>
          <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
          <div className="absolute top-1/3 right-1/4 w-[600px] h-[600px] bg-amber-500/5 rounded-full blur-[140px] pointer-events-none animate-pulse duration-[8s]" />
          <div className="absolute bottom-10 left-1/3 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[120px] pointer-events-none" />
        </>
      ) : (
        <>
          <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-cyan-500/5 rounded-full blur-[140px] pointer-events-none" />
          <div className="absolute top-1/3 right-1/4 w-[600px] h-[600px] bg-amber-500/5 rounded-full blur-[140px] pointer-events-none" />
        </>
      )}

      {/* Header / Navbar */}
      <header className={`border-b sticky top-0 z-50 backdrop-blur-md transition-colors duration-300 ${
        isDarkMode ? 'border-slate-900 bg-slate-950/90' : 'border-slate-200 bg-white/90'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center space-x-2.5 sm:space-x-3">
            <div className="p-2 sm:p-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-amber-500 shadow-lg text-white shrink-0">
              <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <div>
              <span className={`text-lg sm:text-xl font-black ${
                isDarkMode ? 'bg-gradient-to-r from-white to-slate-350 bg-clip-text text-transparent' : 'text-slate-900'
              }`}>
                SalonAI
              </span>
              <span className="block text-[8px] tracking-widest text-cyan-500 font-black uppercase -mt-0.5 sm:-mt-1">Luxury Booking</span>
            </div>
          </div>

          {/* Navigation Links - Desktop */}
          <div className="hidden lg:flex items-center space-x-8">
            <a href="#services" className={`text-xs font-bold transition-all ${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-slate-650 hover:text-slate-950'}`}>Services</a>
            <a href="#benefits" className={`text-xs font-bold transition-all ${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-slate-650 hover:text-slate-950'}`}>Why Choose Us</a>
            <a href="#stylists" className={`text-xs font-bold transition-all ${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-slate-650 hover:text-slate-950'}`}>Stylists</a>
            <a href="#locations" className={`text-xs font-bold transition-all ${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-slate-650 hover:text-slate-950'}`}>Locations</a>
            <a href="#testimonials" className={`text-xs font-bold transition-all ${isDarkMode ? 'text-slate-400 hover:text-white' : 'text-slate-650 hover:text-slate-950'}`}>Testimonials</a>
          </div>

          {/* CTAs & Mobile Menu Toggle */}
          <div className="flex items-center space-x-2.5 sm:space-x-4">
            {/* Theme Toggle */}
            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className={`p-2 rounded-xl border transition-all cursor-pointer ${
                isDarkMode ? 'bg-slate-900 border-slate-800 text-amber-400 hover:bg-slate-800' : 'bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200'
              }`}
              title="Toggle Theme"
              aria-label="Toggle Theme"
            >
              {isDarkMode ? '☀️' : '🌙'}
            </button>

            <button
              onClick={onNavigateToLogin}
              className="px-4 sm:px-6 py-2 sm:py-2.5 bg-gradient-to-r from-cyan-500 to-amber-500 hover:from-cyan-400 hover:to-amber-400 text-white text-xs font-extrabold rounded-xl transition-all shadow-lg shadow-cyan-500/20 cursor-pointer"
            >
              Sign In
            </button>

            {/* Mobile Hamburger Button */}
            <button
              onClick={() => setIsMobileNavOpen(!isMobileNavOpen)}
              className={`lg:hidden p-2 rounded-xl border transition-all cursor-pointer ${
                isDarkMode ? 'bg-slate-900 border-slate-800 text-slate-300' : 'bg-slate-100 border-slate-200 text-slate-700'
              }`}
              aria-label="Open Navigation Menu"
            >
              {isMobileNavOpen ? (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer Dropdown */}
        {isMobileNavOpen && (
          <div className={`lg:hidden border-t px-6 py-4 space-y-3 animate-fade-in ${
            isDarkMode ? 'bg-slate-950 border-slate-900' : 'bg-white border-slate-200'
          }`}>
            <a
              href="#services"
              onClick={() => setIsMobileNavOpen(false)}
              className={`block py-2 text-sm font-bold ${isDarkMode ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-slate-950'}`}
            >
              💇 Services Catalog
            </a>
            <a
              href="#benefits"
              onClick={() => setIsMobileNavOpen(false)}
              className={`block py-2 text-sm font-bold ${isDarkMode ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-slate-950'}`}
            >
              ⚡ Why Choose Us
            </a>
            <a
              href="#stylists"
              onClick={() => setIsMobileNavOpen(false)}
              className={`block py-2 text-sm font-bold ${isDarkMode ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-slate-950'}`}
            >
              👩‍🎨 Featured Stylists
            </a>
            <a
              href="#locations"
              onClick={() => setIsMobileNavOpen(false)}
              className={`block py-2 text-sm font-bold ${isDarkMode ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-slate-950'}`}
            >
              📍 Branches & Locations
            </a>
            <a
              href="#testimonials"
              onClick={() => setIsMobileNavOpen(false)}
              className={`block py-2 text-sm font-bold ${isDarkMode ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-slate-950'}`}
            >
              ⭐ Guest Testimonials
            </a>
          </div>
        )}
      </header>

      {/* Hero Section */}
      <section className="relative min-h-[70vh] sm:min-h-[80vh] flex flex-col items-center justify-center px-4 sm:px-6 py-12 sm:py-20 text-center">
        <div className="max-w-4xl space-y-4 sm:space-y-6 z-10">
          <span className="inline-flex items-center px-3.5 py-1 rounded-full text-[10px] font-black bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 uppercase tracking-widest">
            ✨ Premium Salon & Spa Platform
          </span>
          <h1 className={`text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-black tracking-tight leading-tight sm:leading-none ${
            isDarkMode ? 'bg-gradient-to-b from-white via-slate-100 to-slate-400 bg-clip-text text-transparent' : 'text-slate-900'
          }`}>
            Book Salon & Spa <br />
            <span className="bg-gradient-to-r from-cyan-400 to-amber-500 bg-clip-text text-transparent">Appointments Online</span>
          </h1>
          <p className={`text-sm sm:text-base md:text-lg max-w-2xl mx-auto leading-relaxed ${
            isDarkMode ? 'text-slate-400' : 'text-slate-650'
          }`}>
            Experience high-definition grooming and stress-free schedules. Connect with our elite, AI-driven booking hub to lock in perfect styling sessions effortlessly.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 pt-3 sm:pt-4">
            <button
              onClick={onNavigateToLogin}
              className="w-full sm:w-auto px-6 sm:px-8 py-3.5 sm:py-4 bg-gradient-to-r from-cyan-500 to-amber-500 hover:from-cyan-400 hover:to-amber-400 text-white text-xs font-black rounded-xl transition-all shadow-xl shadow-cyan-500/25 cursor-pointer uppercase tracking-wider"
            >
              📅 Book Appointment Now
            </button>
            <a
              href="#services"
              className={`w-full sm:w-auto px-6 sm:px-8 py-3.5 sm:py-4 border rounded-xl text-xs font-black transition-all text-center cursor-pointer uppercase tracking-wider ${
                isDarkMode ? 'bg-slate-900 hover:bg-slate-850 border-slate-800 text-slate-350 hover:text-white' : 'bg-white hover:bg-slate-100 border-slate-200 text-slate-700 hover:text-slate-950'
              }`}
            >
              Explore Catalog
            </a>
          </div>
        </div>

        {/* Category Pills (Zenoti Style) */}
        <div className="mt-10 sm:mt-16 max-w-5xl w-full z-10 px-2 sm:px-4">
          <div className="flex overflow-x-auto no-scrollbar sm:flex-wrap items-center justify-start sm:justify-center gap-2.5 sm:gap-3 py-1">
            {categories.map((cat, idx) => (
              <a
                href="#services"
                key={idx}
                className={`flex items-center gap-2 px-3.5 sm:px-4.5 py-2 sm:py-2.5 rounded-full text-xs font-bold border transition-all whitespace-nowrap shrink-0 hover:scale-103 ${
                  isDarkMode 
                    ? 'bg-slate-900/60 border-slate-800 hover:border-cyan-500/50 hover:bg-slate-900 text-slate-300' 
                    : 'bg-white border-slate-200 hover:border-cyan-500/50 hover:bg-slate-50 text-slate-750'
                }`}
              >
                <span>{cat.icon}</span>
                <span>{cat.label}</span>
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* Why Choose Us (Benefits Grid) */}
      <section id="benefits" className={`py-12 sm:py-20 md:py-24 border-t ${isDarkMode ? 'border-slate-900 bg-slate-950/40' : 'border-slate-200 bg-slate-100/40'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 space-y-8 sm:space-y-12">
          <div className="text-center space-y-2">
            <span className="text-[10px] font-black text-cyan-500 uppercase tracking-widest">Seamless Operations</span>
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-black">Why Choose SalonAI?</h2>
            <div className="h-1.5 w-16 bg-gradient-to-r from-cyan-400 to-amber-500 mx-auto rounded-full mt-2" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {benefits.map((b, idx) => (
              <div key={idx} className={`p-6 rounded-2xl border transition-all duration-300 text-left ${
                isDarkMode 
                  ? 'bg-slate-900/40 border-slate-800/80 hover:border-cyan-500/40 hover:bg-slate-900/60' 
                  : 'bg-white border-slate-200 hover:border-cyan-500/40 hover:bg-slate-50 shadow-sm'
              }`}>
                <span className="text-3xl block mb-4">{b.icon}</span>
                <h3 className="text-sm font-black text-white capitalize mb-2">{b.title}</h3>
                <p className={`text-xs leading-relaxed font-medium ${isDarkMode ? 'text-slate-400' : 'text-slate-650'}`}>
                  {b.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Services Grid Section */}
      <section id="services" className={`py-12 sm:py-20 px-4 sm:px-6 max-w-7xl mx-auto space-y-8 sm:space-y-12 border-t ${
        isDarkMode ? 'border-slate-900' : 'border-slate-200'
      }`}>
        <div className="text-center space-y-2">
          <span className="text-[10px] font-black text-cyan-500 uppercase tracking-widest">Grooming & Wellness</span>
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-black">Our Premium Offerings</h2>
          <div className="h-1.5 w-16 bg-gradient-to-r from-cyan-400 to-amber-500 mx-auto rounded-full mt-2" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {services.map((s, idx) => (
            <div key={idx} className={`p-5 sm:p-6 rounded-2xl border flex flex-col justify-between transition-all duration-300 text-left group hover:-translate-y-1 ${
              isDarkMode 
                ? 'bg-slate-900/40 border-slate-800/80 hover:border-cyan-500/40 hover:bg-slate-900/60' 
                : 'bg-white border-slate-200 hover:border-cyan-500/40 hover:bg-slate-50 shadow-sm'
            }`}>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-3xl sm:text-4xl block group-hover:scale-110 transition-transform duration-300 w-fit">{s.icon}</span>
                  <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-wider bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                    {s.category}
                  </span>
                </div>
                <h3 className={`text-base font-extrabold transition-colors ${
                  isDarkMode ? 'text-white group-hover:text-cyan-400' : 'text-slate-900 group-hover:text-cyan-600'
                }`}>
                  {s.name}
                </h3>
                <p className={`text-xs leading-relaxed font-medium ${isDarkMode ? 'text-slate-400' : 'text-slate-650'}`}>{s.desc}</p>
              </div>
              <div className={`flex items-center justify-between border-t pt-4 mt-6 text-xs ${
                isDarkMode ? 'border-slate-800/65' : 'border-slate-150'
              }`}>
                <span className="text-slate-500 font-bold">⏱️ {s.duration}</span>
                <span className="text-cyan-400 text-sm font-black">{s.price}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Featured Stylists Section */}
      <section id="stylists" className={`py-12 sm:py-20 border-t border-b px-4 sm:px-6 ${
        isDarkMode ? 'bg-slate-900/20 border-slate-900' : 'bg-slate-100/40 border-slate-200'
      }`}>
        <div className="max-w-7xl mx-auto space-y-8 sm:space-y-12">
          <div className="text-center space-y-2">
            <span className="text-[10px] font-black text-cyan-500 uppercase tracking-widest">Master Artists</span>
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-black">Featured Staff Stylists</h2>
            <div className="h-1.5 w-16 bg-gradient-to-r from-cyan-400 to-amber-500 mx-auto rounded-full mt-2" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8 max-w-4xl mx-auto">
            {stylists.map((stylist, idx) => (
              <div key={idx} className={`border rounded-2xl sm:rounded-3xl p-5 sm:p-6 flex flex-col sm:flex-row items-center sm:items-start text-center sm:text-left space-y-3 sm:space-y-0 sm:space-x-6 transition-all duration-300 ${
                isDarkMode 
                  ? 'bg-slate-900/50 border-slate-800/80 hover:border-cyan-500/40' 
                  : 'bg-white border-slate-200 hover:border-cyan-500/40 shadow-sm'
              }`}>
                <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-3xl sm:text-4xl shadow-inner shrink-0">
                  {stylist.avatar}
                </div>
                <div className="space-y-1.5 flex-1 min-w-0">
                  <span className="inline-block text-[9px] font-black text-cyan-400 uppercase tracking-widest bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-full">{stylist.experience} Experience</span>
                  <h3 className={`text-base sm:text-lg font-black truncate ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>{stylist.name}</h3>
                  <p className={`text-xs font-bold ${isDarkMode ? 'text-slate-355' : 'text-slate-650'}`}>{stylist.role}</p>
                  <p className={`text-xs font-medium truncate ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>Specialty: {stylist.specialty}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Locations Section */}
      <section id="locations" className="py-12 sm:py-20 px-4 sm:px-6 max-w-7xl mx-auto space-y-8 sm:space-y-12">
        <div className="text-center space-y-2">
          <span className="text-[10px] font-black text-cyan-500 uppercase tracking-widest">Our Lounges</span>
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-black">Luxury Branches</h2>
          <div className="h-1.5 w-16 bg-gradient-to-r from-cyan-400 to-amber-500 mx-auto rounded-full mt-2" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {branches.map((b, idx) => (
            <div key={idx} className={`border p-5 sm:p-6 rounded-2xl text-left space-y-4 transition-all duration-300 hover:-translate-y-0.5 ${
              isDarkMode 
                ? 'bg-slate-900/40 border-slate-800/80 hover:border-cyan-500/30' 
                : 'bg-white border-slate-200 hover:border-cyan-500/30 shadow-sm'
            }`}>
              <div>
                <span className="text-[10px] font-black text-cyan-400 uppercase tracking-widest bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-0.5 rounded-full">{b.city}</span>
                <h3 className={`text-base sm:text-lg font-black mt-2 ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>{b.location}</h3>
                <p className={`text-xs mt-1 leading-relaxed ${isDarkMode ? 'text-slate-400' : 'text-slate-550'}`}>{b.address}</p>
              </div>
              <div className={`pt-3 border-t flex items-center justify-between text-xs font-bold ${
                isDarkMode ? 'border-slate-800/60' : 'border-slate-150'
              }`}>
                <span className="text-slate-500">📞 Support</span>
                <span className={isDarkMode ? 'text-slate-300' : 'text-slate-700'}>{b.phone}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className={`py-12 sm:py-20 border-t px-4 sm:px-6 ${
        isDarkMode ? 'bg-slate-900/20 border-slate-900' : 'bg-slate-100/40 border-slate-200'
      }`}>
        <div className="max-w-7xl mx-auto space-y-8 sm:space-y-12">
          <div className="text-center space-y-2">
            <span className="text-[10px] font-black text-cyan-500 uppercase tracking-widest">Loved by guests</span>
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-black">Client Commendations</h2>
            <div className="h-1.5 w-16 bg-gradient-to-r from-cyan-400 to-amber-500 mx-auto rounded-full mt-2" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {testimonials.map((t, idx) => (
              <div key={idx} className={`p-5 sm:p-6 rounded-2xl border text-left space-y-4 ${
                isDarkMode ? 'bg-slate-900/40 border-slate-850' : 'bg-white border-slate-200 shadow-sm'
              }`}>
                <p className={`text-xs italic leading-relaxed font-medium ${isDarkMode ? 'text-slate-300' : 'text-slate-650'}`}>"{t.text}"</p>
                <div>
                  <h4 className={`text-xs font-bold ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>{t.author}</h4>
                  <span className="text-[10px] text-slate-550 uppercase font-black tracking-wider">{t.role}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Business Details Section */}
      <section className={`py-12 sm:py-20 px-4 sm:px-6 max-w-4xl mx-auto text-center space-y-6 sm:space-y-8 border-t ${
        isDarkMode ? 'border-slate-900' : 'border-slate-200'
      }`}>
        <div className="space-y-2">
          <h2 className="text-2xl sm:text-3xl font-black">Elite Salon Operation Details</h2>
          <p className={`text-xs max-w-lg mx-auto leading-relaxed ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
            Open daily. Experience luxurious Zenoti-standard styling across all active branches.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 text-xs font-bold max-w-2xl mx-auto">
          <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-900/40 border-slate-850' : 'bg-white border-slate-200 shadow-sm'}`}>
            <span className="block text-slate-500 uppercase tracking-wider text-[9px] mb-1">Opening Hours</span>
            <span className={`text-sm ${isDarkMode ? 'text-white' : 'text-slate-800'}`}>9:00 AM - 9:00 PM</span>
          </div>
          <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-900/40 border-slate-850' : 'bg-white border-slate-200 shadow-sm'}`}>
            <span className="block text-slate-500 uppercase tracking-wider text-[9px] mb-1">Corporate Email</span>
            <span className={`text-sm ${isDarkMode ? 'text-white' : 'text-slate-800'}`}>contact@salonai.com</span>
          </div>
          <div className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-900/40 border-slate-850' : 'bg-white border-slate-200 shadow-sm'}`}>
            <span className="block text-slate-500 uppercase tracking-wider text-[9px] mb-1">Main Phone</span>
            <span className={`text-sm ${isDarkMode ? 'text-white' : 'text-slate-800'}`}>+1 (212) 555-0100</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={`border-t py-8 sm:py-12 px-4 sm:px-6 ${
        isDarkMode ? 'border-slate-900 bg-slate-950' : 'border-slate-205 bg-slate-100'
      }`}>
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 sm:gap-6 text-xs text-slate-500">
          <div>
            <span>&copy; {new Date().getFullYear()} SalonAI Platform. All rights reserved.</span>
          </div>
          <div className="flex space-x-6">
            <a href="#services" className="hover:text-cyan-500 transition-all">Privacy Policy</a>
            <a href="#services" className="hover:text-cyan-500 transition-all">Terms of Service</a>
          </div>
        </div>
      </footer>

      {/* Floating AI Chat Widget */}
      <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50">
        {!isChatOpen ? (
          <button
            onClick={() => setIsChatOpen(true)}
            aria-label="Open AI Salon Receptionist Chat"
            className="w-12 h-12 sm:w-14 sm:h-14 bg-gradient-to-tr from-cyan-500 to-amber-500 hover:from-cyan-400 hover:to-amber-400 text-white rounded-full flex items-center justify-center shadow-2xl shadow-cyan-500/30 hover:scale-105 transition-all duration-300 cursor-pointer relative group border border-cyan-400/20"
          >
            <span className="absolute -top-1 -right-1 w-3.5 h-3.5 sm:w-4 sm:h-4 bg-green-500 border-2 border-slate-950 rounded-full animate-pulse" />
            <svg className="w-5 h-5 sm:w-6 sm:h-6 text-white group-hover:rotate-12 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span className="hidden sm:block absolute right-16 bg-slate-900 border border-slate-800 text-[10px] text-white px-2.5 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap font-bold shadow-md">
              Chat with Clara
            </span>
          </button>
        ) : (
          <div className="fixed inset-x-3 bottom-3 top-auto h-[84vh] max-h-[620px] sm:static sm:inset-auto sm:w-[480px] sm:h-[550px] bg-white border border-slate-200 shadow-2xl rounded-2xl overflow-hidden flex flex-col animate-fade-in z-50">
            {/* Widget Mini-Header */}
            <div className="bg-slate-900 px-4 py-3 flex items-center justify-between text-white border-b border-slate-800 shrink-0">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-full bg-cyan-100 border border-cyan-200 flex items-center justify-center font-bold text-cyan-600 shadow-sm text-sm">
                  C
                </div>
                <div className="text-left">
                  <h4 className="text-xs font-bold">Clara AI Receptionist</h4>
                  <span className="text-[9px] text-emerald-400 font-bold block -mt-0.5">● Online & Ready</span>
                </div>
              </div>
              <button
                onClick={() => setIsChatOpen(false)}
                className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-all cursor-pointer"
                aria-label="Close Chat Window"
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
