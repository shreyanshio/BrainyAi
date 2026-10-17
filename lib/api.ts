import {
  AdminUsageReport,
  AdminUsersResponse,
  AuthResponse,
  ChatMessage,
  ChatSendRequest,
  ChatSendResponse,
  ChatSession,
  ModelDefinition,
  SystemHealthStatus,
  UsageStatus,
  User,
  UserMemoryData,
  UserProfileStats,
  UserPreferences,
  StreamEvent,
  StreamChatCallbacks,
} from '@/types/api'

export const AUTH_TOKEN_KEY = 'brainy_auth_token'

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token: string): void {
  if (typeof window === 'undefined') return
  try {
    if (token) {
      localStorage.setItem(AUTH_TOKEN_KEY, token)
    } else {
      localStorage.removeItem(AUTH_TOKEN_KEY)
    }
  } catch {
    // ignore
  }
}

export function clearStoredToken(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY)
  } catch {
    // ignore
  }
}

export const getApiBase = (): string => {
  return (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')
}

export class ApiError extends Error {
  status: number
  data?: any
  constructor(message: string, status: number, data?: any) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const base = getApiBase()
  const url = `${base}${path}`
  const token = getStoredToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers,
  })

  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/me') {
      clearStoredToken()
    }
    let errorData: any = null
    try {
      errorData = await response.json()
    } catch {
      // ignore json parse error
    }
    const message = errorData?.error || errorData?.message || `Request failed with status ${response.status}`
    throw new ApiError(message, response.status, errorData)
  }

  return response.json() as Promise<T>
}

// ── Auth APIs ──────────────────────────────────────────────

export async function fetchPublicConfig(): Promise<{ google_client_id?: string }> {
  try {
    return await request<{ google_client_id?: string }>('/api/config')
  } catch {
    return {}
  }
}

export async function checkAuth(): Promise<User | null> {
  try {
    const res = await request<{ authenticated: boolean; user?: User; token?: string }>('/api/auth/me')
    if (res?.authenticated && res.user) {
      if (res.token) setStoredToken(res.token)
      return res.user
    }
  } catch {
    // Session not found or 401
  }

  // Fallback to checking /api/user/profile if session cookie/token is valid
  try {
    const prof = await request<UserProfileStats>('/api/user/profile')
    if (prof?.user_id) {
      return {
        id: prof.user_id,
        first_name: prof.first_name || 'Student',
        username: prof.username || '',
        photo_url: '',
      }
    }
  } catch {
    // not logged in
  }

  return null
}

export async function loginWithTelegramInitData(initData: string): Promise<User> {
  const res = await request<AuthResponse>('/api/auth/initdata', {
    method: 'POST',
    body: JSON.stringify({ initData }),
  })
  if (!res.user) throw new ApiError('Authentication failed: no user returned', 401)
  if (res.token) setStoredToken(res.token)
  return res.user
}

export async function loginWithGoogle(credential: string): Promise<User> {
  const res = await request<AuthResponse>('/api/auth/google', {
    method: 'POST',
    body: JSON.stringify({ credential }),
  })
  if (!res.user) throw new ApiError('Authentication failed: no user returned', 401)
  if (res.token) setStoredToken(res.token)
  return res.user
}

export async function loginWeb(name: string, username?: string): Promise<User> {
  const res = await request<AuthResponse>('/api/auth/web', {
    method: 'POST',
    body: JSON.stringify({ name, username }),
  })
  if (!res.user) throw new ApiError('Authentication failed: no user returned', 401)
  if (res.token) setStoredToken(res.token)
  return res.user
}

export async function loginStudentPass(): Promise<User> {
  const res = await request<AuthResponse>('/api/auth/student_pass', {
    method: 'POST',
  })
  if (!res.user) throw new ApiError('Authentication failed: no user returned', 401)
  if (res.token) setStoredToken(res.token)
  return res.user
}


export async function initTelegramLogin(): Promise<{ session_id: string; bot_url: string }> {
  return request<{ session_id: string; bot_url: string }>('/api/auth/init', {
    method: 'POST',
  })
}

export async function pollTelegramLogin(sessionId: string): Promise<{ status: string; user?: User; token?: string }> {
  const res = await request<{ status: string; user?: User; token?: string }>(`/api/auth/poll/${sessionId}`)
  if (res?.token) setStoredToken(res.token)
  return res
}

export async function checkAuthSessionParam(sessionId: string): Promise<{ status: string; user?: User; token?: string }> {
  const res = await request<{ status: string; user?: User; token?: string }>(`/api/auth/status/${sessionId}`)
  if (res?.token) setStoredToken(res.token)
  return res
}

export async function logoutUser(): Promise<void> {
  try {
    await request('/api/auth/logout', { method: 'POST' })
  } catch {
    // ignore
  } finally {
    clearStoredToken()
  }
}

// ── Usage & Quota APIs (30 msgs / 8 hours) ─────────────────

export async function fetchUsage(): Promise<UsageStatus> {
  return request<UsageStatus>('/api/usage')
}

// ── Chat Session APIs ──────────────────────────────────────

export async function fetchSessions(): Promise<ChatSession[]> {
  const data = await request<ChatSession[] | { sessions: ChatSession[] }>('/api/sessions')
  if (Array.isArray(data)) return data
  return data.sessions || []
}

