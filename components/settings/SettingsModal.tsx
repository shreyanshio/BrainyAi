'use client'

import React, { useState } from 'react'
import {
  X,
  Palette,
  Sliders,
  ShieldCheck,
  User as UserIcon,
  Check,
  Lock,
  Download,
  Trash2,
  Sparkles,
  RefreshCw,
  LogOut,
  Type,
  Maximize2,
  BookOpen,
} from 'lucide-react'
import {
  AccentColor,
  AppTheme,
  ChatSession,
  FontSizeOption,
  InterfaceFont,
  LineSpacingOption,
  UsageStatus,
  User,
  UserMemoryData,
  UserPreferences,
} from '@/types/api'
import {
  ACCENT_PRESETS,
  CAPABILITY_MODELS,
  FONT_OPTIONS,
  THEME_PRESETS,
} from '@/lib/constants'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
  user: User
  preferences: UserPreferences
  onUpdatePreferences: (updated: Partial<UserPreferences>) => void
  sessions: ChatSession[]
  usage: UsageStatus | null
  memoryData: UserMemoryData | null
  onLogout: () => void
}

type SettingsTab = 'appearance' | 'study' | 'privacy' | 'account'

export function SettingsModal({
  isOpen,
  onClose,
  user,
  preferences,
  onUpdatePreferences,
  sessions,
  usage,
  memoryData,
  onLogout,
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>('appearance')
  const [customHex, setCustomHex] = useState(preferences.customAccentHex || '#059669')

  if (!isOpen) return null

  const handleExportData = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            user: { id: user.id, name: user.first_name, username: user.username },
            exported_at: new Date().toISOString(),
            sessions_count: sessions.length,
            sessions: sessions,
          },
          null,
          2
        )
      )
    const downloadAnchor = document.createElement('a')
    downloadAnchor.setAttribute('href', dataStr)
    downloadAnchor.setAttribute('download', `brainy_study_export_${Date.now()}.json`)
    document.body.appendChild(downloadAnchor)
    downloadAnchor.click()
    downloadAnchor.remove()
  }

  const currentFont =
    FONT_OPTIONS.find((f) => f.id === preferences.interfaceFont) || FONT_OPTIONS[0]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-3xl rounded-3xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-[var(--card-shadow)] overflow-hidden flex flex-col max-h-[85vh]">
        
        {/* Modal Top Bar */}
        <div className="p-4 sm:p-5 border-b border-[var(--border-subtle)] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[var(--bg-surface-elevated)] flex items-center justify-center text-[var(--text-primary)]">
              <Sliders size={16} />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
                Settings & Customization
              </h2>
              <p className="text-[11px] text-[var(--text-muted)]">
                Personalize your workspace, typography, study models, and security
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-[var(--bg-surface-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition cursor-pointer"
            aria-label="Close settings"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body with Left Tabs & Right Content */}
        <div className="flex-1 flex flex-col sm:flex-row overflow-hidden">
          
          {/* Navigation Tabs */}
          <div className="sm:w-48 p-3 border-b sm:border-b-0 sm:border-r border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] flex sm:flex-col gap-1 overflow-x-auto sm:overflow-x-visible">
            <button
              onClick={() => setActiveTab('appearance')}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition cursor-pointer flex-shrink-0 sm:flex-shrink ${
                activeTab === 'appearance'
                  ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              <Palette size={14} />
              <span>Appearance</span>
            </button>

            <button
              onClick={() => setActiveTab('study')}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition cursor-pointer flex-shrink-0 sm:flex-shrink ${
                activeTab === 'study'
                  ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              <BookOpen size={14} />
              <span>Study AI</span>
            </button>

            <button
              onClick={() => setActiveTab('privacy')}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition cursor-pointer flex-shrink-0 sm:flex-shrink ${
                activeTab === 'privacy'
                  ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              <ShieldCheck size={14} />
              <span>Security</span>
            </button>

            <button
              onClick={() => setActiveTab('account')}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition cursor-pointer flex-shrink-0 sm:flex-shrink ${
                activeTab === 'account'
                  ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              <UserIcon size={14} />
              <span>Account</span>
            </button>
          </div>

          {/* Tab Content Panels */}
          <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
            
            {/* ── TAB 1: APPEARANCE ───────────────────────────── */}
            {activeTab === 'appearance' && (
              <div className="space-y-6">
                
                {/* 1. Theme Presets */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2.5">
                    Workspace Theme (5 Coordinated Palettes)
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    {THEME_PRESETS.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => onUpdatePreferences({ theme: t.id })}
                        className={`p-3 rounded-2xl border text-left transition cursor-pointer flex flex-col justify-between ${
                          preferences.theme === t.id
                            ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-[var(--bg-surface-elevated)]'
                            : 'border-[var(--border-subtle)] hover:border-[var(--border-strong)] bg-[var(--bg-surface)]'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold text-[var(--text-primary)]">
                            {t.name}
                          </span>
                          {preferences.theme === t.id && (
                            <Check size={13} className="text-emerald-500" />
                          )}
                        </div>

                        {/* Theme preview swatch */}
                        <div
                          className="w-full h-7 rounded-lg border flex items-center justify-center text-[10px] font-mono"
                          style={{
                            backgroundColor: t.bgPreview,
                            borderColor: t.borderPreview,
                            color: t.textPreview,
                          }}
                        >
                          Aa Bb 12
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)] mt-1.5 line-clamp-1">
                          {t.tagline}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 2. Curated Accent Colors (Zero Purple) */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2.5">
                    Primary Accent Color (Zero Purple Palette)
                  </label>
                  <div className="flex flex-wrap items-center gap-2">
                    {ACCENT_PRESETS.map((acc) => (
                      <button
                        key={acc.id}
                        onClick={() =>
                          onUpdatePreferences({
                            accentColor: acc.id,
                            customAccentHex: acc.hex,
                          })
                        }
                        className={`px-3 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-2 transition cursor-pointer ${
                          preferences.accentColor === acc.id
                            ? 'border-zinc-800 dark:border-white shadow-sm'
                            : 'border-[var(--border-subtle)] hover:border-[var(--border-strong)]'
                        }`}
                      >
                        <span
                          className="w-3.5 h-3.5 rounded-full"
                          style={{ backgroundColor: acc.hex }}
                        />
                        <span className="text-[var(--text-primary)]">{acc.name}</span>
                        {preferences.accentColor === acc.id && (
                          <Check size={12} className="text-[var(--text-primary)]" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Typography Selector & Live Preview */}
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Typography & Live Reading Flow
                    </label>
                    <span className="text-[11px] text-[var(--text-muted)]">
                      {currentFont.category}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-3">
                    {FONT_OPTIONS.map((f) => (
                      <button
                        key={f.id}
                        onClick={() => onUpdatePreferences({ interfaceFont: f.id as InterfaceFont })}
                        className={`p-2.5 rounded-xl border text-left text-xs transition cursor-pointer ${
                          preferences.interfaceFont === f.id
                            ? 'border-emerald-500 bg-[var(--bg-surface-elevated)] font-bold text-[var(--text-primary)]'
                            : 'border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span>{f.name}</span>
                          {preferences.interfaceFont === f.id && (
                            <Check size={12} className="text-emerald-500" />
                          )}
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* Live Typography Preview Box */}
                  <div
                    className="p-4 rounded-2xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] space-y-1.5 transition-all"
                    style={{ fontFamily: currentFont.fontFamily }}
                  >
                    <div className="text-[10px] uppercase font-bold tracking-wider text-[var(--text-muted)] font-mono">
                      Live Sample Preview: {currentFont.name}
                    </div>
                    <p className="text-xs sm:text-sm text-[var(--text-primary)] leading-relaxed">
                      {currentFont.sample}
                    </p>
                    <p className="text-xs text-[var(--text-secondary)]">
                      &ldquo;Mathematics is the language with which God has written the universe.&rdquo; — Galileo
                    </p>
                  </div>
                </div>

                {/* 4. Font Size & Line Spacing */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Font Size */}
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      Font Size
                    </label>
                    <div className="grid grid-cols-4 gap-1 p-1 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs">
                      {(['sm', 'md', 'lg', 'xl'] as FontSizeOption[]).map((sz) => (
                        <button
                          key={sz}
                          onClick={() => onUpdatePreferences({ fontSize: sz })}
                          className={`py-1.5 rounded-lg font-medium transition cursor-pointer ${
                            preferences.fontSize === sz
                              ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                          }`}
                        >
                          {sz.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Line Spacing */}
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      Line Spacing
                    </label>
                    <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs">
                      {(['compact', 'comfortable', 'relaxed'] as LineSpacingOption[]).map((sp) => (
                        <button
                          key={sp}
                          onClick={() => onUpdatePreferences({ lineSpacing: sp })}
                          className={`py-1.5 rounded-lg capitalize font-medium transition cursor-pointer ${
                            preferences.lineSpacing === sp
                              ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                          }`}
                        >
                          {sp}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 5. Chat Width & Readability Mode */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-[var(--border-subtle)]">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      Chat Message Width
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => onUpdatePreferences({ chatWidth: 'standard' })}
                        className={`flex-1 py-2 px-3 rounded-xl border text-xs font-medium cursor-pointer transition ${
                          preferences.chatWidth === 'standard'
                            ? 'border-emerald-500 bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-bold'
                            : 'border-[var(--border-subtle)] text-[var(--text-muted)]'
                        }`}
                      >
                        Standard (800px)
                      </button>
                      <button
                        onClick={() => onUpdatePreferences({ chatWidth: 'wide' })}
                        className={`flex-1 py-2 px-3 rounded-xl border text-xs font-medium cursor-pointer transition ${
                          preferences.chatWidth === 'wide'
                            ? 'border-emerald-500 bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-bold'
                            : 'border-[var(--border-subtle)] text-[var(--text-muted)]'
                        }`}
                      >
                        Wide (1100px)
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      Readability Mode
                    </label>
                    <button
                      onClick={() =>
                        onUpdatePreferences({ readabilityMode: !preferences.readabilityMode })
                      }
                      className={`w-full py-2 px-3 rounded-xl border text-xs font-medium flex items-center justify-between cursor-pointer transition ${
                        preferences.readabilityMode
                          ? 'border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold'
                          : 'border-[var(--border-subtle)] text-[var(--text-muted)]'
                      }`}
                    >
                      <span>Enhanced Contrast & Spacing</span>
                      <span>{preferences.readabilityMode ? 'ON' : 'OFF'}</span>
                    </button>
                  </div>
                </div>

              </div>
            )}

            {/* ── TAB 2: STUDY AI ─────────────────────────────── */}
            {activeTab === 'study' && (
              <div className="space-y-6">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2.5">
                    Default Capability Model
                  </label>
                  <div className="space-y-2">
                    {CAPABILITY_MODELS.map((m) => (
                      <div
                        key={m.id}
                        onClick={() => onUpdatePreferences({ defaultModel: m.id })}
                        className={`p-3.5 rounded-2xl border text-xs flex items-center justify-between cursor-pointer transition ${
                          preferences.defaultModel === m.id
                            ? 'border-emerald-500 bg-[var(--bg-surface-elevated)] ring-1 ring-emerald-500/20'
                            : 'border-[var(--border-subtle)] hover:border-[var(--border-strong)]'
                        }`}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-[var(--text-primary)]">{m.name}</span>
                            {m.badge && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-zinc-200 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-mono">
                                {m.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                            {m.description}
                          </p>
                        </div>
                        {preferences.defaultModel === m.id && (
                          <Check size={16} className="text-emerald-500 flex-shrink-0 ml-2" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-2 border-t border-[var(--border-subtle)]">
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                    Default Answer Verbosity
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: 'short', label: 'Short', desc: 'Direct & bulleted' },
                      { id: 'medium', label: 'Medium', desc: 'Balanced depth' },
                      { id: 'long', label: 'In-Depth', desc: 'Comprehensive guides' },
                    ].map((opt) => (
                      <button
                        key={opt.id}
                        onClick={() =>
                          onUpdatePreferences({ defaultLength: opt.id as any })
                        }
                        className={`p-3 rounded-xl border text-left text-xs transition cursor-pointer ${
                          preferences.defaultLength === opt.id
                            ? 'border-emerald-500 bg-[var(--bg-surface-elevated)] font-bold'
                            : 'border-[var(--border-subtle)]'
                        }`}
                      >
                        <div className="text-[var(--text-primary)]">{opt.label}</div>
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5">{opt.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── TAB 3: PRIVACY & SECURITY ───────────────────── */}
            {activeTab === 'privacy' && (
              <div className="space-y-6">
                {/* Supabase Cryptographic Hash Shield Banner */}
                <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-800 dark:text-emerald-300 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-sm text-emerald-700 dark:text-emerald-400">
                    <Lock size={15} />
                    <span>Cryptographic Hash Storage Active</span>
                  </div>
                  <p className="leading-relaxed">
                    Brainy implements real-time cryptographic masking and hashing for all user questions and session titles before persisting them into Supabase database rows.
                  </p>
                  <p className="text-[11px] text-emerald-600 dark:text-emerald-400">
                    Database administrators or leaked tables only see unreadable hash payloads, protecting your academic intellectual property and private questions.
                  </p>
                </div>

                {/* Stored Context / Memory */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Active Study Learning Context
                    </label>
                    <span className="text-[11px] text-[var(--text-muted)]">
                      {memoryData?.liked_notes?.length || 0} saved notes
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] font-mono max-h-32 overflow-y-auto">
                    {memoryData?.learn_context || 'No custom learning patterns registered yet.'}
                  </div>
                </div>

                {/* Data Export */}
                <div className="pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-[var(--text-primary)]">
                      Export Study Conversations
                    </div>
                    <div className="text-[11px] text-[var(--text-muted)]">
                      Download all {sessions.length} study sessions as a portable JSON file
                    </div>
                  </div>

                  <button
                    onClick={handleExportData}
                    className="px-3.5 py-2 rounded-xl bg-[var(--bg-surface-elevated)] hover:bg-[var(--border-strong)] border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-primary)] transition flex items-center gap-1.5 cursor-pointer"
                  >
                    <Download size={13} />
                    <span>Export Data</span>
                  </button>
                </div>
              </div>
            )}

            {/* ── TAB 4: ACCOUNT ──────────────────────────────── */}
            {activeTab === 'account' && (
              <div className="space-y-6">
                <div className="p-4 rounded-2xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 flex items-center justify-center font-bold text-sm">
                      {user.first_name ? user.first_name[0].toUpperCase() : 'U'}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-[var(--text-primary)]">
                        {user.first_name || 'Scholar'}
                      </div>
                      <div className="text-xs text-[var(--text-muted)]">
                        {user.username ? `@${user.username}` : `Student #${user.id}`}
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-[var(--border-subtle)] grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-[var(--text-muted)]">User ID:</span>{' '}
                      <span className="font-mono text-[var(--text-primary)]">#{user.id}</span>
                    </div>
                    <div>
                      <span className="text-[var(--text-muted)]">Role:</span>{' '}
                      <span className="font-medium text-[var(--text-primary)]">Verified Student</span>
                    </div>
                    <div>
                      <span className="text-[var(--text-muted)]">Total Sessions:</span>{' '}
                      <span className="font-medium text-[var(--text-primary)]">{sessions.length}</span>
                    </div>
                    <div>
                      <span className="text-[var(--text-muted)]">Message quota:</span>{' '}
                      <span className="font-medium text-[var(--text-primary)]">{usage ? `${usage.limit} questions / ${usage.window_hours}h` : 'Unavailable'}</span>
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-[var(--border-subtle)] flex justify-end">
                  <button
                    onClick={() => {
                      onClose()
                      onLogout()
                    }}
                    className="px-4 py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-bold transition flex items-center gap-2 cursor-pointer"
                  >
                    <LogOut size={14} />
                    <span>Sign Out of Brainy</span>
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-3.5 sm:p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] flex items-center justify-between text-xs">
          <span className="text-[11px] text-[var(--text-muted)]">
            Changes are saved instantly to your workspace
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 font-semibold hover:opacity-90 transition cursor-pointer"
          >
            Done
          </button>
        </div>

      </div>
    </div>
  )
}
