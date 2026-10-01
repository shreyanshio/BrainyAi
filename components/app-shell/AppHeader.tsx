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
  User as UserIcon,
  ShieldAlert,
} from 'lucide-react'
import { AnswerLength, ModelDefinition, UsageStatus, User } from '@/types/api'
import { CAPABILITY_MODELS, ANSWER_LENGTH_OPTIONS } from '@/lib/constants'

interface AppHeaderProps {
  user: User
  activeModel: string
  onSelectModel: (modelId: string) => void
  activeLength: AnswerLength
  onSelectLength: (length: AnswerLength) => void
  usage: UsageStatus | null
  onOpenUsageModal: () => void
  onToggleSidebar: () => void
  onLogout: () => void
}

const getModelIcon = (id: string) => {
  switch (id) {
    case 'brainy-fast':
      return <Zap size={14} className="text-amber-400" />
    case 'brainy-reasoning':
      return <Sparkles size={14} className="text-emerald-400" />
    case 'brainy-coding':
      return <Code2 size={14} className="text-teal-400" />
    case 'brainy-exam':
      return <BookOpen size={14} className="text-emerald-300" />
    default:
      return <Sparkles size={14} className="text-emerald-400" />
  }
}

export function AppHeader({
  user,
  activeModel,
  onSelectModel,
  activeLength,
  onSelectLength,
  usage,
  onOpenUsageModal,
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
    <header className="h-14 border-b border-zinc-800/80 bg-[#0c0d13]/90 backdrop-blur-md px-4 flex items-center justify-between z-20 flex-shrink-0">
      {/* Left: Mobile hamburger & Brand */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu size={18} />
        </button>

        <div className="hidden sm:flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-white text-xs">
            B
          </div>
          <span className="font-semibold text-sm tracking-tight text-white">Brainy</span>
        </div>

        {/* Model Selector Dropdown */}
        <div className="relative">
          <button
            onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800 text-xs text-zinc-200 transition"
          >
            {getModelIcon(currentModel.id)}
            <span className="font-medium hidden xs:inline">{currentModel.name}</span>
            <ChevronDown size={13} className="text-zinc-500" />
          </button>

          {modelDropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setModelDropdownOpen(false)}
              />
              <div className="absolute left-0 top-full mt-1.5 w-64 rounded-xl bg-[#12141c] border border-zinc-800 shadow-2xl p-1.5 z-40 space-y-1">
                <div className="px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold text-zinc-500">
                  Study Capability Models
                </div>
                {CAPABILITY_MODELS.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => {
                      onSelectModel(m.id)
                      setModelDropdownOpen(false)
                    }}
                    className={`w-full text-left p-2 rounded-lg text-xs flex items-start gap-2.5 transition ${
                      activeModel === m.id
                        ? 'bg-zinc-800/90 text-white'
                        : 'text-zinc-300 hover:bg-zinc-800/50 hover:text-white'
                    }`}
                  >
                    <div className="mt-0.5">{getModelIcon(m.id)}</div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium">{m.name}</span>
                        {m.badge && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-zinc-700/60 text-zinc-300 font-mono">
                            {m.badge}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-400 mt-0.5 leading-snug">
                        {m.tagline}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Answer Length Pill Toggle */}
        <div className="hidden md:flex items-center p-0.5 rounded-lg bg-zinc-900 border border-zinc-800 text-[11px]">
          {ANSWER_LENGTH_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => onSelectLength(opt.id as AnswerLength)}
              title={opt.desc}
              className={`px-2.5 py-1 rounded-md transition font-medium ${
                activeLength === opt.id
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Right: Usage Quota & User Profile */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Quota Button / Indicator */}
        <button
          onClick={onOpenUsageModal}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition ${
            isExhausted
              ? 'bg-rose-950/40 border-rose-800/60 text-rose-300 hover:bg-rose-900/40'
              : isNearLimit
              ? 'bg-amber-950/40 border-amber-800/60 text-amber-300 hover:bg-amber-900/40'
              : 'bg-zinc-900/80 border-zinc-800 text-zinc-300 hover:bg-zinc-800'
          }`}
          title="Global message quota: 30 messages per 8 hours"
        >
          <Clock size={12} className={isExhausted ? 'text-rose-400' : isNearLimit ? 'text-amber-400' : 'text-zinc-400'} />
          <span>
            {usage ? `${remaining}/${usage.limit}` : '30/30'}
          </span>
          <span className="hidden sm:inline text-zinc-500 font-normal">left</span>
        </button>

        {/* User Avatar & Dropdown */}
        <div className="relative">
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex items-center gap-2 p-1 rounded-lg hover:bg-zinc-800 transition"
            aria-label="User account menu"
          >
            <div className="w-7 h-7 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs font-semibold text-zinc-200">
              {user.first_name ? user.first_name[0].toUpperCase() : 'U'}
            </div>
            <ChevronDown size={12} className="text-zinc-500 hidden sm:block" />
          </button>

          {userDropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setUserDropdownOpen(false)}
              />
              <div className="absolute right-0 top-full mt-1.5 w-48 rounded-xl bg-[#12141c] border border-zinc-800 shadow-2xl p-1.5 z-40 space-y-1 text-xs">
                <div className="px-3 py-2 border-b border-zinc-800/80">
                  <div className="font-semibold text-white truncate">{user.first_name}</div>
                  {user.username && (
                    <div className="text-[11px] text-zinc-400 truncate">@{user.username}</div>
                  )}
                </div>

                <button
                  onClick={() => {
                    setUserDropdownOpen(false)
                    onOpenUsageModal()
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-zinc-300 hover:text-white hover:bg-zinc-800/60 transition"
                >
                  <Clock size={13} />
                  <span>8-Hour Quota Details</span>
                </button>

                <div className="border-t border-zinc-800/80 my-1" />

                <button
                  onClick={() => {
                    setUserDropdownOpen(false)
                    onLogout()
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-rose-300 hover:bg-rose-950/40 transition"
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
