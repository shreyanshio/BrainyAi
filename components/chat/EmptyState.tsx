'use client'

import React, { useMemo } from 'react'

interface EmptyStateProps {
  userName?: string
}

export function EmptyState({ userName }: EmptyStateProps) {
  const timeOfDay = useMemo(() => {
    const hour = new Date().getHours()
    if (hour < 12) return 'morning'
    if (hour < 17) return 'afternoon'
    return 'evening'
  }, [])

  return (
    <div className="w-full max-w-2xl mx-auto px-4 py-6 sm:py-14 text-center select-none">
      <h1 className="text-2xl sm:text-4xl md:text-5xl font-medium tracking-tight text-[var(--text-primary)] leading-tight">
        Good {timeOfDay}, {userName || 'Scholar'}
      </h1>
      <p className="text-xs sm:text-sm text-[var(--text-muted)] mt-2 sm:mt-3 max-w-md mx-auto">
        Ask any academic concept, formula derivation, code question, or upload course PDFs to start studying.
      </p>
    </div>
  )
}
