'use client'

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  checkAuth,
  checkAuthSessionParam,
  createSession,
  deleteSession,
  fetchSessionHistory,
  fetchSessionPage,
  fetchUsage,
  fetchUserMemory,
  fetchUserProfile,
  fetchUserPreferences,
  loginWithTelegramInitData,
  loginWithGoogle,
  logoutUser,
  renameSession,
  saveUserMemoryNote,
  saveUserPreferences,
  sendChatMessage,
  streamChatMessage,
  updateSessionWorkspace,
} from '@/lib/api'
import {
  AnswerLength,
  ChatMessage,
  ChatSession,
  UsageStatus,
  User,
  UserMemoryData,
  UserProfileStats,
  UserPreferences,
} from '@/types/api'
import { DEFAULT_PREFERENCES, FONT_OPTIONS, THEME_PRESETS, ACCENT_PRESETS } from '@/lib/constants'
import { LoginView } from '@/components/auth/LoginView'
import { AppHeader } from '@/components/app-shell/AppHeader'
import { Sidebar } from '@/components/app-shell/Sidebar'
import { StudentDashboard } from '@/components/dashboard/StudentDashboard'
import { EmptyState } from '@/components/chat/EmptyState'
import { MessageList } from '@/components/chat/MessageList'
import { Composer } from '@/components/chat/Composer'
import { UsageModal } from '@/components/modals/UsageModal'
import { NotesModal } from '@/components/modals/NotesModal'
import { SettingsModal } from '@/components/settings/SettingsModal'

