/**
 * request.ts
 * Native fetch wrapper replacing the original wx.request helper.
 * - Auto-attaches the JWT token from localStorage (Authorization: Bearer ...)
 * - Silently logs in as a guest when no token exists
 * - Retries once after a 401 (fresh guest token)
 * - Per-scenario resilience:
 *   startGameSession -> fast fail (3s AbortController timeout, no retry)
 *   saveScore        -> fetchWithRetry (exponential backoff + jitter, silent)
 */

const TOKEN_KEY = 'hd_token'
const DEVICE_ID_KEY = 'hd_device_id'

/** Anti-cheat salt: must match the backend ANTI_CHEAT_SALT exactly. */
const SIGN_SALT = 'Hd@2026!AntiCheat#7xQz$K9vM'

/**
 * Backend base URL:
 * - 生产/联调可显式设置 VITE_API_BASE_URL（构建期注入）；
 * - 未设置时按页面访问来源推导（同源主机名 + 8089 端口），
 *   局域网内手机通过 http://<本机IP>:5173 访问时，API 自动指向 http://<本机IP>:8089，
 *   不会误指向手机自己的 localhost。
 */
const BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ??
  `${location.protocol}//${location.hostname}:8089`

import type { ApiResponse, RankItem } from '../types/api'

/** startGameSession hard timeout (fast fail, no retry). */
const START_TIMEOUT_MS = 3000
/** Defaults for fetchWithRetry (saveScore). */
const RETRY_MAX_ATTEMPTS = 4
const RETRY_BASE_DELAY_MS = 1000
const RETRY_TIMEOUT_MS = 10_000

interface RequestOptions {
  method?: 'GET' | 'POST'
  data?: unknown
  /** External abort signal (caller-owned timeout / cancellation). */
  signal?: AbortSignal
}

/** HTTP/business error carrying a retry decision for fetchWithRetry. */
class HttpError extends Error {
  readonly status: number
  readonly retryable: boolean

  constructor(message: string, status: number, retryable: boolean) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.retryable = retryable
  }
}

/** Sleep helper for backoff delays. */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * Auth token storage, shared with the SDK adapters (WebAdapter / LineAdapter).
 * The SDK layer owns identity; the request layer only reads the JWT it stores.
 */
export function getAuthToken(): string {
  return getToken()
}

export function setAuthToken(token: string): void {
  setToken(token)
}

/**
 * Core request: fetch with JSON headers, optional Bearer token,
 * and 401 -> guest login -> retry once.
 * Network failures (fetch reject / timeout) throw retryable errors;
 * deterministic business rejections (4xx / code != 0) are non-retryable.
 */
async function request<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const { method = 'GET', data, signal } = options

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    signal,
    body: data === undefined ? undefined : JSON.stringify(data),
  })

  // Token missing/expired: silently refresh the token and retry once.
  if (response.status === 401 && !retried && path !== '/api/auth/guest-login') {
    await loginAsGuest()
    return request<T>(path, options, true)
  }

  const body = (await response.json()) as ApiResponse<T>
  if (response.ok && body.code === 0) return body.data
  throw new HttpError(body.message || `请求失败 (HTTP ${response.status})`, response.status, response.status >= 500)
}

/**
 * Higher-order fetch wrapper: exponential backoff with full jitter.
 * - maxAttempts attempts total (first attempt is immediate)
 * - baseDelayMs doubled per retry, then jittered in [0, delay) to de-correlate
 *   concurrent retries
 * - retries ONLY network-level failures (fetch reject / timeout / 5xx);
 *   deterministic 4xx/business errors throw immediately
 * - each attempt gets its own timeoutMs cap so the loop always terminates
 */
async function fetchWithRetry<T>(
  path: string,
  options: RequestOptions = {},
  config: { maxAttempts?: number; baseDelayMs?: number; timeoutMs?: number } = {},
): Promise<T> {
  const { maxAttempts = RETRY_MAX_ATTEMPTS, baseDelayMs = RETRY_BASE_DELAY_MS, timeoutMs = RETRY_TIMEOUT_MS } = config
  let lastError: unknown

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)

    try {
      return await request<T>(path, { ...options, signal: controller.signal })
    } catch (err) {
      lastError = err
      if (err instanceof HttpError && !err.retryable) throw err
      if (attempt >= maxAttempts - 1) break

      // Full jitter: delay in [0, base * 2^attempt) — AWS-recommended pattern.
      const delay = Math.floor(baseDelayMs * 2 ** attempt * Math.random())
      await sleep(delay)
    } finally {
      clearTimeout(timer)
    }
  }

  throw lastError
}

/** Get or create a stable client UUID (guest identity for silent auth). */
function getOrCreateDeviceId(): string {
  let id = localStorage.getItem(DEVICE_ID_KEY)
  if (!id) {
    id =
      typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `device-${Date.now()}-${Math.random().toString(36).slice(2)}`
    localStorage.setItem(DEVICE_ID_KEY, id)
  }
  return id
}

