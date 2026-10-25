'use client'

import React, { useState, useEffect, useRef } from 'react'
import {
  FileText,
  Upload,
  Trash2,
  BookOpen,
  HelpCircle,
  Award,
  Sparkles,
  CheckCircle2,
  XCircle,
  RotateCcw,
  ChevronRight,
  ChevronLeft,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  FileSpreadsheet,
  Clock,
  Layers,
  ArrowRight,
  Search
} from 'lucide-react'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import 'katex/dist/katex.min.css'

import {
  PdfDocument,
  DocumentNote,
  DocumentQuiz,
  QuizAttempt,
  DocumentFlashcardDeck,
  DocumentStudyProgress
} from '@/types/api'
import {
  uploadPdfDocument,
  fetchPdfDocuments,
  deletePdfDocument,
  generatePdfNotes,
  fetchPdfNotes,
  askPdfDocument,
  generatePdfQuiz,
  fetchPdfQuizzes,
  submitPdfQuizAttempt,
  generatePdfFlashcards,
  fetchPdfFlashcards,
  fetchPdfStudyProgress
} from '@/lib/api'

interface PdfStudioViewProps {
  onBackToChat?: () => void
}

type StudioTab = 'notes' | 'ask' | 'quiz' | 'flashcards' | 'progress'

