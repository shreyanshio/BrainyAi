'use client'

import React, { useState, useEffect, useCallback } from 'react'
import {
  checkAuth,
  checkAuthSessionParam,
  createSession,
  deleteSession,
  fetchSessionHistory,
  fetchSessions,
  fetchUsage,
  fetchUserMemory,
  loginWithTelegramInitData,
  logoutUser,
  renameSession,
  saveUserMemoryNote,
  sendChatMessage,
} from '@/lib/api'
import {
  AnswerLength,
  ChatMessage,
  ChatSession,
  UsageStatus,
  User,
  UserMemoryData,
} from '@/types/api'
import { LoginView } from '@/components/auth/LoginView'
import { AppHeader } from '@/components/app-shell/AppHeader'
import { Sidebar } from '@/components/app-shell/Sidebar'
import { EmptyState } from '@/components/chat/EmptyState'
import { MessageList } from '@/components/chat/MessageList'
import { Composer } from '@/components/chat/Composer'
import { UsageModal } from '@/components/modals/UsageModal'
import { NotesModal } from '@/components/modals/NotesModal'

export default function BrainyApp() {
  // Auth state
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)

  // Chat & Session state
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeSessionTitle, setActiveSessionTitle] = useState('New Study Session')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isThinking, setIsThinking] = useState(false)

  // Capabilities & Preferences state
  const [activeModel, setActiveModel] = useState('brainy-balanced')
  const [activeLength, setActiveLength] = useState<AnswerLength>('medium')

  // Global 30 msg / 8h Quota state
  const [usage, setUsage] = useState<UsageStatus | null>(null)
  const [memoryData, setMemoryData] = useState<UserMemoryData | null>(null)

  // Modal & Drawer state
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false)
  const [usageModalOpen, setUsageModalOpen] = useState(false)
  const [notesModalOpen, setNotesModalOpen] = useState(false)

  // ── Initial Auth & Bootstrap ──────────────────────────────
  const loadInitialData = useCallback(async () => {
    try {
      const [sessList, usageStatus, mem] = await Promise.all([
        fetchSessions().catch(() => []),
        fetchUsage().catch(() => null),
        fetchUserMemory().catch(() => null),
      ])

      setSessions(sessList)
      if (usageStatus) setUsage(usageStatus)
      if (mem) setMemoryData(mem)

      if (sessList.length > 0) {
        await selectSession(sessList[0].id, sessList[0].title)
      }
    } catch (err) {
      console.error('Failed to load initial data:', err)
    }
  }, [])

  useEffect(() => {
    const authenticate = async () => {
      setAuthLoading(true)
      try {
        // 1. Check URL query params for Telegram handshake redirect (?auth_session=...)
        if (typeof window !== 'undefined') {
          const urlParams = new URLSearchParams(window.location.search)
          const authSessionParam = urlParams.get('auth_session')
          if (authSessionParam) {
            const statusRes = await checkAuthSessionParam(authSessionParam)
            if (statusRes.status === 'authenticated' && statusRes.user) {
              setUser(statusRes.user)
              window.history.replaceState({}, document.title, window.location.pathname)
              await loadInitialData()
              setAuthLoading(false)
              return
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
            await loadInitialData()
            setAuthLoading(false)
            return
          }
        }

        // 3. Check existing browser session cookie
        const currentUser = await checkAuth()
        if (currentUser) {
          setUser(currentUser)
          await loadInitialData()
        }
      } catch (err) {
        console.warn('Auth check skipped:', err)
      } finally {
        setAuthLoading(false)
      }
    }

    authenticate()
  }, [loadInitialData])

  // ── Session Operations ────────────────────────────────────
  const selectSession = async (sessionId: string, title?: string) => {
    setActiveSessionId(sessionId)
    if (title) setActiveSessionTitle(title)
    setSidebarMobileOpen(false)

    try {
      const data = await fetchSessionHistory(sessionId)
      setMessages(data.messages || [])
      if (data.usage) setUsage(data.usage)
      if (data.title) setActiveSessionTitle(data.title)
    } catch (err) {
      console.error('Failed to load session history:', err)
    }
  }

  const handleNewSession = () => {
    setActiveSessionId(null)
    setActiveSessionTitle('New Study Session')
    setMessages([])
    setInputMessage('')
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

  // ── Message Operations ────────────────────────────────────
  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = (customPrompt || inputMessage).trim()
    if (!textToSend || isThinking) return

    // Immediately add user message
    const userMsg: ChatMessage = {
      role: 'user',
      content: textToSend,
      created_at: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMsg])
    if (!customPrompt) setInputMessage('')
    setIsThinking(true)

    try {
      const res = await sendChatMessage({
        session_id: activeSessionId,
        message: textToSend,
        model: activeModel,
        answer_length: activeLength,
      })

      // If backend created a new session
      if (res.session_id && res.session_id !== activeSessionId) {
        setActiveSessionId(res.session_id)
        if (res.new_title) setActiveSessionTitle(res.new_title)
        const updatedSessions = await fetchSessions().catch(() => [])
        setSessions(updatedSessions)
      } else if (res.new_title) {
        setActiveSessionTitle(res.new_title)
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSessionId ? { ...s, title: res.new_title || s.title } : s
          )
        )
      }

      // Append assistant reply
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: res.content || res.response || 'No response generated.',
        created_at: new Date().toISOString(),
        model: res.model,
        answer_length: res.answer_length,
      }

      setMessages((prev) => [...prev, assistantMsg])
      if (res.usage) setUsage(res.usage)
    } catch (err: any) {
      console.error('Failed to send message:', err)

      // Handle 429 quota exhaustion specifically
      if (err?.status === 429) {
        const refreshedUsage = await fetchUsage().catch(() => null)
        if (refreshedUsage) setUsage(refreshedUsage)
        setUsageModalOpen(true)

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `⚠️ **8-Hour Quota Reached**: You have reached the limit of 30 messages for this 8-hour window. Please wait for the window to reset to continue studying.`,
            created_at: new Date().toISOString(),
          },
        ])
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `⚠️ ${err?.message || 'Could not generate an answer. Please check connection and retry.'}`,
            created_at: new Date().toISOString(),
          },
        ])
      }
    } finally {
      setIsThinking(false)
    }
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

  const handleLogout = async () => {
    await logoutUser()
    setUser(null)
    setSessions([])
    setActiveSessionId(null)
    setMessages([])
    setUsage(null)
  }

  // Loading Screen
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#090a0f] flex flex-col items-center justify-center gap-3 text-zinc-400">
        <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-white text-sm animate-pulse">
          B
        </div>
        <p className="text-xs text-zinc-500 font-medium">Loading Brainy...</p>
      </div>
    )
  }

  // Unauthenticated: Show Clean SaaS Login View
  if (!user) {
    return (
      <LoginView
        onLoginSuccess={(loggedInUser) => {
          setUser(loggedInUser)
          loadInitialData()
        }}
      />
    )
  }

  // Authenticated: Full Study Companion App Shell
  return (
    <div className="flex h-screen h-[100dvh] overflow-hidden bg-[#090a0f] text-zinc-100 font-sans antialiased">
      {/* Left Sidebar */}
      <Sidebar
        user={user}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={(id) => selectSession(id)}
        onNewSession={handleNewSession}
        onRenameSession={handleRenameSession}
        onDeleteSession={handleDeleteSession}
        usage={usage}
        onOpenUsageModal={() => setUsageModalOpen(true)}
        onOpenNotesModal={() => setNotesModalOpen(true)}
        onLogout={handleLogout}
        mobileOpen={sidebarMobileOpen}
        onCloseMobile={() => setSidebarMobileOpen(false)}
      />

      {/* Main Study Workspace */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64 h-full">
        {/* Top App Header */}
        <AppHeader
          user={user}
          activeModel={activeModel}
          onSelectModel={setActiveModel}
          activeLength={activeLength}
          onSelectLength={setActiveLength}
          usage={usage}
          onOpenUsageModal={() => setUsageModalOpen(true)}
          onToggleSidebar={() => setSidebarMobileOpen(!sidebarMobileOpen)}
          onLogout={handleLogout}
        />

        {/* Chat Conversation Scroll Area */}
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {messages.length === 0 ? (
            <EmptyState onSelectPrompt={(prompt) => handleSendMessage(prompt)} />
          ) : (
            <MessageList
              messages={messages}
              isThinking={isThinking}
              user={user}
              onSaveNote={handleSaveNote}
            />
          )}
        </main>

        {/* Bottom Input Composer */}
        <Composer
          inputMessage={inputMessage}
          onInputChange={setInputMessage}
          onSendMessage={() => handleSendMessage()}
          isThinking={isThinking}
          usage={usage}
          activeModel={activeModel}
          onSelectModel={setActiveModel}
          activeLength={activeLength}
          onSelectLength={setActiveLength}
          onOpenUsageModal={() => setUsageModalOpen(true)}
        />
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
    </div>
  )
}
