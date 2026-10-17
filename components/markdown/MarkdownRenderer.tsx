'use client'

import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { Check, Copy } from 'lucide-react'

interface MarkdownRendererProps {
  content: string
  className?: string
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="my-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] overflow-hidden text-xs shadow-xs">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg-surface-hover)] border-b border-[var(--border-subtle)] text-[var(--text-muted)] font-mono text-[11px]">
        <span>{language || 'text'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition cursor-pointer"
          aria-label="Copy code block"
        >
          {copied ? (
            <>
              <Check size={12} className="text-emerald-500" />
              <span className="text-emerald-500 text-[10px]">Copied</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span className="text-[10px]">Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto font-mono text-[var(--text-primary)] text-xs leading-relaxed selection:bg-[var(--accent-subtle)] selection:text-[var(--text-primary)]">
        <code>{code}</code>
      </pre>
    </div>
  )
}

export function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
  return (
    <div className={`prose-container overflow-hidden break-words text-sm leading-relaxed ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const codeString = String(children).replace(/\n$/, '')
            const isInline = !match && !codeString.includes('\n')

            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded-md bg-[var(--bg-surface-elevated)] text-[var(--text-primary)] font-mono text-[13px] border border-[var(--border-subtle)]"
                  {...props}
                >
                  {children}
                </code>
              )
            }

            return <CodeBlock language={match ? match[1] : ''} code={codeString} />
          },
          table({ children }) {
            return (
              <div className="my-3 overflow-x-auto rounded-xl border border-[var(--border-subtle)]">
                <table className="w-full text-left border-collapse text-xs">{children}</table>
              </div>
            )
          },
          th({ children }) {
            return (
              <th className="border-b border-[var(--border-subtle)] bg-[var(--bg-surface-elevated)] px-3 py-2 font-semibold text-[var(--text-primary)]">
                {children}
              </th>
            )
          },
          td({ children }) {
            return <td className="border-b border-[var(--border-subtle)] px-3 py-2 text-[var(--text-secondary)]">{children}</td>
          },
          ul({ children }) {
            return <ul className="my-2 space-y-1 list-disc pl-5 text-[var(--text-secondary)]">{children}</ul>
          },
          ol({ children }) {
            return <ol className="my-2 space-y-1 list-decimal pl-5 text-[var(--text-secondary)]">{children}</ol>
          },
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>
          },
          h1({ children }) {
            return <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)] mt-4 mb-2">{children}</h1>
          },
          h2({ children }) {
            return <h2 className="text-lg font-semibold tracking-tight text-[var(--text-primary)] mt-3.5 mb-1.5">{children}</h2>
          },
          h3({ children }) {
            return <h3 className="text-base font-semibold text-[var(--text-primary)] mt-3 mb-1">{children}</h3>
          },
          p({ children }) {
            return <p className="my-2 leading-relaxed text-[var(--text-secondary)]">{children}</p>
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-3 border-l-2 border-[var(--accent-primary)] bg-[var(--bg-surface-elevated)]/50 px-3.5 py-1.5 italic text-[var(--text-secondary)] rounded-r-lg">
                {children}
              </blockquote>
            )
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-[var(--accent-primary)] font-medium underline underline-offset-2 hover:opacity-80 transition"
              >
                {children}
              </a>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
