'use client'

import React, { useState, useEffect } from 'react'
import { ExternalLink, ShieldCheck, CheckCircle2, Lock, ArrowRight, Sparkles } from 'lucide-react'
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
              theme: 'outline',
              size: 'large',
              text: 'continue_with',
              shape: 'rectangular',
              width: 320,
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
      setError(err?.message || 'Google verification failed. You can use Telegram or Student Pass.')
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



  return (
    <div className="min-h-screen bg-[#0e1017] text-zinc-100 flex items-center justify-center p-4 sm:p-6 lg:p-8 font-sans antialiased relative overflow-hidden select-none">
      {/* Quiet background texture */}
      <div className="absolute inset-0 bg-[radial-gradient(#1c2230_1px,transparent_1px)] [background-size:24px_24px] opacity-40 pointer-events-none" />
      <div className="absolute top-1/4 -left-32 w-96 h-96 bg-emerald-950/20 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-cyan-950/20 rounded-full blur-[140px] pointer-events-none" />

      {/* Main Split Floating Card (Exact Design Inspired by Reference Image 1) */}
      <div className="w-full max-w-4xl bg-white text-zinc-900 rounded-3xl shadow-[0_30px_90px_rgba(0,0,0,0.45)] border border-zinc-200/80 overflow-hidden relative z-10 flex flex-col md:flex-row p-3 sm:p-4">
        
        {/* Left Dark Card (Matching Image 1 Left Textured Panel) */}
        <div className="md:w-[45%] rounded-2xl bg-[#111319] text-white p-8 sm:p-10 flex flex-col justify-between relative overflow-hidden shadow-inner">
          {/* Subtle curved mesh texture overlay */}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_rgba(5,150,105,0.18)_0%,_transparent_70%)] pointer-events-none" />
          <div className="absolute -bottom-10 -right-10 w-64 h-64 bg-[radial-gradient(circle,_rgba(255,255,255,0.06)_1px,_transparent_1px)] [background-size:12px_12px] rounded-full pointer-events-none opacity-60" />

          {/* Top Brand Logo */}
          <div className="flex items-center gap-2.5 relative z-10">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-600 to-emerald-400 flex items-center justify-center text-white font-black text-sm shadow-md shadow-emerald-950/40">
              B
            </div>
            <span className="font-brand-display font-bold text-base tracking-tight text-white uppercase">Brainy</span>
          </div>

          {/* Center Welcome Headline */}
          <div className="relative z-10 my-10 sm:my-14 space-y-3">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white leading-tight">
              Welcome <br />
              Back!
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
              A calmer place to understand difficult ideas, work through solutions, and build a study routine that fits you.
            </p>

            <div className="pt-4 space-y-2 text-xs text-zinc-300">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" />
                <span>Pick up your study sessions where you left off</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" />
                <span>Save useful answers as study notes</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" />
                <span>Ask questions, revise topics, and keep your notes together</span>
              </div>
            </div>
          </div>

          {/* Bottom Pill Badge Matching Reference Image 1 */}
          <div className="relative z-10">
            <div className="p-3 rounded-xl bg-white/5 border border-white/10 backdrop-blur-md flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 flex-shrink-0">
                <ShieldCheck size={18} />
              </div>
              <div>
                <div className="text-xs font-semibold text-white">Your study space</div>
                <div className="text-[11px] text-zinc-400">Sign in to continue learning</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Light Card (Matching Image 1 Right Clean Form Panel) */}
        <div className="md:w-[55%] p-6 sm:p-10 flex flex-col justify-between">
          <div>
            {/* Header */}
            <div className="text-center sm:text-left mb-8">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-900 mb-2">
                Login
              </h2>
              <p className="text-xs sm:text-sm text-zinc-500">
                Sign in to return to your conversations and saved study notes.
              </p>
            </div>

            {error && (
              <div className="mb-6 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs text-center leading-relaxed font-medium">
                {error}
              </div>
            )}

            {/* Telegram Waiting Mode */}
            {telegramWaiting ? (
              <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200 text-center space-y-4">
                <div className="w-12 h-12 mx-auto rounded-full bg-emerald-100 border border-emerald-200 flex items-center justify-center text-emerald-700">
                  <TelegramIcon className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-zinc-900 mb-1">
                    Waiting for @AiChatExpert_bot
                  </h3>
                  <p className="text-xs text-zinc-600 leading-relaxed">
                    Open <strong className="text-zinc-900">@AiChatExpert_bot</strong> on Telegram, type{' '}
                    <code className="px-1.5 py-0.5 rounded bg-zinc-200 font-mono text-[11px] text-zinc-800">
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
                    className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition flex items-center justify-center gap-2 shadow-sm"
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
                    className="text-xs text-zinc-500 hover:text-zinc-800 py-1 transition underline cursor-pointer"
                  >
                    Cancel Telegram Login
                  </button>
                </div>
              </div>
            ) : (
              /* Verified Auth Actions */
              <div className="space-y-4 max-w-sm mx-auto sm:mx-0">
                
                {/* 1. Continue with Telegram (@AiChatExpert_bot) */}
                <button
                  type="button"
                  onClick={handleStartTelegram}
                  disabled={isSubmitting}
                  className="w-full py-3 px-4 rounded-xl bg-zinc-900 hover:bg-black text-white text-xs font-semibold transition flex items-center justify-center gap-2.5 shadow-md shadow-zinc-900/10 cursor-pointer disabled:opacity-50"
                >
                  <TelegramIcon className="w-4 h-4 text-emerald-400" />
                  <span>Continue with Telegram (@AiChatExpert_bot)</span>
                </button>

                {/* Divider */}
                <div className="relative flex items-center justify-center my-4">
                  <div className="border-t border-zinc-200 w-full" />
                  <span className="bg-white px-3 text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
                    or
                  </span>
                </div>

                {/* 2. Continue with Google */}
                <div className="w-full flex flex-col items-center">
                  <div id="google-signin-btn-target" className="w-full flex justify-center" />
                  {!googleClientId && (
                    <button
                      type="button"
                      onClick={() => {
                        const g = (window as any).google
                        if (g?.accounts?.id && googleClientId) {
                          g.accounts.id.prompt()
                        } else {
                          setError('Google OAuth client ID is not configured on this server. Please use Continue with Telegram.')
                        }
                      }}
                      className="w-full py-2.5 px-4 rounded-xl border border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50 text-zinc-700 text-xs font-medium flex items-center justify-center gap-2 transition cursor-pointer"
                    >
                      <GoogleIcon className="w-4 h-4" />
                      <span>Continue with Google</span>
                    </button>
                  )}
                </div>

                <div className="pt-2 text-center text-[11px] text-zinc-400">
                  Select Telegram or Google to authenticate securely.
                </div>
              </div>
            )}
          </div>

          {/* Bottom Security & Copyright Footer */}
          <div className="mt-8 pt-4 border-t border-zinc-100 flex flex-col sm:flex-row items-center justify-between text-[11px] text-zinc-400 gap-2">
            <div className="flex items-center gap-1.5 text-zinc-500 font-medium">
              <Lock size={12} />
              <span>Sign in to your personal study space</span>
            </div>
            <span>© 2026 BrainyAi</span>
          </div>
        </div>

      </div>
    </div>
  )
}
