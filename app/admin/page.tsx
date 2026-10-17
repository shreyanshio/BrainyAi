'use client'

import React, { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import {
  ShieldCheck,
  ShieldAlert,
  Users,
  Activity,
  Database,
  Cpu,
  Search,
  RefreshCw,
  Trash2,
  Ban,
  CheckCircle,
  ArrowLeft,
  Key,
  Clock,
  MessageSquare,
  AlertTriangle,
} from 'lucide-react'
import {
  fetchAdminCheck,
  fetchAdminOverview,
  fetchAdminUsers,
  fetchSystemHealth,
  toggleUserSuspend,
  deleteUserAccount,
  checkAuth,
} from '@/lib/api'
import {
  AdminUsageReport,
  AdminUserRecord,
  SystemHealthStatus,
  User,
} from '@/types/api'

export default function AdminPage() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'health'>('overview')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // Overview data
  const [overview, setOverview] = useState<AdminUsageReport | null>(null)

  // Users data
  const [users, setUsers] = useState<AdminUserRecord[]>([])
  const [userTotal, setUserTotal] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [userActionLoading, setUserActionLoading] = useState<number | null>(null)

  // Health data
  const [health, setHealth] = useState<SystemHealthStatus | null>(null)

  // Error toast or notice
  const [notice, setNotice] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  const showNotice = (message: string, type: 'success' | 'error' = 'success') => {
    setNotice({ message, type })
    setTimeout(() => setNotice(null), 4000)
  }

  // 1. Initial Access Verification
  useEffect(() => {
    const verifyAccess = async () => {
      setLoading(true)
      try {
        const loggedUser = await checkAuth()
        setUser(loggedUser)

        const adminStatus = await fetchAdminCheck()
        setIsAdmin(adminStatus)

        if (adminStatus) {
          await loadAllData()
        }
      } catch (err) {
        console.error('Admin verification error:', err)
        setIsAdmin(false)
      } finally {
        setLoading(false)
      }
    }

    verifyAccess()
  }, [])

  const loadAllData = async () => {
    try {
      const [ovData, healthData, usersData] = await Promise.all([
        fetchAdminOverview().catch(() => null),
        fetchSystemHealth().catch(() => null),
        fetchAdminUsers('', 1, 25).catch(() => ({ total: 0, page: 1, limit: 25, users: [] })),
      ])

      if (ovData) setOverview(ovData)
      if (healthData) setHealth(healthData)
      if (usersData) {
        setUsers(usersData.users)
        setUserTotal(usersData.total)
      }
    } catch (err) {
      console.error('Failed to load admin data:', err)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadAllData()
    setRefreshing(false)
    showNotice('Telemetry refreshed from Supabase', 'success')
  }

  // Handle User Search
  const handleSearchUsers = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    try {
      const res = await fetchAdminUsers(searchQuery, 1, 25)
      setUsers(res.users)
      setUserTotal(res.total)
      setCurrentPage(1)
    } catch (err) {
      showNotice('Failed to search users', 'error')
    }
  }

  // Handle Toggle Suspension
  const handleToggleSuspend = async (targetUserId: number) => {
    setUserActionLoading(targetUserId)
    try {
      const res = await toggleUserSuspend(targetUserId)
      setUsers((prev) =>
        prev.map((u) =>
          u.user_id === targetUserId ? { ...u, is_suspended: res.is_suspended } : u
        )
      )
      showNotice(
        `User #${targetUserId} has been ${res.is_suspended ? 'suspended' : 're-activated'}.`,
        'success'
      )
    } catch (err: any) {
      showNotice(err?.message || 'Failed to toggle suspension', 'error')
    } finally {
      setUserActionLoading(null)
    }
  }

  // Handle Delete Account
  const handleDeleteUser = async (targetUserId: number) => {
    if (
      !window.confirm(
        `Are you sure you want to permanently delete user #${targetUserId}? This will erase all their study sessions and logins across Supabase.`
      )
    ) {
      return
    }

    setUserActionLoading(targetUserId)
    try {
      await deleteUserAccount(targetUserId)
      setUsers((prev) => prev.filter((u) => u.user_id !== targetUserId))
      setUserTotal((prev) => Math.max(0, prev - 1))
      showNotice(`User #${targetUserId} has been permanently deleted.`, 'success')
    } catch (err: any) {
      showNotice(err?.message || 'Failed to delete user', 'error')
    } finally {
      setUserActionLoading(null)
    }
  }

  // ── Access Denied / Loading Views ─────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0e1017] flex flex-col items-center justify-center gap-3 text-zinc-400">
        <div className="w-8 h-8 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-white text-sm animate-pulse">
          B
        </div>
        <p className="text-xs text-zinc-500 font-medium">Verifying administrator credentials...</p>
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-[#090a0f] text-zinc-200 flex items-center justify-center p-6">
        <div className="max-w-md w-full p-8 rounded-3xl bg-[#12141c] border border-red-500/30 text-center space-y-4 shadow-2xl">
          <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center mx-auto">
            <ShieldAlert size={24} />
          </div>
          <h1 className="text-xl font-extrabold text-white">403 — Unauthorized</h1>
          <p className="text-xs text-zinc-400 leading-relaxed">
            The administrator control panel is restricted to verified Brainy administrators.
            Your current account does not have authorization to view this interface.
          </p>
          <div className="pt-2">
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold transition"
            >
              <ArrowLeft size={14} />
              Return to Study Sanctuary
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#090a0f] text-zinc-100 flex flex-col antialiased">
      {/* Top Admin Navbar */}
      <header className="h-14 border-b border-zinc-800/80 bg-[#10121a]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition py-1 px-2 rounded-lg hover:bg-zinc-800"
          >
            <ArrowLeft size={14} />
            <span>Study Workspace</span>
          </Link>
          <div className="h-4 w-px bg-zinc-800" />
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-amber-500 text-black flex items-center justify-center font-black text-xs">
              B
            </div>
            <span className="font-bold text-sm tracking-tight text-white uppercase">
              Brainy Admin
            </span>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30">
              Live Supabase
            </span>
          </div>
        </div>

        {/* Tab Navigation & Refresh */}
        <div className="flex items-center gap-3">
          <div className="flex items-center p-1 rounded-xl bg-zinc-900 border border-zinc-800 text-xs">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-3 py-1 rounded-lg font-semibold transition ${
                activeTab === 'overview'
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('users')}
              className={`px-3 py-1 rounded-lg font-semibold transition ${
                activeTab === 'users'
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              Users ({userTotal})
            </button>
            <button
              onClick={() => setActiveTab('health')}
              className={`px-3 py-1 rounded-lg font-semibold transition ${
                activeTab === 'health'
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              Health
            </button>
          </div>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-white transition cursor-pointer"
            title="Refresh Telemetry"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin text-amber-400' : ''} />
          </button>
        </div>
      </header>

      {/* Flash Notice */}
      {notice && (
        <div
          className={`px-6 py-2.5 text-xs font-semibold flex items-center justify-center gap-2 ${
            notice.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-400 border-b border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border-b border-rose-500/20'
          }`}
        >
          {notice.type === 'success' ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
          <span>{notice.message}</span>
        </div>
      )}

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* ── TAB 1: OVERVIEW ── */}
        {activeTab === 'overview' && overview && (
          <div className="space-y-6">
            {/* 4 Metric Bento Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-zinc-400 text-xs">
                  <span>Registered Students</span>
                  <Users size={16} className="text-blue-400" />
                </div>
                <div className="text-3xl font-extrabold text-white">
                  {overview.summary.total_users}
                </div>
                <div className="text-[11px] text-zinc-500">
                  {overview.summary.active_today} active today · {overview.summary.active_7d} active this week
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-zinc-400 text-xs">
                  <span>Total Logins Recorded</span>
                  <Activity size={16} className="text-emerald-400" />
                </div>
                <div className="text-3xl font-extrabold text-white">
                  {overview.summary.total_logins}
                </div>
                <div className="text-[11px] text-zinc-500">
                  Across Google, Telegram &amp; Student Pass
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-zinc-400 text-xs">
                  <span>Study Sessions Created</span>
                  <Database size={16} className="text-teal-400" />
                </div>
                <div className="text-3xl font-extrabold text-white">
                  {overview.summary.total_sessions}
                </div>
                <div className="text-[11px] text-zinc-500">
                  Titles encrypted with SHA-256 masking
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-2">
                <div className="flex items-center justify-between text-zinc-400 text-xs">
                  <span>User Queries Processed</span>
                  <MessageSquare size={16} className="text-amber-400" />
                </div>
                <div className="text-3xl font-extrabold text-white">
                  {overview.summary.total_messages}
                </div>
                <div className="text-[11px] text-zinc-500">
                  Guarded by 5-hour atomic rate limiters
                </div>
              </div>
            </div>

            {/* Auth Provider Distribution */}
            <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Key size={15} className="text-amber-400" />
                Authentication Provider Distribution
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {Object.entries(overview.login_type_breakdown).map(([type, count]) => {
                  const percent = Math.round((count / (overview.summary.total_logins || 1)) * 100)
                  return (
                    <div key={type} className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/60 space-y-2">
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold text-zinc-300 capitalize">
                          {type.replace('_', ' ')}
                        </span>
                        <span className="font-bold text-white">{count} ({percent}%)</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className="h-full bg-amber-500 rounded-full"
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Recent Logins Feed */}
            <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Clock size={15} className="text-blue-400" />
                Recent Authenticated Logins (Latest 50 Events)
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-zinc-300">
                  <thead className="bg-zinc-900/70 text-zinc-400 uppercase text-[10px] tracking-wider border-b border-zinc-800">
                    <tr>
                      <th className="py-2.5 px-3">User ID</th>
                      <th className="py-2.5 px-3">Student Name</th>
                      <th className="py-2.5 px-3">Username</th>
                      <th className="py-2.5 px-3">Auth Type</th>
                      <th className="py-2.5 px-3">IP Address</th>
                      <th className="py-2.5 px-3">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    {overview.recent_logins.map((login, idx) => (
                      <tr key={idx} className="hover:bg-zinc-800/20">
                        <td className="py-2.5 px-3 font-mono text-zinc-400">#{login.user_id}</td>
                        <td className="py-2.5 px-3 font-medium text-white">{login.first_name || '—'}</td>
                        <td className="py-2.5 px-3 text-zinc-400">
                          {login.username ? `@${login.username}` : '—'}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-300 border border-zinc-700">
                            {login.login_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-zinc-400">{login.ip_address || '—'}</td>
                        <td className="py-2.5 px-3 text-zinc-500">
                          {login.created_at ? new Date(login.created_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 2: USERS MANAGEMENT ── */}
        {activeTab === 'users' && (
          <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <Users size={15} className="text-emerald-400" />
                  Student Directory &amp; Access Control
                </h2>
                <p className="text-xs text-zinc-500 mt-0.5">
                  Search, monitor, suspend, or wipe student accounts directly.
                </p>
              </div>

              {/* Search Form */}
              <form onSubmit={handleSearchUsers} className="flex items-center gap-2 w-full sm:w-auto">
                <div className="relative flex-1 sm:w-64">
                  <Search size={14} className="absolute left-3 top-2.5 text-zinc-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by ID, name, username..."
                    className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-700"
                  />
                </div>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold transition"
                >
                  Search
                </button>
              </form>
            </div>

            {/* Users Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-zinc-300">
                <thead className="bg-zinc-900/70 text-zinc-400 uppercase text-[10px] tracking-wider border-b border-zinc-800">
                  <tr>
                    <th className="py-2.5 px-3">User ID</th>
                    <th className="py-2.5 px-3">Student Name</th>
                    <th className="py-2.5 px-3">Username</th>
                    <th className="py-2.5 px-3">Logins</th>
                    <th className="py-2.5 px-3">Questions</th>
                    <th className="py-2.5 px-3">Last Active</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {users.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-zinc-500 text-xs">
                        No students found matching your criteria.
                      </td>
                    </tr>
                  ) : (
                    users.map((u) => {
                      const isSelf = user?.id === u.user_id
                      const isActing = userActionLoading === u.user_id

                      return (
                        <tr key={u.user_id} className="hover:bg-zinc-800/20">
                          <td className="py-2.5 px-3 font-mono text-zinc-400">
                            #{u.user_id}
                            {u.is_admin && (
                              <span className="ml-1.5 px-1.5 py-0.2 rounded text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/40">
                                ADMIN
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 font-medium text-white">{u.first_name || '—'}</td>
                          <td className="py-2.5 px-3 text-zinc-400">
                            {u.username ? `@${u.username}` : '—'}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-zinc-300">{u.login_count}</td>
                          <td className="py-2.5 px-3 font-mono text-zinc-300">{u.message_count}</td>
                          <td className="py-2.5 px-3 text-zinc-500">
                            {u.last_seen ? new Date(u.last_seen).toLocaleDateString() : '—'}
                          </td>
                          <td className="py-2.5 px-3">
                            {u.is_suspended ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
                                Suspended
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                                Active
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            {!isSelf && (
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => handleToggleSuspend(u.user_id)}
                                  disabled={isActing}
                                  className={`p-1.5 rounded-lg border transition cursor-pointer ${
                                    u.is_suspended
                                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                                      : 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20'
                                  }`}
                                  title={u.is_suspended ? 'Unsuspend Account' : 'Suspend Account'}
                                >
                                  <Ban size={12} />
                                </button>

                                <button
                                  onClick={() => handleDeleteUser(u.user_id)}
                                  disabled={isActing}
                                  className="p-1.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20 transition cursor-pointer"
                                  title="Permanently Delete User"
                                >
                                  <Trash2 size={12} />
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── TAB 3: SYSTEM HEALTH & TELEMETRY ── */}
        {activeTab === 'health' && (
          <div className="space-y-6">
            {health && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Supabase Status */}
                <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-400">Database Layer</span>
                    <Database size={16} className="text-emerald-400" />
                  </div>
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2.5 h-2.5 rounded-full ${
                        health.supabase.status === 'healthy' ? 'bg-emerald-500' : 'bg-rose-500 animate-ping'
                      }`}
                    />
                    <span className="font-bold text-white text-base capitalize">
                      Supabase REST {health.supabase.status}
                    </span>
                  </div>
                  <div className="text-xs text-zinc-500 space-y-1 font-mono">
                    <div>Configured: {health.supabase.configured ? 'YES' : 'NO'}</div>
                    <div>Latency: {health.supabase.latency_ms ? `${health.supabase.latency_ms} ms` : 'N/A'}</div>
                  </div>
                </div>

                {/* AI Providers */}
                <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-400">AI Routing Layer</span>
                    <Cpu size={16} className="text-blue-400" />
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">Groq (Llama 3.3)</span>
                      <span
                        className={`px-2 py-0.5 rounded font-mono text-[10px] ${
                          health.providers.groq.configured
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : 'bg-zinc-800 text-zinc-500'
                        }`}
                      >
                        {health.providers.groq.status}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">OpenRouter (DeepSeek)</span>
                      <span
                        className={`px-2 py-0.5 rounded font-mono text-[10px] ${
                          health.providers.openrouter.configured
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : 'bg-zinc-800 text-zinc-500'
                        }`}
                      >
                        {health.providers.openrouter.status}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-zinc-300">Google Gemini</span>
                      <span
                        className={`px-2 py-0.5 rounded font-mono text-[10px] ${
                          health.providers.gemini.configured
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : 'bg-zinc-800 text-zinc-500'
                        }`}
                      >
                        {health.providers.gemini.status}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Server State */}
                <div className="p-5 rounded-2xl bg-[#12141c] border border-zinc-800/80 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-400">Enforcement Engine</span>
                    <Clock size={16} className="text-amber-400" />
                  </div>
                  <div className="text-xs text-zinc-300 space-y-1.5 font-mono">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Quota Window:</span>
                      <span className="font-bold text-amber-400">{health.server.quota_window_hours} Hours</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Limit per Window:</span>
                      <span className="font-bold text-white">{health.server.global_message_limit} Queries</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Cached Sessions:</span>
                      <span className="text-zinc-300">{health.server.sessions_cached}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Suspended Users:</span>
                      <span className="text-rose-400">{health.server.suspended_users_count}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
