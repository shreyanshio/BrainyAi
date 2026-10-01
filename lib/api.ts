import {
  AuthResponse,
  ChatMessage,
  ChatSendRequest,
  ChatSendResponse,
  ChatSession,
  ModelDefinition,
  UsageStatus,
  User,
  UserMemoryData,
  UserProfileStats,
} from '@/types/api'

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

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
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
    const res = await request<{ authenticated: boolean; user?: User }>('/api/auth/me')
    if (res?.authenticated && res.user) {
      return res.user
    }
  } catch {
    // Session not found or 401
  }

  // Fallback to checking /api/user/profile if session cookie is valid
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
  return res.user
}

export async function loginWithGoogle(credential: string): Promise<User> {
  const res = await request<AuthResponse>('/api/auth/google', {
    method: 'POST',
    body: JSON.stringify({ credential }),
  })
  if (!res.user) throw new ApiError('Authentication failed: no user returned', 401)
  return res.user
}

export async function loginWeb(name: string, username?: string): Promise<User> {
  const res = await request<AuthResponse>('/api/auth/web', {
    method: 'POST',
    body: JSON.stringify({ name, username }),
  })
  if (!res.user) throw new ApiError('Authentication failed: no user returned', 401)
  return res.user
}

export async function initTelegramLogin(): Promise<{ session_id: string; bot_url: string }> {
  return request<{ session_id: string; bot_url: string }>('/api/auth/init', {
    method: 'POST',
  })
}

export async function pollTelegramLogin(sessionId: string): Promise<{ status: string; user?: User }> {
  return request<{ status: string; user?: User }>(`/api/auth/poll/${sessionId}`)
}

export async function checkAuthSessionParam(sessionId: string): Promise<{ status: string; user?: User }> {
  return request<{ status: string; user?: User }>(`/api/auth/status/${sessionId}`)
}

export async function logoutUser(): Promise<void> {
  try {
    await request('/api/auth/logout', { method: 'POST' })
  } catch {
    // ignore
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