export function PdfStudioView({ onBackToChat }: PdfStudioViewProps) {
  // Document state
  const [documents, setDocuments] = useState<PdfDocument[]>([])
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [loadingDocs, setLoadingDocs] = useState<boolean>(true)
  const [uploading, setUploading] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')

  // Active studio tab
  const [activeTab, setActiveTab] = useState<StudioTab>('notes')
  const [depth, setDepth] = useState<'FAST' | 'BALANCED' | 'DEEP'>('BALANCED')

  // Tab: Notes
  const [notes, setNotes] = useState<DocumentNote[]>([])
  const [generatingNotes, setGeneratingNotes] = useState<boolean>(false)
  const [copiedNote, setCopiedNote] = useState<boolean>(false)

  // Tab: Ask PDF
  const [question, setQuestion] = useState<string>('')
  const [askingDoc, setAskingDoc] = useState<boolean>(false)
  const [qnaHistory, setQnaHistory] = useState<Array<{ q: string; a: string; citations: number[] }>>([])

  // Tab: Quiz
  const [quizzes, setQuizzes] = useState<DocumentQuiz[]>([])
  const [currentQuiz, setCurrentQuiz] = useState<DocumentQuiz | null>(null)
  const [generatingQuiz, setGeneratingQuiz] = useState<boolean>(false)
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({})
  const [quizAttempt, setQuizAttempt] = useState<QuizAttempt | null>(null)
  const [submittingQuiz, setSubmittingQuiz] = useState<boolean>(false)

  // Tab: Flashcards
  const [decks, setDecks] = useState<DocumentFlashcardDeck[]>([])
  const [currentDeck, setCurrentDeck] = useState<DocumentFlashcardDeck | null>(null)
  const [generatingCards, setGeneratingCards] = useState<boolean>(false)
  const [cardIndex, setCardIndex] = useState<number>(0)
  const [isFlipped, setIsFlipped] = useState<boolean>(false)

  // Tab: Progress
  const [progress, setProgress] = useState<DocumentStudyProgress | null>(null)
  const [loadingProgress, setLoadingProgress] = useState<boolean>(false)

  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Load documents on mount
  useEffect(() => {
    loadDocs()
  }, [])

  const loadDocs = async () => {
    setLoadingDocs(true)
    setErrorMsg(null)
    try {
      const docs = await fetchPdfDocuments()
      setDocuments(docs)
      if (docs.length > 0 && !selectedDocId) {
        setSelectedDocId(docs[0].id)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load PDF library.')
    } finally {
      setLoadingDocs(false)
    }
  }

  // Load document-specific content when selectedDocId or activeTab changes
  useEffect(() => {
    if (!selectedDocId) return
    setErrorMsg(null)

    if (activeTab === 'notes') {
      fetchPdfNotes(selectedDocId)
        .then((n) => setNotes(n))
        .catch(() => {})
    } else if (activeTab === 'quiz') {
      fetchPdfQuizzes(selectedDocId)
        .then((qz) => {
          setQuizzes(qz)
          if (qz.length > 0 && !currentQuiz) {
            setCurrentQuiz(qz[0])
            setSelectedAnswers({})
            setQuizAttempt(null)
          }
        })
        .catch(() => {})
    } else if (activeTab === 'flashcards') {
      fetchPdfFlashcards(selectedDocId)
        .then((fc) => {
          setDecks(fc)
          if (fc.length > 0 && !currentDeck) {
            setCurrentDeck(fc[0])
            setCardIndex(0)
            setIsFlipped(false)
          }
        })
        .catch(() => {})
    } else if (activeTab === 'progress') {
      setLoadingProgress(true)
      fetchPdfStudyProgress(selectedDocId)
        .then((p) => setProgress(p))
        .catch(() => {})
        .finally(() => setLoadingProgress(false))
    }
  }, [selectedDocId, activeTab])

  const selectedDoc = documents.find((d) => d.id === selectedDocId)

  // Handle File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Please select a valid PDF file.')
      return
    }

    if (file.size > 25 * 1024 * 1024) {
      setErrorMsg('File size exceeds the 25MB limit.')
      return
    }

    setUploading(true)
    setErrorMsg(null)
    try {
      const newDoc = await uploadPdfDocument(file)
      setDocuments((prev) => [newDoc, ...prev])
      setSelectedDocId(newDoc.id)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to upload and process PDF.')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // Delete Document
  const handleDeleteDoc = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this document and all its study materials?')) return
    try {
      await deletePdfDocument(docId)
      const remaining = documents.filter((d) => d.id !== docId)
      setDocuments(remaining)
      if (selectedDocId === docId) {
        setSelectedDocId(remaining.length > 0 ? remaining[0].id : null)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete document.')
    }
  }

  // Generate Notes Action
  const handleGenerateNotes = async () => {
    if (!selectedDocId) return
    setGeneratingNotes(true)
    setErrorMsg(null)
    try {
      const newNote = await generatePdfNotes(selectedDocId, depth)
      setNotes((prev) => [newNote, ...prev])
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate study notes.')
    } finally {
      setGeneratingNotes(false)
    }
  }

  // Ask Question Action
  const handleAskQuestion = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedDocId || !question.trim()) return

    const q = question.trim()
    setQuestion('')
    setAskingDoc(true)
    setErrorMsg(null)

    try {
      const res = await askPdfDocument(selectedDocId, q, depth)
      setQnaHistory((prev) => [{ q, a: res.answer, citations: res.citations || [] }, ...prev])
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to answer document question.')
    } finally {
      setAskingDoc(false)
    }
  }

  // Generate Quiz Action
  const handleGenerateQuiz = async () => {
    if (!selectedDocId) return
    setGeneratingQuiz(true)
    setErrorMsg(null)
    setSelectedAnswers({})
    setQuizAttempt(null)

    try {
      const newQuiz = await generatePdfQuiz(selectedDocId, 5, depth)
      setQuizzes((prev) => [newQuiz, ...prev])
      setCurrentQuiz(newQuiz)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate quiz.')
    } finally {
      setGeneratingQuiz(false)
    }
  }

  // Submit Quiz Action
  const handleSubmitQuiz = async () => {
    if (!currentQuiz) return
    setSubmittingQuiz(true)
    setErrorMsg(null)

    try {
      const answerList = currentQuiz.questions.map((_, idx) => selectedAnswers[idx] ?? -1)
      const attempt = await submitPdfQuizAttempt(currentQuiz.id, answerList)
      setQuizAttempt(attempt)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to grade quiz attempt.')
    } finally {
      setSubmittingQuiz(false)
    }
  }

  // Generate Flashcards Action
  const handleGenerateFlashcards = async () => {
    if (!selectedDocId) return
    setGeneratingCards(true)
    setErrorMsg(null)

    try {
      const newDeck = await generatePdfFlashcards(selectedDocId, 6, depth)
      setDecks((prev) => [newDeck, ...prev])
      setCurrentDeck(newDeck)
      setCardIndex(0)
      setIsFlipped(false)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate flashcards.')
    } finally {
      setGeneratingCards(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col md:flex-row h-full overflow-hidden bg-[var(--bg-app)]">
      {/* ── LEFT SIDEBAR: DOCUMENT LIBRARY & UPLOAD ── */}
      <aside className="w-full md:w-80 lg:w-88 border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col flex-shrink-0">
        {/* Upload Button Header */}
        <div className="p-4 border-b border-[var(--border-subtle)] flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-blue-500" />
              <h2 className="font-bold text-sm tracking-tight text-[var(--text-primary)]">
                Document Library
              </h2>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-[var(--bg-surface-elevated)] text-[var(--text-muted)]">
              {documents.length} docs
            </span>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,application/pdf"
            className="hidden"
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full py-2.5 px-4 rounded-xl font-semibold text-xs text-white bg-blue-600 hover:bg-blue-500 transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer disabled:opacity-50"
          >
            {uploading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>Extracting & Indexing...</span>
              </>
            ) : (
              <>
                <Upload size={14} />
                <span>Upload PDF Document</span>
              </>
            )}
          </button>

          {/* Search Library */}
          {documents.length > 0 && (
            <div className="relative">
              <Search size={13} className="absolute left-3 top-2.5 text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="Search library..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 rounded-xl text-xs bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] focus:outline-none focus:border-blue-500 text-[var(--text-primary)]"
              />
            </div>
          )}
        </div>

        {/* Documents List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loadingDocs ? (
            <div className="flex items-center justify-center p-8 text-[var(--text-muted)] text-xs gap-2">
              <Loader2 size={16} className="animate-spin text-blue-500" />
              <span>Loading library...</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center p-8 border border-dashed border-[var(--border-subtle)] rounded-2xl">
              <FileText className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-2 opacity-50" />
              <p className="text-xs font-semibold text-[var(--text-secondary)]">No documents uploaded</p>
              <p className="text-[11px] text-[var(--text-muted)] mt-1">
                Upload class notes, textbooks, or research papers up to 25MB.
              </p>
            </div>
          ) : (
            documents
              .filter((d) => d.filename.toLowerCase().includes(searchQuery.toLowerCase()))
              .map((doc) => {
              const isSelected = doc.id === selectedDocId
              return (
                <div
                  key={doc.id}
                  onClick={() => setSelectedDocId(doc.id)}
                  className={`group relative p-3 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-blue-500/10 border-blue-500/30 text-[var(--text-primary)]'
                      : 'bg-[var(--bg-surface-elevated)] border-transparent hover:border-[var(--border-subtle)] text-[var(--text-secondary)]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5 overflow-hidden">
                      <div className={`p-2 rounded-lg ${isSelected ? 'bg-blue-500 text-white' : 'bg-[var(--bg-surface)] text-[var(--text-muted)]'}`}>
                        <FileText size={16} />
                      </div>
                      <div className="overflow-hidden">
                        <h4 className="text-xs font-semibold truncate leading-snug">
                          {doc.filename}
                        </h4>
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-[var(--text-muted)]">
                          <span>{doc.page_count} pages</span>
                          <span>•</span>
                          <span>{(doc.file_size / (1024 * 1024)).toFixed(1)} MB</span>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={(e) => handleDeleteDoc(doc.id, e)}
                      title="Delete document"
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 transition"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </aside>

      {/* ── MAIN STAGE ── */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {errorMsg && (
          <div className="m-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
            <button onClick={() => setErrorMsg(null)} className="text-xs font-bold hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {selectedDoc ? (
          <>
            {/* Document Header & Studio Tabs */}
            <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-6 py-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="font-bold text-base text-[var(--text-primary)] flex items-center gap-2">
                  <span>{selectedDoc.filename}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500 font-semibold">
                    {selectedDoc.page_count} Pages
                  </span>
                </h1>
                <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                  AI Multi-Provider Academic Studio grounded in verified document text.
                </p>
              </div>

              {/* Depth Selector & Tabs */}
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center bg-[var(--bg-surface-elevated)] p-1 rounded-xl text-xs border border-[var(--border-subtle)]">
                  {(['FAST', 'BALANCED', 'DEEP'] as const).map((d) => (
                    <button
                      key={d}
                      onClick={() => setDepth(d)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition cursor-pointer ${
                        depth === d
                          ? 'bg-blue-600 text-white shadow-2xs'
                          : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                      }`}
                    >
                      {d}
                    </button>
                  ))}
                </div>

                {/* Studio Tab Pills */}
                <div className="flex items-center bg-[var(--bg-surface-elevated)] p-1 rounded-xl text-xs border border-[var(--border-subtle)]">
                  <button
                    onClick={() => setActiveTab('notes')}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                      activeTab === 'notes'
                        ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    <BookOpen size={13} />
                    <span>Notes</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('ask')}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                      activeTab === 'ask'
                        ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    <HelpCircle size={13} />
                    <span>Ask PDF</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('quiz')}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                      activeTab === 'quiz'
                        ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    <Award size={13} />
                    <span>Quiz (4-Option)</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('flashcards')}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                      activeTab === 'flashcards'
                        ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    <Layers size={13} />
                    <span>Flashcards</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('progress')}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                      activeTab === 'progress'
                        ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    <Sparkles size={13} />
                    <span>Progress</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Tab Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {/* ── TAB: NOTES ── */}
              {activeTab === 'notes' && (
                <div className="max-w-4xl mx-auto space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-[var(--text-primary)]">
                        Synthesized Revision Notes
                      </h3>
                      <p className="text-xs text-[var(--text-muted)]">
                        Executive Overview, Topic Breakdown, Definitions, LaTeX Formulas, and Page Citations.
                      </p>
                    </div>

                    <button
                      onClick={handleGenerateNotes}
                      disabled={generatingNotes}
                      className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      {generatingNotes ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          <span>Synthesizing ({depth})...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles size={14} />
                          <span>Generate New Notes</span>
                        </>
                      )}
                    </button>
                  </div>

                  {notes.length === 0 ? (
                    <div className="p-12 text-center border border-dashed border-[var(--border-subtle)] rounded-2xl">
                      <BookOpen className="w-10 h-10 text-[var(--text-muted)] mx-auto mb-3 opacity-50" />
                      <h4 className="font-semibold text-sm text-[var(--text-secondary)]">No notes generated yet</h4>
                      <p className="text-xs text-[var(--text-muted)] mt-1 max-w-sm mx-auto">
                        Click "Generate New Notes" to synthesize revision notes with page citations.
                      </p>
                    </div>
                  ) : (
                    notes.map((note) => (
                      <div
                        key={note.id}
                        className="p-6 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-sm space-y-4"
                      >
                        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
                          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                            <Clock size={13} />
                            <span>{new Date(note.created_at).toLocaleDateString()}</span>
                            <span className="font-mono px-2 py-0.5 rounded bg-[var(--bg-surface-elevated)] uppercase">
                              {note.depth}
                            </span>
                            {note.citations && note.citations.length > 0 && (
                              <span className="text-blue-500 font-medium">
                                Cited: {note.citations.map((c) => `P.${c}`).join(', ')}
                              </span>
                            )}
                          </div>

                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(note.content)
                              setCopiedNote(true)
                              setTimeout(() => setCopiedNote(false), 2000)
                            }}
                            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1.5 text-xs"
                          >
                            {copiedNote ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                            <span>{copiedNote ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>

                        <div className="max-w-none text-xs sm:text-sm leading-relaxed">
                          <MarkdownRenderer content={note.content} />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* ── TAB: ASK PDF ── */}
              {activeTab === 'ask' && (
                <div className="max-w-3xl mx-auto flex flex-col h-full space-y-6">
                  <div>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">
                      Grounded Document Q&A
                    </h3>
                    <p className="text-xs text-[var(--text-muted)]">
                      Ask questions about this PDF. The AI only answers from document content with page references.
                    </p>
                  </div>

                  <form onSubmit={handleAskQuestion} className="flex gap-2">
                    <input
                      type="text"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="e.g. What is the fundamental theorem explained on page 3?"
                      className="flex-1 px-4 py-2.5 rounded-xl text-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] focus:outline-none focus:border-blue-500 text-[var(--text-primary)]"
                    />
                    <button
                      type="submit"
                      disabled={askingDoc || !question.trim()}
                      className="px-5 py-2.5 rounded-xl font-semibold text-xs text-white bg-blue-600 hover:bg-blue-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      {askingDoc ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
                      <span>Ask</span>
                    </button>
                  </form>

                  <div className="space-y-4">
                    {qnaHistory.length === 0 ? (
                      <div className="p-8 text-center text-xs text-[var(--text-muted)] border border-dashed border-[var(--border-subtle)] rounded-xl">
                        Ask any question above to search and cite exact pages from this document.
                      </div>
                    ) : (
                      qnaHistory.map((item, idx) => (
                        <div
                          key={idx}
                          className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2.5"
                        >
                          <div className="font-semibold text-xs text-blue-500 flex items-center gap-1.5">
                            <HelpCircle size={14} />
                            <span>{item.q}</span>
                          </div>

                          <div className="text-xs sm:text-sm text-[var(--text-primary)] leading-relaxed">
                            <MarkdownRenderer content={item.a} />
                          </div>

                          {item.citations && item.citations.length > 0 && (
                            <div className="flex items-center gap-1.5 pt-2 border-t border-[var(--border-subtle)]">
                              <span className="text-[10px] text-[var(--text-muted)]">Citations:</span>
                              {item.citations.map((page) => (
                                <span
                                  key={page}
                                  className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-500 font-semibold"
                                >
                                  Page {page}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* ── TAB: QUIZ (STRICTLY 4 CLICKABLE OPTIONS) ── */}
              {activeTab === 'quiz' && (
                <div className="max-w-3xl mx-auto space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-[var(--text-primary)]">
                        Interactive Multiple Choice Quiz
                      </h3>
                      <p className="text-xs text-[var(--text-muted)]">
                        Strictly 4 options per question. Click to select your answers and submit for grading.
                      </p>
                    </div>

                    <button
                      onClick={handleGenerateQuiz}
                      disabled={generatingQuiz}
                      className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      {generatingQuiz ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          <span>Generating 4-Option Quiz...</span>
                        </>
                      ) : (
                        <>
                          <Award size={14} />
                          <span>New 5-Question Quiz</span>
                        </>
                      )}
                    </button>
                  </div>

                  {currentQuiz ? (
                    <div className="space-y-6">
                      {/* Score Banner after submission */}
                      {quizAttempt && (
                        <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-500/10 via-emerald-500/10 to-teal-500/10 border border-emerald-500/30 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="p-2.5 rounded-xl bg-emerald-500 text-white font-bold text-sm">
                              {quizAttempt.percentage}%
                            </div>
                            <div>
                              <h4 className="font-bold text-sm text-[var(--text-primary)]">
                                Score: {quizAttempt.score} / {quizAttempt.total} Correct
                              </h4>
                              <p className="text-xs text-[var(--text-muted)]">
                                {quizAttempt.percentage >= 80
                                  ? '🎉 Excellent mastery of this document!'
                                  : quizAttempt.percentage >= 50
                                  ? '👍 Good effort! Review the explanations below.'
                                  : '💪 Keep studying! Review notes and try again.'}
                              </p>
                            </div>
                          </div>

                          <button
                            onClick={() => {
                              setSelectedAnswers({})
                              setQuizAttempt(null)
                            }}
                            className="px-3 py-1.5 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1.5 cursor-pointer"
                          >
                            <RotateCcw size={13} />
                            <span>Retry</span>
                          </button>
                        </div>
                      )}

                      {/* Question Cards */}
                      {currentQuiz.questions.map((q, qIdx) => {
                        const userChoice = selectedAnswers[qIdx]
                        const isGraded = quizAttempt !== null
                        const feedback = isGraded ? quizAttempt.feedback[qIdx] : null

                        return (
                          <div
                            key={qIdx}
                            className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3 shadow-xs"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <h4 className="font-semibold text-xs sm:text-sm text-[var(--text-primary)]">
                                <span className="font-mono text-blue-500 mr-2">Q{qIdx + 1}.</span>
                                {q.question}
                              </h4>
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--bg-surface-elevated)] text-[var(--text-muted)] flex-shrink-0">
                                {q.page_ref}
                              </span>
                            </div>

                            {/* 4 Clickable Options */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                              {q.options.map((optText, optIdx) => {
                                const isSelected = userChoice === optIdx
                                const isCorrect = optIdx === q.correct_index

                                let optionStyle = 'bg-[var(--bg-surface-elevated)] border-transparent hover:border-blue-500/40 text-[var(--text-secondary)]'
                                if (isGraded) {
                                  if (isCorrect) {
                                    optionStyle = 'bg-emerald-500/15 border-emerald-500 text-emerald-600 dark:text-emerald-400 font-semibold'
                                  } else if (isSelected && !isCorrect) {
                                    optionStyle = 'bg-rose-500/15 border-rose-500 text-rose-600 dark:text-rose-400'
                                  } else {
                                    optionStyle = 'bg-[var(--bg-surface-elevated)] opacity-40 border-transparent text-[var(--text-muted)]'
                                  }
                                } else if (isSelected) {
                                  optionStyle = 'bg-blue-600 text-white border-blue-600 font-semibold shadow-xs'
                                }

                                const optLetter = String.fromCharCode(65 + optIdx)

                                return (
                                  <button
                                    key={optIdx}
                                    type="button"
                                    disabled={isGraded}
                                    onClick={() => setSelectedAnswers((prev) => ({ ...prev, [qIdx]: optIdx }))}
                                    className={`p-3 rounded-xl border text-xs text-left transition flex items-center justify-between cursor-pointer ${optionStyle}`}
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className="w-5 h-5 rounded-full bg-black/10 dark:bg-white/10 flex items-center justify-center font-bold text-[10px]">
                                        {optLetter}
                                      </span>
                                      <span>{optText}</span>
                                    </div>

                                    {isGraded && isCorrect && <CheckCircle2 size={15} className="text-emerald-500 flex-shrink-0" />}
                                    {isGraded && isSelected && !isCorrect && <XCircle size={15} className="text-rose-500 flex-shrink-0" />}
                                  </button>
                                )
                              })}
                            </div>

                            {/* Explanation when graded */}
                            {isGraded && feedback && (
                              <div className="p-3 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[11px] space-y-1">
                                <span className="font-semibold text-[var(--text-primary)]">Explanation: </span>
                                <span className="text-[var(--text-muted)]">{q.explanation}</span>
                              </div>
                            )}
                          </div>
                        )
                      })}

                      {/* Submit Answers Button */}
                      {!quizAttempt && (
                        <button
                          onClick={handleSubmitQuiz}
                          disabled={submittingQuiz || Object.keys(selectedAnswers).length === 0}
                          className="w-full py-3 rounded-xl font-bold text-xs text-white bg-emerald-600 hover:bg-emerald-500 transition shadow-sm flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                        >
                          {submittingQuiz ? <Loader2 size={15} className="animate-spin" /> : <Award size={15} />}
                          <span>Submit & Grade Quiz</span>
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="p-12 text-center border border-dashed border-[var(--border-subtle)] rounded-2xl">
                      <Award className="w-10 h-10 text-[var(--text-muted)] mx-auto mb-3 opacity-50" />
                      <h4 className="font-semibold text-sm text-[var(--text-secondary)]">No quiz loaded</h4>
                      <p className="text-xs text-[var(--text-muted)] mt-1 max-w-sm mx-auto">
                        Generate a 4-option multiple choice test strictly based on this document.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* ── TAB: FLASHCARDS (3D FLIP) ── */}
              {activeTab === 'flashcards' && (
                <div className="max-w-xl mx-auto space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-[var(--text-primary)]">
                        Revision Flashcards
                      </h3>
                      <p className="text-xs text-[var(--text-muted)]">
                        Click the card to flip between front (concept) and back (explanation).
                      </p>
                    </div>

                    <button
                      onClick={handleGenerateFlashcards}
                      disabled={generatingCards}
                      className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      {generatingCards ? <Loader2 size={14} className="animate-spin" /> : <Layers size={14} />}
                      <span>Generate Deck</span>
                    </button>
                  </div>

                  {currentDeck && currentDeck.cards.length > 0 ? (
                    <div className="space-y-4">
                      {/* 3D Flip Card */}
                      <div
                        onClick={() => setIsFlipped(!isFlipped)}
                        className="relative h-64 w-full cursor-pointer perspective-1000"
                      >
                        <div
                          className={`w-full h-full rounded-3xl p-8 border border-[var(--border-subtle)] shadow-md flex flex-col justify-between transition-all duration-300 transform ${
                            isFlipped
                              ? 'bg-blue-500/10 border-blue-500/40 text-[var(--text-primary)]'
                              : 'bg-[var(--bg-surface)] text-[var(--text-primary)]'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)] font-mono">
                            <span>
                              Card {cardIndex + 1} of {currentDeck.cards.length}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-[var(--bg-surface-elevated)] font-semibold text-blue-500">
                              {currentDeck.cards[cardIndex].difficulty}
                            </span>
                          </div>

                          <div className="text-center my-auto">
                            <span className="text-[10px] uppercase font-bold tracking-wider text-blue-500 mb-2 block">
                              {isFlipped ? 'Answer / Explanation' : 'Concept / Question'}
                            </span>
                            <p className="text-base sm:text-lg font-bold leading-relaxed">
                              {isFlipped
                                ? currentDeck.cards[cardIndex].back
                                : currentDeck.cards[cardIndex].front}
                            </p>
                          </div>

                          <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                            <span className="font-mono text-blue-500 font-semibold">
                              {currentDeck.cards[cardIndex].page_ref}
                            </span>
                            <span className="text-[10px] opacity-70">Click to flip</span>
                          </div>
                        </div>
                      </div>

                      {/* Controls */}
                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => {
                            setCardIndex((prev) => Math.max(0, prev - 1))
                            setIsFlipped(false)
                          }}
                          disabled={cardIndex === 0}
                          className="px-4 py-2 rounded-xl text-xs font-semibold border border-[var(--border-subtle)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1.5 cursor-pointer disabled:opacity-30"
                        >
                          <ChevronLeft size={16} />
                          <span>Previous</span>
                        </button>

                        <button
                          onClick={() => setIsFlipped(!isFlipped)}
                          className="px-4 py-2 rounded-xl text-xs font-semibold bg-[var(--bg-surface-elevated)] hover:bg-[var(--bg-surface-hover)] transition cursor-pointer"
                        >
                          Flip Card
                        </button>

                        <button
                          onClick={() => {
                            setCardIndex((prev) => Math.min(currentDeck.cards.length - 1, prev + 1))
                            setIsFlipped(false)
                          }}
                          disabled={cardIndex === currentDeck.cards.length - 1}
                          className="px-4 py-2 rounded-xl text-xs font-semibold border border-[var(--border-subtle)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1.5 cursor-pointer disabled:opacity-30"
                        >
                          <span>Next</span>
                          <ChevronRight size={16} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-12 text-center border border-dashed border-[var(--border-subtle)] rounded-2xl">
                      <Layers className="w-10 h-10 text-[var(--text-muted)] mx-auto mb-3 opacity-50" />
                      <h4 className="font-semibold text-sm text-[var(--text-secondary)]">No cards generated yet</h4>
                      <p className="text-xs text-[var(--text-muted)] mt-1">
                        Synthesize memory flashcards from this document.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* ── TAB: STUDY PROGRESS ── */}
              {activeTab === 'progress' && (
                <div className="max-w-2xl mx-auto space-y-6">
                  <div>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">
                      Document Study Progress
                    </h3>
                    <p className="text-xs text-[var(--text-muted)]">
                      Durable tracking across notes, quiz performance, and card reviews.
                    </p>
                  </div>

                  {loadingProgress ? (
                    <div className="flex items-center justify-center p-12 text-xs text-[var(--text-muted)] gap-2">
                      <Loader2 size={16} className="animate-spin text-blue-500" />
                      <span>Loading metrics...</span>
                    </div>
                  ) : progress ? (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
                        <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">
                          Revision Notes
                        </span>
                        <div className="text-xl font-bold text-[var(--text-primary)] flex items-center gap-2">
                          {progress.notes_generated ? (
                            <>
                              <CheckCircle2 size={18} className="text-emerald-500" />
                              <span>Synthesized</span>
                            </>
                          ) : (
                            <span className="text-[var(--text-muted)]">Pending</span>
                          )}
                        </div>
                      </div>

                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
                        <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">
                          Quizzes Taken
                        </span>
                        <div className="text-2xl font-bold text-blue-500">
                          {progress.quizzes_taken}
                        </div>
                      </div>

                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
                        <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">
                          Best Quiz Score
                        </span>
                        <div className="text-2xl font-bold text-emerald-500">
                          {progress.best_quiz_score} correct
                        </div>
                      </div>

                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
                        <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">
                          Cards Reviewed
                        </span>
                        <div className="text-2xl font-bold text-purple-500">
                          {progress.cards_reviewed}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="w-16 h-16 rounded-3xl bg-blue-500/10 text-blue-500 flex items-center justify-center mb-4">
              <FileSpreadsheet size={32} />
            </div>
            <h3 className="font-bold text-base text-[var(--text-primary)]">
              Welcome to Brainy PDF Study Studio
            </h3>
            <p className="text-xs text-[var(--text-muted)] max-w-md mt-1 mb-6">
              Upload any course syllabus, academic paper, or textbook chapter to generate
              verified notes, grounded Q&A, strictly 4-option quizzes, and flashcard decks.
            </p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-6 py-2.5 rounded-xl font-bold text-xs text-white bg-blue-600 hover:bg-blue-500 transition shadow-sm flex items-center gap-2 cursor-pointer"
            >
              <Upload size={15} />
              <span>Upload Document</span>
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
