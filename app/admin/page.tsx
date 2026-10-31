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
  Clock,
  MessageSquare,
  AlertTriangle,
  FileText,
  Download,
  DollarSign,
  BarChart2,
  Sliders,
  AlertCircle,
  Check,
  Eye,
  X,
  Zap,
  Terminal,
  BookOpen,
  ChevronRight,
  Filter
} from 'lucide-react'
import {
  fetchAdminCheck,
  fetchAdminKPIs,
  fetchAdminTimeSeries,
  fetchAdminRequests,
  fetchAdminProviders,
  probeAdminProvider,
  fetchAdminQuotas,
  fetchAdminCosts,
  fetchAdminPdfAnalytics,
  fetchAdminAuditLogs,
  fetchAdminAlerts,
  resolveAdminAlert,
  fetchAdminConfig,
  updateAdminConfig,
  getAdminExportUrl,
  fetchAdminUsers,
  toggleUserSuspend,
  deleteUserAccount,
  checkAuth
} from '@/lib/api'
import type {
  AdminKPIs,
  TimeSeriesBucket,
  AIRequestLog,
  ProviderDetail,
  QuotaObservation,
  PDFAnalytics,
  AdminAuditLog,
  SystemAlert,
  SystemConfig,
  CostsSummary,
  AdminUserRecord,
  User
} from '@/types/api'

type AdminTab =
  | 'overview'
  | 'users'
  | 'ai_observability'
  | 'providers'
  | 'quotas_costs'
  | 'request_logs'
  | 'pdf_analytics'
  | 'security_audit'
  | 'config_exports'

