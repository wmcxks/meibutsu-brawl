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

import type { ApiResponse, MissionItem, PlayerSummary, RankResponse, RemoteLevel, ShopProduct } from '../types/api'

/** startGameSession hard timeout (fast fail, no retry). */
const START_TIMEOUT_MS = 3000
/** Defaults for fetchWithRetry (saveScore). */
const RETRY_MAX_ATTEMPTS = 4
const RETRY_BASE_DELAY_MS = 1000
const RETRY_TIMEOUT_MS = 10_000

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
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
 * Current device/guest UUID. LINE 平台登录时随 id_token 一并上报，
 * 服务端把本机游客数据并入 LINE 账号（A8：防丢号/跨端升级）。
 */
export function getDeviceId(): string {
  return getOrCreateDeviceId()
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

/** Fetch the leaderboard of the given level (national or a region). */
export async function getLeaderboard(
  levelId = 1,
  region = '',
  limit = 50,
): Promise<RankResponse> {
  const query = new URLSearchParams({ level_id: String(levelId), limit: String(limit) })
  if (region) query.set('region', region)
  const data = await request<RankResponse>(`/api/record/rank?${query.toString()}`)
  return data ?? { rank: [], my_rank: null }
}

/** GET /api/user/me：资料 + 累计统计 + 道具/钱包余额。 */
export async function fetchMe(): Promise<PlayerSummary> {
  await ensureToken()
  return request<PlayerSummary>('/api/user/me')
}

/** PATCH /api/user/me：修改昵称 / 区域。 */
export async function updateMe(partial: {
  nickname?: string
  region_code?: string
  country_code?: string
}): Promise<PlayerSummary['user']> {
  return request<PlayerSummary['user']>('/api/user/me', {
    method: 'PATCH',
    data: partial,
  })
}

/** DELETE /api/user/me：账号注销（二次确认后删除本人全部数据）。 */
export async function deleteAccount(): Promise<void> {
  await request('/api/user/me', { method: 'DELETE', data: { confirm: true } })
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(DEVICE_ID_KEY)
}

/** GET /api/missions：任务列表（含进度与领取状态）。 */
export async function fetchMissions(scope: 'daily' | 'weekly' | 'achievement' = 'daily'): Promise<MissionItem[]> {
  const data = await request<{ items: MissionItem[] }>(`/api/missions?scope=${scope}`)
  return data?.items ?? []
}

/** POST /api/missions/claim：领取任务奖励。 */
export async function claimMission(missionKey: string, period: string): Promise<void> {
  await request('/api/missions/claim', { method: 'POST', data: { mission_key: missionKey, period } })
}

/**
 * GET /api/levels：远端关卡配置（布局/标题/图标种类）。
 * 3s 快速失败：关卡配置拿不到时回退到本地静态 LEVELS（不发版前置条件）。
 */
export async function fetchLevels(): Promise<RemoteLevel[]> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 3000)
  try {
    const data = await request<{ items: RemoteLevel[] }>('/api/levels', { signal: controller.signal })
    return data?.items ?? []
  } catch (err) {
    console.warn('[levels] 远端关卡拉取失败（回退本地配置）:', err)
    return []
  } finally {
    clearTimeout(timer)
  }
}

/** GET /api/shop/products：商品目录。 */
export async function fetchProducts(): Promise<ShopProduct[]> {
  const data = await request<{ items: ShopProduct[] }>('/api/shop/products')
  return data?.items ?? []
}

/** POST /api/shop/order：下单（同一用户仅一笔 pending 订单）。 */
export async function createShopOrder(sku: string): Promise<{ order_no: string; status: string }> {
  return request('/api/shop/order', { method: 'POST', data: { sku } })
}

/** POST /api/shop/order/cancel：取消我的待支付订单。 */
export async function cancelShopOrder(): Promise<void> {
  await request('/api/shop/order/cancel', { method: 'POST' })
}

/** GET /api/configs/public：客户端可见远端配置（公告等，无需登录）。 */
export async function fetchPublicConfigs(): Promise<Record<string, unknown>> {
  const data = await request<Record<string, unknown>>('/api/configs/public')
  return data ?? {}
}

/*
 * ============================================================================
 * 埋点上报（F1）—— 轻量批量 + 防阻塞
 * ============================================================================
 */
interface TrackEvent {
  event: string
  props?: Record<string, unknown>
  client_ts?: number
}

let trackQueue: TrackEvent[] = []
let trackTimer: number | null = null
const TRACK_FLUSH_MS = 1500
const TRACK_BATCH_MAX = 10

/**
 * 打点（fire-and-forget）：本地攒批，满 10 条或 1.5s 后统一上报，
 * 页面离开时用 keepalive 兜底。任何失败只告警，绝不影响游戏主流程。
 * @param event 事件名（小写 snake_case，如 level_win）
 * @param props 属性（扁平对象，服务端限制单条 JSON ≤1KB）
 */
export function track(event: string, props: Record<string, unknown> = {}): void {
  trackQueue.push({ event, props, client_ts: Math.floor(Date.now() / 1000) })
  if (trackQueue.length >= TRACK_BATCH_MAX) {
    void flushTrack(false)
    return
  }
  if (trackTimer === null) {
    trackTimer = window.setTimeout(() => {
      trackTimer = null
      void flushTrack(false)
    }, TRACK_FLUSH_MS)
  }
}

async function flushTrack(keepalive: boolean): Promise<void> {
  if (trackQueue.length === 0) return
  const batch = trackQueue.splice(0, 50)
  try {
    const token = getToken()
    await fetch(`${BASE_URL}/api/events`, {
      method: 'POST',
      keepalive,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ events: batch }),
    })
  } catch (err) {
    // 已出队的数据丢弃即可，避免无限重试拖累主流程
    console.warn('[track] 埋点上报失败:', err)
  }
}

// 页面隐藏/关闭前兜底冲刷（keepalive 允许在 unload 阶段发请求）
if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', () => {
    if (trackQueue.length > 0) void flushTrack(true)
  })
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