export async function createSession(title: string = 'New Study Session'): Promise<ChatSession> {
  return request<ChatSession>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  await request(`/api/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request(`/api/sessions/${sessionId}`, {
    method: 'DELETE',
  })
}

export async function fetchSessionHistory(
  sessionId: string
): Promise<{ messages: ChatMessage[]; usage: UsageStatus; title?: string }> {
  return request<{ messages: ChatMessage[]; usage: UsageStatus; title?: string }>(`/api/chat/${sessionId}`)
}

export async function sendChatMessage(req: ChatSendRequest): Promise<ChatSendResponse> {
  return request<ChatSendResponse>('/api/chat/send', {
    method: 'POST',
    body: JSON.stringify({
      session_id: req.session_id,
      message: req.message,
      content: req.message,
      model: req.model,
      answer_length: req.answer_length,
      tone: req.tone,
    }),
  })
}

export async function streamChatMessage(
  req: ChatSendRequest,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal
): Promise<string> {
  const base = getApiBase()
  const url = `${base}/api/chat/stream`
  const token = getStoredToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/x-ndjson',
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: JSON.stringify({
      session_id: req.session_id,
      message: req.message,
      content: req.message,
      model: req.model,
      answer_length: req.answer_length,
      tone: req.tone,
    }),
    signal,
  })

  if (!response.ok) {
    if (response.status === 401) {
      clearStoredToken()
    }
    let errorData: any = null
    try {
      errorData = await response.json()
    } catch {
      // ignore non-json error body
    }
    const message =
      errorData?.error || errorData?.message || `Streaming request failed (${response.status})`
    const err = new ApiError(message, response.status, errorData)
    callbacks.onError?.(err)
    throw err
  }

  if (!response.body) {
    const err = new ApiError('No response body for streaming', response.status)
    callbacks.onError?.(err)
    throw err
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let accumulatedText = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      // Retain incomplete chunk in buffer
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue

        try {
          const event: StreamEvent = JSON.parse(trimmed)
          switch (event.type) {
            case 'start':
              callbacks.onStart?.(event.session_id, event.request_id)
              break
            case 'status':
              callbacks.onStatus?.(event.stage)
              break
            case 'delta':
              accumulatedText += event.text
              callbacks.onDelta?.(event.text, accumulatedText)
              break
            case 'done':
              callbacks.onDone?.(event)
              break
            case 'error': {
              const streamErr = new ApiError(event.message, 500, event)
              callbacks.onError?.(streamErr, accumulatedText)
              throw streamErr
            }
          }
        } catch (parseErr) {
          if (parseErr instanceof ApiError) throw parseErr
          console.warn('[stream] Malformed JSON line in stream:', trimmed, parseErr)
        }
      }
    }

    // Flush any leftover line
    if (buffer.trim()) {
      try {
        const event: StreamEvent = JSON.parse(buffer.trim())
        if (event.type === 'delta') {
          accumulatedText += event.text
          callbacks.onDelta?.(event.text, accumulatedText)
        } else if (event.type === 'done') {
          callbacks.onDone?.(event)
        }
      } catch {
        // ignore
      }
    }

    return accumulatedText
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      return accumulatedText
    }
    callbacks.onError?.(err, accumulatedText)
    throw err
  } finally {
    reader.releaseLock()
  }
}

// ── Profile, Notes & Models ────────────────────────────────

export async function fetchUserProfile(): Promise<UserProfileStats> {
  return request<UserProfileStats>('/api/user/profile')
}

export async function fetchUserMemory(): Promise<UserMemoryData> {
  return request<UserMemoryData>('/api/user/memory')
}

export async function saveUserMemoryNote(note: string): Promise<void> {
  await request('/api/user/memory', {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export async function fetchModels(): Promise<ModelDefinition[]> {
  try {
    return await request<ModelDefinition[]>('/api/models')
  } catch {
    return []
  }
}

export async function fetchUserPreferences(): Promise<Partial<UserPreferences>> {
  try {
    return await request<Partial<UserPreferences>>('/api/user/preferences')
  } catch {
    return {}
  }
}

export async function saveUserPreferences(
  preferences: Partial<UserPreferences>
): Promise<void> {
  await request('/api/user/preferences', {
    method: 'POST',
    body: JSON.stringify(preferences),
  })
}

// ── Admin APIs ─────────────────────────────────────────────

export async function fetchAdminCheck(): Promise<boolean> {
  try {
    const res = await request<{ is_admin: boolean }>('/api/admin/check')
    return Boolean(res?.is_admin)
  } catch {
    return false
  }
}

export async function fetchAdminOverview(): Promise<AdminUsageReport> {
  return request<AdminUsageReport>('/api/admin/overview')
}

export async function fetchAdminUsers(
  q: string = '',
  page: number = 1,
  limit: number = 25
): Promise<AdminUsersResponse> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  params.set('page', String(page))
  params.set('limit', String(limit))
  return request<AdminUsersResponse>(`/api/admin/users?${params.toString()}`)
}

export async function toggleUserSuspend(
  userId: number
): Promise<{ status: string; user_id: number; is_suspended: boolean }> {
  return request<{ status: string; user_id: number; is_suspended: boolean }>(
    `/api/admin/users/${userId}/suspend`,
    { method: 'POST' }
  )
}

export async function deleteUserAccount(
  userId: number
): Promise<{ status: string; deleted_user_id: number }> {
  return request<{ status: string; deleted_user_id: number }>(
    `/api/admin/users/${userId}`,
    { method: 'DELETE' }
  )
}

export async function fetchSystemHealth(): Promise<SystemHealthStatus> {
  return request<SystemHealthStatus>('/api/admin/health')
}
