import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import 'katex/dist/katex.min.css'
import './globals.css'

export const metadata: Metadata = {
  title: 'Brainy — AI Study Companion',
  description: 'A calm, intelligent AI study companion for concepts, mathematical proofs, problem solving, and exam revision.',
  icons: {
    icon: [
      { url: '/favicon.ico' },
      { url: '/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicon-48x48.png', sizes: '48x48', type: 'image/png' },
    ],
    shortcut: '/favicon.ico',
    apple: [
      { url: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
    ],
  },
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#090a0f' },
    { media: '(prefers-color-scheme: dark)', color: '#090a0f' },
  ],
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <script src="https://telegram.org/js/telegram-web-app.js" async />
        <script src="https://accounts.google.com/gsi/client" async defer />
      </head>
      <body className="antialiased bg-[var(--bg-app)] text-[var(--text-primary)] min-h-[100dvh] transition-colors selection:bg-emerald-600 selection:text-white">
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
