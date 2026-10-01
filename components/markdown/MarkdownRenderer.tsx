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
    <div className="my-3 rounded-lg border border-zinc-800 bg-[#0c0d12] overflow-hidden text-xs">
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900/80 border-b border-zinc-800 text-zinc-400 font-mono text-[11px]">
        <span>{language || 'text'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-zinc-800 text-zinc-300 hover:text-white transition"
          aria-label="Copy code block"
        >
          {copied ? (
            <>
              <Check size={12} className="text-emerald-400" />
              <span className="text-emerald-400 text-[10px]">Copied</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span className="text-[10px]">Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3 overflow-x-auto font-mono text-zinc-200 text-xs leading-relaxed selection:bg-zinc-700 selection:text-white">
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
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const codeString = String(children).replace(/\n$/, '')
            const isInline = !match && !codeString.includes('\n')

            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-zinc-800/80 text-zinc-200 font-mono text-[13px] border border-zinc-700/60"
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
              <div className="my-3 overflow-x-auto rounded-lg border border-zinc-800">
                <table className="w-full text-left border-collapse text-xs">{children}</table>
              </div>
            )
          },
          th({ children }) {
            return (
              <th className="border-b border-zinc-800 bg-zinc-900/60 px-3 py-2 font-semibold text-zinc-200">
                {children}
              </th>
            )
          },
          td({ children }) {
            return <td className="border-b border-zinc-800/60 px-3 py-2 text-zinc-300">{children}</td>
          },
          ul({ children }) {
            return <ul className="my-2 space-y-1 list-disc pl-5 text-zinc-300">{children}</ul>
          },
          ol({ children }) {
            return <ol className="my-2 space-y-1 list-decimal pl-5 text-zinc-300">{children}</ol>
          },
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>
          },
          h1({ children }) {
            return <h1 className="text-xl font-bold tracking-tight text-white mt-4 mb-2">{children}</h1>
          },
          h2({ children }) {
            return <h2 className="text-lg font-semibold tracking-tight text-white mt-3.5 mb-1.5">{children}</h2>
          },
          h3({ children }) {
            return <h3 className="text-base font-semibold text-zinc-100 mt-3 mb-1">{children}</h3>
          },
          p({ children }) {
            return <p className="my-2 leading-relaxed text-zinc-300">{children}</p>
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-3 border-l-2 border-zinc-600 pl-3 italic text-zinc-400">
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
                className="text-zinc-200 underline underline-offset-2 hover:text-white transition"
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
