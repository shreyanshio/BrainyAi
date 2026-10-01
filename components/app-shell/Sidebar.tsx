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
  LogOut,
  ChevronRight,
} from 'lucide-react'
import { ChatSession, UsageStatus, User } from '@/types/api'

interface SidebarProps {
  user: User
  sessions: ChatSession[]
  activeSessionId: string | null
  onSelectSession: (sessionId: string) => void
  onNewSession: () => void
  onRenameSession: (sessionId: string, newTitle: string) => void
  onDeleteSession: (sessionId: string) => void
  usage: UsageStatus | null
  onOpenUsageModal: () => void
  onOpenNotesModal: () => void
  onLogout: () => void
  mobileOpen: boolean
  onCloseMobile: () => void
}

export function Sidebar({
  user,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onRenameSession,
  onDeleteSession,
  usage,
  onOpenUsageModal,
  onOpenNotesModal,
  onLogout,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  // Filter sessions by search query
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions
    const q = searchQuery.toLowerCase()
    return sessions.filter((s) => s.title.toLowerCase().includes(q))
  }, [sessions, searchQuery])

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

    filteredSessions.forEach((sess) => {
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
  }, [filteredSessions])

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
        <div className="px-2.5 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
          {title}
        </div>
        <div className="space-y-0.5">
          {items.map((sess) => {
            const isSelected = activeSessionId === sess.id
            const isEditing = editingSessionId === sess.id

            if (isEditing) {
              return (
                <form
                  key={sess.id}
                  onSubmit={(e) => saveEdit(sess.id, e)}
                  className="flex items-center gap-1.5 px-2 py-1 bg-zinc-800 rounded-lg text-xs"
                >
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    autoFocus
                    className="flex-1 bg-transparent text-white focus:outline-none text-xs"
                  />
                  <button
                    type="submit"
                    className="p-1 hover:text-emerald-400 text-zinc-300 transition"
                    title="Save"
                  >
                    <Check size={12} />
                  </button>
                  <button
                    type="button"
                    onClick={cancelEdit}
                    className="p-1 hover:text-rose-400 text-zinc-400 transition"
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
                  onCloseMobile()
                }}
                className={`group flex items-center justify-between px-2.5 py-2 rounded-lg text-xs cursor-pointer transition ${
                  isSelected
                    ? 'bg-zinc-800/90 text-white font-medium'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center gap-2 truncate pr-2">
                  <MessageSquare size={13} className={isSelected ? 'text-zinc-200' : 'text-zinc-500'} />
                  <span className="truncate">{sess.title || 'Untitled Session'}</span>
                </div>

                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => startEditing(sess, e)}
                    className="p-1 hover:text-zinc-200 text-zinc-500 rounded"
                    title="Rename session"
                  >
                    <Edit2 size={11} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteSession(sess.id)
                    }}
                    className="p-1 hover:text-rose-400 text-zinc-500 rounded"
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
        className={`fixed top-0 bottom-0 left-0 w-64 bg-[#090a0f] border-r border-zinc-800/80 flex flex-col z-50 transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Top Brand & New Chat */}
        <div className="p-3.5 border-b border-zinc-800/60 space-y-3">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-white text-xs">
                B
              </div>
              <span className="font-semibold text-sm tracking-tight text-white">Brainy</span>
            </div>
            <button
              onClick={onCloseMobile}
              className="p-1 text-zinc-400 hover:text-white rounded-lg lg:hidden"
              aria-label="Close sidebar"
            >
              <X size={16} />
            </button>
          </div>

          <button
            onClick={() => {
              onNewSession()
              onCloseMobile()
            }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-zinc-100 hover:bg-white text-zinc-900 text-xs font-semibold shadow-sm transition"
          >
            <Plus size={14} />
            <span>New Study Session</span>
          </button>

          {/* Search Box */}
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-2.5 text-zinc-500" />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-700"
            />
          </div>
        </div>

        {/* Chat History List */}
        <div className="flex-1 overflow-y-auto px-2 py-3 scrollbar-thin">
          {filteredSessions.length === 0 ? (
            <div className="text-center py-8 text-xs text-zinc-500">
              {searchQuery ? 'No matching study chats' : 'No study sessions yet'}
            </div>
          ) : (
            <>
              {renderGroup('Today', groupedSessions.today)}
              {renderGroup('Yesterday', groupedSessions.yesterday)}
              {renderGroup('Previous 7 Days', groupedSessions.prev7Days)}
              {renderGroup('Older', groupedSessions.older)}
            </>
          )}
        </div>

        {/* Bottom Quota & User Profile */}
        <div className="p-3 border-t border-zinc-800/80 bg-[#0c0d13] space-y-2.5">
          {/* 8-Hour Quota Meter */}
          <div
            onClick={onOpenUsageModal}
            className="p-2.5 rounded-lg bg-zinc-900/80 border border-zinc-800 cursor-pointer hover:border-zinc-700 transition"
          >
            <div className="flex items-center justify-between text-[11px] mb-1.5">
              <span className="text-zinc-400 font-medium">8-Hour Quota</span>
              <span className="text-zinc-200 font-mono">
                {used} / {limit}
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  progressPercent >= 100
                    ? 'bg-rose-500'
                    : progressPercent >= 80
                    ? 'bg-amber-400'
                    : 'bg-emerald-500'
                }`}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Quick Actions (Saved Notes, Sign Out) */}
          <div className="flex items-center justify-between text-xs pt-1">
            <button
              onClick={onOpenNotesModal}
              className="flex items-center gap-1.5 text-zinc-400 hover:text-white transition py-1"
            >
              <BookMarked size={13} />
              <span>Saved Notes</span>
            </button>

            <button
              onClick={onLogout}
              className="flex items-center gap-1.5 text-zinc-400 hover:text-rose-400 transition py-1"
              title="Sign Out"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