export default function BrainyApp() {
  // Auth state
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)

  // Active View: 'chat' (Study Chat Workspace by default) vs 'overview' (Aptivus Dashboard)
  const [currentView, setCurrentView] = useState<'overview' | 'chat'>('chat')

  // User Customization & Preferences
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES)

  // Chat & Session state
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [sessionsHasMore, setSessionsHasMore] = useState(false)
  const [sessionsNextOffset, setSessionsNextOffset] = useState(0)
  const [sessionsLoadingMore, setSessionsLoadingMore] = useState(false)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeSessionTitle, setActiveSessionTitle] = useState('New Study Session')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [inputMessage, setInputMessage] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const selectionRequestRef = useRef(0)
  const viewGenerationRef = useRef(0)

  // Capabilities & Preferences state
  const [activeModel, setActiveModel] = useState('brainy-balanced')
  const [activeLength, setActiveLength] = useState<AnswerLength>('medium')

  // Global 30 msg / 5h Quota state
  const [usage, setUsage] = useState<UsageStatus | null>(null)
  const [memoryData, setMemoryData] = useState<UserMemoryData | null>(null)
  const [profileStats, setProfileStats] = useState<UserProfileStats | null>(null)

  // Modal & Drawer state
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false)
  const [usageModalOpen, setUsageModalOpen] = useState(false)
  const [notesModalOpen, setNotesModalOpen] = useState(false)
  const [settingsModalOpen, setSettingsModalOpen] = useState(false)

  // ── Apply Preferences to Document Root ────────────────────
  useEffect(() => {
    if (typeof document === 'undefined') return

    const root = document.documentElement

    // 1. Theme Class & Dark Mode Flag
    THEME_PRESETS.forEach((t) => root.classList.remove(`theme-${t.id}`))
    root.classList.add(`theme-${preferences.theme}`)

    const activeTheme = THEME_PRESETS.find((t) => t.id === preferences.theme)
    const isDark = activeTheme ? activeTheme.mode === 'dark' : false
    root.classList.toggle('dark', isDark)

    // 2. Font Class
    FONT_OPTIONS.forEach((f) => root.classList.remove(`font-${f.id}`))
    // Lora is the product-wide default. Other typography preferences remain
    // available as explicit user choices in Settings.
    root.classList.add(`font-${preferences.interfaceFont || 'lora'}`)

    // 3. Font Size & Line Spacing Scaling Classes
    ;['font-size-sm', 'font-size-md', 'font-size-lg', 'font-size-xl'].forEach((cls) => root.classList.remove(cls))
    root.classList.add(`font-size-${preferences.fontSize || 'md'}`)

    ;['line-spacing-compact', 'line-spacing-comfortable', 'line-spacing-relaxed'].forEach((cls) =>
      root.classList.remove(cls)
    )
    root.classList.add(`line-spacing-${preferences.lineSpacing || 'comfortable'}`)

    // 4. Accent Color Custom Property
    const currentAccent = ACCENT_PRESETS.find((a) => a.id === preferences.accentColor)
    const accentHex = preferences.customAccentHex || currentAccent?.hex || '#059669'
    const accentHover = currentAccent?.hoverHex || '#10b981'
    const accentSubtle = currentAccent?.subtleBg || 'rgba(5, 150, 105, 0.12)'

    root.style.setProperty('--accent-primary', accentHex)
    root.style.setProperty('--accent-hover', accentHover)
    root.style.setProperty('--accent-subtle', accentSubtle)

    // Sync active model/length from default preferences if set
    if (preferences.defaultModel) setActiveModel(preferences.defaultModel)
    if (preferences.defaultLength) setActiveLength(preferences.defaultLength)
  }, [preferences])

  const loadSessionIntoView = useCallback(async (sessionId: string, fallbackTitle?: string) => {
    const requestNumber = ++selectionRequestRef.current
    viewGenerationRef.current += 1
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setIsThinking(false)
    setActiveSessionId(sessionId)
    setActiveSessionTitle(fallbackTitle || 'Loading chat...')
    setCurrentView('chat')
    setSidebarMobileOpen(false)
    setMessages([])
    setHistoryError(null)
    setHistoryLoading(true)

    try {
      const data = await fetchSessionHistory(sessionId)
      if (requestNumber !== selectionRequestRef.current) return
      setMessages(data.messages || [])
      if (data.usage) setUsage(data.usage)
      setActiveSessionTitle(data.title || fallbackTitle || 'New Study Session')
      setHistoryError(null)
    } catch (error) {
      if (requestNumber !== selectionRequestRef.current) return
      console.error('Failed to load session history:', error)
      setHistoryError(error instanceof Error ? error.message : 'Chat history could not be loaded.')
    } finally {
      if (requestNumber === selectionRequestRef.current) setHistoryLoading(false)
    }
  }, [])

  // ── Initial Auth & Bootstrap ──────────────────────────────
  const loadInitialData = useCallback(async (userId: number) => {
    setSessionsLoading(true)
    setSessionsError(null)
    try {
      // 1. Load Local Preferences from localStorage first
      if (typeof window !== 'undefined') {
        const savedPrefs = localStorage.getItem('brainy_user_preferences')
        if (savedPrefs) {
          try {
            setPreferences((prev) => ({ ...prev, ...JSON.parse(savedPrefs), interfaceFont: 'lora' }))
          } catch {
            // ignore
          }
        }
      }

      // 2. Fetch Sessions, Quota, Memory, and Server Preferences concurrently
      const [sessionResult, usageResult, memoryResult, preferencesResult, profileResult] = await Promise.allSettled([
        fetchSessionPage(50, 0),
        fetchUsage(),
        fetchUserMemory(),
        fetchUserPreferences(),
        fetchUserProfile(),
      ])

      if (sessionResult.status === 'fulfilled') {
        setSessions(sessionResult.value.sessions)
        setSessionsHasMore(sessionResult.value.has_more)
        setSessionsNextOffset(sessionResult.value.next_offset)
      } else {
        setSessionsError(sessionResult.reason instanceof Error ? sessionResult.reason.message : 'Chat list could not be loaded.')
      }
      if (usageResult.status === 'fulfilled') setUsage(usageResult.value)
      if (memoryResult.status === 'fulfilled') setMemoryData(memoryResult.value)
      if (profileResult.status === 'fulfilled') setProfileStats(profileResult.value)
      const serverPrefs = preferencesResult.status === 'fulfilled' ? preferencesResult.value : {}

      // Restore the last selected conversation for this account after refresh.
      if (typeof window !== 'undefined') {
        const savedSessionId = localStorage.getItem(`brainy_active_session_${userId}`)
        // Do not require the active chat to be in the first sidebar page.
        // This restores older conversations even when the user has many chats.
        if (savedSessionId) await loadSessionIntoView(savedSessionId)
      }

      if (serverPrefs && Object.keys(serverPrefs).length > 0) {
        setPreferences((prev) => {
          const merged = { ...prev, ...serverPrefs, interfaceFont: 'lora' as const }
          if (typeof window !== 'undefined') {
            localStorage.setItem('brainy_user_preferences', JSON.stringify(merged))
          }
          return merged
        })
      }
    } catch (err) {
      console.error('Failed to load initial data:', err)
    } finally {
      setSessionsLoading(false)
    }
  }, [loadSessionIntoView])

  useEffect(() => {
    const authenticate = async () => {
      setAuthLoading(true)
      try {
        // 1. Check URL query params for Telegram handshake or Google OAuth redirect
        if (typeof window !== 'undefined') {
          const urlParams = new URLSearchParams(window.location.search)
          const authSessionParam = urlParams.get('auth_session')
          if (authSessionParam) {
            const statusRes = await checkAuthSessionParam(authSessionParam)
            if (statusRes.status === 'authenticated' && statusRes.user) {
              setUser(statusRes.user)
              setCurrentView('chat')
              window.history.replaceState({}, document.title, window.location.pathname)
              await loadInitialData(statusRes.user.id)
              setAuthLoading(false)
              return
            }
          }

          const googleTokenParam = urlParams.get('google_token')
          if (googleTokenParam) {
            try {
              const googleUser = await loginWithGoogle(googleTokenParam)
              if (googleUser) {
                setUser(googleUser)
                setCurrentView('chat')
                window.history.replaceState({}, document.title, window.location.pathname)
                await loadInitialData(googleUser.id)
                setAuthLoading(false)
                return
              }
            } catch (gErr) {
              console.error('Failed to authenticate with google_token:', gErr)
              window.history.replaceState({}, document.title, window.location.pathname)
            }
          }
        }

        // 2. Check if inside Telegram WebApp
        const tg = typeof window !== 'undefined' && (window as any).Telegram?.WebApp
        if (tg && tg.initData) {
          tg.expand?.()
          const loggedUser = await loginWithTelegramInitData(tg.initData)
          if (loggedUser) {
            setUser(loggedUser)
            setCurrentView('chat')
            await loadInitialData(loggedUser.id)
            setAuthLoading(false)
            return
          }
        }

        // 3. Check existing browser session cookie
        const currentUser = await checkAuth()
        if (currentUser) {
          setUser(currentUser)
          setCurrentView('chat')
          await loadInitialData(currentUser.id)
        }
      } catch (err) {
        console.warn('Auth check skipped:', err)
      } finally {
        setAuthLoading(false)
      }
    }

    authenticate()
  }, [loadInitialData])

  useEffect(() => {
    if (typeof window !== 'undefined' && user && activeSessionId) {
      localStorage.setItem(`brainy_active_session_${user.id}`, activeSessionId)
    }
  }, [activeSessionId, user])

  // ── Session Operations ────────────────────────────────────
  const selectSession = async (sessionId: string, title?: string) => {
    await loadSessionIntoView(sessionId, title)
  }

  const retrySessionList = async () => {
    setSessionsLoading(true)
    setSessionsError(null)
    try {
      const page = await fetchSessionPage(50, 0)
      setSessions((previous) => {
        const refreshedIds = new Set(page.sessions.map((item) => item.id))
        return [...page.sessions, ...previous.filter((item) => !refreshedIds.has(item.id))]
      })
      setSessionsHasMore(page.has_more || sessions.length > page.sessions.length)
      setSessionsNextOffset(Math.max(page.next_offset, sessions.length))
    } catch (error) {
      setSessionsError(error instanceof Error ? error.message : 'Chat list could not be loaded.')
    } finally {
      setSessionsLoading(false)
    }
  }

  const loadMoreSessions = async () => {
    if (sessionsLoadingMore || !sessionsHasMore) return
    setSessionsLoadingMore(true)
    setSessionsError(null)
    try {
      const page = await fetchSessionPage(50, sessionsNextOffset)
      setSessions((previous) => {
        const existing = new Set(previous.map((item) => item.id))
        return [...previous, ...page.sessions.filter((item) => !existing.has(item.id))]
      })
      setSessionsHasMore(page.has_more)
      setSessionsNextOffset(page.next_offset)
    } catch (error) {
      setSessionsError(error instanceof Error ? error.message : 'More chats could not be loaded.')
    } finally {
      setSessionsLoadingMore(false)
    }
  }

  const handleNewSession = () => {
    selectionRequestRef.current += 1
    viewGenerationRef.current += 1
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setIsThinking(false)
    if (typeof window !== 'undefined' && user) {
      localStorage.removeItem(`brainy_active_session_${user.id}`)
    }
    setActiveSessionId(null)
    setActiveSessionTitle('New Study Session')
    setMessages([])
    setHistoryError(null)
    setHistoryLoading(false)
    setInputMessage('')
    setCurrentView('chat')
    setSidebarMobileOpen(false)
  }

  const handleRenameSession = async (sessionId: string, newTitle: string) => {
    try {
      await renameSession(sessionId, newTitle)
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: newTitle } : s))
      )
      if (activeSessionId === sessionId) {
        setActiveSessionTitle(newTitle)
      }
    } catch (err) {
      console.error('Failed to rename session:', err)
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    const target = sessions.find((s) => s.id === sessionId)
    if (!window.confirm(`Permanently delete “${target?.title || 'this chat'}” and its messages?`)) return
    try {
      await deleteSession(sessionId)
      setSessions((prev) => prev.filter((s) => s.id !== sessionId))
      if (activeSessionId === sessionId) {
        handleNewSession()
      }
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const handleUpdateSessionWorkspace = async (
    sessionId: string,
    changes: { is_saved?: boolean; is_pinned?: boolean; is_archived?: boolean }
  ) => {
    const before = sessions
    setSessions((prev) => prev.map((s) => s.id === sessionId ? { ...s, ...changes } : s))
    try {
      await updateSessionWorkspace(sessionId, changes)
    } catch (err) {
      setSessions(before)
      console.error('Failed to update chat workspace settings:', err)
      window.alert('Could not save this chat setting. Please try again.')
    }
  }

  // ── Message Operations ────────────────────────────────────
  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = (customPrompt || inputMessage).trim()
    if (!textToSend || isThinking || historyLoading || historyError) return
    const sendViewGeneration = viewGenerationRef.current
    const belongsToCurrentView = () => sendViewGeneration === viewGenerationRef.current

    // Cancel any ongoing stream
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    // Immediately switch to chat workspace
    setCurrentView('chat')

    // Add user message to UI
    const userMsg: ChatMessage = {
      role: 'user',
      content: textToSend,
      created_at: new Date().toISOString(),
    }

    // Add optimistic assistant message placeholder for streaming
    const assistantMsgId = `assistant-${Date.now()}`
    const idempotencyKey = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`
    const initialAssistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      model: activeModel,
      answer_length: activeLength,
      isStreaming: true,
    }

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg])
    if (!customPrompt) setInputMessage('')
    setIsThinking(true)

    try {
      await streamChatMessage(
        {
          session_id: activeSessionId,
          message: textToSend,
          model: activeModel,
          answer_length: activeLength,
          idempotency_key: idempotencyKey,
        },
        {
          onStart: (sessionId, requestId) => {
            if (!belongsToCurrentView()) return
            if (sessionId && sessionId !== activeSessionId) {
              setActiveSessionId(sessionId)
            }
          },
          onDelta: (deltaText, accumulatedText) => {
            if (!belongsToCurrentView()) return
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, content: accumulatedText } : m
              )
            )
          },
          onDone: (doneEvent) => {
            if (!belongsToCurrentView()) return
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      isStreaming: false,
                      model: doneEvent.model,
                      answer_length: doneEvent.answer_length,
                      content: doneEvent.persistence_warning
                        ? `${m.content}\n\n⚠️ This reply could not be fully saved to your chat. Copy it before leaving this conversation.`
                        : m.content,
                    }
                  : m
              )
            )

            // If backend created a new session
            if (doneEvent.session_id && doneEvent.session_id !== activeSessionId) {
              setActiveSessionId(doneEvent.session_id)
              const sessionTitle = doneEvent.new_title || 'New Study Session'
              if (doneEvent.new_title) setActiveSessionTitle(doneEvent.new_title)
              const optimisticSession: ChatSession = {
                id: doneEvent.session_id,
                title: sessionTitle,
                created_at: new Date().toISOString(),
              }
              setSessions((prev) => [
                optimisticSession,
                ...prev.filter((s) => s.id !== doneEvent.session_id),
              ])
              fetchSessionPage(50, 0)
                .then((page) => {
                  setSessions((previous) => {
                    const refreshedIds = new Set(page.sessions.map((item) => item.id))
                    return [...page.sessions, ...previous.filter((item) => !refreshedIds.has(item.id))]
                  })
                  setSessionsHasMore(page.has_more || sessions.length > page.sessions.length)
                  setSessionsNextOffset(Math.max(page.next_offset, sessions.length))
                })
                .catch((error) => console.warn('Could not refresh saved chats:', error))
            } else if (doneEvent.new_title) {
              setActiveSessionTitle(doneEvent.new_title)
              setSessions((prev) =>
                prev.map((s) =>
                  s.id === activeSessionId ? { ...s, title: doneEvent.new_title || s.title } : s
                )
              )
            }

            if (doneEvent.usage) setUsage(doneEvent.usage)
          },
          onError: (err, partialText) => {
            if (!belongsToCurrentView()) return
            console.error('Streaming error callback:', err)
          },
        },
        abortController.signal
      )
    } catch (err: any) {
      if (!belongsToCurrentView()) return
      if (err?.name === 'AbortError') {
        console.log('User stopped generation')
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, isStreaming: false } : m
          )
        )
      } else if (err?.status === 429) {
        const code = err?.data?.code
        if (code === 'QUOTA_EXCEEDED') {
          setMessages((prev) => prev.filter((m) => m.id !== assistantMsgId))
          const refreshedUsage = await fetchUsage().catch(() => null)
          if (refreshedUsage) setUsage(refreshedUsage)
          setUsageModalOpen(true)
          setMessages((prev) => [...prev, {
            role: 'assistant',
            content: `⚠️ **Study quota reached**: You have used the available messages for this ${usage?.window_hours ?? 5}-hour window. Please try again after it resets.`,
            created_at: new Date().toISOString(),
          }])
        } else {
          setMessages((prev) => prev.map((m) => m.id === assistantMsgId
            ? { ...m, isStreaming: false, content: `⚠️ ${err?.message || 'Too many requests. Please wait before trying again.'}` }
            : m))
        }
      } else {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id === assistantMsgId) {
              if (m.content.trim()) {
                const note = err?.data?.code === 'assistant_save_failed'
                  ? '\n\n⚠️ This answer could not be saved to your chat. Copy it before leaving this conversation.'
                  : err?.data?.partial
                    ? '\n\n⚠️ This response was interrupted and was not saved.'
                    : ''
                return { ...m, isStreaming: false, content: `${m.content}${note}` }
              }
              const requestRef = err?.data?.request_id ? ` (reference ${err.data.request_id})` : ''
              return {
                ...m,
                isStreaming: false,
                content: `⚠️ ${err?.message || 'Could not generate an answer. Please check connection and retry.'}${requestRef}`,
              }
            }
            return m
          })
        )
      }
    } finally {
      if (belongsToCurrentView()) setIsThinking(false)
      if (abortControllerRef.current === abortController) abortControllerRef.current = null
    }
  }

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  const handleStartStudyPrompt = (promptText: string) => {
    setCurrentView('chat')
    setInputMessage(promptText)
  }

  const handleSaveNote = async (noteText: string) => {
    try {
      await saveUserMemoryNote(noteText)
      const updatedMem = await fetchUserMemory().catch(() => null)
      if (updatedMem) setMemoryData(updatedMem)
    } catch (err) {
      console.error('Failed to save study note:', err)
    }
  }

  const handleUpdatePreferences = (updated: Partial<UserPreferences>) => {
    setPreferences((prev) => {
      const next = { ...prev, ...updated }
      if (typeof window !== 'undefined') {
        localStorage.setItem('brainy_user_preferences', JSON.stringify(next))
      }
      saveUserPreferences(next).catch(() => {})
      return next
    })
  }

  const handleLogout = async () => {
    selectionRequestRef.current += 1
    viewGenerationRef.current += 1
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    await logoutUser()
    if (typeof window !== 'undefined' && user) {
      localStorage.removeItem(`brainy_active_session_${user.id}`)
    }
    setUser(null)
    setSessions([])
    setSessionsError(null)
    setSessionsHasMore(false)
    setSessionsNextOffset(0)
    setActiveSessionId(null)
    setMessages([])
    setHistoryError(null)
    setHistoryLoading(false)
    setIsThinking(false)
    setUsage(null)
    setMemoryData(null)
    setProfileStats(null)
    setCurrentView('chat')
  }

  // Loading Screen
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#0e1017] flex flex-col items-center justify-center gap-3 text-zinc-400">
        <div className="w-8 h-8 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-white text-sm animate-pulse">
          B
        </div>
        <p className="text-xs text-zinc-500 font-medium">Loading Brainy...</p>
      </div>
    )
  }

  // Unauthenticated: Show Origin Split-Card Login View
  if (!user) {
    return (
      <LoginView
        onLoginSuccess={(loggedInUser) => {
          setUser(loggedInUser)
          setCurrentView('chat')
          loadInitialData(loggedInUser.id)
        }}
      />
    )
  }

  // Authenticated: Full Study Companion App Shell
  return (
    <div className="flex h-screen h-[100dvh] overflow-hidden ambient-canvas text-[var(--text-primary)] antialiased transition-colors">
      {/* Left Sidebar */}
      <Sidebar
        user={user}
        currentView={currentView}
        onSelectView={setCurrentView}
        sessions={sessions}
        sessionsLoading={sessionsLoading}
        sessionsError={sessionsError}
        sessionsHasMore={sessionsHasMore}
        sessionsLoadingMore={sessionsLoadingMore}
        onRetrySessions={retrySessionList}
        onLoadMoreSessions={loadMoreSessions}
        activeSessionId={activeSessionId}
        onSelectSession={(id) => selectSession(id)}
        onNewSession={handleNewSession}
        onRenameSession={handleRenameSession}
        onDeleteSession={handleDeleteSession}
        onUpdateSessionWorkspace={handleUpdateSessionWorkspace}
        usage={usage}
        onOpenUsageModal={() => setUsageModalOpen(true)}
        onOpenNotesModal={() => setNotesModalOpen(true)}
        onOpenSettingsModal={() => setSettingsModalOpen(true)}
        onLogout={handleLogout}
        mobileOpen={sidebarMobileOpen}
        onCloseMobile={() => setSidebarMobileOpen(false)}
      />

      {/* Main Study Workspace */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64 h-full">
        {/* Top App Header */}
        <AppHeader
          user={user}
          currentView={currentView}
          onSelectView={setCurrentView}
          activeModel={activeModel}
          onSelectModel={setActiveModel}
          activeLength={activeLength}
          onSelectLength={setActiveLength}
          usage={usage}
          onOpenUsageModal={() => setUsageModalOpen(true)}
          onOpenSettingsModal={() => setSettingsModalOpen(true)}
          onOpenNotesModal={() => setNotesModalOpen(true)}
          onToggleSidebar={() => setSidebarMobileOpen(!sidebarMobileOpen)}
          onLogout={handleLogout}
        />

        {/* View 1: Student Overview Dashboard (Aptivus Inspired) */}
        {currentView === 'overview' ? (
          <StudentDashboard
            user={user}
            sessions={sessions}
            usage={usage}
            memoryData={memoryData}
            profileStats={profileStats}
            onStartStudyPrompt={handleStartStudyPrompt}
            onSelectSession={(id) => selectSession(id)}
            onNewSession={handleNewSession}
            onOpenUsageModal={() => setUsageModalOpen(true)}
            onOpenNotesModal={() => setNotesModalOpen(true)}
          />
        ) : (
          /* View 2: Focused Chat Workspace */
          <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
            <main className="flex-1 overflow-y-auto scrollbar-thin">
              {historyLoading ? (
                <div className="h-full flex items-center justify-center text-sm text-[var(--text-muted)]">
                  Restoring your chat…
                </div>
              ) : historyError ? (
                <div className="h-full flex flex-col items-center justify-center gap-3 px-6 text-center">
                  <p className="text-sm text-rose-500">This chat could not be restored: {historyError}</p>
                  {activeSessionId && (
                    <button
                      onClick={() => loadSessionIntoView(activeSessionId, activeSessionTitle)}
                      className="rounded-lg px-3 py-2 text-xs font-semibold bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] cursor-pointer"
                    >Retry loading chat</button>
                  )}
                </div>
              ) : messages.length === 0 ? (
                <EmptyState
                  userName={user?.first_name}
                  usage={usage}
                  onOpenUsageModal={() => setUsageModalOpen(true)}
                  onSelectPrompt={(prompt) => handleSendMessage(prompt)}
                />
              ) : (
                <MessageList
                  messages={messages}
                  isThinking={isThinking}
                  user={user}
                  chatWidth={preferences.chatWidth}
                  onSaveNote={handleSaveNote}
                />
              )}
            </main>

            {/* Bottom Input Composer */}
            <Composer
              inputMessage={inputMessage}
              onInputChange={setInputMessage}
              onSendMessage={() => handleSendMessage()}
              onStop={handleStopGeneration}
              isThinking={isThinking}
              disabled={historyLoading || Boolean(historyError)}
              disabledMessage={historyLoading ? 'Restoring this chat…' : historyError ? 'Retry loading this chat before sending.' : undefined}
              usage={usage}
              activeModel={activeModel}
              onSelectModel={setActiveModel}
              activeLength={activeLength}
              onSelectLength={setActiveLength}
              chatWidth={preferences.chatWidth}
              onOpenUsageModal={() => setUsageModalOpen(true)}
            />
          </div>
        )}
      </div>

      {/* Modals */}
      <UsageModal
        isOpen={usageModalOpen}
        onClose={() => setUsageModalOpen(false)}
        usage={usage}
      />

      <NotesModal
        isOpen={notesModalOpen}
        onClose={() => setNotesModalOpen(false)}
        memoryData={memoryData}
      />

      <SettingsModal
        isOpen={settingsModalOpen}
        onClose={() => setSettingsModalOpen(false)}
        user={user}
        preferences={preferences}
        onUpdatePreferences={handleUpdatePreferences}
        sessions={sessions}
        usage={usage}
        memoryData={memoryData}
        onLogout={handleLogout}
      />
    </div>
  )
}
