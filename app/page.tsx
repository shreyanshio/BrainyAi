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
  photo_url?: string
}

const TelegramIcon = ({ className = 'w-5 h-5' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
  </svg>
)

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
  const [loginError, setLoginError] = useState('')

  // Telegram auth handshake state
  const [telegramSessionId, setTelegramSessionId] = useState<string | null>(null)
  const [telegramBotUrl, setTelegramBotUrl] = useState<string>('')
  const [telegramWaiting, setTelegramWaiting] = useState(false)
  const [telegramStarting, setTelegramStarting] = useState(false)

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

  // Real stats state
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

  // Poll Telegram auth session status
  useEffect(() => {
    if (!telegramWaiting || !telegramSessionId || user) return

    const pollInterval = setInterval(async () => {
      try {
        const resp = await apiFetch(`/api/auth/status/${telegramSessionId}`)
        if (resp.ok) {
          const data = await resp.json()
          if (data.status === 'authenticated' && data.user) {
            clearInterval(pollInterval)
            setTelegramWaiting(false)
            setTelegramSessionId(null)
            setUser(data.user)
            await loadUserData()
          }
        }
      } catch (err) {
        console.error('Polling Telegram auth error:', err)
      }
    }, 2000)

    return () => clearInterval(pollInterval)
  }, [telegramWaiting, telegramSessionId, user])

  const checkCurrentUser = async () => {
    setAuthLoading(true)
    try {
      // 0. Check URL query params (?auth_session=... from Telegram bot / redirect)
      if (typeof window !== 'undefined') {
        const urlParams = new URLSearchParams(window.location.search)
        const authSessionParam = urlParams.get('auth_session')
        if (authSessionParam) {
          const statusResp = await apiFetch(`/api/auth/status/${authSessionParam}`)
          if (statusResp.ok) {
            const data = await statusResp.json()
            if (data.status === 'authenticated' && data.user) {
              setUser(data.user)
              window.history.replaceState({}, document.title, window.location.pathname)
              await loadUserData()
              setAuthLoading(false)
              return
            }
          }
        }
      }

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

      // 2. Check server session via /api/auth/me or /api/user/profile
      const profResp = await apiFetch('/api/user/profile')
      if (profResp.ok) {
        const prof = await profResp.json()
        if (prof.user_id || prof.first_name) {
          setUser({
            id: prof.user_id || 1,
            first_name: prof.first_name || 'Student',
            username: prof.username || '',
            photo_url: prof.photo_url || (prof.username ? `https://t.me/i/userpic/320/${prof.username}.jpg` : ''),
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
  const handleStartTelegramAuth = async () => {
    setTelegramStarting(true)
    setLoginError('')
    try {
      const resp = await apiFetch('/api/auth/init', { method: 'POST' })
      if (resp.ok) {
        const data = await resp.json()
        const botUrl = data.bot_url || 'https://t.me/AiChatExpert_Bot'
        setTelegramSessionId(data.session_id)
        setTelegramBotUrl(botUrl)
        setTelegramWaiting(true)
        window.open(botUrl, '_blank')
      } else {
        setLoginError('Could not initialize Telegram login session.')
      }
    } catch (e) {
      setLoginError('Network error connecting to authentication server.')
    } finally {
      setTelegramStarting(false)
    }
  }

  const handleCancelTelegramAuth = () => {
    setTelegramWaiting(false)
    setTelegramSessionId(null)
    setLoginError('')
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
  // VIEW 1: HERO & STRICT AUTH SECTION (Yellow, White, Black Palette)
  // ═════════════════════════════════════════════════════════════
  if (!user && !authLoading) {
    return (
      <div className="min-h-screen bg-[#050507] text-[#FFFFFF] flex flex-col justify-between selection:bg-[#F59E0B] selection:text-black relative overflow-hidden font-sans">
        {/* Ambient subtle gold highlights */}
        <div className="absolute top-[-15%] right-[5%] w-[650px] h-[650px] bg-[#F59E0B]/[0.06] rounded-full blur-[150px] pointer-events-none" />
        <div className="absolute bottom-[-15%] left-[5%] w-[550px] h-[550px] bg-[#D97706]/[0.04] rounded-full blur-[160px] pointer-events-none" />

        {/* Top Navbar */}
        <header className="w-full max-w-7xl mx-auto px-6 py-6 flex items-center justify-between relative z-10">
          <div className="flex items-center gap-3.5">
            {/* Brainy AI Monogram Emblem */}
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#FEF08A] via-[#F59E0B] to-[#B45309] p-[1.5px] shadow-[0_0_20px_rgba(245,158,11,0.25)] flex items-center justify-center">
              <div className="w-full h-full bg-[#09090B] rounded-[10px] flex items-center justify-center">
                <span className="font-black text-transparent bg-clip-text bg-gradient-to-br from-[#FEF08A] to-[#F59E0B] text-base font-serif">
                  B
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className="font-black text-xl tracking-tight text-white">
                BRAINY <span className="text-[#FBBF24]">AI</span>
              </span>
              {/* Premium Line of Separation */}
              <div className="h-5 w-[1.5px] bg-gradient-to-b from-transparent via-[#F59E0B]/60 to-transparent" />
              <span className="text-[11px] uppercase tracking-[0.2em] font-semibold text-zinc-400 hidden sm:inline-block">
                Cognitive Study Sanctuary
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5 text-xs font-semibold text-zinc-300 bg-zinc-900/90 border border-zinc-800 px-3.5 py-1.5 rounded-full shadow-inner">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#F59E0B] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#F59E0B]" />
            </span>
            <span>Intellect Online • 24/7 Available</span>
          </div>
        </header>

        {/* Hero & Auth Body */}
        <main className="max-w-7xl mx-auto px-6 py-10 flex-1 flex flex-col lg:flex-row items-center justify-center gap-12 lg:gap-20 relative z-10 w-full">
          {/* Left Hero Description ("The Book Cover") */}
          <div className="flex-1 max-w-xl text-center lg:text-left">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#F59E0B]/10 border border-[#F59E0B]/25 text-[#FBBF24] text-xs font-semibold mb-6">
              <Zap size={14} className="text-[#FBBF24]" />
              <span>Autonomous Academic Architecture • Zero Fluff</span>
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.12] mb-6">
              Think Clearly. <br />
              <span className="italic font-serif text-transparent bg-clip-text bg-gradient-to-r from-[#FEF08A] via-[#FBBF24] to-[#D97706]">
                Master Confidently.
              </span>
            </h1>

            <p className="text-zinc-400 text-base sm:text-lg leading-relaxed mb-8">
              Your emotionally intelligent, persistent AI study companion. Instant breakdowns for complex code,
              mathematical derivations, sciences, and deep concept synthesis.
            </p>

            {/* Executive Feature Bento Pills */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-left">
              <div className="p-4 rounded-xl bg-[#0C0D12] border border-zinc-800/80 hover:border-[#F59E0B]/30 transition flex items-center gap-3.5 shadow-sm">
                <div className="w-9 h-9 rounded-lg bg-[#F59E0B]/10 border border-[#F59E0B]/20 flex items-center justify-center text-[#FBBF24] flex-shrink-0">
                  <Code2 size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Socratic Logic Engine</h4>
                  <p className="text-[11px] text-zinc-500 mt-0.5">Real-time traces & step derivations</p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-[#0C0D12] border border-zinc-800/80 hover:border-[#F59E0B]/30 transition flex items-center gap-3.5 shadow-sm">
                <div className="w-9 h-9 rounded-lg bg-[#F59E0B]/10 border border-[#F59E0B]/20 flex items-center justify-center text-[#FBBF24] flex-shrink-0">
                  <Brain size={18} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Persistent Memory</h4>
                  <p className="text-[11px] text-zinc-500 mt-0.5">Remembers your doubt patterns</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Auth Card (Strict, Professional, No Mock Bypass) */}
          <div className="w-full max-w-md bg-[#0C0D12] border border-zinc-800/90 rounded-2xl p-7 shadow-2xl backdrop-blur-xl relative">
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#FBBF24] to-transparent rounded-t-2xl" />

            <div className="mb-6 text-center">
              <h2 className="text-xl font-extrabold text-white mb-1.5 tracking-tight">Access Study Sanctuary</h2>
              <p className="text-xs text-zinc-400">Strict authentication required. Persistent memory active.</p>
            </div>

            {loginError && (
              <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs text-center font-medium">
                {loginError}
              </div>
            )}

            {/* Mode A: Telegram Waiting Screen */}
            {telegramWaiting ? (
              <div className="p-5 rounded-xl bg-[#08090D] border border-[#F59E0B]/30 text-center">
                <div className="relative w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#F59E0B]/20" />
                  <div className="relative w-14 h-14 rounded-full bg-[#229ED9]/15 border border-[#229ED9]/40 flex items-center justify-center text-[#229ED9]">
                    <TelegramIcon className="w-7 h-7" />
                  </div>
                </div>

                <h3 className="text-sm font-bold text-white mb-2">Connecting with Telegram</h3>
                <p className="text-xs text-zinc-400 mb-4 leading-relaxed">
                  Open <span className="text-[#FBBF24] font-semibold">@AiChatExpert_Bot</span> in Telegram, send{' '}
                  <span className="text-white font-mono bg-zinc-800 px-1.5 py-0.5 rounded">/login</span>, and tap{' '}
                  <strong className="text-white">"Authorize Web Login"</strong>.
                </p>

                <div className="flex flex-col gap-2.5">
                  <button
                    onClick={() => {
                      if (telegramBotUrl) window.open(telegramBotUrl, '_blank')
                    }}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#229ED9] hover:bg-[#1E88E5] text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-lg shadow-[#229ED9]/20"
                  >
                    <TelegramIcon className="w-4 h-4" />
                    <span>Open @AiChatExpert_Bot in Telegram ↗</span>
                  </button>

                  <div className="flex items-center justify-center gap-2 py-1 text-[11px] text-[#FBBF24]">
                    <span className="w-2 h-2 rounded-full bg-[#FBBF24] animate-pulse" />
                    <span>Listening for authorization handshake...</span>
                  </div>

                  <button
                    onClick={handleCancelTelegramAuth}
                    className="text-xs text-zinc-500 hover:text-zinc-300 py-1.5 transition underline"
                  >
                    Cancel and use another sign-in method
                  </button>
                </div>
              </div>
            ) : (
              /* Mode B: Strict Sign In Options (Google + Telegram Only) */
              <div className="space-y-4">
                {/* 1. Google OAuth Container */}
                <div>
                  <div
                    id="google-btn-slot"
                    className="w-full flex justify-center min-h-[44px] rounded-xl overflow-hidden"
                  />
                </div>

                {/* Divider */}
                <div className="relative my-4 text-center">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-zinc-800" />
                  </div>
                  <span className="relative px-3 bg-[#0C0D12] text-[10px] uppercase font-bold tracking-widest text-zinc-500">
                    OR SECURE TELEGRAM AUTH
                  </span>
                </div>

                {/* 2. Official Telegram Login Button */}
                <button
                  onClick={handleStartTelegramAuth}
                  disabled={telegramStarting}
                  className="w-full py-3 px-4 rounded-xl bg-[#090A0E] hover:bg-zinc-900 border border-zinc-700/80 hover:border-[#FBBF24]/50 text-white hover:text-white transition duration-200 flex items-center justify-between group shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[#229ED9] flex items-center justify-center text-white flex-shrink-0 shadow-md shadow-[#229ED9]/30">
                      <TelegramIcon className="w-5 h-5" />
                    </div>
                    <div className="text-left">
                      <div className="text-xs font-bold text-white group-hover:text-[#FBBF24] transition">
                        Continue with Telegram
                      </div>
                      <div className="text-[10px] text-zinc-400">@AiChatExpert_Bot</div>
                    </div>
                  </div>
                  <span className="text-zinc-500 group-hover:text-[#FBBF24] text-xs font-semibold transition">
                    {telegramStarting ? 'Connecting...' : 'Authorize →'}
                  </span>
                </button>

                {/* Strict Security Badge */}
                <div className="mt-6 pt-5 border-t border-zinc-800/80 text-center">
                  <div className="inline-flex items-center gap-1.5 text-[11px] font-medium text-zinc-500">
                    <Target size={13} className="text-[#FBBF24]" />
                    <span>Strict Authentication • No Guest Bypass • Verified Identity</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* Executive Footer */}
        <footer className="w-full text-center py-6 text-xs text-zinc-500 border-t border-zinc-900 relative z-10">
          BRAINY AI — Dedicated to high-performing scholars and engineers.
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

          {/* Persistent Chat History */}
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
              <div className="avatar overflow-hidden flex items-center justify-center">
                {user?.photo_url ? (
                  <img
                    src={user.photo_url}
                    alt={user.first_name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none'
                    }}
                  />
                ) : (
                  userInitials
                )}
              </div>
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
                    <span className="user-avatar overflow-hidden flex items-center justify-center">
                      {user?.photo_url ? (
                        <img
                          src={user.photo_url}
                          alt={user.first_name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none'
                          }}
                        />
                      ) : (
                        userInitials
                      )}
                    </span>
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

            {/* User Profile Card */}
            <div className="flex items-center gap-4 p-4 rounded-xl bg-[#08090D] border border-zinc-800 mb-5">
              <div className="w-13 h-13 rounded-full overflow-hidden bg-gradient-to-br from-[#F59E0B] to-[#B45309] flex items-center justify-center text-black font-extrabold text-base flex-shrink-0 border-2 border-[#FBBF24]/40">
                {user?.photo_url ? (
                  <img
                    src={user.photo_url}
                    alt={user.first_name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = 'none'
                    }}
                  />
                ) : (
                  userInitials
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-bold text-white truncate">{user?.first_name || 'Scholar'}</h4>
                <p className="text-xs text-[#FBBF24] font-medium truncate">
                  {user?.username ? `@${user.username}` : 'Verified Scholar'}
                </p>
                <p className="text-[11px] text-zinc-500 mt-0.5">Persistent Session Synced</p>
              </div>
            </div>

            {/* Bento Grid Stats */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              <div className="p-4 rounded-xl bg-[#08090D] border border-zinc-800/80">
                <span className="text-[11px] text-zinc-400 font-semibold uppercase block mb-1">
                  Active Streak
                </span>
                <span className="text-2xl font-bold text-[#FBBF24]">
                  {profileStats.streak} 🔥
                </span>
              </div>

              <div className="p-4 rounded-xl bg-[#08090D] border border-zinc-800/80">
                <span className="text-[11px] text-zinc-400 font-semibold uppercase block mb-1">
                  Scholar Level
                </span>
                <span className="text-2xl font-bold text-white">
                  Lvl {profileStats.level}
                </span>
              </div>

              <div className="p-4 rounded-xl bg-[#08090D] border border-zinc-800/80">
                <span className="text-[11px] text-zinc-400 font-semibold uppercase block mb-1">
                  Questions Asked
                </span>
                <span className="text-2xl font-bold text-white">
                  {profileStats.total}
                </span>
              </div>

              <div className="p-4 rounded-xl bg-[#08090D] border border-zinc-800/80">
                <span className="text-[11px] text-zinc-400 font-semibold uppercase block mb-1">
                  Quiz Accuracy
                </span>
                <span className="text-2xl font-bold text-[#F59E0B]">
                  {profileStats.score}%
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-[#08090D] border border-zinc-800 text-xs text-zinc-400 flex justify-between items-center">
              <span>Security Status:</span>
              <strong className="text-[#FBBF24] flex items-center gap-1">
                <Check size={13} /> Verified & Persistent
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
