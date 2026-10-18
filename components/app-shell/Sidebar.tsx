'use client'

import React, { useState, useMemo } from 'react'
import {
  Plus,
  Search,
  MessageSquare,
  Trash2,
  Edit2,
  Check,
  X,
  Clock,
  BookMarked,
  Bookmark,
  Pin,
  Archive,
  LogOut,
  Sliders,
  LayoutDashboard,
} from 'lucide-react'
import { ChatSession, UsageStatus, User } from '@/types/api'

interface SidebarProps {
  user: User
  currentView: 'overview' | 'chat'
  onSelectView: (view: 'overview' | 'chat') => void
  sessions: ChatSession[]
  activeSessionId: string | null
  onSelectSession: (sessionId: string) => void
  sessionsLoading: boolean
  sessionsError: string | null
  sessionsHasMore: boolean
  sessionsLoadingMore: boolean
  onRetrySessions: () => void
  onLoadMoreSessions: () => void
  onNewSession: () => void
  onRenameSession: (sessionId: string, newTitle: string) => void
  onDeleteSession: (sessionId: string) => void
  onUpdateSessionWorkspace: (sessionId: string, changes: { is_saved?: boolean; is_pinned?: boolean; is_archived?: boolean }) => void
  usage: UsageStatus | null
  onOpenUsageModal: () => void
  onOpenNotesModal: () => void
  onOpenSettingsModal: () => void
  onLogout: () => void
  mobileOpen: boolean
  onCloseMobile: () => void
}

