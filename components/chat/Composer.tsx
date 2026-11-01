'use client'

import React, { useRef, useEffect, useState } from 'react'
import {
  ArrowUp,
  Mic,
  MicOff,
  Clock,
  Square,
  Plus,
  Globe,
  Sparkles,
  ChevronDown,
  X,
} from 'lucide-react'
import { AnswerLength, ChatWidthOption, UsageStatus } from '@/types/api'
import { ANSWER_LENGTH_OPTIONS, CAPABILITY_MODELS } from '@/lib/constants'

interface ComposerProps {
  inputMessage: string
  onInputChange: (val: string) => void
  onSendMessage: (image?: string | null, webSearch?: boolean) => void
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
  const imageInputRef = useRef<HTMLInputElement>(null)
  const [isListening, setIsListening] = useState(false)
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [imageError, setImageError] = useState<string | null>(null)
  const [webSearchActive, setWebSearchActive] = useState<boolean>(false)

  // Auto-resize textarea as text grows
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const maxHeight = typeof window !== 'undefined' && window.innerWidth < 640 ? 140 : 200
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`
    }
  }, [inputMessage])

  const handleSend = () => {
    if ((!inputMessage.trim() && !selectedImage) || isThinking || isExhausted || disabled) return
    onSendMessage(selectedImage, webSearchActive)
    setSelectedImage(null)
    setImageError(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const isTouch = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches
    if (e.key === 'Enter' && !e.shiftKey && !isTouch) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setImageError('Please select a valid image file.')
      return
    }
    if (file.size > 3 * 1024 * 1024) {
      setImageError('Image size exceeds the 3 MB limit. Please select a smaller image.')
      return
    }
    setImageError(null)
    const reader = new FileReader()
    reader.onload = () => {
      setSelectedImage(reader.result as string)
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  // Voice dictation handling using Web Speech API
  const toggleVoice = () => {
    if (typeof window === 'undefined') return
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser.')
      return
    }

    if (isListening) {
      setIsListening(false)
      return
    }

    try {
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = false
      recognition.lang = 'en-US'

      recognition.onstart = () => setIsListening(true)
      recognition.onend = () => setIsListening(false)
      recognition.onerror = () => setIsListening(false)

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript
        if (transcript) {
          onInputChange(inputMessage ? `${inputMessage} ${transcript}` : transcript)
        }
      }

      recognition.start()
    } catch {
      setIsListening(false)
    }
  }

  const isExhausted = Boolean(usage && usage.remaining <= 0)
  const activeModelMeta =
    CAPABILITY_MODELS.find((m) => m.id === activeModel) || CAPABILITY_MODELS[0]

  return (
    <div
      className={`w-full mx-auto px-3 sm:px-4 pb-3 sm:pb-5 pt-1 transition-all ${
        chatWidth === 'wide' ? 'max-w-4xl' : 'max-w-2xl'
      }`}
    >
      {/* Hidden image input for single entry point */}
      <input
        ref={imageInputRef}
        type="file"
        accept="image/*"
        onChange={handleImageChange}
        className="hidden"
      />

      {/* Floating Glassmorphism Composer Card */}
      <div className="relative rounded-3xl glass-panel p-2.5 sm:p-4 shadow-[0_12px_40px_-12px_rgba(0,0,0,0.08)] transition-all focus-within:border-[var(--border-strong)] focus-within:shadow-[0_16px_48px_-10px_rgba(0,0,0,0.12)]">
        {/* Selected Image Preview */}
        {selectedImage && (
          <div className="relative inline-block mb-2">
            <img
              src={selectedImage}
              alt="Attachment preview"
              className="h-20 w-auto max-w-[200px] object-cover rounded-xl border border-[var(--border-subtle)] shadow-xs"
            />
            <button
              type="button"
              onClick={() => setSelectedImage(null)}
              className="absolute -top-2 -right-2 p-1 rounded-full bg-rose-600 text-white hover:bg-rose-500 shadow-sm cursor-pointer"
              title="Remove image"
            >
              <X size={12} />
            </button>
          </div>
        )}

        {imageError && (
          <div className="text-xs text-rose-500 mb-2 font-medium">
            {imageError}
          </div>
        )}

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
        <div className="flex items-center justify-between pt-2 border-t border-[var(--border-subtle)] mt-1 px-0.5 sm:px-1 gap-1">
          {/* Left: Interactive Tools (Image Upload via +, Web Search toggle, Voice) */}
          <div className="flex items-center gap-0.5 sm:gap-1.5 text-[var(--text-muted)]">
            {/* Plus Button - Single Image Attachment Entry Point */}
            <button
              type="button"
              onClick={() => imageInputRef.current?.click()}
              title="Attach image (Max 3 MB)"
              aria-label="Attach image"
              className="p-2 min-h-[38px] min-w-[38px] flex items-center justify-center rounded-xl hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
            >
              <Plus size={16} />
            </button>

            {/* Academic Web Search Indicator with Visible Label */}
            <button
              type="button"
              onClick={() => setWebSearchActive(!webSearchActive)}
              title={webSearchActive ? 'Web Search active (click to disable)' : 'Enable web search'}
              aria-label="Toggle web search"
              className={`px-2.5 py-1.5 min-h-[38px] flex items-center gap-1.5 rounded-xl transition cursor-pointer text-xs font-medium ${
                webSearchActive
                  ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30'
                  : 'hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)]'
              }`}
            >
              <Globe size={15} />
              <span className="text-xs font-medium">Web Search</span>
            </button>

            {/* Voice Dictation */}
            <button
              type="button"
              onClick={toggleVoice}
              disabled={isThinking || isExhausted || disabled}
              title={isListening ? 'Stop listening' : 'Voice input'}
              aria-label={isListening ? 'Stop voice listening' : 'Start voice input'}
              className={`p-2 min-h-[38px] min-w-[38px] flex items-center justify-center rounded-xl transition cursor-pointer ${
                isListening
                  ? 'bg-rose-500/20 text-rose-500 animate-pulse'
                  : 'hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)]'
              }`}
            >
              {isListening ? <MicOff size={15} /> : <Mic size={15} />}
            </button>
          </div>

          {/* Right: Model Selector, Answer Length & Circular Send */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {/* Capability Model Selector Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
                className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-xl text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition border border-[var(--border-subtle)] cursor-pointer"
              >
                <Sparkles size={13} className="text-amber-500" />
                <span className="max-w-[75px] sm:max-w-none truncate">{activeModelMeta.name}</span>
                <ChevronDown size={12} className="opacity-60" />
              </button>

              {modelDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setModelDropdownOpen(false)}
                  />
                  <div className="absolute right-0 bottom-full mb-2 w-72 rounded-2xl glass-panel p-1.5 z-40 space-y-1 shadow-2xl">
                    <div className="px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
                      AI Specialist Models
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
                            ? 'bg-[var(--bg-surface-hover)] text-[var(--text-primary)] font-medium'
                            : 'hover:bg-[var(--bg-surface-elevated)] text-[var(--text-secondary)]'
                        }`}
                      >
                        <div className="p-1 rounded-lg bg-[var(--bg-surface)] mt-0.5 text-amber-500">
                          <Sparkles size={13} />
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
            <div className="hidden lg:flex items-center gap-0.5 bg-[var(--bg-surface-elevated)] rounded-full p-0.5 border border-[var(--border-subtle)] text-[10px]">
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
                className="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-[var(--text-primary)] text-[var(--bg-app)] hover:opacity-90 transition shadow-xs cursor-pointer flex items-center justify-center flex-shrink-0"
              >
                <Square size={13} className="fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={(!inputMessage.trim() && !selectedImage) || isExhausted || disabled}
                aria-label="Send message"
                className="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-[var(--text-primary)] text-[var(--bg-app)] hover:opacity-90 disabled:opacity-25 transition shadow-xs cursor-pointer flex items-center justify-center flex-shrink-0"
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
