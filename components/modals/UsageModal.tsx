'use client'

import React, { useMemo } from 'react'
import { X, Clock, ShieldCheck, Info } from 'lucide-react'
import { UsageStatus } from '@/types/api'

interface UsageModalProps {
  isOpen: boolean
  onClose: () => void
  usage: UsageStatus | null
}

export function UsageModal({ isOpen, onClose, usage }: UsageModalProps) {
  if (!isOpen) return null

  const used = usage ? usage.used : 0
  const limit = usage ? usage.limit : 30
  const remaining = usage ? usage.remaining : 30
  const windowHours = usage ? usage.window_hours : 8

  // Calculate remaining time countdown
  const resetInfo = useMemo(() => {
    if (!usage?.reset_at) return { timeStr: 'N/A', countdownStr: '' }
    try {
      const resetTime = new Date(usage.reset_at)
      const now = new Date()
      const diffMs = resetTime.getTime() - now.getTime()

      const timeStr = resetTime.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })

      if (diffMs <= 0) {
        return { timeStr, countdownStr: 'due to reset now' }
      }

      const diffMins = Math.floor(diffMs / 60000)
      const hours = Math.floor(diffMins / 60)
      const mins = diffMins % 60

      const countdownStr = hours > 0 ? `in ${hours}h ${mins}m` : `in ${mins} minutes`
      return { timeStr, countdownStr }
    } catch {
      return { timeStr: 'N/A', countdownStr: '' }
    }
  }, [usage])

  const percentage = Math.min(100, Math.round((used / limit) * 100))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-md rounded-3xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 shadow-[var(--card-shadow)] text-[var(--text-primary)]"
        role="dialog"
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-emerald-500" />
            <h3 className="font-bold text-sm text-[var(--text-primary)]">8-Hour Message Quota</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Quota Progress */}
        <div className="py-5 space-y-4">
          <div className="flex items-baseline justify-between">
            <div>
              <span className="text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">{used}</span>
              <span className="text-[var(--text-muted)] text-sm ml-1">/ {limit} used</span>
            </div>
            <div className="text-right">
              <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">{remaining}</span>
              <span className="text-xs text-[var(--text-muted)] ml-1">remaining</span>
            </div>
          </div>

          <div className="w-full h-2 rounded-full bg-[var(--bg-surface-elevated)] overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                percentage >= 100
                  ? 'bg-rose-500'
                  : percentage >= 80
                  ? 'bg-amber-500'
                  : 'bg-emerald-500'
              }`}
              style={{ width: `${percentage}%` }}
            />
          </div>

          {/* Reset Details Card */}
          <div className="p-3.5 rounded-2xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] space-y-1.5 text-xs">
            <div className="flex justify-between text-[var(--text-secondary)]">
              <span>Quota Window:</span>
              <span className="text-[var(--text-primary)] font-semibold">{windowHours} Hours</span>
            </div>
            <div className="flex justify-between text-[var(--text-secondary)]">
              <span>Next Reset:</span>
              <span className="text-[var(--text-primary)] font-semibold">
                {resetInfo.timeStr} {resetInfo.countdownStr && `(${resetInfo.countdownStr})`}
              </span>
            </div>
          </div>

          {/* Educational Policy Notice */}
          <div className="flex items-start gap-2.5 p-3 rounded-2xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[11px] text-[var(--text-secondary)] leading-relaxed">
            <Info size={14} className="text-[var(--text-muted)] flex-shrink-0 mt-0.5" />
            <p>
              Every student gets 30 high-yield AI queries every 8 hours. This quota is enforced server-side
              across all your sessions to guarantee high-speed, reliable responses during peak exam seasons.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-2">
          <button
            onClick={onClose}
            className="w-full py-2.5 px-4 rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-xs font-semibold hover:opacity-90 transition cursor-pointer"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  )
}
