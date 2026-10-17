'use client'

import React, { useState, useEffect, useMemo } from 'react'
import {
  Sparkles,
  Play,
  Pause,
  RotateCcw,
  Clock,
  ArrowRight,
  BookOpen,
  Code2,
  FileText,
  Calendar,
  Flame,
  Award,
  BookMarked,
  HelpCircle,
  CheckCircle2,
  Activity,
  BarChart2,
} from 'lucide-react'
import { ChatSession, UsageStatus, User, UserMemoryData, UserProfileStats } from '@/types/api'
import { STUDY_QUICK_PROMPTS } from '@/lib/constants'

interface StudentDashboardProps {
  user: User
  sessions: ChatSession[]
  usage: UsageStatus | null
  memoryData: UserMemoryData | null
  profileStats?: UserProfileStats | null
  onStartStudyPrompt: (promptText: string) => void
  onSelectSession: (sessionId: string) => void
  onNewSession: () => void
  onOpenUsageModal: () => void
  onOpenNotesModal: () => void
}

export function StudentDashboard({
  user,
  sessions,
  usage,
  memoryData,
  profileStats,
  onStartStudyPrompt,
  onSelectSession,
  onNewSession,
  onOpenUsageModal,
  onOpenNotesModal,
}: StudentDashboardProps) {
  const [jumpInput, setJumpInput] = useState('')

  // ── Pomodoro Focus Sprint State ───────────────────────────
  const [sprintMinutes, setSprintMinutes] = useState(25)
  const [timeLeftSeconds, setTimeLeftSeconds] = useState(25 * 60)
  const [isTimerRunning, setIsTimerRunning] = useState(false)
  const [timerEndsAt, setTimerEndsAt] = useState<number | null>(null)
  const timerStorageKey = `brainy_focus_timer_${user.id}`

  // Restore a personal timer and derive the countdown from an end timestamp.
  useEffect(() => {
    try {
      const saved = localStorage.getItem(timerStorageKey)
      if (saved) {
        const timerState = JSON.parse(saved)
        if ([15, 25, 45].includes(timerState.minutes)) setSprintMinutes(timerState.minutes)
        const remaining = timerState.running && timerState.endsAt
          ? Math.max(0, Math.ceil((timerState.endsAt - Date.now()) / 1000))
          : Math.max(0, Number(timerState.remaining) || 0)
        setTimeLeftSeconds(remaining)
        if (timerState.running && remaining > 0) {
          setTimerEndsAt(timerState.endsAt)
          setIsTimerRunning(true)
        }
      }
    } catch {
      localStorage.removeItem(timerStorageKey)
    }
  }, [timerStorageKey])

  useEffect(() => {
    try {
      localStorage.setItem(timerStorageKey, JSON.stringify({
        minutes: sprintMinutes,
        remaining: timeLeftSeconds,
        running: isTimerRunning,
        endsAt: timerEndsAt,
      }))
    } catch { /* Timer remains usable when storage is unavailable. */ }
  }, [timerStorageKey, sprintMinutes, timeLeftSeconds, isTimerRunning, timerEndsAt])

  useEffect(() => {
    if (!isTimerRunning || !timerEndsAt) return
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((timerEndsAt - Date.now()) / 1000))
      setTimeLeftSeconds(remaining)
      if (remaining === 0) {
        setIsTimerRunning(false)
        setTimerEndsAt(null)
        try {
          localStorage.removeItem(timerStorageKey)
        } catch { /* ignore */ }
      try {
        // Subtle audio notification using AudioContext
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.type = 'sine'
        osc.frequency.setValueAtTime(587.33, ctx.currentTime) // D5 note
        gain.gain.setValueAtTime(0.1, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8)
        osc.start()
        osc.stop(ctx.currentTime + 0.8)
      } catch {
        // audio context not available
      }
      }
    }
    tick()
    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [isTimerRunning, timerEndsAt, timerStorageKey])

  const handleSelectSprintDuration = (mins: number) => {
    setIsTimerRunning(false)
    setTimerEndsAt(null)
    setSprintMinutes(mins)
    setTimeLeftSeconds(mins * 60)
  }

  const handleResetTimer = () => {
    setIsTimerRunning(false)
    setTimerEndsAt(null)
    setTimeLeftSeconds(sprintMinutes * 60)
  }

  const handleToggleTimer = () => {
    if (isTimerRunning) {
      setTimeLeftSeconds(Math.max(0, timerEndsAt ? Math.ceil((timerEndsAt - Date.now()) / 1000) : timeLeftSeconds))
      setTimerEndsAt(null)
      setIsTimerRunning(false)
    } else if (timeLeftSeconds > 0) {
      setTimerEndsAt(Date.now() + timeLeftSeconds * 1000)
      setIsTimerRunning(true)
    }
  }

  // Format time mm:ss
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // Circular timer progress calculation
  const totalSeconds = sprintMinutes * 60
  const progressRatio = (totalSeconds - timeLeftSeconds) / totalSeconds
  const strokeDashoffset = 283 - 283 * progressRatio

  // Dynamic Greeting
  const greeting = useMemo(() => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good Morning'
    if (hour < 17) return 'Good Afternoon'
    return 'Good Evening'
  }, [])

  // User stats
  const questionsUsed = usage?.used ?? null
  const questionsLimit = usage?.limit ?? null
  const questionsRemaining = usage?.remaining ?? null
  const savedNotesCount = memoryData?.liked_notes?.length || 0

  // Real 7-day session activity distribution (honest user data, never fabricated)
  const weeklyActivity = useMemo(() => {
    const days: { label: string; dateStr: string; count: number }[] = []
    const now = new Date()
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      const dateStr = d.toISOString().split('T')[0]
      const label = i === 0 ? 'Today' : d.toLocaleDateString(undefined, { weekday: 'short' })
      const count = sessions.filter((s) => s.created_at && s.created_at.startsWith(dateStr)).length
      days.push({ label, dateStr, count })
    }
    const maxCount = Math.max(1, ...days.map((d) => d.count))
    const totalCount = days.reduce((acc, d) => acc + d.count, 0)
    return { days, maxCount, totalCount }
  }, [sessions])

  const handleJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!jumpInput.trim()) return
    onStartStudyPrompt(jumpInput.trim())
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 max-w-7xl mx-auto w-full">
      {/* ── Top Hero Greeting Banner (Inspired by Aptivus Image 2) ── */}
      <div className="relative rounded-3xl p-6 sm:p-8 bg-gradient-to-r from-[var(--bg-surface-elevated)] to-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] overflow-hidden">
        {/* Subtle decorative gold/emerald glow in top right */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-[var(--accent-subtle)] rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="text-xs uppercase font-bold tracking-wider text-[var(--text-muted)]">
              Study Overview
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">
              {greeting}, {user.first_name || 'Scholar'}!
            </h1>
            <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-xl">
              Let&apos;s make today productive. Dive into deep academic concepts, solve formulas step-by-step, or test your memory with exam drills.
            </p>

            {/* Badges / Chips */}
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <Award size={13} />
                <span>{questionsRemaining === null ? 'Usage unavailable' : `${questionsRemaining} Questions Left`}</span>
              </span>

              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[var(--bg-surface-elevated)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
                <Clock size={13} />
                <span>{usage ? `${usage.window_hours}h quota window` : 'Quota window unavailable'}</span>
              </span>
            </div>
          </div>

          {/* Quick Jump Input */}
          <form
            onSubmit={handleJumpSubmit}
            className="w-full lg:max-w-md flex items-center gap-2 p-1.5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-strong)] shadow-sm"
          >
            <input
              type="text"
              value={jumpInput}
              onChange={(e) => setJumpInput(e.target.value)}
              placeholder="Ask a question or enter a topic..."
              className="flex-1 px-3 py-2 text-xs sm:text-sm bg-transparent text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
            />
            <button
              type="submit"
              className="px-4 py-2 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-xs font-semibold hover:opacity-90 transition flex items-center gap-1.5 flex-shrink-0 cursor-pointer"
            >
              <span>Ask</span>
              <ArrowRight size={13} />
            </button>
          </form>
        </div>
      </div>

      {/* ── Grid: Pomodoro Focus Sprint (Left) + Metric Bento Cards (Right) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Pomodoro Focus Sprint (Aptivus "Work Sprint" Card) */}
        <div className="lg:col-span-5 rounded-3xl p-6 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold tracking-tight text-[var(--text-primary)]">
                Study Focus Sprint
              </h2>
              <div className="flex items-center gap-1 text-[11px] font-medium text-[var(--text-muted)]">
                <span>{isTimerRunning ? 'Session in progress' : 'Focus timer'}</span>
              </div>
            </div>

            {/* Duration Selector Tabs */}
            <div className="flex items-center p-1 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs mb-6">
              {[15, 25, 45].map((mins) => (
                <button
                  key={mins}
                  onClick={() => handleSelectSprintDuration(mins)}
                  className={`flex-1 py-1.5 rounded-lg font-medium transition cursor-pointer ${
                    sprintMinutes === mins
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {mins} min
                </button>
              ))}
            </div>

            {/* Circular Progress Display */}
            <div className="flex flex-col items-center justify-center my-4 relative">
              <div className="relative w-48 h-48 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  {/* Background Track */}
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    className="stroke-[var(--bg-surface-elevated)]"
                    strokeWidth="7"
                    fill="transparent"
                  />
                  {/* Animated Progress Ring */}
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    stroke="currentColor"
                    className="text-amber-500 transition-all duration-500"
                    strokeWidth="7"
                    strokeDasharray="283"
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                    fill="transparent"
                  />
                </svg>

                {/* Center Timer Text */}
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="text-3xl font-extrabold tracking-tight font-mono text-[var(--text-primary)]">
                    {formatTime(timeLeftSeconds)}
                  </span>
                  <span className="text-[11px] text-[var(--text-muted)] font-medium mt-1">
                    {isTimerRunning ? 'Deep Focus...' : 'Ready to study'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Timer Action Buttons */}
          <div className="flex items-center gap-2 pt-4">
            <button
              onClick={handleToggleTimer}
              className={`flex-1 py-3 px-4 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer shadow-sm ${
                isTimerRunning
                  ? 'bg-amber-600 hover:bg-amber-700 text-white'
                  : 'bg-zinc-900 hover:bg-black text-white dark:bg-white dark:hover:bg-zinc-100 dark:text-zinc-900'
              }`}
            >
              {isTimerRunning ? (
                <>
                  <Pause size={14} />
                  <span>Pause Timer</span>
                </>
              ) : (
                <>
                  <Play size={14} />
                  <span>Start Focus Sprint</span>
                </>
              )}
            </button>

            <button
              onClick={handleResetTimer}
              className="p-3 rounded-xl border border-[var(--border-subtle)] hover:bg-[var(--bg-surface-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition cursor-pointer"
              title="Reset timer"
            >
              <RotateCcw size={15} />
            </button>
          </div>
        </div>

        {/* Right Column: 4 Bento Metric Cards (Aptivus Metric Bento Grid) */}
        <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
          
          {/* Card 1: Current quota */}
          <div
            onClick={onOpenUsageModal}
            className="rounded-3xl p-6 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] flex flex-col justify-between cursor-pointer hover:border-[var(--border-strong)] transition"
          >
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
              <span className="font-semibold uppercase tracking-wider text-[10px]">
                {usage ? `${usage.window_hours}-Hour Quota` : 'Quota'}
              </span>
              <Clock size={14} className="text-emerald-500" />
            </div>
            <div className="my-3">
              <div className="text-3xl font-extrabold text-[var(--text-primary)]">
                {questionsRemaining === null ? '—' : questionsRemaining}{' '}
                {questionsLimit !== null && <span className="text-sm font-normal text-[var(--text-muted)]">/ {questionsLimit}</span>}
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                {usage ? `Questions available in current ${usage.window_hours}h window` : 'Usage data unavailable'}
              </p>
            </div>
            {usage ? (
              <div className="w-full bg-[var(--bg-surface-elevated)] h-2 rounded-full overflow-hidden" aria-label={`${questionsUsed} of ${questionsLimit} questions used`}>
                <div className="bg-emerald-500 h-full rounded-full transition-all duration-300" style={{ width: `${Math.round((questionsUsed! / questionsLimit!) * 100)}%` }} />
              </div>
            ) : <p className="text-xs text-[var(--text-muted)]">Usage progress is unavailable</p>}
          </div>

          {/* Card 2: Academic progress from recorded quiz data */}
          <div className="rounded-3xl p-6 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] flex flex-col justify-between">
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
              <span className="font-semibold uppercase tracking-wider text-[10px]">
                Quiz progress
              </span>
              <Flame size={14} className="text-[var(--text-muted)]" />
            </div>
            <div className="my-3">
              <div className="text-3xl font-extrabold text-[var(--text-primary)]">
                {profileStats?.total ? `${Math.round((profileStats.score / profileStats.total) * 100)}%` : '—'}
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                {profileStats?.total ? `${profileStats.score} correct of ${profileStats.total} recorded quiz answers` : 'Quiz activity is not available yet'}
              </p>
            </div>
            <div className="text-[11px] text-[var(--text-muted)] font-medium">Based on recorded quiz answers</div>
          </div>

          {/* Card 3: Total Study Sessions */}
          <div
            onClick={onNewSession}
            className="rounded-3xl p-6 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] flex flex-col justify-between cursor-pointer hover:border-[var(--border-strong)] transition"
          >
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
              <span className="font-semibold uppercase tracking-wider text-[10px]">
                Study Sessions
              </span>
              <BookOpen size={14} className="text-blue-500" />
            </div>
            <div className="my-3">
              <div className="text-3xl font-extrabold text-[var(--text-primary)]">
                {sessions.length}
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                Saved academic conversation threads
              </p>
            </div>
            <div className="text-[11px] text-blue-600 dark:text-blue-400 font-medium flex items-center gap-1">
              <span>+ Start new session</span>
            </div>
          </div>

          {/* Card 4: Saved Study Notes */}
          <div
            onClick={onOpenNotesModal}
            className="rounded-3xl p-6 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] flex flex-col justify-between cursor-pointer hover:border-[var(--border-strong)] transition"
          >
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
              <span className="font-semibold uppercase tracking-wider text-[10px]">
                Saved Study Notes
              </span>
              <BookMarked size={14} className="text-teal-500" />
            </div>
            <div className="my-3">
              <div className="text-3xl font-extrabold text-[var(--text-primary)]">
                {savedNotesCount}
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                High-yield definitions & key takeaways
              </p>
            </div>
            <div className="text-[11px] text-teal-600 dark:text-teal-400 font-medium">
              Click to view study context notes
            </div>
          </div>

        </div>
      </div>

      {/* ── Quick Study Bento Actions (6 High-Yield Academic Modes) ── */}
      <div>
        <div className="flex items-center justify-between mb-3 px-1">
          <h2 className="text-sm font-bold tracking-tight text-[var(--text-primary)]">
            Quick Study Bento
          </h2>
          <span className="text-xs text-[var(--text-muted)]">
            Instant 1-click prompts into Chat Workspace
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {STUDY_QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt.id}
              onClick={() => onStartStudyPrompt(prompt.prompt)}
              className="text-left rounded-2xl p-5 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] hover:border-[var(--border-strong)] hover:shadow-md transition group cursor-pointer flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="w-8 h-8 rounded-lg bg-[var(--bg-surface-elevated)] flex items-center justify-center text-[var(--text-primary)] group-hover:scale-105 transition-transform">
                    {prompt.category === 'concept' ? (
                      <Sparkles size={16} />
                    ) : prompt.category === 'problem' ? (
                      <FileText size={16} />
                    ) : prompt.category === 'code' ? (
                      <Code2 size={16} />
                    ) : (
                      <BookOpen size={16} />
                    )}
                  </div>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-[var(--bg-surface-elevated)] text-[var(--text-muted)]">
                    {prompt.category}
                  </span>
                </div>

                <h3 className="text-xs sm:text-sm font-bold text-[var(--text-primary)] group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                  {prompt.title}
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed">
                  {prompt.description}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] font-semibold text-[var(--text-muted)] group-hover:text-[var(--text-primary)]">
                <span>Launch in workspace</span>
                <ArrowRight size={13} className="transform group-hover:translate-x-1 transition-transform" />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── 7-Day Study Cadence (Real Session Activity Distribution) ── */}
      <div className="rounded-3xl p-6 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-tight text-[var(--text-primary)]">
                7-Day Study Cadence
              </h2>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                Verified Supabase History
              </span>
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Genuine study activity over the past 7 days aggregated from your saved conversation sessions
            </p>
          </div>
          <div className="text-xs font-medium text-[var(--text-secondary)] bg-[var(--bg-surface-elevated)] px-3 py-1.5 rounded-xl border border-[var(--border-subtle)] flex items-center gap-2 self-start sm:self-auto">
            <Activity size={14} className="text-emerald-500" />
            <span>
              <strong>{weeklyActivity.totalCount}</strong> sessions in last 7 days
            </span>
          </div>
        </div>

        {/* 7-Day Activity Bars */}
        <div className="grid grid-cols-7 gap-2 sm:gap-4 pt-4 pb-2">
          {weeklyActivity.days.map((day, idx) => {
            const heightPercent = day.count > 0 ? Math.max(18, Math.round((day.count / weeklyActivity.maxCount) * 100)) : 8
            const isToday = idx === 6
            return (
              <div key={day.dateStr} className="flex flex-col items-center gap-2 group">
                <span className="text-[10px] sm:text-xs font-semibold text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition">
                  {day.count > 0 ? `${day.count}` : '0'}
                </span>
                <div className="w-full max-w-[44px] h-28 sm:h-32 bg-[var(--bg-surface-elevated)] rounded-xl p-1 flex flex-col justify-end border border-[var(--border-subtle)]">
                  <div
                    style={{ height: `${heightPercent}%` }}
                    className={`w-full rounded-lg transition-all duration-500 ${
                      day.count > 0
                        ? isToday
                          ? 'bg-emerald-600 dark:bg-emerald-500 shadow-sm'
                          : 'bg-emerald-500/80 dark:bg-emerald-400/80'
                        : 'bg-[var(--border-strong)]/30'
                    }`}
                  />
                </div>
                <div className="text-center">
                  <span
                    className={`text-[11px] font-medium block ${
                      isToday ? 'text-[var(--text-primary)] font-bold' : 'text-[var(--text-muted)]'
                    }`}
                  >
                    {day.label}
                  </span>
                  <span className="text-[9px] text-[var(--text-muted)] hidden sm:block">
                    {day.dateStr.slice(5)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {weeklyActivity.totalCount === 0 && (
          <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] text-center text-xs text-[var(--text-muted)]">
            No study sessions recorded in the past 7 days. Start a topic or question above to log your focus!
          </div>
        )}
      </div>

      {/* ── Recent Study Sessions (Continuity) ── */}
      <div className="rounded-3xl p-6 bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)]">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold tracking-tight text-[var(--text-primary)]">
              Recent Study Sessions
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Resume your recent questions and active study context
            </p>
          </div>
          <button
            onClick={onNewSession}
            className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline cursor-pointer"
          >
            + New Study Session
          </button>
        </div>

        {sessions.length === 0 ? (
          <div className="py-8 text-center text-xs text-[var(--text-muted)]">
            No study sessions yet. Click any quick prompt above to begin!
          </div>
        ) : (
          <div className="divide-y divide-[var(--border-subtle)]">
            {sessions.slice(0, 5).map((sess) => (
              <div
                key={sess.id}
                onClick={() => onSelectSession(sess.id)}
                className="py-3 px-2 flex items-center justify-between hover:bg-[var(--bg-surface-elevated)] rounded-xl transition cursor-pointer group"
              >
                <div className="flex items-center gap-3 truncate pr-4">
                  <div className="w-7 h-7 rounded-lg bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-muted)] group-hover:text-[var(--text-primary)] flex-shrink-0">
                    <BookOpen size={13} />
                  </div>
                  <div className="truncate">
                    <div className="text-xs font-semibold text-[var(--text-primary)] truncate">
                      {sess.title || 'Study Session'}
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)]">
                      {sess.created_at ? new Date(sess.created_at).toLocaleDateString() : 'Active session'}
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg bg-[var(--bg-surface-elevated)] group-hover:bg-zinc-900 group-hover:text-white dark:group-hover:bg-white dark:group-hover:text-zinc-900 text-[11px] font-semibold text-[var(--text-primary)] transition flex items-center gap-1 flex-shrink-0"
                >
                  <span>Continue</span>
                  <ArrowRight size={11} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}
