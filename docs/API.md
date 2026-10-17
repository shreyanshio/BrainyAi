# REST API Reference — Brainy AI

This document provides the authoritative specification for all REST API endpoints exposed by the Brainy AI Flask backend (`app.py`).

---

## 1. Global Conventions & Headers

### Base URL
* **Production**: Configured via `NEXT_PUBLIC_API_URL` (e.g. `https://brainyai-production.up.railway.app`)
* **Local Development**: `http://localhost:5000`

### Authentication Header
Endpoints marked with **🔒 Authenticated** require a signed HS256 Bearer token.
Attach the token in the standard HTTP `Authorization` header:

```http
Authorization: Bearer <your_jwt_token>
```

Alternatively, session cookies (`session=...`) are accepted as an automatic fallback.

### Standard Response Envelope
All JSON responses follow predictable structures. On validation or server failure, error payloads return:

```json
{
  "error": "Human-readable description of the error",
  "code": "OPTIONAL_ERROR_CODE"
}
```

### Common HTTP Status Codes
* `200 OK`: Request succeeded.
* `400 Bad Request`: Missing or malformed parameters.
* `401 Unauthorized`: Missing or invalid Bearer token / session.
* `403 Forbidden`: Authenticated user lacks administrator privileges or is suspended.
* `404 Not Found`: Requested session or user does not exist.
* `429 Too Many Requests`: User exceeded sliding-window rate limit (10 req/min) or 5-hour quota (30 messages / 5 hours).
* `500 Internal Server Error`: Backend runtime or provider error.

---

## 2. System & Configuration Endpoints

### `GET /api/health`
Public health probe used by container orchestrators and status monitors.

* **Authentication**: None
* **Response** `200 OK`:
  ```json
  {
    "status": "ok",
    "service": "brainy-api",
    "timestamp": "2026-10-17T13:45:00.000Z"
  }
  ```

### `GET /api/config`
Exposes public runtime configurations to the frontend.

* **Authentication**: None
* **Response** `200 OK`:
  ```json
  {
    "api_base_url": "https://brainyai-production.up.railway.app",
    "telegram_bot_url": "https://t.me/AiChatExpert_Bot",
    "google_client_id": "your_google_client_id.apps.googleusercontent.com"
  }
  ```

---

## 3. Authentication Endpoints

### `POST /api/auth/student_pass`
Generates a quick-start student identity without passwords.

