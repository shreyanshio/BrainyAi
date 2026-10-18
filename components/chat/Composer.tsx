'use client'

import React, { useRef, useEffect, useState } from 'react'
import {
  ArrowUp,
  Mic,
  MicOff,
  Clock,
  Square,
  Plus,
  Paperclip,
  Globe,
  Sparkles,
  ChevronDown,
} from 'lucide-react'
import { AnswerLength, ChatWidthOption, UsageStatus } from '@/types/api'
import { ANSWER_LENGTH_OPTIONS, CAPABILITY_MODELS, STUDY_QUICK_PROMPTS } from '@/lib/constants'

interface ComposerProps {
  inputMessage: string
  onInputChange: (val: string) => void
  onSendMessage: () => void
  onStop?: () => void
  isThinking: boolean
  disabled?: boolean
  disabledMessage?: string
  usage: UsageStatus | null
  activeModel: string
  onSelectModel: (modelId: string) => void
  activeLength: AnswerLength
  onSelectLength: (length: AnswerLength) => void
  chatWidth?: ChatWidthOption
  onOpenUsageModal: () => void
}

export function Composer({
  inputMessage,
  onInputChange,
  onSendMessage,
  onStop,
  isThinking,
  disabled = false,
  disabledMessage,
  usage,
  activeModel,
  onSelectModel,
  activeLength,
  onSelectLength,
  chatWidth = 'standard',
  onOpenUsageModal,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [isListening, setIsListening] = useState(false)
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [promptMenuOpen, setPromptMenuOpen] = useState(false)

  // Auto-resize textarea as text grows
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [inputMessage])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (inputMessage.trim() && !isThinking && !isExhausted && !disabled) {
        onSendMessage()
      }
    }
  }

  // Web Speech API Voice Recognition
  const toggleVoice = () => {
    if (typeof window === 'undefined') return
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRec) {
      alert('Voice dictation is supported in Chrome, Edge, and Safari.')
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
        const transcript = event.results?.[0]?.[0]?.transcript || ''
        if (transcript) {
          onInputChange(inputMessage ? `${inputMessage} ${transcript}` : transcript)
        }
        setIsListening(false)
      }
      recognition.onerror = () => setIsListening(false)
      recognition.onend = () => setIsListening(false)

      recognition.start()
    } catch {
      setIsListening(false)
    }
  }

  const isExhausted = usage ? usage.remaining === 0 : false

  const formatResetTime = (isoString?: string) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return ''
    }
  }

  const currentModel =
    CAPABILITY_MODELS.find((m) => m.id === activeModel) || CAPABILITY_MODELS[0]

  const maxWidthClass = chatWidth === 'wide' ? 'max-w-4xl' : 'max-w-2xl'

  return (
    <div className={`w-full ${maxWidthClass} mx-auto px-4 pb-5 pt-2 relative z-10`}>
      {/* Quota Exhausted Warning */}
      {isExhausted && (
        <div className="mb-3 p-3 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-rose-500 flex-shrink-0" />
            <span>
              You&apos;ve used your {usage?.window_hours ?? 5}-hour quota ({usage?.limit ?? 30} questions). Resets at{' '}
              <strong>{formatResetTime(usage?.reset_at)}</strong>.
            </span>
          </div>
          <button
            onClick={onOpenUsageModal}
            className="text-[11px] underline hover:opacity-80 font-medium ml-2 cursor-pointer"
          >
            Details
          </button>
        </div>
      )}

      {/* Floating Glassmorphism Composer Card */}
      <div className="relative rounded-3xl glass-panel p-3 sm:p-4 shadow-[0_12px_40px_-12px_rgba(0,0,0,0.08)] transition-all focus-within:border-[var(--border-strong)] focus-within:shadow-[0_16px_48px_-10px_rgba(0,0,0,0.12)]">
        <textarea
          ref={textareaRef}
          value={inputMessage}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isThinking || isExhausted || disabled}
          placeholder={
            disabledMessage
              ? disabledMessage
              : isExhausted
              ? `${usage?.window_hours}-hour quota reached. Please wait for the window to reset.`
              : 'How can I help you today?'
          }
          rows={1}
          className="w-full bg-transparent text-[var(--text-primary)] placeholder-[var(--text-muted)] text-sm sm:text-base leading-relaxed px-2 py-1.5 focus:outline-none resize-none disabled:opacity-50 min-h-[44px]"
        />

        {/* Composer Action Toolbar */}
        <div className="flex items-center justify-between pt-2.5 border-t border-[var(--border-subtle)] mt-1 px-1">
          {/* Left: Interactive Tools (+ Menu, Attach, Academic search, Voice) */}
          <div className="flex items-center gap-1 sm:gap-1.5 text-[var(--text-muted)]">
            {/* Quick Prompt Templates Menu */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setPromptMenuOpen(!promptMenuOpen)}
                title="Study prompt templates"
                className="p-1.5 sm:p-2 rounded-xl hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
              >
                <Plus size={16} />
              </button>

              {promptMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setPromptMenuOpen(false)}
                  />
                  <div className="absolute left-0 bottom-full mb-2 w-64 rounded-2xl glass-panel p-1.5 z-40 space-y-1 shadow-2xl">
                    <div className="px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
                      Quick Study Prompts
                    </div>
                    {STUDY_QUICK_PROMPTS.slice(0, 4).map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => {
                          onInputChange(p.prompt)
                          setPromptMenuOpen(false)
                          textareaRef.current?.focus()
                        }}
                        className="w-full text-left p-2 rounded-xl text-xs hover:bg-[var(--bg-surface-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition cursor-pointer"
                      >
                        <div className="font-semibold">{p.title}</div>
                        <div className="text-[10px] text-[var(--text-muted)] mt-0.5 line-clamp-1">
                          {p.description}
                        </div>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Quick Note Insert */}
            <button
              type="button"
              onClick={() => {
                onInputChange(inputMessage ? `${inputMessage}\n\n[Study Notes: Context]` : 'Summarize the core takeaways from my notes:')
                textareaRef.current?.focus()
              }}
              title="Add study context"
              className="p-1.5 sm:p-2 rounded-xl hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
            >
              <Paperclip size={15} />
            </button>

            {/* Academic Web Search Indicator */}
            <button
              type="button"
              onClick={() => {
                if (!inputMessage.startsWith('Search and explain: ')) {
                  onInputChange(`Search and explain: ${inputMessage}`)
                }
                textareaRef.current?.focus()
              }}
              title="Academic search mode"
              className="p-1.5 sm:p-2 rounded-xl hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
            >
              <Globe size={15} />
            </button>

            {/* Voice Dictation */}
            <button
              type="button"
              onClick={toggleVoice}
              disabled={isThinking || isExhausted || disabled}
              title={isListening ? 'Stop listening' : 'Voice input'}
              className={`p-1.5 sm:p-2 rounded-xl transition cursor-pointer ${
                isListening
                  ? 'bg-rose-500/20 text-rose-500 animate-pulse'
                  : 'hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)]'
              } disabled:opacity-40`}
            >
              {isListening ? <MicOff size={15} /> : <Mic size={15} />}
            </button>
          </div>

          {/* Right: Model Selector & Send Arrow Button */}
          <div className="flex items-center gap-2">
            {/* Capability Model Selector Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] transition cursor-pointer"
              >
                <Sparkles size={13} className="text-emerald-600 dark:text-emerald-400" />
                <span className="font-medium text-xs max-w-[110px] truncate sm:max-w-none">
                  {currentModel.name}
                </span>
                <ChevronDown size={11} className="text-[var(--text-muted)]" />
              </button>

              {modelDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setModelDropdownOpen(false)}
                  />
                  <div className="absolute right-0 bottom-full mb-2 w-64 rounded-2xl glass-panel p-1.5 z-40 space-y-1 shadow-2xl">
                    <div className="px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
                      Capability Models
                    </div>
                    {CAPABILITY_MODELS.map((m) => (
                      <button
                        key={m.id}
                        type="button"
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
                        <div className="mt-0.5">
                          <Sparkles size={13} className={activeModel === m.id ? 'text-emerald-500' : 'text-[var(--text-muted)]'} />
                        </div>
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

            {/* Answer Length Options (Hidden on narrow screens) */}
            <div className="hidden md:flex items-center gap-0.5 bg-[var(--bg-surface-elevated)] rounded-full p-0.5 border border-[var(--border-subtle)] text-[10px]">
              {ANSWER_LENGTH_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onSelectLength(opt.id as AnswerLength)}
                  className={`px-2 py-0.5 rounded-full font-semibold transition cursor-pointer ${
                    activeLength === opt.id
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Circular Send / Stop Button */}
            {isThinking ? (
              <button
                type="button"
                onClick={onStop}
                aria-label="Stop generation"
                title="Stop generation"
                className="w-9 h-9 rounded-full bg-[var(--text-primary)] text-[var(--bg-app)] hover:opacity-90 transition shadow-xs cursor-pointer flex items-center justify-center flex-shrink-0"
              >
                <Square size={13} className="fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={onSendMessage}
                disabled={!inputMessage.trim() || isExhausted || disabled}
                aria-label="Send message"
                className="w-9 h-9 rounded-full bg-[var(--text-primary)] text-[var(--bg-app)] hover:opacity-90 disabled:opacity-25 transition shadow-xs cursor-pointer flex items-center justify-center flex-shrink-0"
              >
                <ArrowUp size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
