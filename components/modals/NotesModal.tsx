'use client'

import React, { useState } from 'react'
import { X, BookMarked, Copy, Check } from 'lucide-react'
import { UserMemoryData } from '@/types/api'

interface NotesModalProps {
  isOpen: boolean
  onClose: () => void
  memoryData: UserMemoryData | null
}

export function NotesModal({ isOpen, onClose, memoryData }: NotesModalProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  if (!isOpen) return null

  const notes = memoryData?.liked_notes || []

  const handleCopy = (text: string, idx: number) => {
    navigator.clipboard.writeText(text)
    setCopiedIndex(idx)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-lg rounded-3xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 shadow-[var(--card-shadow)] text-[var(--text-primary)] flex flex-col max-h-[80vh]"
        role="dialog"
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)] flex-shrink-0">
          <div className="flex items-center gap-2">
            <BookMarked size={16} className="text-emerald-500" />
            <h3 className="font-bold text-sm text-[var(--text-primary)]">Saved Study Notes</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto py-4 space-y-3 scrollbar-thin">
          {notes.length === 0 ? (
            <div className="text-center py-12 text-[var(--text-muted)] text-xs">
              No saved study notes yet. Use the &ldquo;Save note&rdquo; button under any answer in chat to bookmark formulas, definitions, and high-yield takeaways.
            </div>
          ) : (
            notes.map((note, idx) => (
              <div
                key={idx}
                className="p-4 rounded-2xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs space-y-2.5"
              >
                <div className="text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap break-words">
                  {note}
                </div>
                <div className="flex justify-end pt-2 border-t border-[var(--border-subtle)]">
                  <button
                    onClick={() => handleCopy(note, idx)}
                    className="flex items-center gap-1 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition cursor-pointer"
                  >
                    {copiedIndex === idx ? (
                      <>
                        <Check size={12} className="text-emerald-500" />
                        <span className="text-emerald-500 font-semibold">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={12} />
                        <span>Copy note</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-[var(--border-subtle)] flex-shrink-0">
          <button
            onClick={onClose}
            className="w-full py-2.5 px-4 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-xs font-semibold hover:opacity-90 transition cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
