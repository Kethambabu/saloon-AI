/**
 * App.tsx - Main Dashboard Application Portal
 * Integrated with the AgentChat component and premium SaaS KPIs.
 */

import React from 'react';
import { Layout, AgentChat } from './components';

function App() {
  return (
    <Layout>
      <div className="space-y-8 animate-fade-in">
        
        {/* --- Hero / Welcome Section --- */}
        <section className="bg-gradient-to-r from-blue-700 via-blue-600 to-indigo-700 text-white rounded-3xl p-6 md:p-8 shadow-xl flex flex-col md:flex-row items-center justify-between border border-blue-500/20 relative overflow-hidden">
          
          {/* Subtle Background Glow Elements */}
          <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-400/20 rounded-full blur-2xl -ml-16 -mb-16 pointer-events-none" />

          {/* Left Text Segment */}
          <div className="space-y-3 z-10 text-left max-w-xl">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-white/20 text-white border border-white/10 backdrop-blur-md">
              <span className="w-2 h-2 rounded-full bg-green-400 mr-2 animate-pulse" />
              SalonAI Workforce Co-pilot Active
            </span>
            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight">
              AI-Driven Salon Dispatch
            </h1>
            <p className="text-blue-100 text-sm md:text-base font-medium leading-relaxed">
              Meet Clara, your autonomous salon receptionist. Clara answers client queries, checks real-time calendar availability,books or reschedules services, and updates the PostgreSQL database instantly.
            </p>
          </div>

          {/* Right SVG Dashboard Graphic */}
          <div className="mt-6 md:mt-0 z-10 flex-shrink-0">
            <div className="p-4 bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl shadow-inner flex items-center space-x-4">
              <svg className="w-14 h-14 text-blue-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              <div className="text-left">
                <span className="block text-xs font-semibold text-blue-200 uppercase tracking-wider">Operational Engine</span>
                <span className="text-lg font-bold">Autogen Core 0.7.5</span>
              </div>
            </div>
          </div>
        </section>

        {/* --- KPI Performance Metrics Row --- */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* Card 1: Active Stylists */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4 hover:border-blue-200 hover:shadow-md transition-all duration-300">
            <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 035.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <div className="text-left">
              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider">Workforce Roster</span>
              <span className="text-2xl font-extrabold text-slate-800">4 Active</span>
            </div>
          </div>

          {/* Card 2: Booked Appts */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4 hover:border-blue-200 hover:shadow-md transition-all duration-300">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="text-left">
              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider">Bookings Loaded</span>
              <span className="text-2xl font-extrabold text-slate-800">2 Confirmed</span>
            </div>
          </div>

          {/* Card 3: Dispatch Efficiency */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4 hover:border-blue-200 hover:shadow-md transition-all duration-300">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="text-left">
              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider">AI Accuracy</span>
              <span className="text-2xl font-extrabold text-slate-800">100% Checked</span>
            </div>
          </div>

          {/* Card 4: Postgres DB connection */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4 hover:border-blue-200 hover:shadow-md transition-all duration-300">
            <div className="w-12 h-12 rounded-xl bg-cyan-50 flex items-center justify-center text-cyan-600">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
              </svg>
            </div>
            <div className="text-left">
              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider">Database Link</span>
              <span className="text-2xl font-extrabold text-slate-800 text-emerald-600">Connected</span>
            </div>
          </div>

        </section>

        {/* --- Primary Agent Chat Dashboard --- */}
        <section className="space-y-4">
          <div className="text-left">
            <h2 className="text-xl font-bold text-slate-800">Receptionist Console</h2>
            <p className="text-xs text-slate-500 font-medium">Interact with Clara in real-time to book services, reschedule sessions, or cancel bookings.</p>
          </div>
          <AgentChat />
        </section>

      </div>
    </Layout>
  );
}

export default App;
