'use client'

import React, { useState } from 'react'
import {
  Menu,
  ChevronDown,
  Clock,
  Sparkles,
  Zap,
  Code2,
  BookOpen,
  LogOut,
  Sliders,
  LayoutDashboard,
  MessageSquare,
  BookMarked,
} from 'lucide-react'
import { AnswerLength, UsageStatus, User } from '@/types/api'
import { CAPABILITY_MODELS } from '@/lib/constants'

interface AppHeaderProps {
  user: User
  currentView: 'overview' | 'chat'
  onSelectView: (view: 'overview' | 'chat') => void
  activeModel: string
  onSelectModel: (modelId: string) => void
  activeLength: AnswerLength
  onSelectLength: (length: AnswerLength) => void
  usage: UsageStatus | null
  onOpenUsageModal: () => void
  onOpenSettingsModal: () => void
  onOpenNotesModal?: () => void
  onToggleSidebar: () => void
  onLogout: () => void
}

const getModelIcon = (id: string) => {
  switch (id) {
    case 'brainy-fast':
      return <Zap size={13} className="text-amber-500" />
    case 'brainy-reasoning':
      return <Sparkles size={13} className="text-emerald-500" />
    case 'brainy-coding':
      return <Code2 size={13} className="text-teal-500" />
    case 'brainy-exam':
      return <BookOpen size={13} className="text-blue-500" />
    default:
      return <Sparkles size={13} className="text-emerald-500" />
  }
}