* **Authentication**: None
* **Request Body**:
  ```json
  {
    "student_name": "Alex Mercer"
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "success": true,
    "user": {
      "id": 9823418291,
      "username": "alex_mercer",
      "first_name": "Alex Mercer",
      "login_type": "student_pass",
      "level": "Scholar"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

### `POST /api/auth/web`
Authenticates a student using custom display name and optional username.

* **Authentication**: None
* **Request Body**:
  ```json
  {
    "name": "Jane Doe",
    "username": "janedoe"
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "success": true,
    "user": {
      "id": 8172938127,
      "username": "janedoe",
      "first_name": "Jane Doe",
      "login_type": "web",
      "level": "Scholar"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

### `POST /api/auth/google`
Authenticates a user via Google Identity Services OAuth 2.0 credential.

* **Authentication**: None
* **Request Body**:
  ```json
  {
    "credential": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "success": true,
    "user": {
      "id": 10928301928,
      "username": "jane.doe",
      "first_name": "Jane",
      "email": "jane.doe@example.com",
      "login_type": "google",
      "level": "Scholar"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

### `POST /api/auth/initdata`
Validates Telegram WebApp `initData` HMAC-SHA256 signature and returns authentication credentials.

* **Authentication**: None
* **Request Body**:
  ```json
  {
    "init_data": "query_id=AAH...&user=%7B%22id%22%3A7544007323...&hash=..."
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "success": true,
    "user": {
      "id": 7544007323,
      "username": "shreyanshio",
      "first_name": "Shreyansh",
      "login_type": "telegram"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

### `GET /api/auth/status/<session_id>` (Alias: `/api/auth/poll/<session_id>`)
Polls the verification status of a Telegram bot magic `/login` session.

* **Authentication**: None
* **Response (Waiting)** `200 OK`:
  ```json
  {
    "status": "waiting"
  }
  ```
* **Response (Confirmed)** `200 OK`:
  ```json
  {
    "status": "confirmed",
    "user": {
      "id": 7544007323,
      "username": "shreyanshio",
      "first_name": "Shreyansh"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

### `GET /api/auth/me`
Checks the validity of the current token / session and returns student profile metadata.

* **Authentication**: 🔒 Authenticated
* **Response** `200 OK`:
  ```json
  {
    "authenticated": true,
    "user": {
      "id": 7544007323,
      "username": "shreyanshio",
      "first_name": "Shreyansh",
      "login_type": "telegram",
      "level": "Grandmaster",
      "score": 450,
      "total": 52
    }
  }
  ```

### `POST /api/auth/logout`
Terminates the user session.

* **Authentication**: 🔒 Authenticated
* **Response** `200 OK`:
  ```json
  {
    "success": true
  }
  ```

---

## 4. Chat & Conversation Management Endpoints

### `GET /api/sessions`
Retrieves all historical conversation sessions for the authenticated student.

* **Authentication**: 🔒 Authenticated
* **Response** `200 OK`:
  ```json
  {
    "sessions": [
      {
        "id": "e4b6c3d2-8f1a-4d7e-9c2b-1a3f5e7d9c1b",
        "title": "Quantum Mechanics Wave Functions",
        "created_at": "2026-10-17T11:20:00.000Z"
      }
    ]
  }
  ```

### `POST /api/sessions`
Creates a new blank chat session.

* **Authentication**: 🔒 Authenticated
* **Request Body** (Optional):
  ```json
  {
    "title": "Thermodynamics Revision"
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "id": "f8a1b2c3-d4e5-4f6a-8b9c-0d1e2f3a4b5c",
    "title": "Thermodynamics Revision",
    "created_at": "2026-10-17T13:46:00.000Z"
  }
  ```

### `GET /api/chat/<session_id>`
Retrieves message history for a specific conversation session.

* **Authentication**: 🔒 Authenticated
* **Response** `200 OK`:
  ```json
  {
    "session_id": "e4b6c3d2-8f1a-4d7e-9c2b-1a3f5e7d9c1b",
    "title": "Quantum Mechanics Wave Functions",
    "messages": [
      {
        "role": "user",
        "content": "Explain the physical significance of psi squared.",
        "created_at": "2026-10-17T11:20:05.000Z"
      },
      {
        "role": "assistant",
        "content": "In quantum mechanics, $|\\psi(x,t)|^2$ represents the probability density...",
        "created_at": "2026-10-17T11:20:07.000Z"
      }
    ]
  }
  ```

### `DELETE /api/chat/<session_id>`
Deletes a conversation session and all associated messages.

* **Authentication**: 🔒 Authenticated
* **Response** `200 OK`:
  ```json
  {
    "success": true
  }
  ```

### `POST /api/chat/send`
Submits a query to the multi-provider study AI engine within a session.

* **Authentication**: 🔒 Authenticated
* **Request Body**:
  ```json
  {
    "session_id": "e4b6c3d2-8f1a-4d7e-9c2b-1a3f5e7d9c1b",
    "message": "Calculate the de Broglie wavelength of an electron moving at 10^6 m/s.",
    "mode": "brainy"
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "success": true,
    "session_id": "e4b6c3d2-8f1a-4d7e-9c2b-1a3f5e7d9c1b",
    "response": "To find the de Broglie wavelength $\\lambda = \\frac{h}{p} = \\frac{h}{m v}$:\n\n1. Planck's constant $h = 6.626 \\times 10^{-34} \\text{ J}\\cdot\\text{s}$\n2. Electron mass $m = 9.109 \\times 10^{-31} \\text{ kg}$...",
    "message_count": 4,
    "message_limit": 30,
    "quota_window_hours": 5
  }
  ```
* **Error Response (Quota Exceeded)** `429 Too Many Requests`:
  ```json
  {
    "error": "You have reached your limit of 30 questions per 5 hours. Please take a break and return later.",
    "code": "QUOTA_EXCEEDED",
    "message_count": 30,
    "message_limit": 30,
    "quota_window_hours": 5
  }
  ```

---

## 5. Student Profile & Memory Endpoints

### `GET /api/user/profile`
Retrieves academic performance statistics, streak counter, and current level.

* **Authentication**: 🔒 Authenticated
* **Response** `200 OK`:
  ```json
  {
    "user": {
      "id": 7544007323,
      "username": "shreyanshio",
      "first_name": "Shreyansh"
    },
    "stats": {
      "streak": 5,
      "level": "Grandmaster",
      "total_queries": 142,
      "quiz_score": 88,
      "liked_notes_count": 14
    }
  }
  ```

### `GET /api/user/memory`
Retrieves personalized learning memory, saved notebook bookmarks, and past topics.

* **Authentication**: 🔒 Authenticated
* **Response** `200 OK`:
  ```json
  {
    "memory": {
      "level": "Grandmaster",
      "score": 450,
      "total": 52,
      "liked_notes": [
        "Maxwell's Equations integral vs differential forms summary"
      ],
      "history": ["Rotational Dynamics", "Organic Reaction Mechanisms"]
    }
  }
  ```

---

## 6. Administrative Control Endpoints (`/api/admin/*`)

> **Note**: All administrative endpoints require that the caller's user ID, username, or email matches one of the values configured in `ADMIN_USER_IDS`, `ADMIN_USERNAMES`, or `ADMIN_EMAILS`. Non-admin requests receive `403 Forbidden`.

### `GET /api/admin/overview` (Alias: `/api/admin/usage`)
Returns high-level system usage telemetry from Supabase.

* **Authentication**: 🔒 Administrator Only
* **Response** `200 OK`:
  ```json
  {
    "total_users": 1284,
    "active_today": 94,
    "active_week": 412,
    "total_messages": 18450,
    "recent_logins": [
      {
        "user_id": 98127391,
        "username": "scholar_jane",
        "first_name": "Jane",
        "login_type": "google",
        "created_at": "2026-10-17T13:40:12.000Z"
      }
    ],
    "login_breakdown": {
      "google": 520,
      "telegram": 460,
      "web": 210,
      "student_pass": 94
    }
  }
  ```

### `GET /api/admin/users`
Lists registered users with search, pagination, and suspension status.

* **Authentication**: 🔒 Administrator Only
* **Query Parameters**:
  * `search` (Optional): Filter by username, first name, or numeric user ID.
* **Response** `200 OK`:
  ```json
  {
    "count": 1,
    "users": [
      {
        "id": 98127391,
        "username": "scholar_jane",
        "first_name": "Jane",
        "level": "Scholar",
        "total": 45,
        "score": 38,
        "is_suspended": false,
        "joined_at": "2026-09-12T10:00:00.000Z",
        "last_seen": "2026-10-17T13:40:12.000Z"
      }
    ]
  }
  ```

### `POST /api/admin/users/<id>/suspend`
Suspends or reinstates a user's access across the web platform and Telegram bot.

* **Authentication**: 🔒 Administrator Only
* **Request Body**:
  ```json
  {
    "suspend": true
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "success": true,
    "user_id": 98127391,
    "is_suspended": true
  }
  ```

### `DELETE /api/admin/users/<id>`
Permanently deletes a student's profile, session history, memory, and database entries.

* **Authentication**: 🔒 Administrator Only
* **Response** `200 OK`:
  ```json
  {
    "success": true,
    "user_id": 98127391
  }
  ```

### `GET /api/admin/health`
Returns detailed operational telemetry on external providers and database latency.

* **Authentication**: 🔒 Administrator Only
* **Response** `200 OK`:
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "database_latency_ms": 42,
    "uptime_seconds": 86420,
    "active_providers": {
      "groq": "available",
      "gemini": "available",
      "deepseek": "available",
      "openrouter": "available"
    }
  }
  ```
