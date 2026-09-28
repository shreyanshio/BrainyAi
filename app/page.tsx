'use client'

import { useState, useEffect, useRef } from 'react'
import {
  Activity,
  ArrowUp,
  Brain,
  Check,
  ChevronDown,
  Code2,
  Copy,
  Flame,
  Hash,
  Heart,
  Lightbulb,
  LogOut,
  Menu,
  Mic,
  MicOff,
  MoreHorizontal,
  PanelLeftClose,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  Trash2,
  Upload,
  User,
  X,
  Zap,
} from 'lucide-react'

interface UserSession {
  id: number
  first_name: string
  username: string
}

interface ChatSessionItem {
  id: string
  title: string
  created_at?: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
  keyTakeaway?: string
  codeSnippet?: {
    lang: string
    code: string
  }
}

interface ProfileStats {
  streak: number
  level: string
  total: number
  score: number
}

interface MemoryData {
  learn_context: string
  liked_notes: string[]
}

const personaOptions = [
  { id: 'socratic', label: 'Socratic Tutor', desc: 'Asks guiding questions to help you think' },
  { id: 'direct', label: 'Direct & Concise', desc: 'Bullet points, zero filler, exam-focused' },
  { id: 'architect', label: 'Code Architect', desc: 'Deep technical logic & memory breakdown' },
  { id: 'eli5', label: 'Speedrun / ELI5', desc: 'Simple analogies and fast mental models' },
]

const quickPrompts = [
  { title: 'Explain a complex concept', copy: 'Clear breakdown with intuitive real-world mental models.', icon: Lightbulb },
  { title: 'Build a formula cheat sheet', copy: 'Key equations, derivations, and syntax for fast revision.', icon: Target },
  { title: 'Debug my code snippet', copy: 'Find logical bugs, memory leaks, and optimize performance.', icon: Code2 },
  { title: 'Test my knowledge', copy: 'Generate 3 high-yield questions with instant explanations.', icon: Sparkles },
]

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')

const apiFetch = (path: string, options: RequestInit = {}) => {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
  })
}

