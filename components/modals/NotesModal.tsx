'use client'

import React, { useState } from 'react'
import { X, BookMarked, Copy, Check, Trash2 } from 'lucide-react'
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs">
      <div
        className="w-full max-w-lg rounded-2xl bg-[#12141c] border border-zinc-800 p-6 shadow-2xl text-zinc-100 animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[80vh]"
        role="dialog"
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-zinc-800 flex-shrink-0">
          <div className="flex items-center gap-2">
            <BookMarked size={16} className="text-zinc-400" />
            <h3 className="font-semibold text-sm text-white">Saved Study Notes</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto py-4 space-y-3">
          {notes.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 text-xs">
              No saved study notes yet. Use the "Save note" action under any answer to bookmark key takeaways.
            </div>
          ) : (
            notes.map((note, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-zinc-900/80 border border-zinc-800 text-xs space-y-2"
              >
                <div className="text-zinc-300 leading-relaxed whitespace-pre-wrap break-words">
                  {note}
                </div>
                <div className="flex justify-end pt-1 border-t border-zinc-800/60">
                  <button
                    onClick={() => handleCopy(note, idx)}
                    className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-white transition"
                  >
                    {copiedIndex === idx ? (
                      <>
                        <Check size={12} className="text-emerald-400" />
                        <span className="text-emerald-400">Copied</span>
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
        <div className="pt-3 border-t border-zinc-800 flex-shrink-0">
          <button
            onClick={onClose}
            className="w-full py-2 px-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
