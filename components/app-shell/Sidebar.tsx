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
  Bookmark,
  Pin,
  Archive,
  LogOut,
  Sliders,
  LayoutDashboard,
  BookMarked,
  FileText,
} from 'lucide-react'
import { ChatSession, UsageStatus, User } from '@/types/api'

interface SidebarProps {
  user: User
  currentView: 'overview' | 'chat' | 'pdf'
  onSelectView: (view: 'overview' | 'chat' | 'pdf') => void
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
  const [searchActive, setSearchActive] = useState(false)
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
                className={`group flex items-start justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition ${
                  isSelected
                    ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-medium shadow-xs'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)]'
                }`}
              >
                <div className="flex-1 min-w-0 pr-1.5">
                  <div className="flex items-center gap-2">
                    {sess.is_pinned && <Pin size={10} className="text-sky-500 flex-shrink-0" />}
                    {sess.is_saved && <Bookmark size={10} className="text-amber-500 flex-shrink-0" fill="currentColor" />}
                    <span className="truncate font-medium">{sess.title || 'Untitled Session'}</span>
                  </div>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5 truncate">
                    {sess.created_at ? new Date(sess.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : 'Recent study'}
                  </p>
                </div>

                <div className="flex items-center gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity flex-shrink-0 pt-0.5">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onUpdateSessionWorkspace(sess.id, { is_saved: !sess.is_saved })
                    }}
                    className={`p-1.5 min-w-[26px] min-h-[26px] flex items-center justify-center rounded cursor-pointer ${
                      sess.is_saved ? 'text-amber-500' : 'text-[var(--text-muted)] hover:text-amber-500'
                    }`}
                    title={sess.is_saved ? 'Remove from Saved' : 'Save chat'}
                    aria-label={sess.is_saved ? 'Remove from Saved' : 'Save chat'}
                  >
                    <Bookmark size={12} fill={sess.is_saved ? 'currentColor' : 'none'} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onUpdateSessionWorkspace(sess.id, { is_pinned: !sess.is_pinned })
                    }}
                    className={`p-1.5 min-w-[26px] min-h-[26px] flex items-center justify-center rounded cursor-pointer ${
                      sess.is_pinned ? 'text-sky-500' : 'text-[var(--text-muted)] hover:text-sky-500'
                    }`}
                    title={sess.is_pinned ? 'Unpin chat' : 'Pin chat'}
                    aria-label={sess.is_pinned ? 'Unpin chat' : 'Pin chat'}
                  >
                    <Pin size={12} />
                  </button>
                  <button
                    onClick={(e) => startEditing(sess, e)}
                    className="p-1.5 min-w-[26px] min-h-[26px] flex items-center justify-center hover:text-[var(--text-primary)] text-[var(--text-muted)] rounded cursor-pointer"
                    title="Rename session"
                    aria-label="Rename session"
                  >
                    <Edit2 size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteSession(sess.id)
                    }}
                    className="p-1.5 min-w-[26px] min-h-[26px] flex items-center justify-center hover:text-rose-500 text-[var(--text-muted)] rounded cursor-pointer"
                    title="Delete session"
                    aria-label="Delete session"
                  >
                    <Trash2 size={12} />
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
        className={`fixed top-0 bottom-0 left-0 z-40 w-64 max-w-[85vw] border-r border-[var(--border-subtle)] bg-[var(--bg-surface)]/95 backdrop-blur-xl flex flex-col transition-transform duration-200 lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Top Header & Core Actions (Matching reference image) */}
        <div className="p-3.5 space-y-2 border-b border-[var(--border-subtle)]">
          {/* Mobile drawer header with close button */}
          <div className="flex items-center justify-between lg:hidden pb-1">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
              Navigation
            </span>
            <button
              onClick={onCloseMobile}
              className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] cursor-pointer"
              aria-label="Close navigation drawer"
            >
              <X size={16} />
            </button>
          </div>

          {/* + New Chat Button */}
          <button
            onClick={() => {
              onNewSession()
              onSelectView('chat')
              onCloseMobile()
            }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer border border-[var(--border-subtle)]"
          >
            <Plus size={15} className="text-[var(--text-primary)]" />
            <span>New chat</span>
          </button>

          {/* Quick Actions Bar: Search & Customize */}
          <div className="grid grid-cols-2 gap-1.5 pt-0.5">
            <button
              onClick={() => setSearchActive(!searchActive)}
              className={`flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs transition cursor-pointer border border-transparent ${
                searchActive
                  ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] border-[var(--border-subtle)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)]'
              }`}
            >
              <Search size={13} />
              <span>Search</span>
            </button>

            <button
              onClick={onOpenSettingsModal}
              className="flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
            >
              <Sliders size={13} />
              <span>Customize</span>
            </button>
          </div>

          {/* Search Input Box when expanded */}
          {searchActive && (
            <div className="relative pt-1 animate-fade-in">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter recent chats..."
                autoFocus
                className="w-full bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] rounded-xl px-2.5 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-2.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Primary Navigation Section */}
        <div className="px-3 py-2 space-y-0.5 border-b border-[var(--border-subtle)] text-xs">
          <button
            onClick={() => {
              onSelectView('chat')
              onCloseMobile()
            }}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl transition cursor-pointer ${
              currentView === 'chat'
                ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-semibold shadow-xs'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)]'
            }`}
          >
            <MessageSquare size={14} className={currentView === 'chat' ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'} />
            <span>Chats</span>
          </button>

          <button
            onClick={() => {
              onSelectView('overview')
              onCloseMobile()
            }}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl transition cursor-pointer ${
              currentView === 'overview'
                ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-semibold shadow-xs'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)]'
            }`}
          >
            <LayoutDashboard size={14} className={currentView === 'overview' ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'} />
            <span>Overview</span>
          </button>

          <button
            onClick={() => {
              onSelectView('pdf')
              onCloseMobile()
            }}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl transition cursor-pointer ${
              currentView === 'pdf'
                ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-semibold shadow-xs'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)]'
            }`}
          >
            <FileText size={14} className={currentView === 'pdf' ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'} />
            <span>PDF Studio</span>
          </button>

          <button
            onClick={() => {
              onOpenNotesModal()
              onCloseMobile()
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)] transition cursor-pointer"
          >
            <BookMarked size={14} className="text-[var(--text-muted)]" />
            <span>Saved Notes</span>
          </button>
        </div>

        {/* Workspace Filter Pills: All / Saved / Pinned */}
        <div className="px-3 pt-3 pb-1 flex items-center gap-1 text-[10px]">
          {(['recent', 'pinned', 'saved', 'archived'] as const).map((w) => (
            <button
              key={w}
              onClick={() => setWorkspace(w)}
              className={`px-2 py-0.5 rounded-lg capitalize transition cursor-pointer ${
                workspace === w
                  ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-bold'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              }`}
            >
              {w}
            </button>
          ))}
        </div>

        {/* RECENTS Session List */}
        <div className="flex-1 overflow-y-auto p-3 scrollbar-thin">
          <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] px-1 mb-2">
            Recents
          </div>

          {sessionsLoading && sessions.length === 0 ? (
            <div className="text-center py-6 text-xs text-[var(--text-muted)]">
              Loading study history…
            </div>
          ) : sessionsError && sessions.length === 0 ? (
            <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-center text-xs text-rose-500">
              <p>{sessionsError}</p>
              <button onClick={onRetrySessions} className="mt-2 underline font-semibold cursor-pointer">
                Retry loading
              </button>
            </div>
          ) : workspaceSessions.length === 0 ? (
            <div className="text-center py-6 text-xs text-[var(--text-muted)]">
              {searchQuery ? 'No matching chats found' : `No ${workspace} chats`}
            </div>
          ) : (
            <>
              {renderGroup('Today', groupedSessions.today)}
              {renderGroup('Yesterday', groupedSessions.yesterday)}
              {renderGroup('Previous 7 Days', groupedSessions.prev7Days)}
              {renderGroup('Older', groupedSessions.older)}
            </>
          )}

          {sessionsHasMore && (
            <button
              onClick={onLoadMoreSessions}
              disabled={sessionsLoadingMore}
              className="w-full mt-2 rounded-xl py-2 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] disabled:opacity-50 cursor-pointer"
            >
              {sessionsLoadingMore ? 'Loading older chats…' : 'Load older chats'}
            </button>
          )}
        </div>

        {/* Bottom User Profile Section (Matching reference image) */}
        <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)]/60">
          {/* User Card */}
          <div className="flex items-center justify-between p-2 rounded-xl hover:bg-[var(--bg-surface-hover)] transition">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-full bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center text-xs font-bold shadow-xs flex-shrink-0">
                {user.first_name ? user.first_name[0].toUpperCase() : 'U'}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-[var(--text-primary)] truncate">
                  {user.first_name}
                </div>
                <div className="text-[10px] text-[var(--text-muted)] truncate">
                  {user.username ? `@${user.username}` : 'Free Tier'}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={onOpenSettingsModal}
                className="p-2 min-h-[36px] min-w-[36px] flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] transition rounded-lg hover:bg-[var(--bg-surface-elevated)] cursor-pointer"
                title="Workspace settings"
                aria-label="Workspace settings"
              >
                <Sliders size={14} />
              </button>

              <button
                onClick={onLogout}
                className="p-2 min-h-[36px] min-w-[36px] flex items-center justify-center text-[var(--text-muted)] hover:text-rose-500 transition rounded-lg hover:bg-[var(--bg-surface-elevated)] cursor-pointer"
                title="Sign Out"
                aria-label="Sign Out"
              >
                <LogOut size={14} />
              </button>
            </div>
          </div>

          {/* Quota Progress Line */}
          <div
            onClick={onOpenUsageModal}
            className="mt-2 px-2 py-1.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] cursor-pointer hover:border-[var(--border-strong)] transition"
          >
            <div className="flex items-center justify-between text-[10px] mb-1">
              <span className="text-[var(--text-muted)]">5h Study Quota</span>
              <span className="font-mono font-bold text-[var(--text-primary)]">
                {used} / {limit}
              </span>
            </div>
            <div className="w-full h-1 rounded-full bg-[var(--bg-surface-elevated)] overflow-hidden">
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
        </div>
      </aside>
    </>
  )
}
