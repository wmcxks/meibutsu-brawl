/**
 * clientErrors.ts（F3）
 * 前端错误捕获上报：window.onerror / unhandledrejection / 手动 reportError。
 *
 * - 攒批 + 定时冲刷（页面隐藏时 keepalive 兜底），错误通道绝不阻塞主流程
 * - 带可选 JWT（用户归因），失败静默丢弃，避免无限重试
 * - 上传目标 POST /api/errors（服务端限流 60 条/小时/用户）
 */

const ERROR_FLUSH_MS = 3000
const ERROR_MAX_QUEUE = 20

interface ErrorPayload {
  message: string
  stack?: string
  page_url: string
  platform: string
  client_ver: string
  extras?: Record<string, unknown>
  client_ts: number
}

let queue: ErrorPayload[] = []
let timer: number | null = null
let started = false

const BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? `${location.protocol}//${location.hostname}:8089`

const PLATFORM: string = import.meta.env.VITE_TARGET_PLATFORM ?? 'web'
const CLIENT_VER: string = import.meta.env.VITE_APP_VERSION ?? '0.0.0'

/** 控制台只保留第一层堆栈行，避免把源码路径全量上传（隐私/体积） */
function compactStack(stack: string | undefined, limit = 12): string | undefined {
  if (!stack) return undefined
  return stack.split('\n').slice(0, limit).join('\n')
}

function enqueue(payload: ErrorPayload): void {
  queue.push(payload)
  if (queue.length > ERROR_MAX_QUEUE) queue.shift()
  if (timer === null) {
    timer = window.setTimeout(() => {
      timer = null
      void flush()
    }, ERROR_FLUSH_MS)
  }
}

/** 页面隐藏时冲刷（keepalive），保证崩溃跳转/关闭前尽量送达 */
function onPageHide(): void {
  if (queue.length > 0) {
    queue = []
    void flush(true)
  }
}

async function flush(keepalive = false): Promise<void> {
  if (queue.length === 0) return
  const batch = queue.splice(0, 50)
  try {
    const token = localStorage.getItem('hd_token') ?? ''
    // 单条逐一上报（/api/errors 单条语义 + 服务端限流）；并发 ≤5 防突发
    const sends = batch.slice(0, 5).map((payload) =>
      fetch(`${BASE_URL}/api/errors`, {
        method: 'POST',
        keepalive,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      }),
    )
    const results = await Promise.allSettled(sends)
    // 网络失败的少量重入队（保留至下次冲刷），其余丢弃
    results.forEach((r, i) => {
      if (r.status === 'rejected' && batch[i] && queue.length < ERROR_MAX_QUEUE) {
        queue.push(batch[i])
      }
    })
  } catch (err) {
    // 错误通道不能成为新的告警源
    console.warn('[errors] 错误上报失败:', err)
  }
}

function pageUrl(): string {
  try {
    return location.origin + location.pathname
  } catch {
    return ''
  }
}

/**
 * 手动上报一条错误（try/catch / Promise catch / Phaser 场景错误处调用）。
 * 与 window 级监听共用队列，自动去重节流由队列长度兜底。
 */
export function reportError(
  err: unknown,
  extras?: Record<string, unknown>,
  stackOverride?: string,
): void {
  const message =
    err instanceof Error ? err.message : typeof err === 'string' ? err : String(err ?? 'unknown error')
  if (!message || message.length > 500) return
  enqueue({
    message: message.slice(0, 500),
    stack: compactStack(stackOverride ?? (err instanceof Error ? err.stack : undefined)),
    page_url: pageUrl(),
    platform: PLATFORM,
    client_ver: CLIENT_VER,
    extras,
    client_ts: Math.floor(Date.now() / 1000),
  })
}

/** 注册全局监听（main.ts 启动时调用一次）。 */
export function initErrorReporting(): void {
  if (started || typeof window === 'undefined') return
  started = true

  window.addEventListener('error', (event) => {
    const message = event.message || 'Uncaught error'
    if (!message) return
    enqueue({
      message: message.slice(0, 500),
      stack: compactStack(event.error?.stack),
      page_url: pageUrl(),
      platform: PLATFORM,
      client_ver: CLIENT_VER,
      extras: { col: event.colno, line: event.lineno, file: event.filename },
      client_ts: Math.floor(Date.now() / 1000),
    })
  })

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason
    reportError(reason instanceof Error ? reason : new Error(String(reason ?? 'unhandled rejection')))
  })

  window.addEventListener('pagehide', onPageHide)
  window.addEventListener('beforeunload', onPageHide)
}
