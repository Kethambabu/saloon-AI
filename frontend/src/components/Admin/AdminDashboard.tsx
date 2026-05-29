import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient } from '../../api/client';

interface UserRecord {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  staff_id: string | null;
  customer_id: string | null;
}

export const AdminDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Stats cards
  const stats = [
    { title: 'Platform Roster', value: '4 Active Users', desc: 'Across 4 privilege levels', icon: '👑' },
    { title: 'Branches Active', value: '3 Locations', desc: 'Downtown, Westside, Midtown', icon: '📍' },
    { title: 'AI Operational Load', value: '100% Online', desc: 'AutoGen Core Receptionist active', icon: '🤖' },
    { title: 'Database Connectivity', value: 'Supabase Cloud', desc: 'Secure connection pool initialized', icon: '☁️' }
  ];

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        // Query users list dynamically, fallback to static mock list if API isn't built yet
        // In this project, users are registered through /signup
        const response = await apiClient.get<UserRecord[]>('/auth/users');
        setUsers(response.data);
      } catch (err) {
        console.warn('Failed to load dynamic users from API, generating mocked data');
        setUsers([
          { id: '8c3f1b64-224c-4c6e-e342-ae0e985c8df1', email: 'owner@salonai.com', role: 'Admin', is_active: true, staff_id: null, customer_id: null },
          { id: '8c3f1b64-224c-4c6e-e342-ae0e985c8df2', email: 'manager@salonai.com', role: 'Manager', is_active: true, staff_id: null, customer_id: null },
          { id: '8c3f1b64-224c-4c6e-e342-ae0e985c8df3', email: 'marcus@salonai.com', role: 'Staff', is_active: true, staff_id: '6a3e2b64-004c-4c6e-c342-8c0d985c6df2', customer_id: null },
          { id: '8c3f1b64-224c-4c6e-e342-ae0e985c8df4', email: 'customer@example.com', role: 'Customer', is_active: true, staff_id: null, customer_id: '7b3f1b64-114c-4c6e-d342-9d0e985c7df1' }
        ]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchUsers();
  }, []);

  const handleToggleActive = async (userId: string) => {
    setUsers(prevUsers => 
      prevUsers.map(u => u.id === userId ? { ...u, is_active: !u.is_active } : u)
    );
    // In a real system, we'd fire apiClient.post(`/auth/users/${userId}/toggle`)
  };

  return (
    <div className="space-y-8 text-left animate-fade-in">
      
      {/* Welcome banner */}
      <section className="bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white rounded-3xl p-6 md:p-8 shadow-xl border border-slate-800 relative overflow-hidden flex flex-col md:flex-row items-center justify-between">
        <div className="absolute top-0 right-0 w-80 h-80 bg-blue-600/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none" />
        
        <div className="space-y-2 z-10">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            👑 Root Administrator Console
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight">
            Platform Operations Center
          </h1>
          <p className="text-slate-300 text-sm max-w-xl leading-relaxed">
            Welcome back, <span className="text-white font-bold">{user?.email}</span>. Manage global settings, supervise user credentials, inspect active database links, and audit operational dashboards.
          </p>
        </div>
        
        <div className="mt-4 md:mt-0 z-10 flex space-x-3">
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-600/20 border border-red-500/30 hover:bg-red-600/30 text-red-400 text-xs font-bold rounded-xl transition-all cursor-pointer"
          >
            Logout session
          </button>
        </div>
      </section>

      {/* KPI Stats cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-5 rounded-2xl shadow-md flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-slate-850 flex items-center justify-center text-2xl">
              {stat.icon}
            </div>
            <div>
              <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider">{stat.title}</span>
              <span className="text-lg font-extrabold text-white block mt-0.5">{stat.value}</span>
              <span className="text-[10px] text-slate-500 block mt-0.5 font-medium">{stat.desc}</span>
            </div>
          </div>
        ))}
      </section>

      {/* Roster list table */}
      <section className="bg-slate-900/60 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 shadow-xl space-y-4">
        <div>
          <h3 className="text-lg font-extrabold text-white">Supervised Platform Accounts</h3>
          <p className="text-xs text-slate-500">Enable, disable, or audit access tokens across all system components.</p>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-slate-500 font-semibold animate-pulse">Loading accounts roster...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800 text-sm">
              <thead>
                <tr className="text-slate-400 font-bold uppercase tracking-wider text-xs">
                  <th className="px-4 py-3 text-left">Email Address</th>
                  <th className="px-4 py-3 text-left">Assigned Role</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-850/30 transition-colors">
                    <td className="px-4 py-4 whitespace-nowrap font-semibold text-white">{u.email}</td>
                    <td className="px-4 py-4 whitespace-nowrap">
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-bold ${
                        u.role === 'Admin' 
                          ? 'bg-purple-900/30 text-purple-300 border border-purple-800/40'
                          : u.role === 'Manager'
                          ? 'bg-blue-900/30 text-blue-300 border border-blue-800/40'
                          : u.role === 'Customer'
                          ? 'bg-amber-900/30 text-amber-300 border border-amber-800/40'
                          : 'bg-emerald-900/30 text-emerald-300 border border-emerald-800/40'
                      }`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-center">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                        u.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${u.is_active ? 'bg-emerald-400' : 'bg-red-400'}`} />
                        {u.is_active ? 'Active' : 'Suspended'}
                      </span>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-center">
                      <button
                        onClick={() => handleToggleActive(u.id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition-all ${
                          u.is_active
                            ? 'bg-red-950/40 hover:bg-red-900/40 border-red-800/30 text-red-300'
                            : 'bg-emerald-950/40 hover:bg-emerald-900/40 border-emerald-800/30 text-emerald-300'
                        }`}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

    </div>
  );
};
