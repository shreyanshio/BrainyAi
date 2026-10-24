'use client'

import React, { useEffect, useRef, useState } from 'react'
import { ArrowRight, ExternalLink, LoaderCircle } from 'lucide-react'
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

const GoogleIcon = ({ className = 'h-5 w-5' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
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

const TelegramIcon = ({ className = 'h-5 w-5' }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.01.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
  </svg>
)

const DEFAULT_GOOGLE_CLIENT_ID =
  '793579888403-76l0ls9vr4jjrjshmmdbue6apsiabhpk.apps.googleusercontent.com'

export function LoginView({ onLoginSuccess }: LoginViewProps) {
  const [googleClientId, setGoogleClientId] = useState<string>(
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || DEFAULT_GOOGLE_CLIENT_ID
  )
  const [googleBtnRendered, setGoogleBtnRendered] = useState(false)
  const [error, setError] = useState('')
  const [telegramWaiting, setTelegramWaiting] = useState(false)
  const [telegramSessionId, setTelegramSessionId] = useState<string | null>(null)
  const [telegramBotUrl, setTelegramBotUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const googleInitInterval = useRef<number | null>(null)
  const googleResizeObserver = useRef<ResizeObserver | null>(null)
  const initializedGoogleClientId = useRef('')

  const handleGoogleCallback = async (response: { credential?: string }) => {
    if (!response?.credential) {
      setError('Google did not return a sign-in credential. Please try again or use Telegram.')
      return
    }

    setIsSubmitting(true)
    setError('')
    try {
      const user = await loginWithGoogle(response.credential)
      onLoginSuccess(user)
    } catch (err: unknown) {
      console.error('Google verification error:', err)
      setError(err instanceof Error ? err.message : 'Google verification failed. Please try again or use Telegram.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const setupGoogleButton = (clientId: string) => {
    if (!clientId || typeof window === 'undefined') return

    if (googleInitInterval.current !== null) {
      window.clearInterval(googleInitInterval.current)
      googleInitInterval.current = null
    }
    googleResizeObserver.current?.disconnect()
    googleResizeObserver.current = null

    let attempts = 0
    const maxAttempts = 30

    const tryInitialize = () => {
      const google = (window as any).google
      const target = document.getElementById('google-signin-btn-target')
      if (!google?.accounts?.id || !target) return false

      try {
        if (initializedGoogleClientId.current !== clientId) {
          google.accounts.id.initialize({
            client_id: clientId,
            callback: handleGoogleCallback,
            auto_select: false,
            itp_support: true,
            use_fedcm_for_prompt: false,
          })
          initializedGoogleClientId.current = clientId
        }

        let renderedWidth = 0
        const renderButton = () => {
          const width = Math.max(200, Math.min(400, Math.floor(target.clientWidth || 320)))
          if (width === renderedWidth) return
          renderedWidth = width
          target.innerHTML = ''
          google.accounts.id.renderButton(target, {
            type: 'standard',
            theme: 'outline',
            size: 'large',
            text: 'continue_with',
            shape: 'rectangular',
            width,
            logo_alignment: 'left',
          })
          setGoogleBtnRendered(true)
        }

        renderButton()
        if (typeof ResizeObserver !== 'undefined') {
          googleResizeObserver.current = new ResizeObserver(renderButton)
          googleResizeObserver.current.observe(target)
        }
        return true
      } catch (initError) {
        console.error('Google button init error:', initError)
        return false
      }
    }

    if (tryInitialize()) return

    googleInitInterval.current = window.setInterval(() => {
      attempts += 1
      if (tryInitialize() || attempts >= maxAttempts) {
        if (googleInitInterval.current !== null) {
          window.clearInterval(googleInitInterval.current)
          googleInitInterval.current = null
        }
      }
    }, 200)
  }

  // Load public Google config and initialize the existing Google Identity Services button.
  useEffect(() => {
    let mounted = true

    const initialize = async () => {
      const urlParams = new URLSearchParams(window.location.search)
      if (urlParams.has('auth_error')) {
        setError('Google sign-in was cancelled or could not be completed. Please try again or use Telegram.')
        window.history.replaceState({}, document.title, window.location.pathname)
      }

      const activeClientId = googleClientId || DEFAULT_GOOGLE_CLIENT_ID
      setupGoogleButton(activeClientId)

      try {
        const config = await fetchPublicConfig()
        if (mounted && config.google_client_id && config.google_client_id !== activeClientId) {
          setGoogleClientId(config.google_client_id)
          setupGoogleButton(config.google_client_id)
        }
      } catch (configError) {
        console.warn('Could not fetch public auth config:', configError instanceof Error ? configError.name : 'unknown error')
      }
    }

    void initialize()
    return () => {
      mounted = false
      if (googleInitInterval.current !== null) {
        window.clearInterval(googleInitInterval.current)
        googleInitInterval.current = null
      }
      googleResizeObserver.current?.disconnect()
      googleResizeObserver.current = null
    }
    // Google Identity Services is initialized once on mount; a config response can replace its client ID.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Preserve the current Telegram session handshake and polling contract.
  useEffect(() => {
    if (!telegramWaiting || !telegramSessionId) return

    let active = true
    let requestInFlight = false
    const poll = window.setInterval(async () => {
      if (requestInFlight) return
      requestInFlight = true
      try {
        const result = await pollTelegramLogin(telegramSessionId)
        if (!active) return
        if (result.status === 'authenticated' && result.user) {
          window.clearInterval(poll)
          setTelegramWaiting(false)
          setTelegramSessionId(null)
          onLoginSuccess(result.user)
        }
      } catch (pollError) {
        console.warn('Telegram login polling failed:', pollError instanceof Error ? pollError.name : 'unknown error')
      } finally {
        requestInFlight = false
      }
    }, 2000)

    return () => {
      active = false
      window.clearInterval(poll)
    }
  }, [telegramWaiting, telegramSessionId, onLoginSuccess])

  const handleGoogleFallback = () => {
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

  const handleStartTelegram = async () => {
    setError('')
    setIsSubmitting(true)
    try {
      const data = await initTelegramLogin()
      const botUrl = data.bot_url || 'https://t.me/AiChatExpert_Bot'
      setTelegramSessionId(data.session_id)
      setTelegramBotUrl(botUrl)
      setTelegramWaiting(true)
      window.open(botUrl, '_blank', 'noopener,noreferrer')
    } catch (telegramError: unknown) {
      setError(telegramError instanceof Error ? telegramError.message : 'Could not connect to Telegram sign-in.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-root">
      <div className="login-page-frame">
        <header className="login-header">
          <a href="/" aria-label="Brainy home" className="login-brand">
            <span className="login-brand-mark" aria-hidden="true">B</span>
            <span>Brainy<span className="login-brand-period">.</span></span>
          </a>
          <span className="login-header-note">A study space, in good order</span>
        </header>

        <div className="login-layout">
          <section className="login-story" aria-labelledby="login-heading">
            <p className="login-eyebrow"><span /> Learn with clarity</p>
            <h1 id="login-heading" className="login-display">
              Turn study material <em>into understanding.</em>
            </h1>
            <p className="login-intro">
              Ask better questions, work through difficult ideas, and keep your study conversations organised as you learn.
            </p>

            <div className="login-study-preview" aria-label="Illustrative biology study note and review question">
              <div className="login-preview-topline">
                <span>STUDY NOTE <span className="login-preview-dot">/</span> BIOLOGY</span>
                <span>MEMBRANE TRANSPORT</span>
              </div>
              <div className="login-preview-content">
                <div className="login-source-marker" aria-hidden="true">
                  <span>03</span>
                  <span>TOPIC</span>
                </div>
                <div className="login-note-copy">
                  <p className="login-note-label">A useful definition</p>
                  <h2>Selective permeability</h2>
                  <p>
                    A membrane is <mark>selectively permeable</mark> when it allows some substances to pass while restricting others.
                  </p>
                </div>
              </div>
              <div className="login-preview-question">
                <p className="login-question-label">CHECK YOUR UNDERSTANDING</p>
                <h3>Why does oxygen cross the lipid bilayer more easily than sodium?</h3>
                <div className="login-answer-options" aria-label="Sample answer choices">
                  <span><b>A</b> It is small and nonpolar</span>
                  <span><b>B</b> It carries a positive charge</span>
                  <span><b>C</b> It is surrounded by water</span>
                  <span><b>D</b> It binds to a membrane protein</span>
                </div>
              </div>
              <p className="login-preview-caption">Illustrative study example</p>
            </div>
          </section>

          <section className="login-auth" aria-labelledby="auth-heading" aria-busy={isSubmitting}>
            <div className="login-auth-heading">
              <p className="login-auth-kicker">YOUR STUDY SPACE</p>
              <h2 id="auth-heading">Welcome back.</h2>
              <p>Sign in to pick up where your learning left off.</p>
            </div>

            <div className="login-error-slot" aria-live="assertive">
              {error && <p role="alert" className="login-error">{error}</p>}
            </div>

            {telegramWaiting ? (
              <div className="login-telegram-wait" aria-live="polite">
                <div className="login-telegram-wait-title">
                  <TelegramIcon className="h-5 w-5" />
                  <h3>Finish in Telegram</h3>
                </div>
                <p>
                  Open the BrainyAi bot, send <code>/login</code>, then tap <strong>Authorize Web Login</strong>.
                </p>
                <a
                  href={telegramBotUrl || 'https://t.me/AiChatExpert_Bot'}
                  target="_blank"
                  rel="noreferrer"
                  className="login-provider-button login-provider-secondary"
                >
                  <span>Open Telegram bot</span>
                  <ExternalLink size={15} aria-hidden="true" />
                </a>
                <button
                  type="button"
                  onClick={() => {
                    setTelegramWaiting(false)
                    setTelegramSessionId(null)
                  }}
                  className="login-cancel"
                >
                  Cancel sign-in
                </button>
              </div>
            ) : (
              <div className="login-providers">
                <button
                  type="button"
                  onClick={handleStartTelegram}
                  disabled={isSubmitting}
                  className="login-provider-button login-provider-secondary"
                  aria-label="Continue with Telegram"
                >
                  {isSubmitting ? <LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" /> : <TelegramIcon className="h-5 w-5 text-sky-600" />}
                  <span>{isSubmitting ? 'Connecting to Telegram…' : 'Continue with Telegram'}</span>
                  {!isSubmitting && <ArrowRight size={15} className="login-provider-arrow" aria-hidden="true" />}
                </button>

                <div className="login-divider" aria-hidden="true"><span>or</span></div>

                <div
                  id="google-signin-btn-target"
                  className={`login-google-target${googleBtnRendered ? ' is-rendered' : ''}`}
                  aria-label="Google sign-in"
                  aria-busy={!googleBtnRendered}
                />

                {!googleBtnRendered && (
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={handleGoogleFallback}
                    className="login-provider-button login-provider-google"
                  >
                    {isSubmitting ? <LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" /> : <GoogleIcon />}
                    <span>{isSubmitting ? 'Connecting to Google…' : 'Continue with Google'}</span>
                    {!isSubmitting && <ArrowRight size={15} className="login-provider-arrow" aria-hidden="true" />}
                  </button>
                )}

                <p className="login-auth-note">Use your existing Google or Telegram account.</p>
              </div>
            )}

            <div className="login-auth-footnote">
              <span className="login-footnote-rule" />
              <p>Your conversations stay part of your study routine.</p>
            </div>
          </section>
        </div>

        <footer className="login-footer">
          <span>Brainy</span>
          <span>Thoughtful tools for learning.</span>
        </footer>
      </div>
    </main>
  )
}