export default function Page() {
  // Auth state
  const [user, setUser] = useState<UserSession | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [loginName, setLoginName] = useState('')
  const [loginUsername, setLoginUsername] = useState('')
  const [loginSubmitting, setLoginSubmitting] = useState(false)
  const [loginError, setLoginError] = useState('')

  // UI state
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [focusMode, setFocusMode] = useState(false)
  const [selectedPersona, setSelectedPersona] = useState(personaOptions[0])
  const [showPersonaMenu, setShowPersonaMenu] = useState(false)

  // Chat & Session state
  const [sessions, setSessions] = useState<ChatSessionItem[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeSessionTitle, setActiveSessionTitle] = useState('New Study Session')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [messageCount, setMessageCount] = useState(0)

  // Voice recording state
  const [isListening, setIsListening] = useState(false)

  // Modals state
  const [showCommand, setShowCommand] = useState(false)
  const [showProfileModal, setShowProfileModal] = useState(false)
  const [showMemoryModal, setShowMemoryModal] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  // Real stats state (from Supabase)
  const [profileStats, setProfileStats] = useState<ProfileStats>({
    streak: 1,
    level: '1',
    total: 0,
    score: 0,
  })
  const [memoryData, setMemoryData] = useState<MemoryData>({
    learn_context: 'Initializing learning profile...',
    liked_notes: [],
  })

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // ── 1. Initial Load & Auth Check ─────────────────────────────
  useEffect(() => {
    checkCurrentUser()
  }, [])

  // Auto-scroll when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  // Global Keyboard Shortcuts (Cmd+K / Ctrl+K, Cmd+N / Ctrl+N, Esc)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isCmd = e.metaKey || e.ctrlKey
      if (isCmd && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setShowCommand((prev) => !prev)
      } else if (isCmd && e.key.toLowerCase() === 'n') {
        e.preventDefault()
        handleNewSession()
      } else if (e.key === 'Escape') {
        setShowCommand(false)
        setShowProfileModal(false)
        setShowMemoryModal(false)
        setShowPersonaMenu(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Initialize Google Sign-In SDK
  useEffect(() => {
    if (!user) {
      initGoogleAuth()
    }
  }, [user])

  const checkCurrentUser = async () => {
    setAuthLoading(true)
    try {
      // 1. Check if Telegram WebApp has initData
      const tg = typeof window !== 'undefined' && (window as any).Telegram?.WebApp
      if (tg && tg.initData) {
        tg.expand()
        const resp = await apiFetch('/api/auth/initdata', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initData: tg.initData }),
        })
        if (resp.ok) {
          const data = await resp.json()
          setUser(data.user)
          await loadUserData()
          setAuthLoading(false)
          return
        }
      }

      // 2. Check Flask server session via /api/auth/me or /api/user/profile
      const profResp = await apiFetch('/api/user/profile')
      if (profResp.ok) {
        const prof = await profResp.json()
        if (prof.user_id || prof.first_name) {
          setUser({
            id: prof.user_id || 1,
            first_name: prof.first_name || 'Student',
            username: prof.username || '',
          })
          setProfileStats({
            streak: prof.streak || 1,
            level: String(prof.level || '1'),
            total: prof.total || 0,
            score: prof.score || 0,
          })
          await loadSessions()
          await loadMemory()
          setAuthLoading(false)
          return
        }
      }
    } catch (err) {
      console.warn('Auth check skipped:', err)
    } finally {
      setAuthLoading(false)
    }
  }

  const loadUserData = async () => {
    await Promise.all([loadSessions(), loadProfile(), loadMemory()])
  }

  const loadSessions = async () => {
    try {
      const resp = await apiFetch('/api/sessions')
      if (resp.ok) {
        const data = await resp.json()
        const sessList = Array.isArray(data) ? data : data.sessions || []
        setSessions(sessList)
        if (sessList.length > 0 && !activeSessionId) {
          selectSession(sessList[0].id, sessList[0].title)
        }
      }
    } catch (e) {
      console.error('Failed to load sessions:', e)
    }
  }

  const loadProfile = async () => {
    try {
      const resp = await apiFetch('/api/user/profile')
      if (resp.ok) {
        const prof = await resp.json()
        setProfileStats({
          streak: prof.streak || 1,
          level: String(prof.level || '1'),
          total: prof.total || 0,
          score: prof.score || 0,
        })
      }
    } catch (e) {
      console.error('Failed to load profile:', e)
    }
  }

  const loadMemory = async () => {
    try {
      const resp = await apiFetch('/api/user/memory')
      if (resp.ok) {
        const mem = await resp.json()
        setMemoryData({
          learn_context: mem.learn_context || 'Standard personalized study mode.',
          liked_notes: mem.liked_notes || [],
        })
      }
    } catch (e) {
      console.error('Failed to load memory:', e)
    }
  }

  const selectSession = async (sessionId: string, title: string) => {
    setActiveSessionId(sessionId)
    setActiveSessionTitle(title || 'Study Session')
    setMobileOpen(false)
    try {
      const resp = await apiFetch(`/api/chat/${sessionId}`)
      if (resp.ok) {
        const data = await resp.json()
        const msgs = (data.messages || []).map((m: any) => ({
          role: m.role,
          content: m.content,
          created_at: m.created_at,
        }))
        setMessages(msgs)
        setMessageCount(msgs.length)
      }
    } catch (e) {
      console.error('Failed to load session messages:', e)
    }
  }

  const handleNewSession = async () => {
    setActiveSessionId(null)
    setActiveSessionTitle('New Study Session')
    setMessages([])
    setMessageCount(0)
    setInputMessage('')
    setMobileOpen(false)
  }

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      const resp = await apiFetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
      if (resp.ok) {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId))
        if (activeSessionId === sessionId) {
          handleNewSession()
        }
      }
    } catch (e) {
      console.error('Failed to delete session:', e)
    }
  }

  // ── 2. Authentication Handlers ────────────────────────────────
  const handleWebLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!loginName.trim()) {
      setLoginError('Please enter your name.')
      return
    }
    setLoginSubmitting(true)
    setLoginError('')

    try {
      const resp = await apiFetch('/api/auth/web', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: loginName.trim(),
          username: loginUsername.trim(),
        }),
      })

      if (resp.ok) {
        const data = await resp.json()
        setUser(data.user)
        await loadUserData()
      } else {
        const err = await resp.json().catch(() => ({}))
        setLoginError(err.error || 'Failed to sign in. Please try again.')
      }
    } catch (err) {
      setLoginError('Network error connecting to the server.')
    } finally {
      setLoginSubmitting(false)
    }
  }

  const initGoogleAuth = async () => {
    try {
      const cfgResp = await apiFetch('/api/config')
      if (!cfgResp.ok) return
      const cfg = await cfgResp.json()
      if (!cfg.google_client_id) return

      const interval = setInterval(() => {
        const g = (window as any).google
        if (g?.accounts?.id) {
          clearInterval(interval)
          g.accounts.id.initialize({
            client_id: cfg.google_client_id,
            callback: handleGoogleCredential,
            auto_select: false,
          })
          const container = document.getElementById('google-btn-slot')
          if (container) {
            container.innerHTML = ''
            g.accounts.id.renderButton(container, {
              theme: 'outline',
              size: 'large',
              text: 'continue_with',
              shape: 'rectangular',
              width: 320,
            })
          }
        }
      }, 300)
      setTimeout(() => clearInterval(interval), 8000)
    } catch (e) {}
  }

  const handleGoogleCredential = async (response: any) => {
    if (!response?.credential) return
    try {
      const resp = await apiFetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: response.credential }),
      })
      if (resp.ok) {
        const data = await resp.json()
        setUser(data.user)
        await loadUserData()
      } else {
        const err = await resp.json().catch(() => ({}))
        setLoginError(err.error || 'Google login failed.')
      }
    } catch (e) {
      setLoginError('Could not verify Google authentication.')
    }
  }

  const handleLogout = async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' })
    } catch (e) {}
    setUser(null)
    setMessages([])
    setSessions([])
    setActiveSessionId(null)
  }

  // ── 3. Chat Messaging ─────────────────────────────────────────
  const sendMessage = async () => {
    const text = inputMessage.trim()
    if (!text || isThinking) return

    // Append user message immediately
    const userMsg: ChatMessage = { role: 'user', content: text, created_at: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setInputMessage('')
    setIsThinking(true)
    setMessageCount((prev) => prev + 1)

    try {
      const resp = await apiFetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: activeSessionId,
          tone: selectedPersona.id,
        }),
      })

      if (resp.ok) {
        const data = await resp.json()
        if (data.session_id && data.session_id !== activeSessionId) {
          setActiveSessionId(data.session_id)
          if (data.session_title) {
            setActiveSessionTitle(data.session_title)
          }
          await loadSessions()
        }

        const aiMsg: ChatMessage = {
          role: 'assistant',
          content: data.response || 'No response generated.',
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, aiMsg])
        setMessageCount(data.message_count || messageCount + 1)
        loadProfile() // refresh streak/total questions count
      } else {
        const err = await resp.json().catch(() => ({}))
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `⚠️ ${err.error || 'Failed to get response. Please try again.'}`,
          },
        ])
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ Network connection lost. Please check your internet or retry.',
        },
      ])
    } finally {
      setIsThinking(false)
    }
  }

  // Voice Input (Web Speech API)
  const toggleVoice = () => {
    if (typeof window === 'undefined') return
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRec) {
      alert('Voice recognition is not supported in this browser. Please use Chrome or Edge.')
      return
    }

    if (isListening) {
      setIsListening(false)
      return
    }

    try {
      const recognition = new SpeechRec()
      recognition.continuous = false
      recognition.interimResults = false
      recognition.lang = 'en-US'

      recognition.onstart = () => setIsListening(true)
      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript
        setInputMessage((prev) => (prev ? `${prev} ${transcript}` : transcript))
        setIsListening(false)
      }
      recognition.onerror = () => setIsListening(false)
      recognition.onend = () => setIsListening(false)

      recognition.start()
    } catch (e) {
      setIsListening(false)
    }
  }

  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIndex(index)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  const saveToMemory = async (note: string) => {
    try {
      await apiFetch('/api/user/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note }),
      })
      await loadMemory()
    } catch (e) {}
  }

  const userInitials = (user?.first_name || 'U')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .substring(0, 2)
    .toUpperCase()

  // ═════════════════════════════════════════════════════════════
  // VIEW 1: HERO & LOGIN SECTION (When not authenticated)
  // ═════════════════════════════════════════════════════════════
  if (!user && !authLoading) {
    return (
      <div className="min-h-screen bg-[#080a12] text-[#f4f5fb] flex flex-col justify-between selection:bg-[#8a6bff] selection:text-white relative overflow-hidden">
        {/* Background glow effects */}
        <div className="absolute top-[-10%] right-[10%] w-[500px] h-[500px] bg-indigo-600/15 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] left-[5%] w-[450px] h-[450px] bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />

        {/* Top Navbar */}
        <header className="w-full max-w-7xl mx-auto px-6 py-6 flex items-center justify-between relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#a789ff] to-[#38d4e8] flex items-center justify-center text-black font-extrabold shadow-[0_0_20px_rgba(167,137,255,0.4)]">
              <Sparkles size={18} />
            </div>
            <span className="font-extrabold text-lg tracking-wider text-white">
              BRAINY <span className="text-[#8a6bff] text-xs font-semibold">AI</span>
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs font-medium text-[#858da1] bg-white/5 border border-white/10 px-3 py-1.5 rounded-full">
            <span className="w-2 h-2 rounded-full bg-[#43d9a2] animate-pulse" />
            AI Intelligence Online
          </div>
        </header>

        {/* Hero & Login Body */}
        <main className="max-w-7xl mx-auto px-6 py-8 flex-1 flex flex-col lg:flex-row items-center justify-center gap-12 lg:gap-20 relative z-10 w-full">
          {/* Left Hero Description */}
          <div className="flex-1 max-w-xl text-center lg:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-[#a594ff] text-xs font-semibold mb-6">
              <Zap size={14} className="text-[#38d4e8]" />
              <span>Deep Reasoning • Zero Fluff • 24/7 Available</span>
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-medium tracking-tight text-white leading-[1.15] mb-6">
              Think Clearly. <br />
              <span className="italic font-serif text-[#a594ff]">Master Confidently.</span>
            </h1>

            <p className="text-[#80899d] text-base sm:text-lg leading-relaxed mb-8">
              Your emotionally intelligent, pure AI study companion. Instant breakdowns for complex code,
              mathematical derivations, sciences, and deep concept synthesis.
            </p>

            {/* Interactive Feature Pills */}
            <div className="grid grid-cols-2 gap-3 text-left">
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-3">
                <Code2 size={18} className="text-[#38d4e8]" />
                <div>
                  <h4 className="text-xs font-semibold text-white">Code & Logic</h4>
                  <p className="text-[11px] text-[#69748b]">Real-time debugging & traces</p>
                </div>
              </div>
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-3">
                <Brain size={18} className="text-[#a789ff]" />
                <div>
                  <h4 className="text-xs font-semibold text-white">Adaptive Memory</h4>
                  <p className="text-[11px] text-[#69748b]">Learns your doubt patterns</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Auth Card */}
          <div className="w-full max-w-md bg-[#0e111c]/90 border border-white/10 rounded-2xl p-7 shadow-2xl backdrop-blur-xl relative">
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#a789ff] via-[#38d4e8] to-[#43d9a2] rounded-t-2xl" />

            <div className="mb-6 text-center">
              <h2 className="text-xl font-bold text-white mb-1">Enter Study Sanctuary</h2>
              <p className="text-xs text-[#858da1]">Sign in to keep your streak and session memory alive.</p>
            </div>

            {loginError && (
              <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs text-center">
                {loginError}
              </div>
            )}

            {/* Google Sign In Container */}
            <div className="flex flex-col gap-3 mb-5">
              <div id="google-btn-slot" className="w-full flex justify-center min-h-[40px]" />

              {/* Telegram Login */}
              <button
                onClick={() => {
                  window.open('https://t.me/BrainyAiStudyBot', '_blank')
                }}
                className="w-full py-2.5 px-4 rounded-xl bg-[#229ED9]/15 border border-[#229ED9]/30 text-[#229ED9] hover:bg-[#229ED9]/25 transition text-xs font-semibold flex items-center justify-center gap-2"
              >
                <span>✈️ Continue with Telegram Bot</span>
              </button>
            </div>

            {/* Divider */}
            <div className="relative my-5 text-center">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/10" />
              </div>
              <span className="relative px-3 bg-[#0e111c] text-[10px] uppercase font-bold tracking-wider text-[#596174]">
                Or Instant Web Login
              </span>
            </div>

            {/* Direct Web Form */}
            <form onSubmit={handleWebLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#858da1] mb-1.5">Your Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Shrey Pathak"
                  value={loginName}
                  onChange={(e) => setLoginName(e.target.value)}
                  className="w-full bg-[#131725] border border-white/10 focus:border-[#8a6bff] rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-[#596174] outline-none transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#858da1] mb-1.5">
                  Username <span className="text-[#596174] font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. shrey_08"
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  className="w-full bg-[#131725] border border-white/10 focus:border-[#8a6bff] rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-[#596174] outline-none transition"
                />
              </div>

              <button
                type="submit"
                disabled={loginSubmitting}
                className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-[#8a6bff] to-[#5e9df9] text-white font-semibold text-xs shadow-lg shadow-indigo-500/25 hover:opacity-95 transition disabled:opacity-50"
              >
                {loginSubmitting ? 'Entering Sanctuary...' : 'Start Learning Now →'}
              </button>
            </form>

            <p className="mt-5 text-[11px] text-center text-[#596174]">
              Data directly synced with Supabase. Real sessions & memory.
            </p>
          </div>
        </main>

        <footer className="w-full text-center py-6 text-xs text-[#596174] border-t border-white/5 relative z-10">
          BRAINY AI — Dedicated to high-performing learners.
        </footer>
      </div>
    )
  }

  // ═════════════════════════════════════════════════════════════
  // VIEW 2: MASTER CHAT WORKSPACE (When authenticated)
  // ═════════════════════════════════════════════════════════════
  return (
    <main className="brainy-app">
      {/* ── Sidebar ── */}
      <div className={`sidebar-shell ${collapsed ? 'is-collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
        <aside className="sidebar" aria-label="Main navigation">
          {/* Brand Row */}
          <div className="brand-row">
            <div className="brand-mark">
              <Sparkles size={15} />
            </div>
            {!collapsed && (
              <div className="brand-name">
                BRAINY <span>AI</span>
              </div>
            )}
            <button
              className="icon-button sidebar-toggle"
              aria-label="Collapse sidebar"
              onClick={() => setCollapsed(!collapsed)}
            >
              <PanelLeftClose size={16} />
            </button>
          </div>

          {!collapsed && (
            <div className="online-status">
              <i /> Sanctuary Online
            </div>
          )}

          {/* New Session Button */}
          <button className="new-session" onClick={handleNewSession}>
            <Plus size={17} />
            {!collapsed && (
              <>
                <span>New session</span>
                <kbd>⌘ N</kbd>
              </>
            )}
          </button>

          {/* Real Chat History (from Supabase) */}
          {!collapsed && (
            <div className="history-section flex-1 overflow-y-auto">
              <div className="section-heading">
                <span>Recent sessions</span>
                <span className="text-[10px] text-[#596174]">{sessions.length} total</span>
              </div>

              {sessions.length === 0 ? (
                <div className="p-4 text-center text-xs text-[#596174]">No past sessions yet.</div>
              ) : (
                sessions.map((sess) => (
                  <div
                    key={sess.id}
                    onClick={() => selectSession(sess.id, sess.title)}
                    className={`history-item group cursor-pointer ${
                      activeSessionId === sess.id ? 'bg-[#181d2e] text-[#f4f5fb]' : ''
                    }`}
                  >
                    <span className="history-glyph">
                      <Hash size={12} />
                    </span>
                    <span className="flex-1 overflow-hidden">
                      <strong className="truncate">{sess.title}</strong>
                      <small>Session</small>
                    </span>
                    <button
                      onClick={(e) => handleDeleteSession(sess.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 text-[#69748b] hover:text-rose-400 transition"
                      title="Delete session"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Sidebar Footer with Real User Data */}
          <div className="sidebar-bottom">
            {!collapsed && (
              <div className="streak-card">
                <div>
                  <Flame size={16} className="amber" />
                  <strong>{profileStats.streak} day streak</strong>
                </div>
                <span>Keep your momentum alive.</span>
                <div className="streak-bars">
                  {[1, 1, 1, 1, 1, 1, 1, 0].map((on, i) => (
                    <i className={on ? 'on' : ''} key={i} />
                  ))}
                </div>
              </div>
            )}

            {/* Profile Bar */}
            <div className="profile-row">
              <div className="avatar">{userInitials}</div>
              {!collapsed && (
                <span>
                  <strong>{user?.first_name || 'Student'}</strong>
                  <small>Lvl {profileStats.level} • Scholar</small>
                </span>
              )}

              {!collapsed && (
                <div className="flex items-center gap-1 ml-auto">
                  <button
                    onClick={() => setShowProfileModal(true)}
                    className="p-1.5 hover:text-white text-[#69748b] rounded-lg transition"
                    title="Dashboard"
                  >
                    <User size={15} />
                  </button>
                  <button
                    onClick={() => setShowMemoryModal(true)}
                    className="p-1.5 hover:text-white text-[#69748b] rounded-lg transition"
                    title="Memory"
                  >
                    <Brain size={15} />
                  </button>
                  <button
                    onClick={handleLogout}
                    className="p-1.5 hover:text-rose-400 text-[#69748b] rounded-lg transition"
                    title="Log out"
                  >
                    <LogOut size={15} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      {mobileOpen && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Main Workspace ── */}
      <section className="workspace">
        {/* Topbar */}
        <header className="topbar">
          <div className="topbar-context">
            <button
              className="mobile-menu icon-button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <div className="context-icon">
              <Sparkles size={16} />
            </div>
            <div>
              <strong>{activeSessionTitle}</strong>
              <span>Active Study Session</span>
            </div>
          </div>

          {/* Persona Switcher */}
          <div className="relative">
            <button
              className="persona"
              onClick={() => setShowPersonaMenu(!showPersonaMenu)}
            >
              <span className="persona-dot" /> {selectedPersona.label}{' '}
              <ChevronDown size={14} />
            </button>

            {showPersonaMenu && (
              <div className="absolute top-12 left-0 w-64 bg-[#121622] border border-white/10 rounded-xl p-2 shadow-2xl z-30 space-y-1">
                {personaOptions.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setSelectedPersona(p)
                      setShowPersonaMenu(false)
                    }}
                    className={`w-full text-left p-2 rounded-lg text-xs transition ${
                      selectedPersona.id === p.id
                        ? 'bg-indigo-600/20 text-white font-semibold'
                        : 'text-[#858da1] hover:bg-white/5 hover:text-white'
                    }`}
                  >
                    <div className="font-medium text-white">{p.label}</div>
                    <div className="text-[10px] text-[#69748b]">{p.desc}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Top Actions */}
          <div className="top-actions">
            <button
              className="search-trigger"
              onClick={() => setShowCommand(true)}
            >
              <Search size={15} /> <span>Search</span>
              <kbd>⌘ K</kbd>
            </button>

            <button
              onClick={() => setFocusMode(!focusMode)}
              className={`focus-button ${focusMode ? 'text-[#38d4e8]' : ''}`}
              title="Focus Mode"
            >
              <Zap size={15} /> Focus
            </button>
          </div>
        </header>

        {/* ── Content Viewport ── */}
        <div className="content-area">
          {messages.length === 0 ? (
            /* Empty / Welcome State */
            <div className="welcome-state">
              <div className="eyebrow">
                <span className="pulse-dot" /> BRAINY AI SANCTUARY <span className="eyebrow-line" />
              </div>
              <h1>
                What are we <em>mastering</em>
                <br className="desktop-break" /> today, {user?.first_name}?
              </h1>
              <p className="welcome-copy">
                Ask any doubt, debug code, request rigorous derivations,
                <br className="desktop-break" /> or test your understanding with zero sugarcoating.
              </p>

              {/* 4 Quick Prompt Cards */}
              <div className="prompt-grid">
                {quickPrompts.map(({ title, copy, icon: Icon }) => (
                  <button
                    className="prompt-card"
                    key={title}
                    onClick={() => {
                      setInputMessage(title)
                      if (textareaRef.current) textareaRef.current.focus()
                    }}
                  >
                    <span className="prompt-icon">
                      <Icon size={18} />
                    </span>
                    <span>
                      <strong>{title}</strong>
                      <small>{copy}</small>
                    </span>
                    <ArrowUp size={15} className="prompt-arrow" />
                  </button>
                ))}
              </div>

              <div className="suggestion-row">
                <span>Try asking:</span>
                <button onClick={() => setInputMessage('Explain how memory addresses work with pointers')}>
                  “Explain memory addresses”
                </button>
                <button onClick={() => setInputMessage('Give me 3 tough questions on recursion')}>
                  “Quiz me on recursion”
                </button>
              </div>
            </div>
          ) : (
            /* Conversation Messages List */
            <div className="conversation">
              {messages.map((m, index) =>
                m.role === 'user' ? (
                  <div key={index} className="message user-message">
                    <span>{m.content}</span>
                    <span className="user-avatar">{userInitials}</span>
                  </div>
                ) : (
                  <article key={index} className="ai-message">
                    <div className="ai-avatar">
                      <Sparkles size={17} />
                    </div>
                    <div className="ai-body">
                      <div className="ai-meta">
                        <strong>Brainy</strong>
                        <span>{m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'just now'}</span>
                        <span className="status-pill">
                          <Check size={12} /> Verified
                        </span>
                      </div>

                      {/* AI Content */}
                      <div className="text-sm text-[#c9cede] leading-relaxed whitespace-pre-wrap mt-3">
                        {m.content}
                      </div>

                      {/* Action Bar */}
                      <div className="message-actions mt-4 flex items-center gap-4">
                        <button
                          onClick={() => saveToMemory(m.content)}
                          className="hover:text-emerald-400 transition"
                        >
                          <Heart size={14} /> Save Note
                        </button>
                        <button
                          onClick={() => copyToClipboard(m.content, index)}
                          className="hover:text-white transition"
                        >
                          {copiedIndex === index ? (
                            <>
                              <Check size={14} className="text-emerald-400" /> Copied!
                            </>
                          ) : (
                            <>
                              <Copy size={14} /> Copy
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </article>
                )
              )}

              {/* Thinking Indicator */}
              {isThinking && (
                <div className="ai-message">
                  <div className="ai-avatar">
                    <Sparkles size={17} />
                  </div>
                  <div className="ai-body">
                    <div className="flex items-center gap-2 text-xs text-[#a594ff] py-2">
                      <RefreshCw size={14} className="animate-spin text-[#8a6bff]" />
                      <span>Brainy is thinking & formulating answer...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* ── Composer (Input Bar) ── */}
        <div className="composer-wrap">
          <div className="composer">
            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage()
                }
              }}
              placeholder="Ask a doubt, paste code, or explore ideas (Shift+Enter for newline)..."
              rows={1}
            />

            <div className="composer-actions">
              <button
                className={`voice-button ${isListening ? 'text-rose-400 font-bold' : ''}`}
                onClick={toggleVoice}
                title="Voice input"
              >
                {isListening ? <MicOff size={15} /> : <Mic size={15} />}
                <span>{isListening ? 'Listening...' : 'Voice'}</span>
              </button>

              <button
                className="send-button"
                onClick={sendMessage}
                disabled={isThinking || !inputMessage.trim()}
                aria-label="Send message"
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </div>

          <p className="composer-hint">
            <span>{messageCount}/50 messages in this session</span> • Brainy uses verified knowledge. Verify crucial facts.
          </p>
        </div>
      </section>

      {/* ── Command Palette Overlay (⌘ K) ── */}
      {showCommand && (
        <div className="command-overlay" onClick={() => setShowCommand(false)}>
          <div className="command-modal" onClick={(e) => e.stopPropagation()}>
            <div className="command-input">
              <Search size={18} />
              <input
                autoFocus
                placeholder="Search sessions or quick actions..."
                onKeyDown={(e) => {
                  if (e.key === 'Escape') setShowCommand(false)
                }}
              />
              <kbd>ESC</kbd>
            </div>

            <p>Quick Actions</p>
            <button
              onClick={() => {
                handleNewSession()
                setShowCommand(false)
              }}
            >
              <span className="command-icon">
                <Plus size={15} />
              </span>
              Start New Study Session
              <kbd>⌘ N</kbd>
            </button>

            <button
              onClick={() => {
                setShowProfileModal(true)
                setShowCommand(false)
              }}
            >
              <span className="command-icon">
                <User size={15} />
              </span>
              Open Student Profile Dashboard
            </button>

            <button
              onClick={() => {
                setShowMemoryModal(true)
                setShowCommand(false)
              }}
            >
              <span className="command-icon">
                <Brain size={15} />
              </span>
              View Memory & Liked Notes
            </button>

            <button
              className="close-command"
              onClick={() => setShowCommand(false)}
            >
              <X size={14} /> Close
            </button>
          </div>
        </div>
      )}

      {/* ── Student Dashboard Modal ── */}
      {showProfileModal && (
        <div className="command-overlay" onClick={() => setShowProfileModal(false)}>
          <div
            className="w-full max-w-lg bg-[#121622] border border-white/10 rounded-2xl p-6 shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <User size={18} className="text-[#a789ff]" /> Student Dashboard
              </h3>
              <button
                onClick={() => setShowProfileModal(false)}
                className="text-[#69748b] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            {/* Bento Grid Stats */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              <div className="p-4 rounded-xl bg-[#080a12] border border-white/5">
                <span className="text-[11px] text-[#69748b] font-semibold uppercase block mb-1">
                  Active Streak
                </span>
                <span className="text-2xl font-bold text-[#fbbf58]">
                  {profileStats.streak} 🔥
                </span>
              </div>

              <div className="p-4 rounded-xl bg-[#080a12] border border-white/5">
                <span className="text-[11px] text-[#69748b] font-semibold uppercase block mb-1">
                  Scholar Level
                </span>
                <span className="text-2xl font-bold text-[#38d4e8]">
                  Lvl {profileStats.level}
                </span>
              </div>

              <div className="p-4 rounded-xl bg-[#080a12] border border-white/5">
                <span className="text-[11px] text-[#69748b] font-semibold uppercase block mb-1">
                  Questions Asked
                </span>
                <span className="text-2xl font-bold text-white">
                  {profileStats.total}
                </span>
              </div>

              <div className="p-4 rounded-xl bg-[#080a12] border border-white/5">
                <span className="text-[11px] text-[#69748b] font-semibold uppercase block mb-1">
                  Quiz Accuracy
                </span>
                <span className="text-2xl font-bold text-[#43d9a2]">
                  {profileStats.score}%
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-[#080a12] border border-white/5 text-xs text-[#858da1] flex justify-between">
              <span>Account:</span>
              <strong className="text-white">
                {user?.first_name} {user?.username ? `(@${user.username})` : ''}
              </strong>
            </div>
          </div>
        </div>
      )}

      {/* ── Memory & Liked Notes Modal ── */}
      {showMemoryModal && (
        <div className="command-overlay" onClick={() => setShowMemoryModal(false)}>
          <div
            className="w-full max-w-lg bg-[#121622] border border-white/10 rounded-2xl p-6 shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Brain size={18} className="text-[#38d4e8]" /> AI Memory & Saved Notes
              </h3>
              <button
                onClick={() => setShowMemoryModal(false)}
                className="text-[#69748b] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <h4 className="text-xs font-semibold text-[#858da1] mb-2 uppercase tracking-wider">
                  Adaptive Learning Context
                </h4>
                <div className="p-3.5 rounded-xl bg-[#080a12] border border-white/5 text-xs text-[#43d9a2] font-mono leading-relaxed max-h-32 overflow-y-auto">
                  {memoryData.learn_context}
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-[#858da1] mb-2 uppercase tracking-wider">
                  Saved High-Yield Notes ({memoryData.liked_notes.length})
                </h4>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {memoryData.liked_notes.length === 0 ? (
                    <div className="text-xs text-[#596174] p-3 text-center">
                      No saved notes yet. Click &quot;Save Note&quot; under any AI response.
                    </div>
                  ) : (
                    memoryData.liked_notes.map((note, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-xl bg-[#080a12] border-l-2 border-[#43d9a2] text-xs text-[#c9cede]"
                      >
                        {note}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
