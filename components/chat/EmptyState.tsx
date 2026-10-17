'use client'

import React from 'react'
import { Lightbulb, Target, Code2, Sparkles, ArrowRight } from 'lucide-react'
import { STUDY_QUICK_PROMPTS } from '@/lib/constants'
import { QuickPrompt } from '@/types/api'

interface EmptyStateProps {
  onSelectPrompt: (promptText: string) => void
}

const getCategoryIcon = (category: string) => {
  switch (category) {
    case 'concept':
      return <Lightbulb size={16} className="text-amber-500" />
    case 'problem':
      return <Target size={16} className="text-emerald-500" />
    case 'code':
      return <Code2 size={16} className="text-teal-500" />
    case 'exam':
      return <Sparkles size={16} className="text-blue-500" />
    default:
      return <Lightbulb size={16} className="text-[var(--text-muted)]" />
  }
}

export function EmptyState({ onSelectPrompt }: EmptyStateProps) {
  return (
    <div className="w-full max-w-2xl mx-auto px-4 py-12 sm:py-16 text-center">
      <div className="w-10 h-10 mx-auto mb-4 rounded-2xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 flex items-center justify-center font-black text-base shadow-sm">
        B
      </div>

      <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--text-primary)] mb-2">
        What are you studying today?
      </h2>

      <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-8 leading-relaxed">
        Ask conceptual doubts, step-by-step mathematical proofs, code reviews, or exam-style drills.
      </p>

      {/* 2x2 Clean Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-left">
        {STUDY_QUICK_PROMPTS.slice(0, 4).map((item: QuickPrompt) => (
          <button
            key={item.id}
            onClick={() => onSelectPrompt(item.prompt)}
            className="group p-4.5 rounded-2xl bg-[var(--bg-surface)] hover:bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] hover:border-[var(--border-strong)] shadow-[var(--card-shadow)] transition flex flex-col justify-between text-left cursor-pointer"
          >
            <div>
              <div className="w-8 h-8 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] flex items-center justify-center mb-3">
                {getCategoryIcon(item.category)}
              </div>
              <h3 className="text-xs font-bold text-[var(--text-primary)] group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                {item.title}
              </h3>
              <p className="text-[11px] text-[var(--text-secondary)] mt-1 leading-relaxed">
                {item.description}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition">
              <span>Use prompt template</span>
              <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