export default function AdminPage() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null)
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [activeTab, setActiveTab] = useState<AdminTab>('overview')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [windowSec, setWindowSec] = useState<number>(86400) // Default 24h

  // Core Data Stores
  const [kpis, setKpis] = useState<AdminKPIs | null>(null)
  const [timeSeries, setTimeSeries] = useState<TimeSeriesBucket[]>([])
  const [providers, setProviders] = useState<Record<string, ProviderDetail>>({})
  const [quotas, setQuotas] = useState<Record<string, QuotaObservation>>({})
  const [costs, setCosts] = useState<CostsSummary | null>(null)
  const [pdfStats, setPdfStats] = useState<PDFAnalytics | null>(null)
  const [alerts, setAlerts] = useState<SystemAlert[]>([])
  const [config, setConfig] = useState<SystemConfig | null>(null)

  // Users Tab State
  const [users, setUsers] = useState<AdminUserRecord[]>([])
  const [userTotal, setUserTotal] = useState(0)
  const [userSearch, setUserSearch] = useState('')
  const [userPage, setUserPage] = useState(1)
  const [selectedUser, setSelectedUser] = useState<AdminUserRecord | null>(null)
  const [userActionLoading, setUserActionLoading] = useState<number | null>(null)

  // Request Logs Tab State
  const [requestLogs, setRequestLogs] = useState<AIRequestLog[]>([])
  const [logTotal, setLogTotal] = useState(0)
  const [logFilterProvider, setLogFilterProvider] = useState('')
  const [logFilterStatus, setLogFilterStatus] = useState('')
  const [logFilterUser, setLogFilterUser] = useState('')
  const [selectedLog, setSelectedLog] = useState<AIRequestLog | null>(null)

  // Audit Logs Tab State
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([])

  // Probe States
  const [probingProvider, setProbingProvider] = useState<string | null>(null)
  const [probeResults, setProbeResults] = useState<Record<string, any>>({})

  // Notifications
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
        setCurrentUser(loggedUser)

        const adminStatus = await fetchAdminCheck()
        setIsAdmin(adminStatus)

        if (adminStatus) {
          await refreshAllData(86400)
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

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefresh || !isAdmin) return
    const interval = setInterval(() => {
      refreshAllData(windowSec, true)
    }, 15000)
    return () => clearInterval(interval)
  }, [autoRefresh, isAdmin, windowSec])

  // Data Loading Routine
  const refreshAllData = async (activeWindow = windowSec, background = false) => {
    if (!background) setRefreshing(true)
    try {
      const [
        kpiData,
        tsData,
        provData,
        quotaData,
        costsData,
        pdfData,
        alertData,
        cfgData,
        usersData,
        logsData,
        auditData
      ] = await Promise.all([
        fetchAdminKPIs(activeWindow).catch(() => null),
        fetchAdminTimeSeries(activeWindow, 24).catch(() => []),
        fetchAdminProviders().catch(() => ({})),
        fetchAdminQuotas().catch(() => ({})),
        fetchAdminCosts().catch(() => null),
        fetchAdminPdfAnalytics().catch(() => null),
        fetchAdminAlerts().catch(() => []),
        fetchAdminConfig().catch(() => null),
        fetchAdminUsers(userSearch, userPage, 25).catch(() => ({ total: 0, page: 1, limit: 25, users: [] })),
        fetchAdminRequests({ limit: 50, provider: logFilterProvider, status: logFilterStatus, user_id: logFilterUser }).catch(() => ({ total: 0, limit: 50, offset: 0, logs: [] })),
        fetchAdminAuditLogs({ limit: 50 }).catch(() => ({ total: 0, limit: 50, offset: 0, logs: [] }))
      ])

      if (kpiData) setKpis(kpiData)
      if (tsData) setTimeSeries(tsData)
      if (provData) setProviders(provData)
      if (quotaData) setQuotas(quotaData)
      if (costsData) setCosts(costsData)
      if (pdfData) setPdfStats(pdfData)
      if (alertData) setAlerts(alertData)
      if (cfgData) setConfig(cfgData)
      if (usersData) {
        setUsers(usersData.users || [])
        setUserTotal(usersData.total || 0)
      }
      if (logsData) {
        setRequestLogs(logsData.logs || [])
        setLogTotal(logsData.total || 0)
      }
      if (auditData) {
        setAuditLogs(auditData.logs || [])
      }
    } catch (e) {
      console.error('Failed refreshing admin telemetry:', e)
      showNotice('Failed to update dashboard data', 'error')
    } finally {
      if (!background) setRefreshing(false)
    }
  }

  // Provider Probe Handler
  const handleProbe = async (providerId: string) => {
    setProbingProvider(providerId)
    try {
      const res = await probeAdminProvider(providerId)
      setProbeResults(prev => ({ ...prev, [providerId]: res }))
      if (res.success) {
        showNotice(`Probe successful for ${providerId}: ${res.latency_ms}ms`, 'success')
      } else {
        showNotice(`Probe failed for ${providerId}: ${res.error || 'Unknown error'}`, 'error')
      }
      // Refresh provider metrics
      const updatedProvs = await fetchAdminProviders().catch(() => null)
      if (updatedProvs) setProviders(updatedProvs)
    } catch (e) {
      showNotice(`Error probing ${providerId}`, 'error')
    } finally {
      setProbingProvider(null)
    }
  }

  // Alert Resolve Handler
  const handleResolveAlert = async (alertId: string) => {
    try {
      await resolveAdminAlert(alertId)
      setAlerts(prev => prev.filter(a => a.id !== alertId))
      showNotice('Alert marked as resolved', 'success')
    } catch (e) {
      showNotice('Failed to resolve alert', 'error')
    }
  }

  // Config Update Handler
  const handleConfigToggle = async (key: string, currentVal: boolean) => {
    try {
      const updated = await updateAdminConfig(key, !currentVal)
      setConfig(updated)
      showNotice(`Updated config: ${key} -> ${!currentVal}`, 'success')
    } catch (e) {
      showNotice(`Failed updating ${key}`, 'error')
    }
  }

  // User Actions
  const handleToggleSuspend = async (targetUser: AdminUserRecord) => {
    setUserActionLoading(targetUser.user_id)
    try {
      const res = await toggleUserSuspend(targetUser.user_id)
      setUsers(prev =>
        prev.map(u => (u.user_id === targetUser.user_id ? { ...u, is_suspended: res.is_suspended } : u))
      )
      if (selectedUser?.user_id === targetUser.user_id) {
        setSelectedUser(prev => prev ? { ...prev, is_suspended: res.is_suspended } : null)
      }
      showNotice(`User ${targetUser.user_id} suspension updated to ${res.is_suspended}`)
    } catch (err: any) {
      showNotice(err.message || 'Failed to toggle suspension', 'error')
    } finally {
      setUserActionLoading(null)
    }
  }

  const handleDeleteUser = async (targetUser: AdminUserRecord) => {
    if (!window.confirm(`Permanently delete account for ${targetUser.username || targetUser.first_name}? This deletes all chat sessions and history.`)) {
      return
    }
    setUserActionLoading(targetUser.user_id)
    try {
      await deleteUserAccount(targetUser.user_id)
      setUsers(prev => prev.filter(u => u.user_id !== targetUser.user_id))
      setUserTotal(prev => Math.max(0, prev - 1))
      if (selectedUser?.user_id === targetUser.user_id) {
        setSelectedUser(null)
      }
      showNotice(`User ${targetUser.user_id} permanently deleted`)
    } catch (err: any) {
      showNotice(err.message || 'Failed to delete user', 'error')
    } finally {
      setUserActionLoading(null)
    }
  }

  // ── AUTH GUARDS ──
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-300">
        <RefreshCw className="w-8 h-8 animate-spin text-purple-500 mb-4" />
        <p className="text-sm tracking-wide text-slate-400">Verifying administrative security credentials...</p>
      </div>
    )
  }

  if (isAdmin === false) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center px-4 text-center">
        <div className="p-4 bg-red-950/40 border border-red-500/30 rounded-2xl max-w-md w-full backdrop-blur-sm">
          <ShieldAlert className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <h1 className="text-xl font-bold text-red-200 mb-1">Access Restricted</h1>
          <p className="text-sm text-slate-400 mb-6">
            You are logged in as <span className="text-slate-200 font-mono">{currentUser?.email || currentUser?.username || 'Guest'}</span>.
            This terminal requires verified administrative authorization.
          </p>
          <Link
            href="/"
            className="inline-flex items-center justify-center w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-xl transition"
          >
            <ArrowLeft className="w-4 h-4 mr-2" /> Return to Chat
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-purple-900 selection:text-white">
      {/* Toast Notification */}
      {notice && (
        <div
          className={`fixed bottom-5 right-5 z-50 flex items-center px-4 py-3 rounded-xl shadow-2xl border text-sm backdrop-blur-md animate-fade-in ${
            notice.type === 'error'
              ? 'bg-red-950/90 border-red-500/50 text-red-200'
              : 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200'
          }`}
        >
          {notice.type === 'error' ? <AlertCircle className="w-4 h-4 mr-2" /> : <CheckCircle className="w-4 h-4 mr-2" />}
          {notice.message}
        </div>
      )}

      {/* TOP COMMAND BAR */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-3 lg:px-8 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-2 sm:space-x-3">
          <Link
            href="/"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition min-h-[38px] min-w-[38px] flex items-center justify-center"
            title="Return to Application"
            aria-label="Return to chat"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-purple-900/30 flex-shrink-0">
              <ShieldCheck className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5 sm:space-x-2">
                <span className="font-bold text-sm sm:text-base tracking-tight text-white">BrainyAi</span>
                <span className="text-[10px] sm:text-[11px] font-semibold uppercase tracking-wider px-1.5 sm:px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  Admin
                </span>
              </div>
              <p className="text-[10px] sm:text-[11px] text-slate-400 hidden xs:block">AI Operations & Token Accounting</p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 sm:space-x-3">
          {/* Time Window Selector (Dropdown on mobile, pills on sm+) */}
          <select
            value={windowSec}
            onChange={(e) => {
              const val = Number(e.target.value)
              setWindowSec(val)
              refreshAllData(val)
            }}
            className="sm:hidden bg-slate-800 text-slate-200 border border-slate-700 text-xs rounded-lg px-2 py-1.5 focus:outline-none min-h-[36px]"
            aria-label="Select time window"
          >
            <option value={3600}>1H</option>
            <option value={86400}>24H</option>
            <option value={604800}>7D</option>
            <option value={2592000}>30D</option>
          </select>

          <div className="hidden sm:flex items-center bg-slate-800/80 rounded-lg p-0.5 border border-slate-700 text-xs">
            {[
              { label: '1H', val: 3600 },
              { label: '24H', val: 86400 },
              { label: '7D', val: 604800 },
              { label: '30D', val: 2592000 }
            ].map(w => (
              <button
                key={w.val}
                onClick={() => {
                  setWindowSec(w.val)
                  refreshAllData(w.val)
                }}
                className={`px-2.5 py-1 rounded-md font-medium transition ${
                  windowSec === w.val
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>

          {/* Live Polling Status */}
          <div className="flex items-center space-x-1.5 sm:space-x-2 px-2 sm:px-2.5 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300 min-h-[36px]">
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                refreshing
                  ? 'bg-amber-400 animate-ping'
                  : autoRefresh
                  ? 'bg-emerald-400 animate-pulse'
                  : 'bg-slate-500'
              }`}
            />
            <span className="hidden md:inline font-mono text-[11px]">
              {refreshing ? 'Updating...' : autoRefresh ? 'Live Feed' : 'Manual'}
            </span>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className="text-[10px] sm:text-xs text-purple-400 hover:underline ml-0.5"
            >
              {autoRefresh ? 'Pause' : 'Stream'}
            </button>
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => refreshAllData(windowSec)}
            disabled={refreshing}
            className="p-2 min-h-[36px] min-w-[36px] flex items-center justify-center rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition disabled:opacity-50"
            title="Refresh Metrics"
            aria-label="Refresh metrics"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* NAVIGATION TABS */}
      <nav className="bg-slate-900 border-b border-slate-800 px-3 lg:px-8 overflow-x-auto flex space-x-1 py-1.5 scrollbar-none flex-nowrap">
        {[
          { id: 'overview', label: 'Overview', icon: BarChart2 },
          { id: 'users', label: 'Users', icon: Users, badge: kpis?.total_users },
          { id: 'ai_observability', label: 'AI Observability', icon: Activity },
          { id: 'providers', label: 'Providers & Models', icon: Cpu },
          { id: 'quotas_costs', label: 'Quotas & Costs', icon: DollarSign },
          { id: 'request_logs', label: 'Request Logs', icon: Terminal, badge: logTotal },
          { id: 'pdf_analytics', label: 'PDF Studio', icon: BookOpen, badge: pdfStats?.total_documents },
          { id: 'security_audit', label: 'Security & Alerts', icon: ShieldCheck, badge: alerts.length ? alerts.length : undefined },
          { id: 'config_exports', label: 'Config & Exports', icon: Sliders }
        ].map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as AdminTab)}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition cursor-pointer flex-shrink-0 min-h-[36px] ${
                isActive
                  ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 p-4 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
        {/* ── 1. OVERVIEW VIEW ── */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Top KPI Cards Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span>Total AI Requests</span>
                  <Activity className="w-4 h-4 text-purple-400" />
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono text-white">
                    {kpis?.total_requests?.toLocaleString() ?? 0}
                  </span>
                  <span className="text-xs text-emerald-400 font-medium">
                    {kpis?.success_rate_pct ?? 100}% success
                  </span>
                </div>
                <div className="mt-2 text-[11px] text-slate-500">
                  {kpis?.fallback_requests ?? 0} routed via fallback
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span>Total Tokens Processed</span>
                  <Cpu className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono text-white">
                    {kpis?.total_tokens ? `${(kpis.total_tokens / 1000).toFixed(1)}k` : '0'}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    avg {Math.round(kpis?.avg_tokens_per_request ?? 0)}/req
                  </span>
                </div>
                <div className="mt-2 text-[11px] text-slate-500">
                  In: {kpis?.input_tokens?.toLocaleString() ?? 0} | Out: {kpis?.output_tokens?.toLocaleString() ?? 0}
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span>Estimated Cost USD</span>
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono text-emerald-400">
                    ${kpis?.estimated_cost_usd?.toFixed(4) ?? '0.0000'}
                  </span>
                  <span className="text-[10px] uppercase tracking-wider text-slate-400 px-1.5 py-0.5 rounded bg-slate-800">
                    Verified
                  </span>
                </div>
                <div className="mt-2 text-[11px] text-slate-500">
                  Across 5 AI routing backends
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 text-xs">
                  <span>Active Users</span>
                  <Users className="w-4 h-4 text-blue-400" />
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono text-white">
                    {kpis?.total_users?.toLocaleString() ?? 0}
                  </span>
                  <span className="text-xs text-blue-400">
                    {kpis?.active_users_today ?? 0} today
                  </span>
                </div>
                <div className="mt-2 text-[11px] text-slate-500">
                  {kpis?.suspended_users ?? 0} suspended
                </div>
              </div>
            </div>

            {/* Performance Bar Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">Average Latency</span>
                <div className="text-xl font-bold font-mono text-white mt-1">
                  {kpis?.avg_latency_ms ? `${kpis.avg_latency_ms.toFixed(0)} ms` : '—'}
                </div>
                <span className="text-[11px] text-slate-500">End-to-end response time</span>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">P95 Latency</span>
                <div className="text-xl font-bold font-mono text-amber-300 mt-1">
                  {kpis?.p95_latency_ms ? `${kpis.p95_latency_ms.toFixed(0)} ms` : '—'}
                </div>
                <span className="text-[11px] text-slate-500">95th percentile worst-case</span>
              </div>
              <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">PDF Study Documents</span>
                <div className="text-xl font-bold font-mono text-purple-300 mt-1">
                  {kpis?.total_pdf_documents ?? 0} docs ({kpis?.total_pdf_pages ?? 0} pgs)
                </div>
                <span className="text-[11px] text-slate-500">Locally extracted & indexed</span>
              </div>
            </div>

            {/* Interactive SVG Request Volume Trend */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-semibold text-white">AI Request Volume & Token Distribution</h3>
                  <p className="text-xs text-slate-400">Real hourly traffic buckets across the selected timeframe</p>
                </div>
                <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2 py-1 rounded border border-purple-500/20">
                  {timeSeries.reduce((acc, b) => acc + b.requests, 0)} Total Calls
                </span>
              </div>

              {timeSeries.length === 0 || timeSeries.every(b => b.requests === 0) ? (
                <div className="h-44 flex flex-col items-center justify-center text-slate-500 text-xs border border-dashed border-slate-800 rounded-lg">
                  <Activity className="w-6 h-6 mb-2 text-slate-600" />
                  <span>No traffic recorded in this time window</span>
                </div>
              ) : (
                <div className="h-48 flex items-end space-x-1.5 pt-4 pb-1">
                  {(() => {
                    const maxReq = Math.max(...timeSeries.map(b => b.requests), 1)
                    return timeSeries.map((b, idx) => {
                      const heightPct = Math.max(4, Math.round((b.requests / maxReq) * 100))
                      return (
                        <div key={idx} className="flex-1 flex flex-col items-center group relative h-full justify-end">
                          {/* Tooltip */}
                          <div className="absolute -top-12 z-20 hidden group-hover:flex flex-col items-center pointer-events-none bg-slate-800 text-[10px] text-slate-200 px-2 py-1 rounded shadow-lg border border-slate-700 whitespace-nowrap">
                            <span>{b.time_label}: {b.requests} reqs</span>
                            <span className="text-purple-300 font-mono">{b.total_tokens} tokens (${b.cost_usd.toFixed(5)})</span>
                          </div>
                          <div
                            style={{ height: `${heightPct}%` }}
                            className={`w-full rounded-t transition-all ${
                              b.failed > 0
                                ? 'bg-gradient-to-t from-red-600 to-purple-500'
                                : 'bg-gradient-to-t from-purple-700 to-indigo-500 group-hover:from-purple-500 group-hover:to-indigo-400'
                            }`}
                          />
                          <span className="text-[9px] text-slate-500 font-mono mt-1 rotate-45 sm:rotate-0 origin-left">
                            {idx % 4 === 0 ? b.time_label : ''}
                          </span>
                        </div>
                      )
                    })
                  })()}
                </div>
              )}
            </div>

            {/* Quick Actions & Live Providers Snapshot */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Providers Snapshot */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Multi-Provider Router Pool</h3>
                  <button
                    onClick={() => setActiveTab('providers')}
                    className="text-xs text-purple-400 hover:underline flex items-center"
                  >
                    View All <ChevronRight className="w-3 h-3 ml-0.5" />
                  </button>
                </div>
                <div className="space-y-2">
                  {Object.entries(providers).map(([pid, p]) => (
                    <div
                      key={pid}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/40 border border-slate-800/80 text-xs"
                    >
                      <div className="flex items-center space-x-2.5">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            p.configured ? (p.health?.error_rate_pct > 20 ? 'bg-amber-400' : 'bg-emerald-400') : 'bg-slate-600'
                          }`}
                        />
                        <span className="font-semibold text-slate-200">{p.name}</span>
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                          {p.masked_key}
                        </span>
                      </div>
                      <div className="flex items-center space-x-3 text-slate-400">
                        <span>{p.health?.total_requests ?? 0} calls</span>
                        <span className="font-mono text-slate-300">
                          {p.health?.avg_latency_ms ? `${Math.round(p.health.avg_latency_ms)}ms` : '—'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Active System Alerts / Status */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Operational Health Alerts</h3>
                    <span className="text-[11px] text-slate-400">{alerts.length} active</span>
                  </div>
                  {alerts.length === 0 ? (
                    <div className="p-6 text-center text-slate-500 text-xs">
                      <CheckCircle className="w-6 h-6 text-emerald-400 mx-auto mb-2 opacity-80" />
                      All provider routes and storage clusters are performing normally.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {alerts.map(a => (
                        <div
                          key={a.id}
                          className="flex items-start justify-between p-2.5 rounded-lg bg-amber-950/20 border border-amber-500/30 text-xs"
                        >
                          <div className="flex items-start space-x-2">
                            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                            <div>
                              <p className="font-medium text-amber-200">{a.title}</p>
                              <p className="text-[11px] text-slate-400">{a.message}</p>
                            </div>
                          </div>
                          <button
                            onClick={() => handleResolveAlert(a.id)}
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] ml-2 flex-shrink-0"
                          >
                            Resolve
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                  <span>Server: {kpis?.server_time_iso ? new Date(kpis.server_time_iso).toLocaleTimeString() : '—'}</span>
                  <button
                    onClick={() => setActiveTab('config_exports')}
                    className="text-purple-400 hover:underline"
                  >
                    Export System Audit →
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── 2. USERS MANAGEMENT TAB ── */}
        {activeTab === 'users' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-white">Registered User Directory</h2>
                <p className="text-xs text-slate-400">Manage accounts, inspect token consumption, and toggle access permissions</p>
              </div>
              <div className="flex items-center space-x-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={userSearch}
                    onChange={e => setUserSearch(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && refreshAllData(windowSec)}
                    placeholder="Search by ID, username, email..."
                    className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500 w-64"
                  />
                </div>
                <button
                  onClick={() => refreshAllData(windowSec)}
                  className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition"
                >
                  Search
                </button>
              </div>
            </div>

            {/* Users Table */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">User</th>
                      <th className="py-3 px-4">Role / Provider</th>
                      <th className="py-3 px-4">Chat Messages</th>
                      <th className="py-3 px-4">Last Login</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {users.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-500">
                          No registered users found matching the query.
                        </td>
                      </tr>
                    ) : (
                      users.map(u => (
                        <tr key={u.user_id} className="hover:bg-slate-800/30 transition">
                          <td className="py-3 px-4">
                            <div className="flex items-center space-x-2.5">
                              <div className="w-7 h-7 rounded-full bg-purple-600/30 text-purple-300 flex items-center justify-center font-bold text-xs uppercase border border-purple-500/20">
                                {(u.first_name || u.username || 'U')[0]}
                              </div>
                              <div>
                                <button
                                  onClick={() => setSelectedUser(u)}
                                  className="font-medium text-slate-200 hover:text-purple-300 text-left"
                                >
                                  {u.first_name || 'Anonymous User'}
                                </button>
                                <div className="text-[11px] text-slate-500 font-mono">
                                  ID: {u.user_id} {u.username ? `• @${u.username}` : ''}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center space-x-1.5">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider ${
                                u.is_admin ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'bg-slate-800 text-slate-400'
                              }`}>
                                {u.is_admin ? 'Admin' : 'Student'}
                              </span>
                              {u.login_types?.map((lt: string, i: number) => (
                                <span key={i} className="text-[10px] text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded">
                                  {lt}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-300">
                            {u.message_count ?? 0} msgs {u.session_count !== undefined ? `(${u.session_count} chats)` : ''}
                          </td>
                          <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                            {(u.last_seen || u.last_login_at) ? new Date(u.last_seen || u.last_login_at!).toLocaleDateString() : '—'}
                          </td>
                          <td className="py-3 px-4">
                            {u.is_suspended ? (
                              <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30 text-[10px] font-medium">
                                Suspended
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-medium">
                                Active
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end space-x-1.5">
                              <button
                                onClick={() => setSelectedUser(u)}
                                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                                title="Inspect User Details"
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleToggleSuspend(u)}
                                disabled={userActionLoading === u.user_id || u.is_admin}
                                className={`p-1.5 rounded-lg border transition ${
                                  u.is_suspended
                                    ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300 hover:bg-emerald-900/60'
                                    : 'bg-amber-950/40 border-amber-500/40 text-amber-300 hover:bg-amber-900/60'
                                } disabled:opacity-30`}
                                title={u.is_suspended ? 'Reactivate User' : 'Suspend User'}
                              >
                                <Ban className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteUser(u)}
                                disabled={userActionLoading === u.user_id || u.is_admin}
                                className="p-1.5 rounded-lg bg-red-950/40 border border-red-500/40 text-red-300 hover:bg-red-900/60 transition disabled:opacity-30"
                                title="Delete Account"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* User Detail Drawer Modal */}
            {selectedUser && (
              <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                    <div className="flex items-center space-x-2.5">
                      <div className="w-9 h-9 rounded-full bg-purple-600/30 text-purple-300 flex items-center justify-center font-bold text-sm">
                        {(selectedUser.first_name || 'U')[0]}
                      </div>
                      <div>
                        <h3 className="font-bold text-white text-sm">{selectedUser.first_name || 'User'}</h3>
                        <p className="text-xs text-slate-400 font-mono">User ID: {selectedUser.user_id}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedUser(null)}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-100"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-slate-400">Username</span>
                      <div className="font-medium text-slate-200 mt-0.5">{selectedUser.username ? `@${selectedUser.username}` : 'Not set'}</div>
                    </div>
                    <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-slate-400">Account Status</span>
                      <div className="font-medium text-slate-200 mt-0.5">
                        {selectedUser.is_suspended ? 'Suspended' : 'Active'}
                      </div>
                    </div>
                    <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-slate-400">Total Chats</span>
                      <div className="font-medium text-slate-200 mt-0.5">{selectedUser.session_count ?? selectedUser.login_count ?? 0} sessions</div>
                    </div>
                    <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-800">
                      <span className="text-slate-400">Student Messages</span>
                      <div className="font-medium text-slate-200 mt-0.5">{selectedUser.message_count ?? 0} prompts</div>
                    </div>
                  </div>

                  <div className="flex items-center justify-end space-x-2 pt-2">
                    <button
                      onClick={() => handleToggleSuspend(selectedUser)}
                      className="px-3 py-1.5 rounded-lg border border-amber-500/40 text-amber-300 text-xs font-medium hover:bg-amber-950/40 transition"
                    >
                      {selectedUser.is_suspended ? 'Unsuspend' : 'Suspend Account'}
                    </button>
                    <button
                      onClick={() => handleDeleteUser(selectedUser)}
                      className="px-3 py-1.5 rounded-lg border border-red-500/40 text-red-300 text-xs font-medium hover:bg-red-950/40 transition"
                    >
                      Delete User
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── 3. AI OBSERVABILITY & TOKEN ACCOUNTING TAB ── */}
        {activeTab === 'ai_observability' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">AI Observability & Token Metrics</h2>
              <p className="text-xs text-slate-400">Granular input/output token accounting, latencies, and fallback distributions</p>
            </div>

            {/* Token Breakdown Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                <span className="text-xs text-slate-400">Prompt Tokens (Input)</span>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {kpis?.input_tokens?.toLocaleString() ?? 0}
                </div>
                <p className="text-[11px] text-slate-500 mt-2">Tokens sent in system & student messages</p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                <span className="text-xs text-slate-400">Completion Tokens (Output)</span>
                <div className="text-2xl font-bold font-mono text-purple-300 mt-1">
                  {kpis?.output_tokens?.toLocaleString() ?? 0}
                </div>
                <p className="text-[11px] text-slate-500 mt-2">Generated tokens delivered across providers</p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                <span className="text-xs text-slate-400">Router Failover & Continuations</span>
                <div className="text-2xl font-bold font-mono text-indigo-300 mt-1">
                  {kpis?.fallback_requests ?? 0} recovered
                </div>
                <p className="text-[11px] text-slate-500 mt-2">Seamless pre-output provider rotations</p>
              </div>
            </div>

            {/* Time Series Table */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Hourly Traffic & Latency Ledger</h3>
                <span className="text-[11px] text-slate-400">{timeSeries.length} intervals</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Window</th>
                      <th className="py-2.5 px-4">Calls</th>
                      <th className="py-2.5 px-4">Success / Fail</th>
                      <th className="py-2.5 px-4">Tokens In</th>
                      <th className="py-2.5 px-4">Tokens Out</th>
                      <th className="py-2.5 px-4">Avg Latency</th>
                      <th className="py-2.5 px-4 text-right">Cost USD</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                    {timeSeries.map((b, i) => (
                      <tr key={i} className="hover:bg-slate-800/20">
                        <td className="py-2 px-4 text-slate-400">{b.time_label}</td>
                        <td className="py-2 px-4 font-semibold text-white">{b.requests}</td>
                        <td className="py-2 px-4">
                          <span className="text-emerald-400">{b.successful}</span> /{' '}
                          <span className={b.failed > 0 ? 'text-red-400 font-bold' : 'text-slate-500'}>
                            {b.failed}
                          </span>
                        </td>
                        <td className="py-2 px-4 text-slate-400">{b.input_tokens.toLocaleString()}</td>
                        <td className="py-2 px-4 text-purple-300">{b.output_tokens.toLocaleString()}</td>
                        <td className="py-2 px-4 text-slate-300">{b.avg_latency_ms ? `${b.avg_latency_ms} ms` : '—'}</td>
                        <td className="py-2 px-4 text-right text-emerald-400">${b.cost_usd.toFixed(5)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── 4. PROVIDERS & MODELS TAB ── */}
        {activeTab === 'providers' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-base font-bold text-white">AI Provider Hierarchy & Real Probes</h2>
                <p className="text-xs text-slate-400">Live operational status, configured credentials, and real-time connectivity probes</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(providers).map(([pid, p]) => (
                <div key={pid} className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2.5">
                        <span
                          className={`w-3 h-3 rounded-full ${
                            p.configured ? (p.health?.error_rate_pct > 20 ? 'bg-amber-400' : 'bg-emerald-400') : 'bg-slate-600'
                          }`}
                        />
                        <h3 className="font-bold text-white text-sm">{p.name}</h3>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider ${
                        p.configured ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {p.configured ? 'Configured' : 'Missing Key'}
                      </span>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono">
                      <div className="p-2 bg-slate-800/40 rounded border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase">Requests</span>
                        <div className="text-slate-200 mt-0.5">{p.health?.total_requests ?? 0} ({p.health?.error_rate_pct ?? 0}% err)</div>
                      </div>
                      <div className="p-2 bg-slate-800/40 rounded border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase">Avg Latency</span>
                        <div className="text-slate-200 mt-0.5">{p.health?.avg_latency_ms ? `${Math.round(p.health.avg_latency_ms)} ms` : '—'}</div>
                      </div>
                    </div>

                    <div className="mt-3">
                      <span className="text-[11px] text-slate-400 font-medium">Available Models:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {p.models.map((m: string, i: number) => (
                          <span key={i} className="text-[10px] font-mono text-purple-300 bg-purple-950/40 border border-purple-500/20 px-2 py-0.5 rounded">
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>

                    {probeResults[pid] && (
                      <div className={`mt-3 p-2.5 rounded-lg border text-xs font-mono ${
                        probeResults[pid].success
                          ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
                          : 'bg-red-950/30 border-red-500/40 text-red-300'
                      }`}>
                        Probe result: {probeResults[pid].success ? `OK (${probeResults[pid].latency_ms}ms)` : `FAILED (${probeResults[pid].error})`}
                      </div>
                    )}
                  </div>

                  <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                    <span className="text-[11px] text-slate-500 font-mono">Key: {p.masked_key}</span>
                    <button
                      onClick={() => handleProbe(pid)}
                      disabled={probingProvider === pid}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 flex items-center space-x-1.5 transition disabled:opacity-50"
                    >
                      <Zap className={`w-3.5 h-3.5 text-amber-400 ${probingProvider === pid ? 'animate-spin' : ''}`} />
                      <span>{probingProvider === pid ? 'Pinging...' : 'Live Probe'}</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── 5. QUOTAS & COSTS TAB ── */}
        {activeTab === 'quotas_costs' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Rate-Limit Quotas & Pricing Registry</h2>
              <p className="text-xs text-slate-400">Observed upstream headers and official per-model token cost accounting</p>
            </div>

            {/* Observed Quotas */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                Upstream Provider Rate-Limit Headers (Observed)
              </h3>
              {Object.keys(quotas).length === 0 ? (
                <p className="text-xs text-slate-500">
                  No rate-limit headers recorded yet. Headers are automatically observed and parsed when providers return <code className="text-purple-400">x-ratelimit-*</code> response headers.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(quotas).map(([prov, q]) => (
                    <div key={prov} className="p-3 bg-slate-800/40 rounded-lg border border-slate-800 text-xs font-mono space-y-1">
                      <div className="flex items-center justify-between text-slate-200 font-bold">
                        <span>{prov.toUpperCase()}</span>
                        <span className="text-[10px] text-slate-400">{q.observed_iso ? new Date(q.observed_iso).toLocaleTimeString() : ''}</span>
                      </div>
                      <div className="text-slate-400">
                        Remaining Requests: <span className="text-emerald-400">{q.remaining_requests ?? 'Unlimited'}</span> / {q.limit_requests ?? '—'}
                      </div>
                      <div className="text-slate-400">
                        Remaining Tokens: <span className="text-emerald-400">{q.remaining_tokens?.toLocaleString() ?? 'Unlimited'}</span> / {q.limit_tokens?.toLocaleString() ?? '—'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Pricing Registry Table */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                  Verified Model Pricing Rates (per 1,000,000 tokens)
                </h3>
                <span className="text-[10px] text-emerald-400 font-mono">Official Oct 2026 Documentation</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Model Identifier</th>
                      <th className="py-2.5 px-4">Input Price / 1M</th>
                      <th className="py-2.5 px-4">Output Price / 1M</th>
                      <th className="py-2.5 px-4">Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {costs?.pricing_registry &&
                      Object.entries(costs.pricing_registry).map(([m, r]) => (
                        <tr key={m} className="hover:bg-slate-800/20">
                          <td className="py-2 px-4 text-purple-300 font-medium">{m}</td>
                          <td className="py-2 px-4 text-slate-200">${r.input.toFixed(3)}</td>
                          <td className="py-2 px-4 text-slate-200">${r.output.toFixed(3)}</td>
                          <td className="py-2 px-4">
                            {r.input === 0 && r.output === 0 ? (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">Free Tier</span>
                            ) : (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">Standard</span>
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── 6. REQUEST LOGS INSPECTOR TAB ── */}
        {activeTab === 'request_logs' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-white">Live AI Request Stream & Audit</h2>
                <p className="text-xs text-slate-400">Zero sensitive prompts or API keys logged. Full token, latency, and status inspection.</p>
              </div>
              {/* Filter controls */}
              <div className="flex items-center space-x-2">
                <select
                  value={logFilterProvider}
                  onChange={e => {
                    setLogFilterProvider(e.target.value)
                  }}
                  className="bg-slate-900 border border-slate-800 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="">All Providers</option>
                  <option value="groq">Groq</option>
                  <option value="gemini">Gemini</option>
                  <option value="sambanova">SambaNova</option>
                  <option value="cerebras">Cerebras</option>
                  <option value="openrouter">OpenRouter</option>
                </select>
                <select
                  value={logFilterStatus}
                  onChange={e => {
                    setLogFilterStatus(e.target.value)
                  }}
                  className="bg-slate-900 border border-slate-800 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="">All Statuses</option>
                  <option value="success">Success</option>
                  <option value="error">Error</option>
                  <option value="fallback_recovered">Fallback Recovered</option>
                </select>
                <button
                  onClick={() => refreshAllData(windowSec)}
                  className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition"
                >
                  Filter
                </button>
              </div>
            </div>

            {/* Request Logs Table */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Request ID / Time</th>
                      <th className="py-2.5 px-4">User</th>
                      <th className="py-2.5 px-4">Task</th>
                      <th className="py-2.5 px-4">Provider & Model</th>
                      <th className="py-2.5 px-4">Latency (TTFT)</th>
                      <th className="py-2.5 px-4">Tokens</th>
                      <th className="py-2.5 px-4">Cost USD</th>
                      <th className="py-2.5 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {requestLogs.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-slate-500 font-sans">
                          No AI request logs recorded matching current filters.
                        </td>
                      </tr>
                    ) : (
                      requestLogs.map(r => (
                        <tr
                          key={r.request_id}
                          onClick={() => setSelectedLog(r)}
                          className="hover:bg-slate-800/40 transition cursor-pointer"
                        >
                          <td className="py-2 px-4">
                            <span className="text-purple-300 font-medium">{r.request_id.slice(0, 8)}...</span>
                            <div className="text-[10px] text-slate-500">
                              {r.timestamp ? new Date(r.timestamp * 1000).toLocaleTimeString() : '—'}
                            </div>
                          </td>
                          <td className="py-2 px-4 text-slate-400">
                            {r.user_id ? `ID: ${r.user_id}` : 'system'}
                          </td>
                          <td className="py-2 px-4">
                            <span className="text-[10px] font-sans px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                              {r.task}
                            </span>
                          </td>
                          <td className="py-2 px-4">
                            <span className="text-slate-200 font-semibold">{r.provider}</span>
                            <div className="text-[10px] text-slate-400 truncate max-w-xs">{r.model}</div>
                          </td>
                          <td className="py-2 px-4">
                            <span>{Math.round(r.latency_ms)}ms</span>
                            {r.ttft_ms && <span className="text-[10px] text-slate-500 block">({Math.round(r.ttft_ms)}ms ttft)</span>}
                          </td>
                          <td className="py-2 px-4">
                            <span className="text-slate-200">{r.total_tokens ?? 0}</span>
                            <span className="text-[10px] text-slate-500 block">
                              {r.input_tokens ?? 0} in / {r.output_tokens ?? 0} out
                            </span>
                          </td>
                          <td className="py-2 px-4 text-emerald-400">${r.cost_usd.toFixed(5)}</td>
                          <td className="py-2 px-4">
                            {r.status === 'error' ? (
                              <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 text-[10px]">Failed</span>
                            ) : r.fallback_used ? (
                              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px]">Recovered</span>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">Success</span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Log Detail Inspector Modal */}
            {selectedLog && (
              <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                    <div>
                      <h3 className="font-bold text-white text-sm">Request Telemetry Record</h3>
                      <p className="text-xs text-slate-400 font-mono">{selectedLog.request_id}</p>
                    </div>
                    <button
                      onClick={() => setSelectedLog(null)}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-100"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="space-y-2 text-xs font-mono">
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-500">Provider & Model:</span>
                      <span className="text-slate-200">{selectedLog.provider} / {selectedLog.model}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-500">Task Classification:</span>
                      <span className="text-slate-200">{selectedLog.task} ({selectedLog.depth})</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-500">Latency:</span>
                      <span className="text-slate-200">{selectedLog.latency_ms.toFixed(1)} ms</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-500">Tokens:</span>
                      <span className="text-slate-200">{selectedLog.input_tokens} In | {selectedLog.output_tokens} Out ({selectedLog.total_tokens} Total)</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-500">Calculated Cost:</span>
                      <span className="text-emerald-400 font-bold">${selectedLog.cost_usd.toFixed(6)} USD</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-500">Fallback Used:</span>
                      <span className="text-slate-200">{selectedLog.fallback_used ? `Yes (from ${selectedLog.fallback_from})` : 'No'}</span>
                    </div>
                    {selectedLog.error_category && (
                      <div className="flex justify-between py-1 border-b border-slate-800/60 text-red-300">
                        <span>Error Category:</span>
                        <span>{selectedLog.error_category}</span>
                      </div>
                    )}
                  </div>

                  <div className="pt-2 text-right">
                    <button
                      onClick={() => setSelectedLog(null)}
                      className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium"
                    >
                      Close Inspector
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── 7. PDF STUDY STUDIO ANALYTICS TAB ── */}
        {activeTab === 'pdf_analytics' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">PDF Study Studio Document Analytics</h2>
              <p className="text-xs text-slate-400">Tracking local document extraction, native text vs OCR fallback, and storage footprint</p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">Total Uploaded Docs</span>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {pdfStats?.total_documents ?? 0}
                </div>
                <span className="text-[11px] text-slate-500">{pdfStats?.total_pages ?? 0} total pages</span>
              </div>
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">Native Text Pages</span>
                <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                  {pdfStats?.native_pages ?? 0}
                </div>
                <span className="text-[11px] text-slate-500">Zero AI token extraction</span>
              </div>
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">OCR Fallback Pages</span>
                <div className="text-2xl font-bold font-mono text-amber-300 mt-1">
                  {pdfStats?.ocr_pages ?? 0}
                </div>
                <span className="text-[11px] text-slate-500">Scanned / image pages</span>
              </div>
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                <span className="text-xs text-slate-400">Avg Extraction Time</span>
                <div className="text-2xl font-bold font-mono text-purple-300 mt-1">
                  {pdfStats?.avg_extraction_time_ms ? `${pdfStats.avg_extraction_time_ms.toFixed(0)} ms` : '—'}
                </div>
                <span className="text-[11px] text-slate-500">Local PyMuPDF pipeline</span>
              </div>
            </div>

            {/* Recent Uploads Table */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-800">
                <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Recently Processed Documents</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Filename / ID</th>
                      <th className="py-2.5 px-4">Pages</th>
                      <th className="py-2.5 px-4">File Size</th>
                      <th className="py-2.5 px-4">Extraction Time</th>
                      <th className="py-2.5 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300 font-mono">
                    {pdfStats?.recent_documents && pdfStats.recent_documents.length > 0 ? (
                      pdfStats.recent_documents.map(d => (
                        <tr key={d.id} className="hover:bg-slate-800/20">
                          <td className="py-2 px-4 font-sans">
                            <span className="font-medium text-slate-200">{d.filename}</span>
                            <div className="text-[10px] text-slate-500 font-mono">{d.id}</div>
                          </td>
                          <td className="py-2 px-4">{d.page_count} pgs</td>
                          <td className="py-2 px-4">{(d.file_size_bytes / 1024).toFixed(1)} KB</td>
                          <td className="py-2 px-4">{d.extraction_time_ms ? `${d.extraction_time_ms}ms` : '—'}</td>
                          <td className="py-2 px-4">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-sans">
                              {d.status || 'ready'}
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-500 font-sans">
                          No PDF documents uploaded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── 8. SECURITY & AUDIT TRAIL TAB ── */}
        {activeTab === 'security_audit' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Security Compliance & Administrative Audit Trail</h2>
              <p className="text-xs text-slate-400">Immutable ledger of privileged actions, suspension events, and credential tests</p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Audit Log Events</h3>
                <span className="text-[11px] text-slate-400 font-mono">{auditLogs.length} entries</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Timestamp (UTC)</th>
                      <th className="py-2.5 px-4">Administrator</th>
                      <th className="py-2.5 px-4">Action</th>
                      <th className="py-2.5 px-4">Target</th>
                      <th className="py-2.5 px-4">IP Address</th>
                      <th className="py-2.5 px-4 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {auditLogs.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-500 font-sans">
                          No administrative actions recorded in the active session.
                        </td>
                      </tr>
                    ) : (
                      auditLogs.map(l => (
                        <tr key={l.id} className="hover:bg-slate-800/20">
                          <td className="py-2 px-4 text-slate-400">
                            {l.created_at ? new Date(l.created_at).toLocaleString() : '—'}
                          </td>
                          <td className="py-2 px-4 text-purple-300 font-medium">
                            {l.actor_email || l.actor_id || 'system'}
                          </td>
                          <td className="py-2 px-4">
                            <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700">
                              {l.action}
                            </span>
                          </td>
                          <td className="py-2 px-4 text-slate-400">
                            {l.target_type ? `${l.target_type}:${l.target_id || ''}` : '—'}
                          </td>
                          <td className="py-2 px-4 text-slate-500">{l.ip_address || '127.0.0.1'}</td>
                          <td className="py-2 px-4 text-right text-slate-400 text-[11px] truncate max-w-xs">
                            {JSON.stringify(l.details || {})}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── 9. CONFIGURATION & SAFE CSV EXPORTS TAB ── */}
        {activeTab === 'config_exports' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">System Feature Config & Secure Data Exports</h2>
              <p className="text-xs text-slate-400">Manage runtime operational flags and generate injection-defended CSV reports</p>
            </div>

            {/* Feature Flags Grid */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Operational Feature Toggles</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { key: 'maintenance_mode', label: 'Maintenance Mode', desc: 'Denies student requests gracefully with system status notice' },
                  { key: 'enable_web_grounding', label: 'Web Research Grounding', desc: 'Allows pre-search hooks on Tavily and DuckDuckGo' },
                  { key: 'enable_ocr_fallback', label: 'OCR Extraction Fallback', desc: 'Runs Tesseract/Tesseract-OCR when native text density is 0' }
                ].map(item => {
                  const val = Boolean(config ? config[item.key] : false)
                  return (
                    <div key={item.key} className="flex items-center justify-between p-3.5 bg-slate-800/40 border border-slate-800 rounded-xl">
                      <div>
                        <div className="font-semibold text-white text-xs">{item.label}</div>
                        <div className="text-[11px] text-slate-400">{item.desc}</div>
                      </div>
                      <button
                        onClick={() => handleConfigToggle(item.key, val)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          val ? 'bg-purple-600' : 'bg-slate-700'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            val ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Secure CSV Exports */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Export Sanitized Operational Data</h3>
                  <p className="text-xs text-slate-400">
                    Defends against spreadsheet formula injection (<code className="text-purple-400">=, +, -, @</code> escaped with single quote)
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { type: 'requests', label: 'AI Request Logs', desc: 'Up to 2,000 granular request telemetry records' },
                  { type: 'users', label: 'User Directory', desc: 'Registered user logins, dates, and suspension states' },
                  { type: 'audit_logs', label: 'Security Audit Logs', desc: 'Administrative action log history' },
                  { type: 'costs', label: 'Pricing & Token Costs', desc: 'Model registry pricing breakdown' }
                ].map(exp => (
                  <a
                    key={exp.type}
                    href={getAdminExportUrl(exp.type as any)}
                    download
                    className="p-4 rounded-xl bg-slate-800/50 hover:bg-slate-800 border border-slate-700/60 flex flex-col justify-between group transition"
                  >
                    <div>
                      <div className="flex items-center justify-between text-slate-300 group-hover:text-white">
                        <span className="font-semibold text-xs">{exp.label}</span>
                        <Download className="w-4 h-4 text-purple-400" />
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1">{exp.desc}</p>
                    </div>
                    <span className="text-[10px] text-purple-400 font-mono mt-3 inline-block">Download CSV →</span>
                  </a>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
