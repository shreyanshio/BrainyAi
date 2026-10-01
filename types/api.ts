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
}

export interface AuthResponse {
  authenticated: boolean
  user: User | null
  status?: string
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
}

export interface ChatSendRequest {
  session_id?: string | null
  message: string
  content?: string
  model?: string
  answer_length?: AnswerLength
  tone?: string
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
}

export interface QuickPrompt {
  id: string
  title: string
  description: string
  prompt: string
  category: 'concept' | 'problem' | 'code' | 'exam'
}
