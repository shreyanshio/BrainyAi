'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Copy, Check, Bookmark, BookmarkCheck, Sparkles } from 'lucide-react'
import { ChatMessage, ChatWidthOption, User } from '@/types/api'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'

interface MessageListProps {
  messages: ChatMessage[]
  isThinking: boolean
  user: User
  chatWidth?: ChatWidthOption
  onSaveNote: (content: string) => void
}

export function MessageList({
  messages,
  isThinking,
  user,
  chatWidth = 'standard',
  onSaveNote,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [savedIndex, setSavedIndex] = useState<number | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIndex(index)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  const handleSaveNote = (text: string, index: number) => {
    onSaveNote(text)
    setSavedIndex(index)
    setTimeout(() => setSavedIndex(null), 2500)
  }

  const maxWidthClass = chatWidth === 'wide' ? 'max-w-4xl' : 'max-w-2xl'

  return (
    <div className={`w-full ${maxWidthClass} mx-auto px-4 py-8 space-y-6 sm:space-y-8`}>
      {messages.map((msg, idx) => {
        const isUser = msg.role === 'user'
        const messageKey = msg.id ?? `${msg.role}-${msg.created_at || 'pending'}-${idx}`

        if (isUser) {
          return (
            <div key={messageKey} className="flex justify-end items-start gap-2.5 sm:gap-3">
              <div className="max-w-[85%] sm:max-w-[78%] rounded-3xl rounded-tr-sm bg-[var(--text-primary)] text-[var(--bg-app)] px-4 sm:px-5 py-3 text-xs sm:text-sm leading-relaxed shadow-sm break-words">
                {msg.content}
              </div>
              <div className="w-7 h-7 rounded-full bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-xs">
                {user.first_name ? user.first_name[0].toUpperCase() : 'U'}
              </div>
            </div>
          )
        }

        const isStreaming = Boolean(msg.isStreaming)

        return (
          <div key={messageKey} className="flex items-start gap-3 sm:gap-3.5">
            <div className="w-7 h-7 rounded-xl bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center font-bold text-xs flex-shrink-0 mt-1 shadow-xs">
              B
            </div>

            <div className="flex-1 min-w-0">
              <div className="rounded-3xl rounded-tl-sm glass-panel p-5 sm:p-6 shadow-xs text-[var(--text-primary)] leading-relaxed text-xs sm:text-sm">
                {msg.content ? (
                  <>
                    <MarkdownRenderer content={msg.content} />
                    {isStreaming && (
                      <span
                        className="inline-block w-1.5 h-4 ml-1 bg-emerald-500 dark:bg-emerald-400 animate-pulse align-middle rounded-full"
                        aria-label="streaming cursor"
                      />
                    )}
                  </>
                ) : (
                  <div className="flex items-center gap-2.5 text-xs text-[var(--text-muted)] py-1">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span>Brainy is formulating your explanation...</span>
                  </div>
                )}
              </div>

              {/* Message Toolbar */}
              {!isStreaming && msg.content && (
                <div className="flex items-center gap-3 mt-2 px-1 text-[11px] text-[var(--text-muted)]">
                  <button
                    onClick={() => handleCopy(msg.content, idx)}
                    className="flex items-center gap-1.5 hover:text-[var(--text-primary)] transition py-0.5 cursor-pointer"
                    title="Copy response"
                  >
                    {copiedIndex === idx ? (
                      <>
                        <Check size={12} className="text-emerald-500" />
                        <span className="text-emerald-500 font-medium">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        <span>Copy</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => handleSaveNote(msg.content, idx)}
                    className="flex items-center gap-1.5 hover:text-[var(--text-primary)] transition py-0.5 cursor-pointer"
                    title="Save to study notes"
                  >
                    {savedIndex === idx ? (
                      <>
                        <BookmarkCheck size={12} className="text-blue-500" />
                        <span className="text-blue-500 font-medium">Saved to Notes</span>
                      </>
                    ) : (
                      <>
                        <Bookmark size={12} />
                        <span>Save note</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        )
      })}

      {/* Thinking Indicator */}
      {isThinking && !messages.some((m) => m.isStreaming) && (
        <div className="flex items-start gap-3 sm:gap-3.5">
          <div className="w-7 h-7 rounded-xl bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center font-bold text-xs flex-shrink-0 mt-1 shadow-xs">
            B
          </div>
          <div className="rounded-3xl rounded-tl-sm glass-panel px-5 py-3.5 text-xs text-[var(--text-muted)] flex items-center gap-2.5 shadow-xs">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Formulating step-by-step academic response...</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} className="h-6" />
    </div>
  )
}
