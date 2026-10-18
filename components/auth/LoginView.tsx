'use client'

import React, { useState, useEffect, useRef } from 'react'
import { ExternalLink, CheckCircle2, Lock, ArrowRight, Sparkles } from 'lucide-react'
import {
  fetchPublicConfig,
  initTelegramLogin,
  loginWithGoogle,
  pollTelegramLogin,
} from '@/lib/api'
import { User } from '@/types/api'

interface LoginViewProps {
  onLoginSuccess: (user: User) => void
}

const GoogleIcon = ({ className = 'w-5 h-5' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
    />
  </svg>
)

const TelegramIcon = ({ className = 'w-5 h-5' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
  </svg>
)

const DEFAULT_GOOGLE_CLIENT_ID = '793579888403-76l0ls9vr4jjrjshmmdbue6apsiabhpk.apps.googleusercontent.com'

export function LoginView({ onLoginSuccess }: LoginViewProps) {
  const sceneRef = useRef<HTMLDivElement>(null)
  const [googleClientId, setGoogleClientId] = useState<string>(
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || DEFAULT_GOOGLE_CLIENT_ID
  )
  const [googleBtnRendered, setGoogleBtnRendered] = useState(false)
  const [error, setError] = useState<string>('')
  const [telegramWaiting, setTelegramWaiting] = useState(false)
  const [telegramSessionId, setTelegramSessionId] = useState<string | null>(null)
  const [telegramBotUrl, setTelegramBotUrl] = useState<string>('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Load public Google Client ID and initialize GIS
  useEffect(() => {
    let mounted = true
    const init = async () => {
      if (typeof window !== 'undefined') {
        const urlParams = new URLSearchParams(window.location.search)
        const authErr = urlParams.get('auth_error')
        if (authErr) {
          setError('Google authentication was cancelled or failed. Please try again or use Telegram.')
          window.history.replaceState({}, document.title, window.location.pathname)
        }
      }

      const activeClientId = googleClientId || DEFAULT_GOOGLE_CLIENT_ID
      if (activeClientId) {
        setupGoogleButton(activeClientId)
      }

      try {
        const cfg = await fetchPublicConfig()
        if (mounted && cfg.google_client_id && cfg.google_client_id !== activeClientId) {
          setGoogleClientId(cfg.google_client_id)
          setupGoogleButton(cfg.google_client_id)
        }
      } catch (err) {
        console.warn('Could not fetch public config from backend:', err)
      }
    }
    init()
    return () => {
      mounted = false
    }
  }, [])

  const setupGoogleButton = (clientId: string) => {
    if (!clientId) return
    let attempts = 0
    const maxAttempts = 30
    const checkGSI = setInterval(() => {
      attempts++
      const g = (window as any).google
      if (g?.accounts?.id) {
        clearInterval(checkGSI)
        try {
          g.accounts.id.initialize({
            client_id: clientId,
            callback: handleGoogleCallback,
            auto_select: false,
            itp_support: true,
            use_fedcm_for_prompt: false,
          })
          const target = document.getElementById('google-signin-btn-target')
          if (target) {
            target.innerHTML = ''
            g.accounts.id.renderButton(target, {
              type: 'standard',
              theme: 'outline',
              size: 'large',
              text: 'continue_with',
              shape: 'rectangular',
              width: 320,
              logo_alignment: 'left',
            })
            setGoogleBtnRendered(true)
          }
        } catch (e) {
          console.error('Google button init error:', e)
        }
      } else if (attempts >= maxAttempts) {
        clearInterval(checkGSI)
      }
    }, 200)
  }

  const handleGoogleButtonClick = () => {
    setError('')
    setIsSubmitting(true)
    const activeClientId = googleClientId || DEFAULT_GOOGLE_CLIENT_ID
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${encodeURIComponent(
      activeClientId
    )}&response_type=token&scope=${encodeURIComponent(
      'openid email profile'
    )}&redirect_uri=${encodeURIComponent('https://brainyai.up.railway.app')}&prompt=select_account`

    window.location.href = authUrl
  }

  const handleGoogleCallback = async (response: any) => {
    if (!response?.credential) {
      setError('No credential received from Google. Please try again.')
      return
    }
    setIsSubmitting(true)
    setError('')
    try {
      const user = await loginWithGoogle(response.credential)
      onLoginSuccess(user)
    } catch (err: any) {
      console.error('Google verification error:', err)
      setError(err?.message || 'Google verification failed. Please try again or use Continue with Telegram.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Telegram auth handshake polling
  useEffect(() => {
    if (!telegramWaiting || !telegramSessionId) return

    const poll = setInterval(async () => {
      try {
        const res = await pollTelegramLogin(telegramSessionId)
        if (res.status === 'authenticated' && res.user) {
          clearInterval(poll)
          setTelegramWaiting(false)
          setTelegramSessionId(null)
          onLoginSuccess(res.user)
        }
      } catch (err) {
        console.warn('Telegram login polling failed:', err instanceof Error ? err.name : 'unknown error')
      }
    }, 2000)

    return () => clearInterval(poll)
  }, [telegramWaiting, telegramSessionId, onLoginSuccess])

  const handleStartTelegram = async () => {
    setError('')
    setIsSubmitting(true)
    try {
      const data = await initTelegramLogin()
      const botUrl = data.bot_url || 'https://t.me/AiChatExpert_Bot'
      setTelegramSessionId(data.session_id)
      setTelegramBotUrl(botUrl)
      setTelegramWaiting(true)
      window.open(botUrl, '_blank')
    } catch (err: any) {
      setError(err?.message || 'Could not connect to Telegram authentication.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleScenePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - bounds.left) / bounds.width - 0.5
    const y = (event.clientY - bounds.top) / bounds.height - 0.5
    sceneRef.current?.style.setProperty('--scene-rotate-x', `${-y * 6}deg`)
    sceneRef.current?.style.setProperty('--scene-rotate-y', `${x * 8}deg`)
  }

  const resetScenePointer = () => {
    sceneRef.current?.style.setProperty('--scene-rotate-x', '0deg')
    sceneRef.current?.style.setProperty('--scene-rotate-y', '0deg')
  }

  return (
    <main className="min-h-screen text-[var(--text-primary)] ambient-canvas relative overflow-hidden px-5 py-8 sm:px-8 lg:px-14 flex flex-col justify-between">
      <div className="login-grain" aria-hidden="true" />

      {/* Top Header */}
      <header className="relative z-10 mx-auto w-full max-w-7xl flex items-center justify-between">
        <a href="/" aria-label="Brainy home" className="inline-flex items-center gap-3 no-underline group">
          <div className="w-8 h-8 rounded-xl bg-[var(--text-primary)] text-[var(--bg-app)] flex items-center justify-center font-bold text-sm shadow-xs transition-transform group-hover:scale-105">
            B
          </div>
          <span className="text-lg font-bold tracking-tight text-[var(--text-primary)]">
            Brainy<span className="text-emerald-500">.</span>
          </span>
        </a>

        <div className="hidden sm:inline-flex items-center gap-2 rounded-full glass-panel px-4 py-1.5 text-xs text-[var(--text-secondary)] shadow-xs">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          <span>Personal AI Study Companion</span>
        </div>
      </header>

      {/* Main Two-Area Content Grid */}
      <div className="relative z-10 mx-auto w-full max-w-7xl grid flex-1 items-center gap-12 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16 lg:py-16">
        
        {/* Left Area: Hero Narrative & Interactive Perspective Centerpiece */}
        <section className="min-w-0" aria-labelledby="login-heading">
          <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-400 mb-4">
            <Sparkles size={13} aria-hidden="true" />
            <span>Intuitive Academic Workspace</span>
          </div>

          <h1
            id="login-heading"
            className="text-4xl sm:text-6xl lg:text-7xl font-medium leading-[1.05] tracking-tight text-[var(--text-primary)] max-w-2xl"
          >
            Make room for <span className="italic text-emerald-600 dark:text-emerald-400">understanding.</span>
          </h1>

          <p className="mt-6 max-w-xl text-sm sm:text-base leading-relaxed text-[var(--text-secondary)]">
            A quiet space to ask difficult conceptual questions, derive formulas step-by-step, review code, and build durable mastery that stays with you.
          </p>

          {/* Interactive Perspective Scene */}
          <div
            ref={sceneRef}
            className="login-scene mt-8 hidden min-h-[260px] sm:block cursor-default"
            onPointerMove={handleScenePointerMove}
            onPointerLeave={resetScenePointer}
            aria-label="An interactive study workspace illustration"
          >
            <div className="login-orbit login-orbit-one" aria-hidden="true" />
            <div className="login-orbit login-orbit-two" aria-hidden="true" />
            <div className="login-scene-glow" aria-hidden="true" />
            <div className="login-book login-book-back" aria-hidden="true">
              <span /><span /><span />
            </div>
            <div className="login-book login-book-front" aria-hidden="true">
              <span /><span /><span /><span />
            </div>
            <div className="login-study-card" aria-hidden="true">
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-emerald-300">
                <span>Active Recall</span>
                <span className="login-card-spark">✳</span>
              </div>
              <div className="mt-4 h-2 w-2/3 rounded-full bg-white/70" />
              <div className="mt-2.5 h-1.5 w-full rounded-full bg-white/20" />
              <div className="mt-2 h-1.5 w-4/5 rounded-full bg-white/20" />
              <div className="mt-4 flex items-center gap-2 text-[11px] text-stone-200">
                <span className="h-5 w-5 rounded-md bg-emerald-400/20 text-center leading-5 text-emerald-200">
                  ∑
                </span>
                Concepts, made clear
              </div>
            </div>
            <div className="login-orbit-dot" aria-hidden="true">
              <Sparkles size={16} />
            </div>
          </div>

          {/* Value Highlights */}
          <div className="mt-8 hidden flex-wrap gap-x-6 gap-y-2.5 text-xs text-[var(--text-secondary)] sm:flex">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-emerald-500" />
              Conversations saved to Supabase
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-emerald-500" />
              Step-by-step mathematical proofs
            </span>
          </div>
        </section>

        {/* Right Area: Minimalist Glassmorphic Auth Panel */}
        <section className="mx-auto w-full max-w-md" aria-labelledby="auth-heading">
          <div className="rounded-3xl glass-panel p-6 sm:p-8 shadow-2xl relative">
            <div className="mb-6">
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-400 mb-1">
                Welcome back
              </div>
              <h2 id="auth-heading" className="text-2xl sm:text-3xl font-medium tracking-tight text-[var(--text-primary)]">
                Continue learning
              </h2>
              <p className="mt-2 text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                Sign in to return to your study chats, notes, and personal memory context.
              </p>
            </div>

            {error && (
              <div role="alert" className="mb-5 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3.5 text-xs leading-relaxed text-rose-600 dark:text-rose-400">
                {error}
              </div>
            )}

            {telegramWaiting ? (
              <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] p-5 text-center">
                <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <TelegramIcon className="h-6 w-6" />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-[var(--text-primary)]">
                  Waiting for Telegram Handshake
                </h3>
                <p className="mt-1.5 text-xs text-[var(--text-secondary)] leading-relaxed">
                  Open the bot, send <code className="rounded bg-[var(--bg-surface)] px-1.5 py-0.5 font-mono text-[11px]">/login</code>, then tap &ldquo;Authorize Web Login&rdquo;.
                </p>
                <a
                  href={telegramBotUrl || 'https://t.me/AiChatExpert_Bot'}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-[var(--text-primary)] text-[var(--bg-app)] text-xs font-semibold shadow-xs hover:opacity-90 transition"
                >
                  <span>Open Telegram Bot</span>
                  <ExternalLink size={13} />
                </a>
                <button
                  type="button"
                  onClick={() => {
                    setTelegramWaiting(false)
                    setTelegramSessionId(null)
                  }}
                  className="mt-3 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition cursor-pointer underline-offset-4 hover:underline"
                >
                  Cancel sign-in
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Continue with Telegram */}
                <button
                  type="button"
                  onClick={handleStartTelegram}
                  disabled={isSubmitting}
                  className="w-full flex items-center justify-center gap-2.5 py-3 px-4 rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] text-xs sm:text-sm font-semibold text-[var(--text-primary)] transition cursor-pointer shadow-xs disabled:opacity-50"
                  aria-label="Continue with Telegram"
                >
                  <TelegramIcon className="h-5 w-5 text-sky-500" />
                  <span>Continue with Telegram</span>
                  <ArrowRight size={14} className="ml-auto text-[var(--text-muted)]" />
                </button>

                <div className="flex items-center gap-3 py-1.5" aria-hidden="true">
                  <span className="h-px flex-1 bg-[var(--border-subtle)]" />
                  <span className="text-[10px] uppercase tracking-widest text-[var(--text-muted)] font-medium">or</span>
                  <span className="h-px flex-1 bg-[var(--border-subtle)]" />
                </div>

                {/* Google Sign-in Target */}
                <div id="google-signin-btn-target" className="flex min-h-11 w-full justify-center" />

                {/* Google Fallback Button */}
                {!googleBtnRendered && (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={handleGoogleButtonClick}
                    className="w-full flex items-center justify-center gap-2.5 py-3 px-4 rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] text-xs sm:text-sm font-semibold text-[var(--text-primary)] transition cursor-pointer shadow-xs disabled:opacity-50"
                  >
                    <GoogleIcon className="h-5 w-5" />
                    <span>{isSubmitting ? 'Connecting to Google…' : 'Continue with Google'}</span>
                    <ArrowRight size={14} className="ml-auto text-[var(--text-muted)]" />
                  </button>
                )}

                <p className="pt-2 text-center text-[11px] leading-relaxed text-[var(--text-muted)]">
                  Instant sign-in · No passwords required
                </p>
              </div>
            )}

            <div className="mt-6 flex items-center justify-center gap-2 border-t border-[var(--border-subtle)] pt-4 text-[11px] text-[var(--text-muted)]">
              <Lock size={12} aria-hidden="true" />
              <span>Isolated study context & private memory</span>
            </div>
          </div>
        </section>
      </div>

      {/* Footer */}
      <footer className="relative z-10 mx-auto w-full max-w-7xl text-center text-[11px] text-[var(--text-muted)] pt-4">
        © 2026 BrainyAi · Precision academic intelligence
      </footer>
    </main>
  )
}
