'use client'

import React, { useMemo } from 'react'
import { Code2, FileText, Sparkles, Compass, ArrowRight } from 'lucide-react'
import { UsageStatus } from '@/types/api'

interface EmptyStateProps {
  userName?: string
  usage?: UsageStatus | null
  onOpenUsageModal?: () => void
  onSelectPrompt: (promptText: string) => void
}

interface QuickStartCard {
  id: string
  title: string
  description: string
  prompt: string
  icon: React.ReactNode
  iconBg: string
}

export function EmptyState({
  userName,
  usage,
  onOpenUsageModal,
  onSelectPrompt,
}: EmptyStateProps) {
  const timeOfDay = useMemo(() => {
    const hour = new Date().getHours()
    if (hour < 12) return 'morning'
    if (hour < 17) return 'afternoon'
    return 'evening'
  }, [])

  const remaining = usage ? usage.remaining : 30

  const quickCards: QuickStartCard[] = [
    {
      id: 'script',
      title: 'Write a script',
      description: 'Write a TypeScript script or algorithm that fetches data from an API and processes it.',
      prompt: 'Write a clean, optimized TypeScript script that fetches data from a REST API, handles errors and rate limits gracefully, and parses the result with full typing.',
      icon: <Code2 size={16} className="text-amber-600 dark:text-amber-400" />,
      iconBg: 'bg-amber-500/10 dark:bg-amber-400/10 border-amber-500/20',
    },
    {
      id: 'analyze',
      title: 'Analyze document',
      description: 'Analyze study materials or notes and provide a comprehensive summary with key insights.',
      prompt: 'Summarize the following topic into a high-yield study sheet with core definitions, formulas, and common exam traps:',
      icon: <FileText size={16} className="text-emerald-600 dark:text-emerald-400" />,
      iconBg: 'bg-emerald-500/10 dark:bg-emerald-400/10 border-emerald-500/20',
    },
    {
      id: 'brainstorm',
      title: 'Brainstorm ideas',
      description: 'Build intuition with first-principles mental models, real-world analogies, and thought experiments.',
      prompt: 'Explain the core intuition behind this concept from first principles with a real-world analogy and key misconceptions:',
      icon: <Sparkles size={16} className="text-amber-500 dark:text-amber-300" />,
      iconBg: 'bg-amber-500/10 dark:bg-amber-300/10 border-amber-500/20',
    },
    {
      id: 'research',
      title: 'Research topic',
      description: 'Provide a comprehensive research overview, step-by-step mathematical proofs, and derivations.',
      prompt: 'Provide a rigorous, step-by-step derivation for this theorem or formula, explaining the mathematical reasoning behind each transition:',
      icon: <Compass size={16} className="text-teal-600 dark:text-teal-400" />,
      iconBg: 'bg-teal-500/10 dark:bg-teal-400/10 border-teal-500/20',
    },
  ]

  return (
    <div className="w-full max-w-2xl mx-auto px-4 py-8 sm:py-14 text-center select-none">
      {/* Top Status Capsule Pill */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[11px] font-medium text-[var(--text-secondary)] mb-6 shadow-xs backdrop-blur-md">
        <span>Free Plan</span>
        <span className="text-[var(--text-muted)]">·</span>
        <button
          onClick={onOpenUsageModal}
          className="text-[var(--text-primary)] hover:text-emerald-600 dark:hover:text-emerald-400 font-semibold transition cursor-pointer"
        >
          {remaining} of {usage?.limit ?? 30} left
        </button>
      </div>

      {/* Hero Greeting in Lora */}
      <h1 className="text-3xl sm:text-5xl font-medium tracking-tight text-[var(--text-primary)] mb-3 leading-tight">
        Good {timeOfDay}, {userName || 'Scholar'}
      </h1>

      <p className="text-xs sm:text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-10 leading-relaxed">
        What difficult concept, mathematical proof, or study problem shall we tackle together?
      </p>

      {/* Quick Start Section */}
      <div className="text-left max-w-2xl mx-auto">
        <div className="text-[11px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-3 px-1">
          Quick Start
        </div>

        {/* 2x2 Clean Glassmorphism Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-3.5">
          {quickCards.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelectPrompt(item.prompt)}
              className="group p-4 rounded-2xl glass-card text-left cursor-pointer flex flex-col justify-between"
            >
              <div className="flex items-start gap-3">
                <div
                  className={`w-9 h-9 rounded-xl border flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-105 ${item.iconBg}`}
                >
                  {item.icon}
                </div>
                <div className="min-w-0">
                  <h3 className="text-xs font-bold text-[var(--text-primary)] group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                    {item.title}
                  </h3>
                  <p className="text-[11px] text-[var(--text-secondary)] mt-1 leading-relaxed line-clamp-2">
                    {item.description}
                  </p>
                </div>
              </div>

              <div className="mt-3 pt-2.5 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition">
                <span>Start with template</span>
                <ArrowRight
                  size={12}
                  className="group-hover:translate-x-1 transition-transform"
                />
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
