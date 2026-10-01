'use client'

import React, { useState, useEffect } from 'react'
import { ExternalLink, ShieldCheck, ArrowRight, CheckCircle2, Lock } from 'lucide-react'
import {
  fetchPublicConfig,
  initTelegramLogin,
  loginWithGoogle,
  loginStudentPass,
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

export function LoginView({ onLoginSuccess }: LoginViewProps) {
  const [googleClientId, setGoogleClientId] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [telegramWaiting, setTelegramWaiting] = useState(false)
  const [telegramSessionId, setTelegramSessionId] = useState<string | null>(null)
  const [telegramBotUrl, setTelegramBotUrl] = useState<string>('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Load public Google Client ID and initialize GIS
  useEffect(() => {
    let mounted = true
    const init = async () => {
      const cfg = await fetchPublicConfig()
      if (mounted && cfg.google_client_id) {
        setGoogleClientId(cfg.google_client_id)
        setupGoogleButton(cfg.google_client_id)
      }
    }
    init()
    return () => {
      mounted = false
    }
  }, [])

  const setupGoogleButton = (clientId: string) => {
    const checkGSI = setInterval(() => {
      const g = (window as any).google
      if (g?.accounts?.id) {
        clearInterval(checkGSI)
        try {
          g.accounts.id.initialize({
            client_id: clientId,
            callback: handleGoogleCallback,
            auto_select: false,
          })
          const target = document.getElementById('google-signin-btn-target')
          if (target) {
            target.innerHTML = ''
            g.accounts.id.renderButton(target, {
              theme: 'filled_black',
              size: 'large',
              text: 'continue_with',
              shape: 'rectangular',
              width: 300,
            })
          }
        } catch (e) {
          console.error('Google button init error:', e)
        }
      }
    }, 250)

    setTimeout(() => clearInterval(checkGSI), 8000)
  }

  const handleGoogleCallback = async (response: any) => {
    if (!response?.credential) return
    setIsSubmitting(true)
    setError('')
    try {
      const user = await loginWithGoogle(response.credential)
      onLoginSuccess(user)
    } catch (err: any) {
      setError(err?.message || 'Google verification failed. Use Telegram or Student Pass.')
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
      } catch {
        // ignore network hiccups
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

  // 1-Click Secure Student Pass (Zero manual passwords or personal info required)
  const handleStudentPassLogin = async () => {
    setError('')
    setIsSubmitting(true)
    try {
      const user = await loginStudentPass()
      onLoginSuccess(user)
    } catch (err: any) {
      setError(err?.message || 'Could not generate student pass.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#040d07] text-[#f4fbf6] flex items-center justify-center p-4 sm:p-6 lg:p-8 font-sans antialiased relative overflow-hidden select-none">
      {/* Botanical Forest Background Decorative Radiants */}
      <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#059669]/15 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-[30rem] h-[30rem] bg-[#10b981]/10 rounded-full blur-[160px] pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[radial-gradient(ellipse_at_center,_rgba(4,24,14,0.7)_0%,_rgba(3,10,6,0.98)_100%)] pointer-events-none" />

      {/* Main Botanical Card (2-Column Layout Matching User Reference Image) */}
      <div className="w-full max-w-4xl rounded-2xl sm:rounded-3xl border border-[#143522] bg-[#07130b]/90 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.85),0_0_40px_-10px_rgba(5,150,105,0.18)] backdrop-blur-xl overflow-hidden relative z-10 flex flex-col md:flex-row">
        
        {/* Left Column: "Let's Get Started" Botanical Showcase */}
        <div className="md:w-1/2 p-8 sm:p-12 flex flex-col justify-between relative bg-gradient-to-b from-[#091f12]/80 via-[#07190e]/90 to-[#040f08]/95 border-b md:border-b-0 md:border-r border-[#143522]/80">
          {/* Subtle leafy botanical overlay */}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,_rgba(16,185,129,0.12),_transparent_65%)] pointer-events-none" />

          {/* Top Brand Tag */}
          <div className="flex items-center gap-2 relative z-10 mb-8 md:mb-0">
            <div className="w-7 h-7 rounded-lg bg-[#059669] border border-[#10b981]/40 flex items-center justify-center font-bold text-white text-xs shadow-md shadow-[#059669]/30">
              B
            </div>
            <span className="font-bold text-sm tracking-wide text-white uppercase">Brainy AI</span>
          </div>

          {/* Center Showcase Headline */}
          <div className="relative z-10 my-auto py-6">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-[1.15] mb-4">
              Let&apos;s Get <br />
              <span className="text-[#10b981]">Started</span>
            </h1>
            <p className="text-xs sm:text-sm text-[#8aa995] leading-relaxed max-w-sm">
              Your AI study companion. Master academic concepts, derive complex formulas, and retain knowledge with context.
            </p>

            <div className="mt-6 flex flex-col gap-2.5 text-xs text-[#a3cbb1]">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-[#10b981]" />
                <span>Zero manual entry of names or passwords</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-[#10b981]" />
                <span>Encrypted hash storage in Supabase</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-[#10b981]" />
                <span>30 high-yield questions every 8 hours</span>
              </div>
            </div>
          </div>

          {/* Bottom attribution badge matching user reference image */}
          <div className="relative z-10 pt-4 flex items-center gap-2">
            <div className="px-3 py-1 rounded-full bg-[#051a0e] border border-[#143522] flex items-center gap-1.5 text-[11px] text-[#8aa995]">
              <span>presented by</span>
              <strong className="text-white font-semibold">Brainy</strong>
            </div>
          </div>
        </div>

        {/* Right Column: Direct Secure Auth & Social Options (Matching Image Layout) */}
        <div className="md:w-1/2 p-8 sm:p-12 flex flex-col justify-between bg-[#06110a]/95 relative">
          <div>
            {/* Header */}
            <div className="mb-6">
              <h2 className="text-2xl font-bold tracking-tight text-white mb-1.5">Sign in</h2>
              <p className="text-xs text-[#8aa995]">
                Direct verified access — zero passwords or manual entries to leak.
              </p>
            </div>

            {error && (
              <div className="mb-5 p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs text-center leading-relaxed">
                {error}
              </div>
            )}

            {/* Telegram Waiting Handshake Mode */}
            {telegramWaiting ? (
              <div className="p-6 rounded-2xl bg-[#091b10] border border-[#143522] text-center space-y-4">
                <div className="w-14 h-14 mx-auto rounded-full bg-[#059669]/15 border border-[#10b981]/30 flex items-center justify-center text-[#10b981]">
                  <TelegramIcon className="w-7 h-7" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">
                    Waiting for @AiChatExpert_bot
                  </h3>
                  <p className="text-xs text-[#8aa995] leading-relaxed">
                    Open <strong className="text-white">@AiChatExpert_bot</strong> in Telegram, send{' '}
                    <code className="px-1.5 py-0.5 rounded bg-black/40 text-[#10b981] font-mono text-[11px]">
                      /login
                    </code>
                    , and tap <strong>&ldquo;Authorize Web Login&rdquo;</strong>.
                  </p>
                </div>

                <div className="pt-2 flex flex-col gap-2">
                  <a
                    href={telegramBotUrl || 'https://t.me/AiChatExpert_Bot'}
                    target="_blank"
                    rel="noreferrer"
                    className="w-full py-2.5 px-4 rounded-xl bg-[#059669] hover:bg-[#10b981] text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-lg shadow-[#059669]/20"
                  >
                    <span>Open @AiChatExpert_bot</span>
                    <ExternalLink size={13} />
                  </a>

                  <button
                    type="button"
                    onClick={() => {
                      setTelegramWaiting(false)
                      setTelegramSessionId(null)
                    }}
                    className="text-xs text-[#8aa995] hover:text-white py-1 transition underline"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              /* Normal Auth Actions (Matching the Split + Right Icons Design) */
              <div className="flex gap-4">
                {/* Left side of right column: Primary CTA Buttons */}
                <div className="flex-1 space-y-4">
                  {/* Primary Button: Continue with Telegram (@AiChatExpert_bot) */}
                  <button
                    type="button"
                    onClick={handleStartTelegram}
                    disabled={isSubmitting}
                    className="w-full py-3 px-4 rounded-xl bg-[#059669] hover:bg-[#10b981] active:bg-[#047857] text-white text-xs font-bold transition flex items-center justify-center gap-2.5 shadow-lg shadow-[#059669]/25 hover:shadow-[#059669]/40 cursor-pointer disabled:opacity-50"
                  >
                    <TelegramIcon className="w-4 h-4 text-white" />
                    <span>Continue with Telegram</span>
                  </button>

                  {/* Secondary: 1-Click Secure Student Pass (Zero Passwords) */}
                  <button
                    type="button"
                    onClick={handleStudentPassLogin}
                    disabled={isSubmitting}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#091b10] hover:bg-[#0e2718] border border-[#143522] hover:border-[#10b981]/50 text-white text-xs font-medium transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    <ShieldCheck size={15} className="text-[#10b981]" />
                    <span>Enter with Student Pass</span>
                  </button>

                  {/* Google OAuth Slot / Fallback Button */}
                  <div className="w-full flex justify-center">
                    <div id="google-signin-btn-target" className="w-full flex justify-center" />
                    {!googleClientId && (
                      <button
                        type="button"
                        onClick={handleStartTelegram}
                        className="w-full py-2.5 px-4 rounded-xl bg-[#091b10] border border-[#143522] text-[#a3cbb1] text-xs font-medium flex items-center justify-center gap-2"
                      >
                        <GoogleIcon className="w-4 h-4" />
                        <span>Google via Telegram verification</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Right Divider & Circular Icons (Exact match from the uploaded reference image!) */}
                <div className="hidden sm:flex flex-col items-center justify-center pl-3 border-l border-[#143522]/80 space-y-3">
                  <span className="text-[10px] font-bold text-[#62806d] tracking-wider uppercase mb-1">
                    OR
                  </span>

                  {/* Telegram Circular Icon Button */}
                  <button
                    onClick={handleStartTelegram}
                    title="Telegram Login (@AiChatExpert_bot)"
                    className="w-9 h-9 rounded-full bg-[#091b10] border border-[#143522] hover:border-[#10b981] hover:bg-[#059669]/20 flex items-center justify-center text-white transition cursor-pointer"
                  >
                    <TelegramIcon className="w-4 h-4 text-[#10b981]" />
                  </button>

                  {/* Google Circular Icon Button */}
                  <button
                    onClick={handleStartTelegram}
                    title="Google Account"
                    className="w-9 h-9 rounded-full bg-[#091b10] border border-[#143522] hover:border-[#10b981] hover:bg-[#059669]/20 flex items-center justify-center text-white transition cursor-pointer"
                  >
                    <GoogleIcon className="w-4 h-4" />
                  </button>

                  {/* Secure Pass Circular Icon Button */}
                  <button
                    onClick={handleStudentPassLogin}
                    title="1-Click Secure Student Pass"
                    className="w-9 h-9 rounded-full bg-[#091b10] border border-[#143522] hover:border-[#10b981] hover:bg-[#059669]/20 flex items-center justify-center text-white transition cursor-pointer"
                  >
                    <ShieldCheck size={16} className="text-[#10b981]" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Bottom Security Note */}
          <div className="mt-8 pt-4 border-t border-[#143522]/80 flex items-center justify-between text-[11px] text-[#62806d]">
            <div className="flex items-center gap-1.5">
              <Lock size={12} className="text-[#10b981]" />
              <span>Hashed storage in Supabase</span>
            </div>
            <span>@AiChatExpert_bot</span>
          </div>
        </div>

      </div>
    </div>
  )
}
