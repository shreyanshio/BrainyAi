/**
 * Unified API Contract & Data Types for Brainy
 */

export interface User {
  id: number
  first_name: string
  username: string
  email?: string
  photo_url?: string
  role?: 'student' | 'admin'
  token?: string
}

export interface AuthResponse {
  authenticated: boolean
  user: User | null
  status?: string
  token?: string
}

export interface UsageStatus {
  used: number
  limit: number
  remaining: number
  reset_at: string
  window_hours: number
}

export interface ChatSession {
  id: string
  user_id?: number
  title: string
  created_at?: string
  updated_at?: string
  last_message_at?: string
  is_saved?: boolean
  is_pinned?: boolean
  is_archived?: boolean
}

export type AnswerLength = 'short' | 'medium' | 'long'

export interface ModelDefinition {
  id: string
  name: string
  tagline: string
  description: string
  badge?: string
  recommendedFor: string
}

export interface ChatMessage {
  id?: string | number
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at?: string
  model?: string
  answer_length?: AnswerLength
  keyTakeaway?: string
  isStreaming?: boolean
}

export interface ChatSendRequest {
  session_id?: string | null
  message: string
  content?: string
  model?: string
  answer_length?: AnswerLength
  tone?: string
  idempotency_key?: string
}

export interface ChatSendResponse {
  role: 'assistant'
  content: string
  response?: string
  session_id: string
  new_title?: string | null
  model: string
  answer_length: AnswerLength
  usage: UsageStatus
  user_message_count?: number
  message_limit?: number
  latency_ms?: StreamLatencyMetrics
}

export type StreamStage = 'preparing' | 'searching' | 'generating' | 'persisting'

export interface StreamLatencyMetrics {
  auth_ms?: number
  security_validation_ms?: number
  session_validation_ms?: number
  history_fetch_ms?: number
  context_build_ms?: number
  pipeline_ms?: number
  pre_gen_ms?: number
  model_ttft_ms?: number
  ttft_ms?: number
  generation_ms?: number
  persistence_ms?: number
  total_duration_ms?: number
  request_total_ms?: number
}

export type StreamEvent =
  | { type: 'start'; request_id: string; session_id: string | null }
  | { type: 'status'; stage: StreamStage }
  | { type: 'delta'; text: string }
  | {
      type: 'done'
      session_id: string | null
      new_title: string | null
      model: string
      answer_length: AnswerLength
      usage: UsageStatus
      persistence_warning?: boolean
      request_id?: string
      latency_ms?: StreamLatencyMetrics
    }
  | { type: 'error'; code: string; message: string; partial?: boolean; request_id?: string }

export interface StreamChatCallbacks {
  onStart?: (sessionId: string | null, requestId: string) => void
  onStatus?: (stage: StreamStage) => void
  onDelta?: (deltaText: string, accumulatedText: string) => void
  onDone?: (event: Extract<StreamEvent, { type: 'done' }>) => void
  onError?: (error: Error, partialText?: string) => void
}

export interface UserProfileStats {
  user_id: number
  first_name: string
  username: string
  level: string
  score: number
  total: number
  joined: string
  streak?: number
}

export interface UserMemoryData {
  learn_context: string
  liked_notes: string[]
  preferences?: Record<string, unknown>
}

export interface QuickPrompt {
  id: string
  title: string
  description: string
  prompt: string
  category: 'concept' | 'problem' | 'code' | 'exam'
}

export type AppTheme = 'warm-paper' | 'pure-light' | 'midnight' | 'graphite' | 'oled'

export type AccentColor = 'emerald' | 'sapphire' | 'amber' | 'crimson' | 'slate' | string

export type InterfaceFont =
  | 'inter'
  | 'geist'
  | 'jakarta'
  | 'dmsans'
  | 'manrope'
  | 'ibm'
  | 'lora'
  | 'sourceserif'
  | 'optizither'
  | 'jetbrains'

export type FontSizeOption = 'sm' | 'md' | 'lg' | 'xl'

export type LineSpacingOption = 'compact' | 'comfortable' | 'relaxed'

export type ChatWidthOption = 'standard' | 'wide'

export type LayoutDensity = 'comfortable' | 'compact'

export interface UserPreferences {
  theme: AppTheme
  accentColor: AccentColor
  customAccentHex?: string
  interfaceFont: InterfaceFont
  fontSize: FontSizeOption
  lineSpacing: LineSpacingOption
  chatWidth: ChatWidthOption
  density: LayoutDensity
  readabilityMode: boolean
  defaultModel: string
  defaultLength: AnswerLength
  focusTimerMinutes: number
}

export interface AdminSummary {
  total_users: number
  total_logins: number
  total_sessions: number
  total_messages: number
  active_today: number
  active_7d: number
}

export interface AdminUserRecord {
  user_id: number
  first_name: string
  username: string
  login_types: string[]
  login_count: number
  message_count: number
  session_count?: number
  first_seen: string | null
  last_seen: string | null
  last_login_at?: string | null
  is_suspended?: boolean
  is_admin?: boolean
}

export interface AdminRecentLogin {
  user_id: number
  first_name: string
  username: string
  login_type: string
  ip_address: string
  created_at: string
}

export interface AdminUsageReport {
  summary: AdminSummary
  login_type_breakdown: Record<string, number>
  users: AdminUserRecord[]
  recent_logins: AdminRecentLogin[]
}

export interface AdminUsersResponse {
  total: number
  page: number
  limit: number
  users: AdminUserRecord[]
}