export function AppHeader({
  user,
  currentView,
  onSelectView,
  activeModel,
  onSelectModel,
  usage,
  onOpenUsageModal,
  onOpenSettingsModal,
  onOpenNotesModal,
  onToggleSidebar,
  onLogout,
}: AppHeaderProps) {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [userDropdownOpen, setUserDropdownOpen] = useState(false)

  const currentModel =
    CAPABILITY_MODELS.find((m) => m.id === activeModel) || CAPABILITY_MODELS[0]

  const remaining = usage ? usage.remaining : 30
  const isNearLimit = remaining <= 5
  const isExhausted = remaining === 0

  return (
    <header className="h-14 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]/80 backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between z-20 flex-shrink-0 transition-colors">
      {/* Left: Mobile menu toggle, Logo & Model */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition lg:hidden cursor-pointer"
          aria-label="Toggle sidebar"
        >
          <Menu size={18} />
        </button>

        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center font-bold text-xs shadow-xs">
            B
          </div>
          <span className="font-bold text-sm tracking-tight text-[var(--text-primary)] hidden sm:inline">
            Brainy
          </span>
        </div>

        {/* Capability Model Selector Dropdown */}
        {currentView === 'chat' && (
          <div className="relative ml-1 sm:ml-2">
            <button
              onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] transition cursor-pointer shadow-2xs"
            >
              {getModelIcon(currentModel.id)}
              <span className="font-medium hidden md:inline">{currentModel.name}</span>
              <ChevronDown size={11} className="text-[var(--text-muted)]" />
            </button>

            {modelDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setModelDropdownOpen(false)}
                />
                <div className="absolute left-0 top-full mt-2 w-64 rounded-2xl glass-panel p-1.5 z-40 space-y-1 shadow-2xl">
                  <div className="px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
                    Capability Models
                  </div>
                  {CAPABILITY_MODELS.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        onSelectModel(m.id)
                        setModelDropdownOpen(false)
                      }}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-start gap-2.5 transition cursor-pointer ${
                        activeModel === m.id
                          ? 'bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-bold'
                          : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface-hover)] hover:text-[var(--text-primary)]'
                      }`}
                    >
                      <div className="mt-0.5">{getModelIcon(m.id)}</div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold">{m.name}</span>
                          {m.badge && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] bg-[var(--bg-surface-elevated)] text-[var(--text-muted)] font-mono">
                              {m.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)] mt-0.5 leading-snug">
                          {m.tagline}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Center: Segmented Floating Capsule Toggle (Inspired by reference image) */}
      <div className="flex items-center p-0.5 rounded-full bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs shadow-2xs">
        <button
          onClick={() => onSelectView('chat')}
          className={`flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs transition cursor-pointer ${
            currentView === 'chat'
              ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <MessageSquare size={13} />
          <span>Chats</span>
        </button>

        <button
          onClick={() => onSelectView('overview')}
          className={`flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs transition cursor-pointer ${
            currentView === 'overview'
              ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <LayoutDashboard size={13} />
          <span>Overview</span>
        </button>

        {onOpenNotesModal && (
          <button
            onClick={onOpenNotesModal}
            className="hidden sm:flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition cursor-pointer"
          >
            <BookMarked size={13} />
            <span>Notes</span>
          </button>
        )}
      </div>

      {/* Right: 5h Quota Capsule, Settings Button, and User Avatar */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Quota Indicator Button */}
        <button
          onClick={onOpenUsageModal}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition cursor-pointer ${
            isExhausted
              ? 'bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-400'
              : isNearLimit
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400'
              : 'bg-[var(--bg-surface-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
          }`}
          title={usage ? `Quota: ${usage.remaining} of ${usage.limit} left` : 'Quota info'}
        >
          <Clock size={12} className={isExhausted ? 'text-rose-500' : isNearLimit ? 'text-amber-500' : 'text-emerald-500'} />
          <span>
            {usage ? `${remaining}/${usage.limit}` : '30/30'}
          </span>
          <span className="hidden lg:inline text-[var(--text-muted)] font-normal">left</span>
        </button>

        {/* Settings Button */}
        <button
          onClick={onOpenSettingsModal}
          className="p-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition cursor-pointer"
          title="Customize Workspace"
          aria-label="Open settings"
        >
          <Sliders size={14} />
        </button>

        {/* User Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex items-center gap-1 p-0.5 rounded-full hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
            aria-label="User account menu"
          >
            <div className="w-7 h-7 rounded-full bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center text-xs font-bold shadow-xs">
              {user.first_name ? user.first_name[0].toUpperCase() : 'U'}
            </div>
            <ChevronDown size={11} className="text-[var(--text-muted)] hidden sm:block" />
          </button>

          {userDropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setUserDropdownOpen(false)}
              />
              <div className="absolute right-0 top-full mt-2 w-52 rounded-2xl glass-panel p-1.5 z-40 space-y-1 text-xs shadow-2xl">
                <div className="px-3 py-2 border-b border-[var(--border-subtle)]">
                  <div className="font-bold text-[var(--text-primary)] truncate">{user.first_name}</div>
                  {user.username && (
                    <div className="text-[11px] text-[var(--text-muted)] truncate">@{user.username}</div>
                  )}
                </div>

                <button
                  onClick={() => {
                    setUserDropdownOpen(false)
                    onOpenSettingsModal()
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-hover)] transition cursor-pointer"
                >
                  <Sliders size={13} />
                  <span>Customize Workspace</span>
                </button>

                <button
                  onClick={() => {
                    setUserDropdownOpen(false)
                    onOpenUsageModal()
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-hover)] transition cursor-pointer"
                >
                  <Clock size={13} />
                  <span>5-Hour Quota Details</span>
                </button>

                {user.role === 'admin' && (
                  <a
                    href="/admin"
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-amber-500 hover:bg-amber-500/10 transition cursor-pointer font-semibold"
                  >
                    <LayoutDashboard size={13} />
                    <span>Admin Control Panel</span>
                  </a>
                )}

                <div className="border-t border-[var(--border-subtle)] my-1" />

                <button
                  onClick={() => {
                    setUserDropdownOpen(false)
                    onLogout()
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition cursor-pointer"
                >
                  <LogOut size={13} />
                  <span>Sign Out</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