export function Sidebar({
  user,
  currentView,
  onSelectView,
  sessions,
  activeSessionId,
  onSelectSession,
  sessionsLoading,
  sessionsError,
  sessionsHasMore,
  sessionsLoadingMore,
  onRetrySessions,
  onLoadMoreSessions,
  onNewSession,
  onRenameSession,
  onDeleteSession,
  onUpdateSessionWorkspace,
  usage,
  onOpenUsageModal,
  onOpenNotesModal,
  onOpenSettingsModal,
  onLogout,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [workspace, setWorkspace] = useState<'recent' | 'saved' | 'pinned' | 'archived'>('recent')

  // Filter sessions by search query
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions
    const q = searchQuery.toLowerCase()
    return sessions.filter((s) => s.title.toLowerCase().includes(q))
  }, [sessions, searchQuery])

  const workspaceSessions = useMemo(() => filteredSessions.filter((s) => {
    if (workspace === 'archived') return !!s.is_archived
    if (s.is_archived) return false
    if (workspace === 'saved') return !!s.is_saved
    if (workspace === 'pinned') return !!s.is_pinned
    return true
  }), [filteredSessions, workspace])

  // Group sessions by date
  const groupedSessions = useMemo(() => {
    const today: ChatSession[] = []
    const yesterday: ChatSession[] = []
    const prev7Days: ChatSession[] = []
    const older: ChatSession[] = []

    const now = new Date()
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    const yesterdayStart = todayStart - 86400000
    const weekStart = todayStart - 6 * 86400000

    workspaceSessions.forEach((sess) => {
      const ts = sess.created_at ? new Date(sess.created_at).getTime() : todayStart
      if (ts >= todayStart) {
        today.push(sess)
      } else if (ts >= yesterdayStart) {
        yesterday.push(sess)
      } else if (ts >= weekStart) {
        prev7Days.push(sess)
      } else {
        older.push(sess)
      }
    })

    return { today, yesterday, prev7Days, older }
  }, [workspaceSessions])

  const startEditing = (sess: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingSessionId(sess.id)
    setEditTitle(sess.title)
  }

  const saveEdit = (sessionId: string, e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (editTitle.trim()) {
      onRenameSession(sessionId, editTitle.trim())
    }
    setEditingSessionId(null)
  }

  const cancelEdit = () => {
    setEditingSessionId(null)
    setEditTitle('')
  }

  const renderGroup = (title: string, items: ChatSession[]) => {
    if (items.length === 0) return null
    return (
      <div className="mb-4">
        <div className="px-2.5 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
          {title}
        </div>
        <div className="space-y-0.5">
          {items.map((sess) => {
            const isSelected = activeSessionId === sess.id && currentView === 'chat'
            const isEditing = editingSessionId === sess.id

            if (isEditing) {
              return (
                <form
                  key={sess.id}
                  onSubmit={(e) => saveEdit(sess.id, e)}
                  className="flex items-center gap-1.5 px-2 py-1.5 bg-[var(--bg-surface-elevated)] border border-[var(--border-strong)] rounded-xl text-xs"
                >
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    autoFocus
                    className="flex-1 bg-transparent text-[var(--text-primary)] focus:outline-none text-xs"
                  />
                  <button
                    type="submit"
                    className="p-1 hover:text-emerald-500 text-[var(--text-secondary)] transition cursor-pointer"
                    title="Save"
                  >
                    <Check size={12} />
                  </button>
                  <button
                    type="button"
                    onClick={cancelEdit}
                    className="p-1 hover:text-rose-500 text-[var(--text-muted)] transition cursor-pointer"
                    title="Cancel"
                  >
                    <X size={12} />
                  </button>
                </form>
              )
            }

            return (
              <div
                key={sess.id}
                onClick={() => {
                  onSelectSession(sess.id)
                  onSelectView('chat')
                  onCloseMobile()
                }}
                className={`group flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition ${
                  isSelected
                    ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-bold shadow-xs'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)]'
                }`}
              >
                <div className="flex items-center gap-2.5 truncate pr-2">
                  <MessageSquare size={13} className={isSelected ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'} />
                  <span className="truncate">{sess.title || 'Untitled Session'}</span>
                </div>

                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => { e.stopPropagation(); onUpdateSessionWorkspace(sess.id, { is_saved: !sess.is_saved }) }}
                    className={`p-1 rounded cursor-pointer ${sess.is_saved ? 'text-amber-500' : 'text-[var(--text-muted)] hover:text-amber-500'}`}
                    title={sess.is_saved ? 'Remove from Saved' : 'Save chat'}
                  ><Bookmark size={11} fill={sess.is_saved ? 'currentColor' : 'none'} /></button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onUpdateSessionWorkspace(sess.id, { is_pinned: !sess.is_pinned }) }}
                    className={`p-1 rounded cursor-pointer ${sess.is_pinned ? 'text-sky-500' : 'text-[var(--text-muted)] hover:text-sky-500'}`}
                    title={sess.is_pinned ? 'Unpin chat' : 'Pin chat'}
                  ><Pin size={11} /></button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onUpdateSessionWorkspace(sess.id, { is_archived: !sess.is_archived }) }}
                    className="p-1 hover:text-[var(--text-primary)] text-[var(--text-muted)] rounded cursor-pointer"
                    title={sess.is_archived ? 'Restore chat' : 'Archive chat'}
                  ><Archive size={11} /></button>
                  <button
                    onClick={(e) => startEditing(sess, e)}
                    className="p-1 hover:text-[var(--text-primary)] text-[var(--text-muted)] rounded cursor-pointer"
                    title="Rename session"
                  >
                    <Edit2 size={11} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteSession(sess.id)
                    }}
                    className="p-1 hover:text-rose-500 text-[var(--text-muted)] rounded cursor-pointer"
                    title="Delete session"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const used = usage ? usage.used : 0
  const limit = usage ? usage.limit : 30
  const progressPercent = Math.min(100, Math.round((used / limit) * 100))

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 w-64 bg-[var(--bg-surface)] border-r border-[var(--border-subtle)] flex flex-col z-50 transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Top Brand & Actions */}
        <div className="p-4 border-b border-[var(--border-subtle)] space-y-3">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 flex items-center justify-center font-black text-xs">
                B
              </div>
              <span className="font-brand-display font-extrabold text-sm tracking-tight text-[var(--text-primary)] uppercase">
                Brainy
              </span>
            </div>
            <button
              onClick={onCloseMobile}
              className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] rounded-lg lg:hidden cursor-pointer"
              aria-label="Close sidebar"
            >
              <X size={16} />
            </button>
          </div>

          {/* View Switcher: Overview vs New Session */}
          <div className="space-y-1.5">
            <button
              onClick={() => {
                onSelectView('overview')
                onCloseMobile()
              }}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition cursor-pointer ${
                currentView === 'overview'
                  ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 shadow-sm'
                  : 'bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] text-[var(--text-primary)]'
              }`}
            >
              <LayoutDashboard size={14} />
              <span>Student Overview</span>
            </button>

            <button
              onClick={() => {
                onNewSession()
                onSelectView('chat')
                onCloseMobile()
              }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-xs font-semibold transition cursor-pointer"
            >
              <Plus size={14} />
              <span>New Study Chat</span>
            </button>
          </div>

          {/* Search Box */}
          <div className="relative">
            <Search size={13} className="absolute left-3 top-2.5 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Search study chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--border-strong)]"
            />
          </div>
          <div className="grid grid-cols-4 gap-1" aria-label="Chat sections">
            {(['recent', 'saved', 'pinned', 'archived'] as const).map((item) => (
              <button key={item} onClick={() => setWorkspace(item)} className={`rounded-lg py-1.5 text-[10px] font-semibold capitalize ${workspace === item ? 'bg-[var(--bg-surface-hover)] text-[var(--text-primary)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}>
                {item}
              </button>
            ))}
          </div>
        </div>

        {/* Chat History List */}
        <div className="flex-1 overflow-y-auto px-3 py-3 scrollbar-thin">
          {sessionsLoading && sessions.length === 0 ? (
            <div className="text-center py-8 text-xs text-[var(--text-muted)]">Loading your chats…</div>
          ) : sessionsError && sessions.length === 0 ? (
            <div className="text-center py-6 text-xs text-rose-500">
              <p>{sessionsError}</p>
              <button onClick={onRetrySessions} className="mt-2 underline cursor-pointer">Retry</button>
            </div>
          ) : workspaceSessions.length === 0 ? (
            <div className="text-center py-8 text-xs text-[var(--text-muted)]">
              {sessionsError
                ? <><p className="text-rose-500">{sessionsError}</p><button onClick={onRetrySessions} className="mt-2 underline cursor-pointer">Retry</button></>
                : searchQuery
                  ? (sessionsHasMore ? 'No matching chats in the loaded history' : 'No matching study chats')
                  : (sessionsHasMore ? `No loaded ${workspace} chats` : `No ${workspace} chats`)}
            </div>
          ) : (
            <>
              {renderGroup('Today', groupedSessions.today)}
              {renderGroup('Yesterday', groupedSessions.yesterday)}
              {renderGroup('Previous 7 Days', groupedSessions.prev7Days)}
              {renderGroup('Older', groupedSessions.older)}
            </>
          )}
          {sessionsError && sessions.length > 0 && (
            <div className="text-center py-2 text-[10px] text-rose-500">
              <span>{sessionsError}</span>{' '}
              <button onClick={onRetrySessions} className="underline cursor-pointer">Retry</button>
            </div>
          )}
          {sessionsHasMore && (
            <button
              onClick={onLoadMoreSessions}
              disabled={sessionsLoadingMore}
              className="w-full mt-2 rounded-lg py-2 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] disabled:opacity-50 cursor-pointer"
            >
              {sessionsLoadingMore ? 'Loading older chats…' : 'Load older chats'}
            </button>
          )}
        </div>

        {/* Bottom Quota & Navigation */}
        <div className="p-3.5 border-t border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] space-y-2.5">
          {/* 5-Hour Quota Meter */}
          <div
            onClick={onOpenUsageModal}
            className="p-2.5 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] cursor-pointer hover:border-[var(--border-strong)] transition"
          >
            <div className="flex items-center justify-between text-[11px] mb-1.5">
              <span className="text-[var(--text-muted)] font-medium">5-Hour Quota</span>
              <span className="text-[var(--text-primary)] font-mono font-bold">
                {used} / {limit}
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-[var(--bg-surface-elevated)] overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  progressPercent >= 100
                    ? 'bg-rose-500'
                    : progressPercent >= 80
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Quick Actions (Saved Notes, Settings, Sign Out) */}
          <div className="flex items-center justify-between text-xs pt-1">
            <button
              onClick={onOpenNotesModal}
              className="flex items-center gap-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition py-1 cursor-pointer font-medium"
            >
              <BookMarked size={13} />
              <span>Saved Notes</span>
            </button>

            <div className="flex items-center gap-1">
              <button
                onClick={onOpenSettingsModal}
                className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition rounded-lg hover:bg-[var(--bg-surface-hover)] cursor-pointer"
                title="Settings & Customization"
              >
                <Sliders size={14} />
              </button>

              <button
                onClick={onLogout}
                className="p-1.5 text-[var(--text-secondary)] hover:text-rose-500 transition rounded-lg hover:bg-[var(--bg-surface-hover)] cursor-pointer"
                title="Sign Out"
              >
                <LogOut size={14} />
              </button>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