export interface SystemHealthStatus {
  status: 'healthy' | 'degraded' | 'down'
  timestamp: string
  supabase: {
    configured: boolean
    status: string
    latency_ms: number | null
  }
  providers: {
    groq: { configured: boolean; status: string }
    openrouter: { configured: boolean; status: string }
    gemini: { configured: boolean; status: string }
  }
  server: {
    quota_window_hours: number
    global_message_limit: number
    sessions_cached: number
    messages_cached: number
    suspended_users_count: number
  }
}

// ── PDF Study Studio & AI Routing Types ──

export interface PdfDocument {
  id: string
  user_id: number
  filename: string
  file_size: number
  page_count: number
  storage_path?: string
  processing_status: 'ready' | 'processing' | 'error'
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface DocumentNote {
  id: string
  document_id: string
  user_id: number
  depth: 'FAST' | 'BALANCED' | 'DEEP'
  content: string
  citations: number[]
  created_at: string
}

export interface QuizQuestion {
  question: string
  options: string[]
  correct_index: number
  explanation: string
  page_ref: string
}

export interface DocumentQuiz {
  id: string
  document_id: string
  user_id: number
  title: string
  questions: QuizQuestion[]
  created_at: string
}

export interface QuizAnswerFeedback {
  question_index: number
  selected_option: number
  correct_option: number
  is_correct: boolean
  explanation: string
  page_ref: string
}

export interface QuizAttempt {
  id: string
  quiz_id: string
  user_id: number
  score: number
  total: number
  percentage: number
  feedback: QuizAnswerFeedback[]
  created_at: string
}

export interface FlashcardItem {
  front: string
  back: string
  page_ref: string
  difficulty: string
}

export interface DocumentFlashcardDeck {
  id: string
  document_id: string
  user_id: number
  cards: FlashcardItem[]
  created_at: string
}

export interface DocumentStudyProgress {
  user_id: number
  document_id: string
  notes_generated: boolean
  quizzes_taken: number
  best_quiz_score: number
  cards_reviewed: number
  last_studied_at: string
}

export interface AIProviderHealth {
  total_requests: number
  total_calls: number
  success: number
  success_count: number
  failure: number
  error_count: number
  error_rate_pct: number
  avg_latency_ms: number
  healthy: boolean
}

export interface AIHealthSummary {
  status: string
  providers: Record<string, AIProviderHealth>
  recent_events: any[]
  timestamp: string
}

// ── ADMIN CONTROL CENTER DATA TYPES ──
export interface AdminKPIs {
  total_requests: number
  successful_requests: number
  failed_requests: number
  fallback_requests: number
  success_rate_pct: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  avg_tokens_per_request: number
  estimated_cost_usd: number
  avg_latency_ms: number
  p95_latency_ms: number
  active_users_in_window: number
  total_users: number
  active_users_today: number
  active_users_week: number
  suspended_users: number
  total_pdf_documents: number
  total_pdf_pages: number
  active_alerts_count: number
  server_timestamp: number
  server_time_iso: string
}

export interface TimeSeriesBucket {
  time_label: string
  timestamp: number
  requests: number
  successful: number
  failed: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
  avg_latency_ms: number
}

export interface AIRequestLog {
  request_id: string
  user_id?: number | string | null
  task: string
  depth: string
  provider: string
  model: string
  latency_ms: number
  ttft_ms?: number | null
  input_tokens?: number | null
  output_tokens?: number | null
  total_tokens?: number | null
  cost_usd: number
  is_estimated: boolean
  status: string
  fallback_used: boolean
  fallback_from?: string | null
  error_category?: string | null
  continuation_used?: boolean
  continuation_rounds?: number
  timestamp: number
}

export interface ProviderDetail {
  id: string
  name: string
  configured: boolean
  masked_key: string
  models: string[]
  health: AIProviderHealth & {
    p95_latency_ms?: number
    total_cost_usd?: number
    last_success_at?: number | null
    last_failure_at?: number | null
  }
}

export interface QuotaObservation {
  provider: string
  model?: string | null
  limit_requests?: number | null
  remaining_requests?: number | null
  limit_tokens?: number | null
  remaining_tokens?: number | null
  observed_at: number
  observed_iso: string
  source: string
}

export interface PDFAnalytics {
  total_documents: number
  total_pages: number
  total_size_bytes: number
  native_pages: number
  ocr_pages: number
  avg_extraction_time_ms: number
  failed_documents: number
  recent_documents: any[]
}

export interface AdminAuditLog {
  id: string
  actor_id?: string | null
  actor_email: string
  action: string
  target_type?: string | null
  target_id?: string | null
  ip_address?: string | null
  details: Record<string, any>
  created_at: string
  timestamp: number
}

export interface SystemAlert {
  id: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  title: string
  message: string
  component: string
  created_at: string
  is_resolved: boolean
  resolved_at?: string | null
  resolved_by?: string | null
}

export interface SystemConfig {
  maintenance_mode: boolean
  default_response_depth: string
  global_rate_limit_per_min: number
  pdf_max_file_size_mb: number
  enable_web_grounding: boolean
  enable_ocr_fallback: boolean
  [key: string]: any
}

export interface CostsSummary {
  total_estimated_cost_usd: number
  pricing_registry: Record<string, { input: number; output: number }>
  fallback_rates: { input: number; output: number }
  cost_by_provider: Record<string, { tokens_in: number; tokens_out: number; cost_usd: number }>
}