/**
 * Guest silent login (platform-agnostic): exchange the stable client UUID
 * for a JWT via POST /api/auth/guest-login, store it, and return the token.
 * Used by WebAdapter.login() and the 401 auto-refresh path.
 */
export async function loginAsGuest(): Promise<string> {
  const data = await request<{ token: string }>('/api/auth/guest-login', {
    method: 'POST',
    data: { guest_uuid: getOrCreateDeviceId() },
  })
  setAuthToken(data.token)
  return data.token
}

/**
 * Generic POST helper for SDK adapters that exchange platform credentials
 * for a unified JWT (e.g. LineAdapter -> POST /api/auth/line).
 */
export async function postApi<T>(path: string, data: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', data })
}

/** Ensure a valid token exists; silently obtain a guest one when missing. */
export async function ensureToken(): Promise<void> {
  if (!getAuthToken()) await loginAsGuest()
}

/** SHA-256 hex digest via the native Web Crypto API (no third-party deps). */
async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

/**
 * Open a game session before the level starts.
 * Backend stores { start_time, level_id } in Redis and returns a session id
 * that /api/record/submit requires (anti-bot timing baseline + replay guard).
 *
 * Resilience: FAST FAIL — 3s AbortController timeout, NO automatic retry.
 * Any failure (timeout / network / backend) throws 'NETWORK_START_FAILED' so
 * the caller can surface a manual "重新连接" dialog.
 */
export async function startGameSession(levelId = 1): Promise<string> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), START_TIMEOUT_MS)

  try {
    await ensureToken()
    const data = await request<{ session_id: string }>('/api/record/start', {
      method: 'POST',
      data: { level_id: levelId },
      signal: controller.signal,
    })
    return data.session_id
  } catch (err) {
    console.warn('[session] 开局会话失败（快速失败）:', err)
    throw new Error('NETWORK_START_FAILED')
  } finally {
    clearTimeout(timer)
  }
}

/**
 * Save the current run result to the backend.
 * win 时按 clear_time(秒)入排行榜；win/fail/quit 都会累计服务端每日统计
 * （对局数/时长），因此失败与中途退出也必须携带开局会话结算。
 * Signature: SHA256(level_id + clear_time + timestamp + SIGN_SALT), timestamp in seconds.
 *
 * Resilience: EXPONENTIAL BACKOFF via fetchWithRetry (4 attempts, 1s base,
 * full jitter). Runs silently: the win/lose panel flow is never blocked.
 * @param score Run duration in seconds.
 * @param levelId Level number (1-based).
 * @param sessionId Session id from startGameSession(); empty skips the submit.
 * @param outcome 本局结局：win / fail / quit（默认 win）
 */
export async function saveScore(
  score: number,
  levelId = 1,
  sessionId = '',
  outcome: 'win' | 'fail' | 'quit' = 'win',
): Promise<void> {
  if (!sessionId) {
    console.warn('[save] 缺少开局会话，跳过上报')
    return
  }

  await ensureToken()

  const timestamp = Math.floor(Date.now() / 1000)
  const sign = await sha256(`${levelId}${score}${timestamp}${SIGN_SALT}`)

  await fetchWithRetry('/api/record/submit', {
    method: 'POST',
    data: { level_id: levelId, clear_time: score, outcome, timestamp, sign, session_id: sessionId },
  })
}

/** Fetch the leaderboard of the given level (each user's best time). */
export async function getLeaderboard(levelId = 1, limit = 50): Promise<RankItem[]> {
  const data = await request<RankItem[]>(`/api/record/rank?level_id=${levelId}&limit=${limit}`)
  return Array.isArray(data) ? data : []
}

/*
 * ============================================================================
 * Backend CORS configuration guide (server/main.py)
 * ----------------------------------------------------------------------------
 * To allow this H5 (vite dev on http://localhost:5173, or the deployed H5
 * domain) to call the FastAPI backend cross-origin, enable CORSMiddleware:
 *
 *   from fastapi.middleware.cors import CORSMiddleware
 *
 *   app.add_middleware(
 *       CORSMiddleware,
 *       # "*" for development; restrict to real H5 domains in production.
 *       allow_origins=["*"],
 *       # Required to carry the Authorization header / credentials.
 *       allow_credentials=True,
 *       allow_methods=["*"],   # GET/POST/OPTIONS all allowed
 *       allow_headers=["*"],   # Authorization, Content-Type, ...
 *   )
 *
 * Notes:
 *   - Browsers always send a preflight OPTIONS request for cross-origin
 *     requests with an Authorization header; the middleware answers it.
 *   - When allow_origins=["*"] and allow_credentials=True are combined,
 *     Starlette echoes the request origin instead of "*", which is valid.
 *   - The backend in this repo already applies this config, so only enable
 *     it in case you run a different FastAPI entry (e.g. a gateway).
 * ============================================================================
 */
