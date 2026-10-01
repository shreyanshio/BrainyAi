'use client'

import React, { useRef, useEffect, useState } from 'react'
import { ArrowUp, Mic, MicOff, Clock, ShieldAlert } from 'lucide-react'
import { AnswerLength, ModelDefinition, UsageStatus } from '@/types/api'
import { ANSWER_LENGTH_OPTIONS, CAPABILITY_MODELS } from '@/lib/constants'

interface ComposerProps {
  inputMessage: string
  onInputChange: (val: string) => void
  onSendMessage: () => void
  isThinking: boolean
  usage: UsageStatus | null
  activeModel: string
  onSelectModel: (modelId: string) => void
  activeLength: AnswerLength
  onSelectLength: (length: AnswerLength) => void
  onOpenUsageModal: () => void
}

export function Composer({
  inputMessage,
  onInputChange,
  onSendMessage,
  isThinking,
  usage,
  activeModel,
  onSelectModel,
  activeLength,
  onSelectLength,
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

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      {/* Quota Exhausted Warning */}
      {isExhausted && (
        <div className="mb-2.5 p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-rose-400 flex-shrink-0" />
            <span>
              You've used your 8-hour quota (30 messages). Resets at{' '}
              <strong>{formatResetTime(usage?.reset_at)}</strong>.
            </span>
          </div>
          <button
            onClick={onOpenUsageModal}
            className="text-[11px] underline hover:text-white font-medium ml-2"
          >
            Details
          </button>
        </div>
      )}

      {/* Input Card Container */}
      <div className="rounded-2xl border border-zinc-800 bg-[#10121a] focus-within:border-zinc-700 transition p-2.5 shadow-lg">
        <textarea
          ref={textareaRef}
          value={inputMessage}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isThinking || isExhausted}
          placeholder={
            isExhausted
              ? '8-hour quota reached. Please wait for the window to reset.'
              : 'Ask a question, enter code, or paste a problem... (Shift+Enter for new line)'
          }
          rows={1}
          className="w-full bg-transparent text-zinc-100 placeholder-zinc-500 text-sm leading-relaxed px-2 py-1 focus:outline-none resize-none disabled:opacity-50"
        />

        {/* Composer Controls Bar */}
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60 mt-1 px-1">
          {/* Left: Quick options (Model & Length pills) */}
          <div className="flex items-center gap-2 text-[11px]">
            {/* Quick model indicator */}
            <span className="text-zinc-500 hidden sm:inline">
              Model: <strong className="text-zinc-400">{CAPABILITY_MODELS.find((m) => m.id === activeModel)?.name}</strong>
            </span>

            {/* Quick length selector */}
            <div className="flex items-center gap-1 bg-zinc-900/90 rounded-md p-0.5 border border-zinc-800">
              {ANSWER_LENGTH_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => onSelectLength(opt.id as AnswerLength)}
                  className={`px-2 py-0.5 rounded text-[10px] font-medium transition ${
                    activeLength === opt.id
                      ? 'bg-zinc-800 text-zinc-100'
                      : 'text-zinc-500 hover:text-zinc-300'
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
              className={`p-2 rounded-lg transition ${
                isListening
                  ? 'bg-rose-500/20 text-rose-400 animate-pulse'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              } disabled:opacity-40`}
            >
              {isListening ? <MicOff size={15} /> : <Mic size={15} />}
            </button>

            <button
              type="button"
              onClick={onSendMessage}
              disabled={!inputMessage.trim() || isThinking || isExhausted}
              aria-label="Send message"
              className="p-2 rounded-lg bg-zinc-100 hover:bg-white text-zinc-900 disabled:opacity-30 disabled:hover:bg-zinc-100 transition shadow-xs"
            >
              <ArrowUp size={15} />
            </button>
          </div>
        </div>
      </div>

      <div className="text-center text-[10px] text-zinc-500 mt-2">
        Brainy provides educational assistance. Verify critical academic formulas & sources.
      </div>
    </div>
  )
}
