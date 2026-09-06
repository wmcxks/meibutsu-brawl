/**
 * bootPrefetch.ts
 * 首屏启动预取（第一关免「ステージ生成中...」提示）：
 * 在 Phaser 游戏创建前，把「远端关卡配置 + 第 1 关开局会话」一次拉好，
 * GameScene 首次进入第 1 关时直接消费，跳过等待提示；
 * 任一环节失败则返回 null，场景走原有「显示提示 → 现场请求」兜底。
 * 全程 best-effort，绝不阻塞游戏启动。
 */

import { fetchLevels, startGameSession } from '../api/request'
import type { RemoteLevel } from '../types/api'

/** 消费一次即清空：重启/换关后不再复用同一会话（防重放与过期）。 */
interface FirstStageData {
  levels: RemoteLevel[] | null
  sessionId: string | null
}

let cached: FirstStageData | null = null

/** 启动期调用：拉取远端关卡并预约第 1 关会话（失败静默）。 */
export async function prefetchFirstStage(): Promise<void> {
  try {
    // 两项相互独立 → 并行预取，缩短首屏等待
    const [levelsResult, sessionResult] = await Promise.allSettled([
      fetchLevels(),
      startGameSession(1),
    ])
    let levels: RemoteLevel[] | null = null
    if (levelsResult.status === 'fulfilled' && levelsResult.value.length > 0) {
      levels = levelsResult.value
    } else {
      console.warn('[boot] 远端关卡预取失败（进入游戏时回退本地）:', levelsResult.status === 'rejected' ? levelsResult.reason : 'empty')
    }
    let sessionId: string | null = null
    if (sessionResult.status === 'fulfilled') {
      sessionId = sessionResult.value
    } else {
      console.warn('[boot] 第 1 关会话预取失败（进游戏时兜底重试）:', sessionResult.reason)
    }
    cached = { levels, sessionId }
    console.log('[boot] 第 1 关预取完成:', {
      levels: levels?.length ?? 0,
      session: Boolean(sessionId),
    })
  } catch (err) {
    console.warn('[boot] 首关预取失败（忽略，进入游戏时兜底）:', err)
  }
}

/** GameScene 首次进入时取走预取数据（只可取一次）。 */
export function takeFirstStageData(): FirstStageData | null {
  const data = cached
  cached = null
  return data
}

/** BootScene 预载第一关图标时读取：预取到的远端第 1 关 icon_types（不消费缓存）。 */
export function getPrefetchedFirstIconTypes(): number | null {
  return cached?.levels?.[0]?.icon_types ?? null
}
