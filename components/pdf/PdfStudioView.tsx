'use client'

import React, { useState, useEffect, useRef, useMemo } from 'react'
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
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  FileSpreadsheet,
  Clock,
  Layers,
  ArrowRight,
  Search,
  Printer,
  Download,
  MessageSquare,
  Zap,
  ShieldCheck,
  Filter,
  X,
  FileQuestion,
  ListOrdered
} from 'lucide-react'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import 'katex/dist/katex.min.css'

import {
  PdfDocument,
  DocumentNote,
  DocumentQuiz,
  QuizAttempt,
  DocumentFlashcardDeck,
  DocumentStudyProgress,
  ImportantQuestion,
  DocumentImportantQuestions
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
  fetchPdfStudyProgress,
  generatePdfImportantQuestions,
  fetchPdfImportantQuestions
} from '@/lib/api'

interface PdfStudioViewProps {
  onBackToChat?: () => void
}

type StudioTab = 'notes' | 'questions' | 'ask' | 'quiz' | 'flashcards' | 'progress'
type NoteDepthMode = 'quick' | 'standard' | 'detailed'

interface NoteSection {
  id: string
  title: string
  content: string
}

function parseNoteSections(markdown: string): NoteSection[] {
  if (!markdown) return []
  const lines = markdown.split('\n')
  const sections: NoteSection[] = []
  let currentTitle = 'Document Overview'
  let currentId = 'section-0'
  let currentLines: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.startsWith('## ')) {
      if (currentLines.length > 0) {
        sections.push({
          id: currentId,
          title: currentTitle,
          content: currentLines.join('\n').trim(),
        })
      }
      currentTitle = line.replace(/^##\s+/, '').trim()
      currentId = `section-${sections.length + 1}`
      currentLines = [line]
    } else {
      currentLines.push(line)
    }
  }

  if (currentLines.length > 0) {
    sections.push({
      id: currentId,
      title: currentTitle,
      content: currentLines.join('\n').trim(),
    })
  }

  return sections
}

