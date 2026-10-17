'use client'

import React, { useRef, useEffect, useState } from 'react'
import { ArrowUp, Mic, MicOff, Clock, Square } from 'lucide-react'
import { AnswerLength, ChatWidthOption, UsageStatus } from '@/types/api'
import { ANSWER_LENGTH_OPTIONS, CAPABILITY_MODELS } from '@/lib/constants'

interface ComposerProps {
  inputMessage: string
  onInputChange: (val: string) => void
  onSendMessage: () => void
  onStop?: () => void
  isThinking: boolean
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

  // Auto-resize textarea as text grows
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [inputMessage])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (inputMessage.trim() && !isThinking && !isExhausted) {
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

  const maxWidthClass = chatWidth === 'wide' ? 'max-w-5xl' : 'max-w-3xl'

  return (
    <div className={`w-full ${maxWidthClass} mx-auto px-4 pb-4`}>
      {/* Quota Exhausted Warning */}
      {isExhausted && (
        <div className="mb-2.5 p-3 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-rose-500 flex-shrink-0" />
            <span>
              You&apos;ve used your {usage?.window_hours}-hour quota ({usage?.limit} questions). Resets at{' '}
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

      {/* Input Card Container */}
      <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] focus-within:border-[var(--border-strong)] transition p-2.5 shadow-[var(--card-shadow)]">
        <textarea
          ref={textareaRef}
          value={inputMessage}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isThinking || isExhausted}
          placeholder={
            isExhausted
              ? `${usage?.window_hours}-hour quota reached. Please wait for the window to reset.`
              : 'Ask a question, enter code, or paste a problem... (Shift+Enter for new line)'
          }
          rows={1}
          className="w-full bg-transparent text-[var(--text-primary)] placeholder-[var(--text-muted)] text-xs sm:text-sm leading-relaxed px-2 py-1 focus:outline-none resize-none disabled:opacity-50"
        />

        {/* Composer Controls Bar */}
        <div className="flex items-center justify-between pt-2 border-t border-[var(--border-subtle)] mt-1 px-1">
          {/* Left: Quick options (Model & Length pills) */}
          <div className="flex items-center gap-2 text-[11px]">
            {/* Quick model indicator */}
            <span className="text-[var(--text-muted)] hidden sm:inline">
              Model: <strong className="text-[var(--text-primary)]">{CAPABILITY_MODELS.find((m) => m.id === activeModel)?.name}</strong>
            </span>

            {/* Quick length selector */}
            <div className="flex items-center gap-1 bg-[var(--bg-surface-elevated)] rounded-xl p-0.5 border border-[var(--border-subtle)]">
              {ANSWER_LENGTH_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => onSelectLength(opt.id as AnswerLength)}
                  className={`px-2 py-0.5 rounded-lg text-[10px] font-semibold transition cursor-pointer ${
                    activeLength === opt.id
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Right: Voice Dictation & Send Button */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={toggleVoice}
              disabled={isThinking || isExhausted}
              title={isListening ? 'Stop listening' : 'Dictate with voice'}
              className={`p-2 rounded-xl transition cursor-pointer ${
                isListening
                  ? 'bg-rose-500/20 text-rose-500 animate-pulse'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)]'
              } disabled:opacity-40`}
            >
              {isListening ? <MicOff size={15} /> : <Mic size={15} />}
            </button>

            {isThinking ? (
              <button
                type="button"
                onClick={onStop}
                aria-label="Stop generation"
                title="Stop generation"
                className="p-2 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 hover:opacity-90 transition shadow-xs cursor-pointer flex items-center justify-center"
              >
                <Square size={13} className="fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={onSendMessage}
                disabled={!inputMessage.trim() || isExhausted}
                aria-label="Send message"
                className="p-2 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 hover:opacity-90 disabled:opacity-30 transition shadow-xs cursor-pointer"
              >
                <ArrowUp size={15} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="text-center text-[10px] text-[var(--text-muted)] mt-2">
        Brainy provides academic assistance. Verify critical formulas & solutions.
      </div>
    </div>
  )
}
