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
      return <Lightbulb size={16} className="text-amber-400" />
    case 'problem':
      return <Target size={16} className="text-indigo-400" />
    case 'code':
      return <Code2 size={16} className="text-emerald-400" />
    case 'exam':
      return <Sparkles size={16} className="text-rose-400" />
    default:
      return <Lightbulb size={16} className="text-zinc-400" />
  }
}

export function EmptyState({ onSelectPrompt }: EmptyStateProps) {
  return (
    <div className="w-full max-w-2xl mx-auto px-4 py-12 sm:py-16 text-center">
      <div className="w-10 h-10 mx-auto mb-4 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-white text-base shadow-sm">
        B
      </div>

      <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mb-2">
        What are you studying today?
      </h2>

      <p className="text-xs sm:text-sm text-zinc-400 max-w-md mx-auto mb-8 leading-relaxed">
        Ask conceptual doubts, step-by-step mathematical proofs, code reviews, or exam-style drills.
      </p>

      {/* 2x2 Clean Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
        {STUDY_QUICK_PROMPTS.map((item: QuickPrompt) => (
          <button
            key={item.id}
            onClick={() => onSelectPrompt(item.prompt)}
            className="group p-4 rounded-xl bg-[#10121a] hover:bg-[#141722] border border-zinc-800/80 hover:border-zinc-700 transition flex flex-col justify-between text-left"
          >
            <div>
              <div className="w-8 h-8 rounded-lg bg-zinc-800/80 border border-zinc-700/60 flex items-center justify-center mb-3">
                {getCategoryIcon(item.category)}
              </div>
              <h3 className="text-xs font-semibold text-zinc-100 group-hover:text-white transition">
                {item.title}
              </h3>
              <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
                {item.description}
              </p>
            </div>

            <div className="mt-4 flex items-center gap-1 text-[11px] text-zinc-500 group-hover:text-zinc-300 transition">
              <span>Use template</span>
              <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