export function PdfStudioView({ onBackToChat }: PdfStudioViewProps) {
  // Document state
  const [documents, setDocuments] = useState<PdfDocument[]>([])
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [loadingDocs, setLoadingDocs] = useState<boolean>(true)
  const [uploading, setUploading] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [mobilePanel, setMobilePanel] = useState<'library' | 'studio'>('studio')

  // Active studio tab
  const [activeTab, setActiveTab] = useState<StudioTab>('notes')

  // Tab: Notes
  const [notes, setNotes] = useState<DocumentNote[]>([])
  const [noteMode, setNoteMode] = useState<NoteDepthMode>('standard')
  const [generatingNotes, setGeneratingNotes] = useState<boolean>(false)
  const [copiedNote, setCopiedNote] = useState<boolean>(false)
  const [copiedSectionId, setCopiedSectionId] = useState<string | null>(null)
  const [activeTOC, setActiveTOC] = useState<string>('')
  const [isNotesChatOpen, setIsNotesChatOpen] = useState<boolean>(false)

  // Conversational Chat (Shared across Notes Companion & Ask PDF)
  // Strict 10-message limit enforced on frontend and backend
  const [conversationalHistory, setConversationalHistory] = useState<
    Array<{ role: 'user' | 'assistant'; content: string; citations?: number[] }>
  >([])
  const [conversationalInput, setConversationalInput] = useState<string>('')
  const [askingConversational, setAskingConversational] = useState<boolean>(false)

  // Tab: Important Questions
  const [questionsSets, setQuestionsSets] = useState<DocumentImportantQuestions[]>([])
  const [currentQuestionsSet, setCurrentQuestionsSet] = useState<DocumentImportantQuestions | null>(null)
  const [generatingQuestions, setGeneratingQuestions] = useState<boolean>(false)
  const [targetQuestionCount, setTargetQuestionCount] = useState<number>(10)
  const [priorityFilter, setPriorityFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL')
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL')
  const [expandedQuestions, setExpandedQuestions] = useState<Record<number, boolean>>({})
  const [copiedQuestionIdx, setCopiedQuestionIdx] = useState<number | null>(null)
  const [copiedAllQuestions, setCopiedAllQuestions] = useState<boolean>(false)

  // Tab: Quiz
  const [quizzes, setQuizzes] = useState<DocumentQuiz[]>([])
  const [currentQuiz, setCurrentQuiz] = useState<DocumentQuiz | null>(null)
  const [generatingQuiz, setGeneratingQuiz] = useState<boolean>(false)
  const [quizDifficulty, setQuizDifficulty] = useState<'EASY' | 'MEDIUM' | 'HARD'>('MEDIUM')
  const [quizNumQuestions, setQuizNumQuestions] = useState<number>(5)
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
  const chatBottomRef = useRef<HTMLDivElement | null>(null)

  // Load documents on mount
  useEffect(() => {
    loadDocs()
  }, [])

  // Auto-scroll chat window when new message arrives
  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [conversationalHistory, askingConversational])

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

  // When selectedDocId changes, reset conversational chat and load document-specific content
  useEffect(() => {
    if (!selectedDocId) return
    setErrorMsg(null)
    // Clear chat on PDF change
    setConversationalHistory([])
    setConversationalInput('')

    if (activeTab === 'notes') {
      fetchPdfNotes(selectedDocId)
        .then((n) => setNotes(n))
        .catch(() => {})
    } else if (activeTab === 'questions') {
      fetchPdfImportantQuestions(selectedDocId)
        .then((qs) => {
          setQuestionsSets(qs)
          if (qs.length > 0 && !currentQuestionsSet) {
            setCurrentQuestionsSet(qs[0])
          }
        })
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

  // Most recent note for current doc
  const activeNote = notes.length > 0 ? notes[0] : null
  const parsedSections = useMemo(() => {
    return activeNote ? parseNoteSections(activeNote.content) : []
  }, [activeNote])

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
      setMobilePanel('studio')
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

  // Generate Notes Action (100% Local Processing - Zero LLM API calls)
  const handleGenerateNotes = async () => {
    if (!selectedDocId) return
    setGeneratingNotes(true)
    setErrorMsg(null)
    try {
      const newNote = await generatePdfNotes(selectedDocId, noteMode)
      setNotes((prev) => [newNote, ...prev])
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate study notes.')
    } finally {
      setGeneratingNotes(false)
    }
  }

  // Download Notes as Markdown
  const handleDownloadMarkdown = (note: DocumentNote) => {
    if (!note || !selectedDoc) return
    const blob = new Blob([note.content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedDoc.filename.replace(/\.pdf$/i, '')}_${note.depth.toLowerCase()}_notes.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Copy Section
  const handleCopySection = (sectionId: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedSectionId(sectionId)
    setTimeout(() => setCopiedSectionId(null), 2000)
  }

  // Conversational Chat Submit (Strict 10-message limit enforced)
  const handleSendConversational = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!selectedDocId || !conversationalInput.trim()) return

    const userMessage = conversationalInput.trim()
    setConversationalInput('')
    setAskingConversational(true)
    setErrorMsg(null)

    // Slice previous history to at most 9 messages so user + assistant <= 10 turns
    const historyPayload = conversationalHistory.slice(-9).map((m) => ({
      role: m.role,
      content: m.content
    }))

    // Optimistically append user message (cap local view to last 9 before adding new)
    setConversationalHistory((prev) => [
      ...prev.slice(-9),
      { role: 'user', content: userMessage }
    ])

    try {
      const res = await askPdfDocument(selectedDocId, userMessage, 'BALANCED', historyPayload)
      setConversationalHistory((prev) => [
        ...prev.slice(-9),
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations || []
        }
      ])
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to answer question.')
    } finally {
      setAskingConversational(false)
    }
  }

  // Generate Important Questions Action (Non-Gemini Router)
  const handleGenerateImportantQuestions = async () => {
    if (!selectedDocId) return
    setGeneratingQuestions(true)
    setErrorMsg(null)
    setExpandedQuestions({})

    try {
      const res = await generatePdfImportantQuestions(selectedDocId, targetQuestionCount)
      setQuestionsSets((prev) => [res, ...prev])
      setCurrentQuestionsSet(res)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate important questions.')
    } finally {
      setGeneratingQuestions(false)
    }
  }

  // Filtered Questions List
  const filteredQuestions = useMemo(() => {
    if (!currentQuestionsSet) return []
    return currentQuestionsSet.questions.filter((q) => {
      const matchesPriority = priorityFilter === 'ALL' || q.priority === priorityFilter
      const matchesCategory = categoryFilter === 'ALL' || q.category.toLowerCase() === categoryFilter.toLowerCase()
      return matchesPriority && matchesCategory
    })
  }, [currentQuestionsSet, priorityFilter, categoryFilter])

  // Copy Single Question
  const handleCopyQuestion = (idx: number, q: ImportantQuestion) => {
    const text = `Question: ${q.question}\nPriority: ${q.priority}\nCategory: ${q.category}\nSource: ${q.page_ref}\n\nExpected Answer Outline:\n${q.answer_outline.map((p) => `• ${p}`).join('\n')}`
    navigator.clipboard.writeText(text)
    setCopiedQuestionIdx(idx)
    setTimeout(() => setCopiedQuestionIdx(null), 2000)
  }

  // Copy All Questions
  const handleCopyAllQuestions = () => {
    if (!filteredQuestions.length) return
    const text = filteredQuestions
      .map(
        (q, i) =>
          `Q${i + 1}. [${q.priority} | ${q.category} | ${q.page_ref}]\n${q.question}\nAnswer Outline:\n${q.answer_outline.map((p) => `• ${p}`).join('\n')}\n`
      )
      .join('\n---\n\n')
    navigator.clipboard.writeText(text)
    setCopiedAllQuestions(true)
    setTimeout(() => setCopiedAllQuestions(false), 2000)
  }

  // Generate Quiz Action (Non-Gemini Router, Strictly 4 Options)
  const handleGenerateQuiz = async () => {
    if (!selectedDocId) return
    setGeneratingQuiz(true)
    setErrorMsg(null)
    setSelectedAnswers({})
    setQuizAttempt(null)

    try {
      const newQuiz = await generatePdfQuiz(selectedDocId, quizNumQuestions, 'BALANCED', quizDifficulty)
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

  // Generate Flashcards Action (Non-Gemini Router)
  const handleGenerateFlashcards = async () => {
    if (!selectedDocId) return
    setGeneratingCards(true)
    setErrorMsg(null)

    try {
      const newDeck = await generatePdfFlashcards(selectedDocId, 8, 'BALANCED')
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
      {/* ── MOBILE VIEW SWITCHER (Visible only on < md screens) ── */}
      <div className="flex md:hidden items-center justify-between p-2.5 bg-[var(--bg-surface)] border-b border-[var(--border-subtle)] flex-shrink-0">
        <div className="flex items-center p-0.5 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs w-full">
          <button
            onClick={() => setMobilePanel('library')}
            className={`flex-1 py-1.5 px-3 rounded-lg font-semibold text-xs transition cursor-pointer flex items-center justify-center gap-1.5 min-h-[36px] ${
              mobilePanel === 'library'
                ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-xs'
                : 'text-[var(--text-muted)]'
            }`}
          >
            <FileSpreadsheet size={14} className="text-blue-500" />
            <span>Library ({documents.length})</span>
          </button>
          <button
            onClick={() => setMobilePanel('studio')}
            className={`flex-1 py-1.5 px-3 rounded-lg font-semibold text-xs transition cursor-pointer flex items-center justify-center gap-1.5 min-h-[36px] ${
              mobilePanel === 'studio'
                ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-xs'
                : 'text-[var(--text-muted)]'
            }`}
          >
            <BookOpen size={14} className="text-emerald-500" />
            <span className="truncate max-w-[140px]">{selectedDoc ? selectedDoc.filename : 'Studio'}</span>
          </button>
        </div>
      </div>

      {/* ── LEFT SIDEBAR: DOCUMENT LIBRARY & UPLOAD ── */}
      <aside
        className={`w-full md:w-80 lg:w-88 border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] flex-col flex-shrink-0 ${
          mobilePanel === 'library' ? 'flex flex-1 h-full' : 'hidden md:flex'
        }`}
      >
        {/* Upload Button Header */}
        <div className="p-3 sm:p-4 border-b border-[var(--border-subtle)] flex flex-col gap-2.5 sm:gap-3">
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
            className="w-full py-2.5 px-4 rounded-xl font-semibold text-xs text-white bg-blue-600 hover:bg-blue-500 transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer disabled:opacity-50 min-h-[42px]"
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
              <Search size={13} className="absolute left-3 top-3 text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="Search library..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-2 rounded-xl text-xs bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] focus:outline-none focus:border-blue-500 text-[var(--text-primary)] min-h-[38px]"
              />
            </div>
          )}
        </div>

        {/* Documents List */}
        <div className="flex-1 overflow-y-auto p-2.5 sm:p-3 space-y-2">
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
                    onClick={() => {
                      setSelectedDocId(doc.id)
                      setMobilePanel('studio')
                    }}
                    className={`group relative p-3 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-blue-500/10 border-blue-500/30 text-[var(--text-primary)]'
                        : 'bg-[var(--bg-surface-elevated)] border-transparent hover:border-[var(--border-subtle)] text-[var(--text-secondary)]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5 overflow-hidden">
                        <div
                          className={`p-2 rounded-lg flex-shrink-0 ${
                            isSelected
                              ? 'bg-blue-500 text-white'
                              : 'bg-[var(--bg-surface)] text-[var(--text-muted)]'
                          }`}
                        >
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
                        aria-label="Delete document"
                        className="opacity-100 md:opacity-0 md:group-hover:opacity-100 p-2 min-h-[32px] min-w-[32px] flex items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 transition"
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
      <main
        className={`flex-1 flex flex-col h-full overflow-hidden ${
          mobilePanel === 'studio' ? 'flex' : 'hidden md:flex'
        }`}
      >
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
            <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 sm:px-6 py-2.5 sm:py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 sm:gap-3 flex-shrink-0">
              <div>
                <h1 className="font-bold text-sm sm:text-base text-[var(--text-primary)] flex items-center gap-2">
                  <span className="truncate max-w-[200px] sm:max-w-none">{selectedDoc.filename}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500 font-semibold flex-shrink-0">
                    {selectedDoc.page_count} Pages
                  </span>
                  {activeTab === 'notes' && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                      <ShieldCheck size={12} />
                      <span>100% Local • Zero LLM</span>
                    </span>
                  )}
                </h1>
                <p className="text-[11px] text-[var(--text-muted)] mt-0.5 hidden sm:block">
                  Academic Revision Studio • Grounded deterministic extraction & non-Gemini exam intelligence.
                </p>
              </div>

              {/* Studio Tab Pills */}
              <div className="flex items-center bg-[var(--bg-surface-elevated)] p-1 rounded-xl text-xs border border-[var(--border-subtle)] overflow-x-auto scrollbar-none flex-nowrap flex-shrink-0">
                <button
                  onClick={() => setActiveTab('notes')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer whitespace-nowrap flex-shrink-0 ${
                    activeTab === 'notes'
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <BookOpen size={13} className="text-emerald-500" />
                  <span>Notes</span>
                </button>

                <button
                  onClick={() => setActiveTab('questions')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer whitespace-nowrap flex-shrink-0 ${
                    activeTab === 'questions'
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <FileQuestion size={13} className="text-amber-500" />
                  <span>Important Qs</span>
                </button>

                <button
                  onClick={() => setActiveTab('ask')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer whitespace-nowrap flex-shrink-0 ${
                    activeTab === 'ask'
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <HelpCircle size={13} className="text-blue-500" />
                  <span>Ask PDF</span>
                </button>

                <button
                  onClick={() => setActiveTab('quiz')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer whitespace-nowrap flex-shrink-0 ${
                    activeTab === 'quiz'
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <Award size={13} className="text-purple-500" />
                  <span>Quiz</span>
                </button>

                <button
                  onClick={() => setActiveTab('flashcards')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer whitespace-nowrap flex-shrink-0 ${
                    activeTab === 'flashcards'
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <Layers size={13} className="text-pink-500" />
                  <span>Flashcards</span>
                </button>

                <button
                  onClick={() => setActiveTab('progress')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer whitespace-nowrap flex-shrink-0 ${
                    activeTab === 'progress'
                      ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] font-semibold shadow-xs'
                      : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <Sparkles size={13} className="text-teal-500" />
                  <span>Progress</span>
                </button>
              </div>
            </div>

            {/* Tab Body */}
            <div className="flex-1 overflow-y-auto p-3 sm:p-6">
              {/* ════════════════════════════════════════════════════════════════
                  TAB: NOTES (100% LOCAL DETERMINISTIC REVISION WORKSPACE)
              ════════════════════════════════════════════════════════════════ */}
              {activeTab === 'notes' && (
                <div className="max-w-6xl mx-auto space-y-6">
                  {/* Top Bar: Mode Selector & Local Generation */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-xs">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold text-[var(--text-primary)]">
                          Local Revision Notes
                        </h3>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">
                          100% Offline • Zero LLM
                        </span>
                      </div>
                      <p className="text-xs text-[var(--text-muted)] mt-1">
                        Deterministic keyword relevance, section boundary detection, LaTeX formulas, and page citations.
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2.5">
                      {/* Depth Mode Selector */}
                      <div className="flex items-center bg-[var(--bg-surface-elevated)] p-1 rounded-xl text-xs border border-[var(--border-subtle)]">
                        {(
                          [
                            { key: 'quick', label: 'Quick Revision' },
                            { key: 'standard', label: 'Standard Notes' },
                            { key: 'detailed', label: 'Detailed Study' }
                          ] as const
                        ).map((m) => (
                          <button
                            key={m.key}
                            onClick={() => setNoteMode(m.key)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                              noteMode === m.key
                                ? 'bg-blue-600 text-white shadow-2xs'
                                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                            }`}
                          >
                            {m.label}
                          </button>
                        ))}
                      </div>

                      {/* Generate Action */}
                      <button
                        onClick={handleGenerateNotes}
                        disabled={generatingNotes}
                        className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50 shadow-xs"
                      >
                        {generatingNotes ? (
                          <>
                            <Loader2 size={14} className="animate-spin" />
                            <span>Extracting Notes...</span>
                          </>
                        ) : (
                          <>
                            <Zap size={14} />
                            <span>Generate Notes</span>
                          </>
                        )}
                      </button>

                      {/* Companion Chat Drawer Toggle */}
                      <button
                        onClick={() => setIsNotesChatOpen(!isNotesChatOpen)}
                        className={`px-3 py-2 rounded-xl text-xs font-semibold border transition flex items-center gap-1.5 cursor-pointer ${
                          isNotesChatOpen
                            ? 'bg-blue-500/15 border-blue-500/40 text-blue-500'
                            : 'border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-surface-elevated)]'
                        }`}
                      >
                        <MessageSquare size={13} />
                        <span>Chat Assistant</span>
                        {conversationalHistory.length > 0 && (
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-blue-500 text-white">
                            {conversationalHistory.length}/10
                          </span>
                        )}
                      </button>
                    </div>
                  </div>

                  {notes.length === 0 ? (
                    <div className="p-12 text-center border border-dashed border-[var(--border-subtle)] rounded-2xl">
                      <BookOpen className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3 opacity-40" />
                      <h4 className="font-semibold text-sm text-[var(--text-secondary)]">No notes generated yet</h4>
                      <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md mx-auto">
                        Select a revision depth mode above and click &quot;Generate Notes&quot; to synthesize structured study material directly from the extracted text without calling external AI models.
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
                      {/* Left: Table of Contents & Tools (Desktop) */}
                      <div className="hidden lg:block lg:col-span-1 sticky top-4 space-y-4">
                        <div className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-xs space-y-3">
                          <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5">
                            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-1.5">
                              <ListOrdered size={14} className="text-blue-500" />
                              <span>Table of Contents</span>
                            </h4>
                            <span className="text-[10px] font-mono text-[var(--text-muted)]">
                              {parsedSections.length} parts
                            </span>
                          </div>

                          <nav className="space-y-1 max-h-[60vh] overflow-y-auto pr-1">
                            {parsedSections.map((sec) => (
                              <button
                                key={sec.id}
                                onClick={() => {
                                  setActiveTOC(sec.id)
                                  const el = document.getElementById(sec.id)
                                  if (el) el.scrollIntoView({ behavior: 'smooth' })
                                }}
                                className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs truncate transition cursor-pointer flex items-center justify-between ${
                                  activeTOC === sec.id
                                    ? 'bg-blue-500/10 text-blue-500 font-semibold'
                                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)]'
                                }`}
                              >
                                <span className="truncate">{sec.title}</span>
                                <ChevronRight size={12} className="opacity-40 flex-shrink-0" />
                              </button>
                            ))}
                          </nav>
                        </div>

                        {/* Quick Actions Panel */}
                        <div className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-xs space-y-2.5">
                          <button
                            onClick={() => {
                              if (activeNote) {
                                navigator.clipboard.writeText(activeNote.content)
                                setCopiedNote(true)
                                setTimeout(() => setCopiedNote(false), 2000)
                              }
                            }}
                            className="w-full py-2 px-3 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center justify-center gap-2 cursor-pointer"
                          >
                            {copiedNote ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                            <span>{copiedNote ? 'Copied Full Notes' : 'Copy Full Notes'}</span>
                          </button>

                          <button
                            onClick={() => activeNote && handleDownloadMarkdown(activeNote)}
                            className="w-full py-2 px-3 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center justify-center gap-2 cursor-pointer"
                          >
                            <Download size={14} />
                            <span>Download Markdown</span>
                          </button>

                          <button
                            onClick={() => window.print()}
                            className="w-full py-2 px-3 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center justify-center gap-2 cursor-pointer"
                          >
                            <Printer size={14} />
                            <span>Print Friendly</span>
                          </button>
                        </div>
                      </div>

                      {/* Main Note Reading Body */}
                      <div className={`space-y-6 ${isNotesChatOpen ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
                        {activeNote && (
                          <div className="p-6 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-sm space-y-6">
                            {/* Note Metadata Bar */}
                            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-4">
                              <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                                <Clock size={13} />
                                <span>{new Date(activeNote.created_at).toLocaleDateString()}</span>
                                <span className="font-mono px-2 py-0.5 rounded bg-[var(--bg-surface-elevated)] uppercase text-[11px] font-semibold text-blue-500">
                                  {activeNote.depth}
                                </span>
                                {activeNote.citations && activeNote.citations.length > 0 && (
                                  <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                                    Citations: {activeNote.citations.map((c) => `P.${c}`).join(', ')}
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(activeNote.content)
                                    setCopiedNote(true)
                                    setTimeout(() => setCopiedNote(false), 2000)
                                  }}
                                  className="p-1.5 px-2.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1.5 text-xs border border-[var(--border-subtle)]"
                                >
                                  {copiedNote ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                                  <span>{copiedNote ? 'Copied' : 'Copy All'}</span>
                                </button>
                                <button
                                  onClick={() => handleDownloadMarkdown(activeNote)}
                                  className="p-1.5 px-2.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1.5 text-xs border border-[var(--border-subtle)]"
                                >
                                  <Download size={14} />
                                  <span>.md</span>
                                </button>
                              </div>
                            </div>

                            {/* Section Cards */}
                            <div className="space-y-6">
                              {parsedSections.map((sec) => (
                                <section
                                  key={sec.id}
                                  id={sec.id}
                                  className="group relative p-5 rounded-xl bg-[var(--bg-surface-elevated)]/40 border border-[var(--border-subtle)]/70 hover:border-blue-500/30 transition-all space-y-3"
                                >
                                  <div className="flex items-center justify-between border-b border-[var(--border-subtle)]/50 pb-2">
                                    <h3 className="font-bold text-sm text-[var(--text-primary)] tracking-tight">
                                      {sec.title}
                                    </h3>
                                    <button
                                      onClick={() => handleCopySection(sec.id, sec.content)}
                                      className="opacity-0 group-hover:opacity-100 text-[11px] text-[var(--text-muted)] hover:text-blue-500 transition flex items-center gap-1 cursor-pointer"
                                      title="Copy this section"
                                    >
                                      {copiedSectionId === sec.id ? (
                                        <>
                                          <Check size={12} className="text-green-500" />
                                          <span className="text-green-500">Copied</span>
                                        </>
                                      ) : (
                                        <>
                                          <Copy size={12} />
                                          <span>Copy Section</span>
                                        </>
                                      )}
                                    </button>
                                  </div>

                                  <div className="max-w-none text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
                                    <MarkdownRenderer content={sec.content} />
                                  </div>
                                </section>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Right: Notes Conversational Assistant (Strict 10-message limit) */}
                      {isNotesChatOpen && (
                        <div className="lg:col-span-1 sticky top-4 flex flex-col h-[75vh] p-4 rounded-2xl bg-[var(--bg-surface)] border border-blue-500/30 shadow-md">
                          {/* Chat Header */}
                          <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3 flex-shrink-0">
                            <div>
                              <h4 className="font-bold text-xs text-[var(--text-primary)] flex items-center gap-1.5">
                                <MessageSquare size={13} className="text-blue-500" />
                                <span>Notes Assistant</span>
                              </h4>
                              <p className="text-[10px] text-[var(--text-muted)]">
                                Grounded Q&A • Non-Gemini
                              </p>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500 font-semibold">
                                {conversationalHistory.length} / 10
                              </span>
                              <button
                                onClick={() => setConversationalHistory([])}
                                title="Clear chat context"
                                className="p-1 rounded text-[var(--text-muted)] hover:text-red-500 text-[10px]"
                              >
                                Clear
                              </button>
                              <button
                                onClick={() => setIsNotesChatOpen(false)}
                                className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                              >
                                <X size={13} />
                              </button>
                            </div>
                          </div>

                          {/* Chat Messages */}
                          <div className="flex-1 overflow-y-auto py-3 space-y-3 text-xs">
                            {conversationalHistory.length === 0 ? (
                              <div className="p-6 text-center text-xs text-[var(--text-muted)] space-y-2">
                                <HelpCircle size={20} className="mx-auto opacity-40 text-blue-500" />
                                <p className="font-medium text-[var(--text-secondary)]">Ask anything about this document</p>
                                <p className="text-[11px]">Strict 10-message conversational context window with exact page citations.</p>
                              </div>
                            ) : (
                              conversationalHistory.map((m, idx) => (
                                <div
                                  key={idx}
                                  className={`p-2.5 rounded-xl space-y-1 ${
                                    m.role === 'user'
                                      ? 'bg-blue-600 text-white ml-4'
                                      : 'bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] mr-2'
                                  }`}
                                >
                                  <div className="text-[10px] font-semibold opacity-70">
                                    {m.role === 'user' ? 'You' : 'Assistant'}
                                  </div>
                                  <div className="text-xs leading-relaxed">
                                    <MarkdownRenderer content={m.content} />
                                  </div>
                                  {m.citations && m.citations.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1 text-[10px]">
                                      {m.citations.map((c) => (
                                        <span
                                          key={c}
                                          className="px-1.5 py-0.2 rounded bg-black/10 dark:bg-white/10 font-mono"
                                        >
                                          P.{c}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))
                            )}
                            {askingConversational && (
                              <div className="p-2.5 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] flex items-center gap-2 text-xs text-[var(--text-muted)]">
                                <Loader2 size={13} className="animate-spin text-blue-500" />
                                <span>Searching document pages...</span>
                              </div>
                            )}
                            <div ref={chatBottomRef} />
                          </div>

                          {/* Chat Input */}
                          <form onSubmit={handleSendConversational} className="flex gap-1.5 pt-2 border-t border-[var(--border-subtle)] flex-shrink-0">
                            <input
                              type="text"
                              value={conversationalInput}
                              onChange={(e) => setConversationalInput(e.target.value)}
                              placeholder="Ask a question..."
                              className="flex-1 px-3 py-1.5 rounded-lg text-xs bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] focus:outline-none focus:border-blue-500 text-[var(--text-primary)]"
                            />
                            <button
                              type="submit"
                              disabled={askingConversational || !conversationalInput.trim()}
                              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 transition cursor-pointer flex items-center justify-center"
                            >
                              <ArrowRight size={13} />
                            </button>
                          </form>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* ════════════════════════════════════════════════════════════════
                  TAB: IMPORTANT QUESTIONS (EXAM QUESTION BANK, NON-GEMINI)
              ════════════════════════════════════════════════════════════════ */}
              {activeTab === 'questions' && (
                <div className="max-w-4xl mx-auto space-y-6">
                  {/* Top Bar: Generate Questions Controls */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-xs">
                    <div>
                      <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
                        <span>Examination & Revision Question Bank</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold">
                          Non-Gemini Router
                        </span>
                      </h3>
                      <p className="text-xs text-[var(--text-muted)] mt-1">
                        High-yield questions categorized into 8 core types with priority ratings and expected answer outlines.
                      </p>
                    </div>

                    <div className="flex items-center gap-2.5">
                      {/* Count Selector */}
                      <div className="flex items-center bg-[var(--bg-surface-elevated)] p-1 rounded-xl text-xs border border-[var(--border-subtle)]">
                        {[10, 20, 30].map((cnt) => (
                          <button
                            key={cnt}
                            onClick={() => setTargetQuestionCount(cnt)}
                            className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                              targetQuestionCount === cnt
                                ? 'bg-amber-600 text-white shadow-2xs'
                                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                            }`}
                          >
                            {cnt} Qs
                          </button>
                        ))}
                      </div>

                      <button
                        onClick={handleGenerateImportantQuestions}
                        disabled={generatingQuestions}
                        className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-amber-600 hover:bg-amber-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50 shadow-xs"
                      >
                        {generatingQuestions ? (
                          <>
                            <Loader2 size={14} className="animate-spin" />
                            <span>Generating {targetQuestionCount} Qs...</span>
                          </>
                        ) : (
                          <>
                            <FileQuestion size={14} />
                            <span>Generate Questions</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Filter Toolbar */}
                  {currentQuestionsSet && (
                    <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs">
                      {/* Priority Filters */}
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--text-muted)] mr-1">Priority:</span>
                        {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((p) => (
                          <button
                            key={p}
                            onClick={() => setPriorityFilter(p)}
                            className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition cursor-pointer ${
                              priorityFilter === p
                                ? p === 'HIGH'
                                  ? 'bg-rose-500 text-white'
                                  : p === 'MEDIUM'
                                  ? 'bg-amber-500 text-white'
                                  : p === 'LOW'
                                  ? 'bg-blue-500 text-white'
                                  : 'bg-[var(--text-primary)] text-[var(--bg-app)]'
                                : 'bg-[var(--bg-surface-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                            }`}
                          >
                            {p}
                          </button>
                        ))}
                      </div>

                      {/* Category Filter */}
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-[var(--text-muted)] mr-1">Category:</span>
                        <select
                          value={categoryFilter}
                          onChange={(e) => setCategoryFilter(e.target.value)}
                          className="px-2.5 py-1 rounded-lg text-[11px] bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none"
                        >
                          <option value="ALL">All Categories</option>
                          <option value="Short Answer">Short Answer</option>
                          <option value="Long Answer">Long Answer</option>
                          <option value="Definition">Definition</option>
                          <option value="Conceptual">Conceptual</option>
                          <option value="Derivation/Proof">Derivation/Proof</option>
                          <option value="Numerical/Formula">Numerical/Formula</option>
                          <option value="Comparison">Comparison</option>
                          <option value="Application">Application</option>
                        </select>

                        <button
                          onClick={handleCopyAllQuestions}
                          className="px-3 py-1 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1 text-[11px] font-semibold text-[var(--text-secondary)]"
                        >
                          {copiedAllQuestions ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
                          <span>{copiedAllQuestions ? 'Copied All' : 'Copy All'}</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Question Cards List */}
                  {!currentQuestionsSet ? (
                    <div className="p-12 text-center border border-dashed border-[var(--border-subtle)] rounded-2xl">
                      <FileQuestion className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3 opacity-40" />
                      <h4 className="font-semibold text-sm text-[var(--text-secondary)]">No exam questions generated yet</h4>
                      <p className="text-xs text-[var(--text-muted)] mt-1 max-w-sm mx-auto">
                        Click &quot;Generate Questions&quot; above to produce high-yield revision questions with answer outlines and page citations.
                      </p>
                    </div>
                  ) : filteredQuestions.length === 0 ? (
                    <div className="p-8 text-center text-xs text-[var(--text-muted)] border border-dashed border-[var(--border-subtle)] rounded-xl">
                      No questions match the selected priority or category filters.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {filteredQuestions.map((q, idx) => {
                        const isExpanded = Boolean(expandedQuestions[idx])
                        return (
                          <div
                            key={idx}
                            className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3 shadow-xs hover:border-amber-500/30 transition-all"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <span
                                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                                    q.priority === 'HIGH'
                                      ? 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30'
                                      : q.priority === 'MEDIUM'
                                      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                                      : 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30'
                                  }`}
                                >
                                  {q.priority} PRIORITY
                                </span>
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[var(--bg-surface-elevated)] text-[var(--text-muted)]">
                                  {q.category}
                                </span>
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500 font-semibold">
                                  {q.page_ref}
                                </span>
                              </div>

                              <button
                                onClick={() => handleCopyQuestion(idx, q)}
                                className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1 text-[11px]"
                                title="Copy question"
                              >
                                {copiedQuestionIdx === idx ? (
                                  <Check size={13} className="text-green-500" />
                                ) : (
                                  <Copy size={13} />
                                )}
                              </button>
                            </div>

                            {/* Question Statement */}
                            <h4 className="font-bold text-sm text-[var(--text-primary)] leading-snug">
                              <span className="font-mono text-amber-500 mr-2">Q{idx + 1}.</span>
                              {q.question}
                            </h4>

                            {/* Expected Answer Outline Toggle */}
                            <div className="pt-1">
                              <button
                                onClick={() =>
                                  setExpandedQuestions((prev) => ({
                                    ...prev,
                                    [idx]: !prev[idx]
                                  }))
                                }
                                className="text-xs font-semibold text-amber-600 dark:text-amber-400 hover:underline flex items-center gap-1 cursor-pointer"
                              >
                                {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                <span>{isExpanded ? 'Hide Expected Answer Outline' : 'Show Expected Answer Outline'}</span>
                              </button>

                              {isExpanded && (
                                <div className="mt-2.5 p-3.5 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] space-y-2 text-xs">
                                  <div className="font-semibold text-[11px] text-[var(--text-muted)] uppercase tracking-wider">
                                    Key Marking Points & Outline:
                                  </div>
                                  <ul className="space-y-1.5">
                                    {q.answer_outline.map((point, pIdx) => (
                                      <li key={pIdx} className="flex items-start gap-2 text-[var(--text-secondary)]">
                                        <span className="text-amber-500 mt-0.5">•</span>
                                        <span>{point}</span>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* ════════════════════════════════════════════════════════════════
                  TAB: ASK PDF (10-MESSAGE CONVERSATIONAL CHAT, NON-GEMINI)
              ════════════════════════════════════════════════════════════════ */}
              {activeTab === 'ask' && (
                <div className="max-w-3xl mx-auto flex flex-col h-full space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-[var(--text-primary)]">
                        Grounded Document Q&A
                      </h3>
                      <p className="text-xs text-[var(--text-muted)]">
                        Ask questions about this PDF. strictly non-Gemini routing with 10-message conversational context.
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500 font-semibold">
                        {conversationalHistory.length} / 10 Context Messages
                      </span>
                      {conversationalHistory.length > 0 && (
                        <button
                          onClick={() => setConversationalHistory([])}
                          className="px-2.5 py-1 rounded-lg text-xs border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-red-500"
                        >
                          Clear Chat
                        </button>
                      )}
                    </div>
                  </div>

                  <form onSubmit={handleSendConversational} className="flex gap-2">
                    <input
                      type="text"
                      value={conversationalInput}
                      onChange={(e) => setConversationalInput(e.target.value)}
                      placeholder="e.g. What is the fundamental theorem explained on page 3?"
                      className="flex-1 px-4 py-2.5 rounded-xl text-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] focus:outline-none focus:border-blue-500 text-[var(--text-primary)]"
                    />
                    <button
                      type="submit"
                      disabled={askingConversational || !conversationalInput.trim()}
                      className="px-5 py-2.5 rounded-xl font-semibold text-xs text-white bg-blue-600 hover:bg-blue-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      {askingConversational ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
                      <span>Ask</span>
                    </button>
                  </form>

                  <div className="space-y-4">
                    {conversationalHistory.length === 0 ? (
                      <div className="p-8 text-center text-xs text-[var(--text-muted)] border border-dashed border-[var(--border-subtle)] rounded-xl">
                        Ask any question above to search and cite exact pages from this document.
                      </div>
                    ) : (
                      conversationalHistory.map((item, idx) => (
                        <div
                          key={idx}
                          className={`p-4 rounded-xl border space-y-2.5 ${
                            item.role === 'user'
                              ? 'bg-blue-600/10 border-blue-500/30'
                              : 'bg-[var(--bg-surface)] border-[var(--border-subtle)]'
                          }`}
                        >
                          <div className="font-semibold text-xs text-blue-500 flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              {item.role === 'user' ? <HelpCircle size={14} /> : <BookOpen size={14} />}
                              <span>{item.role === 'user' ? 'Your Question' : 'Document Answer'}</span>
                            </div>
                            {item.citations && item.citations.length > 0 && (
                              <div className="flex gap-1 text-[10px]">
                                {item.citations.map((c) => (
                                  <span key={c} className="px-2 py-0.5 rounded-md bg-blue-500/15 text-blue-500 font-mono">
                                    Page {c}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          <div className="text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
                            <MarkdownRenderer content={item.content} />
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* ════════════════════════════════════════════════════════════════
                  TAB: QUIZ (STRICTLY 4 OPTIONS, DIFFICULTY SELECTOR, NON-GEMINI)
              ════════════════════════════════════════════════════════════════ */}
              {activeTab === 'quiz' && (
                <div className="max-w-3xl mx-auto space-y-6">
                  {/* Top Bar: Generate Quiz Controls */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] shadow-xs">
                    <div>
                      <h3 className="text-base font-bold text-[var(--text-primary)]">
                        Interactive Knowledge Quiz
                      </h3>
                      <p className="text-xs text-[var(--text-muted)]">
                        Strict 4-option MCQs sampled evenly across the document.
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {/* Difficulty Selector */}
                      <div className="flex items-center bg-[var(--bg-surface-elevated)] p-1 rounded-xl text-xs border border-[var(--border-subtle)]">
                        {(['EASY', 'MEDIUM', 'HARD'] as const).map((d) => (
                          <button
                            key={d}
                            onClick={() => setQuizDifficulty(d)}
                            className={`px-2 py-1 rounded-lg text-[10px] font-semibold transition cursor-pointer ${
                              quizDifficulty === d
                                ? 'bg-purple-600 text-white shadow-2xs'
                                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                            }`}
                          >
                            {d}
                          </button>
                        ))}
                      </div>

                      {/* Question Count Selector */}
                      <div className="flex items-center bg-[var(--bg-surface-elevated)] p-1 rounded-xl text-xs border border-[var(--border-subtle)]">
                        {[5, 10, 15].map((cnt) => (
                          <button
                            key={cnt}
                            onClick={() => setQuizNumQuestions(cnt)}
                            className={`px-2 py-1 rounded-lg text-[10px] font-semibold transition cursor-pointer ${
                              quizNumQuestions === cnt
                                ? 'bg-purple-600 text-white shadow-2xs'
                                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                            }`}
                          >
                            {cnt} Qs
                          </button>
                        ))}
                      </div>

                      <button
                        onClick={handleGenerateQuiz}
                        disabled={generatingQuiz}
                        className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50 shadow-xs"
                      >
                        {generatingQuiz ? (
                          <>
                            <Loader2 size={14} className="animate-spin" />
                            <span>Generating Quiz...</span>
                          </>
                        ) : (
                          <>
                            <Award size={14} />
                            <span>New Quiz</span>
                          </>
                        )}
                      </button>
                    </div>
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
                                <span className="font-mono text-purple-500 mr-2">Q{qIdx + 1}.</span>
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

                                let optionStyle =
                                  'bg-[var(--bg-surface-elevated)] border-transparent hover:border-purple-500/40 text-[var(--text-secondary)]'
                                if (isGraded) {
                                  if (isCorrect) {
                                    optionStyle =
                                      'bg-emerald-500/15 border-emerald-500 text-emerald-600 dark:text-emerald-400 font-semibold'
                                  } else if (isSelected && !isCorrect) {
                                    optionStyle =
                                      'bg-rose-500/15 border-rose-500 text-rose-600 dark:text-rose-400'
                                  } else {
                                    optionStyle =
                                      'bg-[var(--bg-surface-elevated)] opacity-40 border-transparent text-[var(--text-muted)]'
                                  }
                                } else if (isSelected) {
                                  optionStyle = 'bg-purple-600 text-white border-purple-600 font-semibold shadow-xs'
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

                                    {isGraded && isCorrect && (
                                      <CheckCircle2 size={15} className="text-emerald-500 flex-shrink-0" />
                                    )}
                                    {isGraded && isSelected && !isCorrect && (
                                      <XCircle size={15} className="text-rose-500 flex-shrink-0" />
                                    )}
                                  </button>
                                )
                              })}
                            </div>

                            {/* Explanation when graded */}
                            {isGraded && feedback && (
                              <div className="mt-2.5 p-3 rounded-xl bg-[var(--bg-surface-elevated)] border border-[var(--border-subtle)] text-xs space-y-1">
                                <div className="font-semibold text-emerald-600 dark:text-emerald-400 text-[11px] flex items-center gap-1">
                                  <span>Explanation ({feedback.page_ref})</span>
                                </div>
                                <p className="text-[var(--text-muted)]">{feedback.explanation}</p>
                              </div>
                            )}
                          </div>
                        )
                      })}

                      {/* Submit Quiz Button */}
                      {!quizAttempt && (
                        <div className="flex justify-end pt-2">
                          <button
                            onClick={handleSubmitQuiz}
                            disabled={
                              submittingQuiz || Object.keys(selectedAnswers).length < currentQuiz.questions.length
                            }
                            className="px-6 py-2.5 rounded-xl font-semibold text-xs text-white bg-emerald-600 hover:bg-emerald-500 transition shadow-sm cursor-pointer disabled:opacity-50"
                          >
                            {submittingQuiz ? (
                              <span className="flex items-center gap-2">
                                <Loader2 size={14} className="animate-spin" />
                                <span>Grading...</span>
                              </span>
                            ) : (
                              <span>
                                Submit Quiz ({Object.keys(selectedAnswers).length}/{currentQuiz.questions.length})
                              </span>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="p-12 text-center border border-dashed border-[var(--border-subtle)] rounded-2xl">
                      <Award className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3 opacity-40" />
                      <h4 className="font-semibold text-sm text-[var(--text-secondary)]">No quiz generated yet</h4>
                      <p className="text-xs text-[var(--text-muted)] mt-1 max-w-sm mx-auto">
                        Click &quot;New Quiz&quot; above to generate a multiple-choice quiz strictly verified against the document.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* ════════════════════════════════════════════════════════════════
                  TAB: FLASHCARDS
              ════════════════════════════════════════════════════════════════ */}
              {activeTab === 'flashcards' && (
                <div className="max-w-xl mx-auto space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-[var(--text-primary)]">
                        Spaced Repetition Flashcards
                      </h3>
                      <p className="text-xs text-[var(--text-muted)]">
                        Key definitions, formulas, and terminology formatted for active recall.
                      </p>
                    </div>

                    <button
                      onClick={handleGenerateFlashcards}
                      disabled={generatingCards}
                      className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-pink-600 hover:bg-pink-500 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                    >
                      {generatingCards ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          <span>Creating Cards...</span>
                        </>
                      ) : (
                        <>
                          <Layers size={14} />
                          <span>New Flashcard Deck</span>
                        </>
                      )}
                    </button>
                  </div>

                  {currentDeck && currentDeck.cards.length > 0 ? (
                    <div className="space-y-4">
                      {/* Active Card */}
                      <div
                        onClick={() => setIsFlipped(!isFlipped)}
                        className="h-64 sm:h-72 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 sm:p-8 flex flex-col justify-between cursor-pointer hover:border-pink-500/40 transition shadow-sm relative overflow-hidden"
                      >
                        <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                          <span className="font-mono">
                            Card {cardIndex + 1} of {currentDeck.cards.length}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-[var(--bg-surface-elevated)] font-semibold text-[10px]">
                            {currentDeck.cards[cardIndex].difficulty}
                          </span>
                        </div>

                        <div className="text-center my-auto px-4">
                          <span className="text-[10px] uppercase tracking-wider font-semibold text-pink-500 mb-2 block">
                            {isFlipped ? 'Answer / Concept' : 'Term / Prompt'}
                          </span>
                          <h3 className="font-bold text-base sm:text-lg text-[var(--text-primary)] leading-snug">
                            {isFlipped
                              ? currentDeck.cards[cardIndex].back
                              : currentDeck.cards[cardIndex].front}
                          </h3>
                        </div>

                        <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)] border-t border-[var(--border-subtle)] pt-3">
                          <span>{currentDeck.cards[cardIndex].page_ref}</span>
                          <span className="text-pink-500 font-medium">Click to flip card</span>
                        </div>
                      </div>

                      {/* Navigation Controls */}
                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => {
                            setCardIndex((prev) => Math.max(0, prev - 1))
                            setIsFlipped(false)
                          }}
                          disabled={cardIndex === 0}
                          className="px-4 py-2 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1 disabled:opacity-30 cursor-pointer"
                        >
                          <ChevronLeft size={14} />
                          <span>Previous</span>
                        </button>

                        <span className="text-xs font-mono text-[var(--text-muted)]">
                          {cardIndex + 1} / {currentDeck.cards.length}
                        </span>

                        <button
                          onClick={() => {
                            setCardIndex((prev) => Math.min(currentDeck.cards.length - 1, prev + 1))
                            setIsFlipped(false)
                          }}
                          disabled={cardIndex === currentDeck.cards.length - 1}
                          className="px-4 py-2 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-surface-elevated)] transition flex items-center gap-1 disabled:opacity-30 cursor-pointer"
                        >
                          <span>Next</span>
                          <ChevronRight size={14} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-12 text-center border border-dashed border-[var(--border-subtle)] rounded-2xl">
                      <Layers className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3 opacity-40" />
                      <h4 className="font-semibold text-sm text-[var(--text-secondary)]">No flashcards generated yet</h4>
                      <p className="text-xs text-[var(--text-muted)] mt-1 max-w-sm mx-auto">
                        Click &quot;New Flashcard Deck&quot; to synthesize interactive revision cards from key terms.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* ════════════════════════════════════════════════════════════════
                  TAB: PROGRESS
              ════════════════════════════════════════════════════════════════ */}
              {activeTab === 'progress' && (
                <div className="max-w-2xl mx-auto space-y-6">
                  <div>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">
                      Document Study Progress
                    </h3>
                    <p className="text-xs text-[var(--text-muted)]">
                      Durable learning metrics tracked across your sessions in Supabase.
                    </p>
                  </div>

                  {loadingProgress ? (
                    <div className="p-12 flex items-center justify-center gap-2 text-xs text-[var(--text-muted)]">
                      <Loader2 size={16} className="animate-spin text-blue-500" />
                      <span>Loading metrics...</span>
                    </div>
                  ) : progress ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
                        <div className="flex items-center gap-2 text-blue-500">
                          <BookOpen size={16} />
                          <h4 className="font-semibold text-xs text-[var(--text-secondary)]">Revision Notes</h4>
                        </div>
                        <div className="text-2xl font-bold text-[var(--text-primary)]">
                          {progress.notes_generated ? 'Generated' : 'Not Generated'}
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          {progress.notes_generated ? 'Local revision notes are ready for review.' : 'Synthesize notes to begin studying.'}
                        </p>
                      </div>

                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
                        <div className="flex items-center gap-2 text-purple-500">
                          <Award size={16} />
                          <h4 className="font-semibold text-xs text-[var(--text-secondary)]">Quizzes Taken</h4>
                        </div>
                        <div className="text-2xl font-bold text-[var(--text-primary)]">
                          {progress.quizzes_taken}
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          Best Score: {progress.best_quiz_score} correct questions
                        </p>
                      </div>

                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
                        <div className="flex items-center gap-2 text-pink-500">
                          <Layers size={16} />
                          <h4 className="font-semibold text-xs text-[var(--text-secondary)]">Flashcards Reviewed</h4>
                        </div>
                        <div className="text-2xl font-bold text-[var(--text-primary)]">
                          {progress.cards_reviewed}
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          Active recall flashcards completed
                        </p>
                      </div>

                      <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2">
                        <div className="flex items-center gap-2 text-emerald-500">
                          <Clock size={16} />
                          <h4 className="font-semibold text-xs text-[var(--text-secondary)]">Last Studied</h4>
                        </div>
                        <div className="text-sm font-semibold text-[var(--text-primary)] mt-1">
                          {new Date(progress.last_studied_at).toLocaleString()}
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          Synced with Supabase study progress
                        </p>
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <div className="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center text-blue-500 mb-4">
              <FileSpreadsheet size={32} />
            </div>
            <h3 className="font-bold text-base text-[var(--text-primary)]">
              Welcome to BRAINY PDF Study Studio
            </h3>
            <p className="text-xs text-[var(--text-muted)] mt-1.5 max-w-sm">
              Upload a course PDF, lecture slide, or textbook to synthesize 100% local revision notes, exam question banks, and strictly verified 4-option quizzes.
            </p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="mt-5 px-5 py-2.5 rounded-xl font-semibold text-xs text-white bg-blue-600 hover:bg-blue-500 transition shadow-sm cursor-pointer"
            >
              Upload Your First Document
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
