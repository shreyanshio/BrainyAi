'use client'

import React, { useState, useEffect, useRef } from 'react'
import { Copy, Check, Bookmark, BookmarkCheck, ArrowDown } from 'lucide-react'
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
  const isNearBottomRef = useRef(true)
  const [showScrollBottom, setShowScrollBottom] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [savedIndex, setSavedIndex] = useState<number | null>(null)

  // Attach scroll listener to scroll container to track user position
  useEffect(() => {
    const scrollContainer = bottomRef.current?.closest('main')
    if (!scrollContainer) return

    const handleScroll = () => {
      const distanceToBottom =
        scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight
      const nearBottom = distanceToBottom < 130
      isNearBottomRef.current = nearBottom
      setShowScrollBottom(!nearBottom && distanceToBottom > 250)
    }

    scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
    return () => scrollContainer.removeEventListener('scroll', handleScroll)
  }, [])

  // Sensible conversation auto-scroll: follow if user is near bottom, don't interrupt if user scrolled up
  useEffect(() => {
    if (isNearBottomRef.current) {
      const scrollContainer = bottomRef.current?.closest('main')
      if (scrollContainer) {
        // Use instant scroll during streaming for stability, smooth on message addition
        const hasStreaming = messages.some((m) => m.isStreaming)
        if (hasStreaming) {
          scrollContainer.scrollTop = scrollContainer.scrollHeight
        } else {
          bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
        }
      }
    }
  }, [messages, isThinking])

  const scrollToBottom = () => {
    isNearBottomRef.current = true
    setShowScrollBottom(false)
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

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
    <div className={`w-full ${maxWidthClass} mx-auto px-2.5 sm:px-4 py-4 sm:py-8 space-y-4 sm:space-y-7 relative`}>
      {messages.map((msg, idx) => {
        const isUser = msg.role === 'user'
        const messageKey = msg.id ?? `${msg.role}-${msg.created_at || 'pending'}-${idx}`

        if (isUser) {
          return (
            <div key={messageKey} className="flex justify-end items-start gap-2 sm:gap-3">
              <div className="max-w-[90%] sm:max-w-[78%] rounded-3xl rounded-tr-sm bg-[var(--text-primary)] text-[var(--bg-app)] px-3.5 sm:px-5 py-2.5 sm:py-3 text-xs sm:text-sm leading-relaxed shadow-sm break-words">
                {msg.content}
              </div>
              <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 shadow-xs">
                {user.first_name ? user.first_name[0].toUpperCase() : 'U'}
              </div>
            </div>
          )
        }

        const isStreaming = Boolean(msg.isStreaming)

        return (
          <div key={messageKey} className="flex items-start gap-2 sm:gap-3.5">
            <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-xl bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center font-bold text-xs flex-shrink-0 mt-1 shadow-xs">
              B
            </div>

            <div className="flex-1 min-w-0">
              <div className="rounded-3xl rounded-tl-sm glass-panel p-3.5 sm:p-6 shadow-xs text-[var(--text-primary)] leading-relaxed text-xs sm:text-sm">
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

              {/* Message Toolbar with touch targets */}
              {!isStreaming && msg.content && (
                <div className="flex items-center gap-2 sm:gap-3 mt-1.5 px-1 text-[11px] text-[var(--text-muted)]">
                  <button
                    onClick={() => handleCopy(msg.content, idx)}
                    className="flex items-center gap-1.5 hover:text-[var(--text-primary)] transition py-1.5 px-2 rounded-lg hover:bg-[var(--bg-surface-elevated)] cursor-pointer min-h-[32px]"
                    title="Copy response"
                    aria-label="Copy response text"
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
                    className="flex items-center gap-1.5 hover:text-[var(--text-primary)] transition py-1.5 px-2 rounded-lg hover:bg-[var(--bg-surface-elevated)] cursor-pointer min-h-[32px]"
                    title="Save to study notes"
                    aria-label="Save note to study context"
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
        <div className="flex items-start gap-2 sm:gap-3.5">
          <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-xl bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center font-bold text-xs flex-shrink-0 mt-1 shadow-xs">
            B
          </div>
          <div className="rounded-3xl rounded-tl-sm glass-panel px-4 sm:px-5 py-3 sm:py-3.5 text-xs text-[var(--text-muted)] flex items-center gap-2.5 shadow-xs">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Formulating step-by-step academic response...</span>
          </div>
        </div>
      )}

      {/* Floating Scroll-to-Bottom Jump Button */}
      {showScrollBottom && (
        <button
          onClick={scrollToBottom}
          className="fixed bottom-24 right-5 sm:right-8 z-30 p-2.5 rounded-full bg-[var(--text-primary)] text-[var(--bg-app)] shadow-lg hover:opacity-90 transition-all flex items-center gap-1.5 text-xs font-semibold cursor-pointer animate-fade-in"
          aria-label="Jump to latest messages"
        >
          <ArrowDown size={14} />
          <span className="hidden sm:inline text-[11px]">Latest</span>
        </button>
      )}

      <div ref={bottomRef} className="h-4 sm:h-6" />
    </div>
  )
}

