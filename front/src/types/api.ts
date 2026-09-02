/**
 * types/api.ts
 * Client <-> backend communication contracts.
 */

/** One row of the leaderboard returned by /api/record/rank. */
export interface RankItem {
  rank: number
  user_id: number
  nickname: string
  avatar_url: string
  region_code?: string
  best_time: number
}

/** /api/record/rank response (list + optional my rank). */
export interface RankResponse {
  rank: RankItem[]
  my_rank: number | null
}

/** GET /api/user/me -> data. */
export interface PlayerSummary {
  user: {
    id: number
    nickname: string
    avatar_url: string
    platform: string
    country_code: string
    region_code: string
    status: number
    created_at: string | null
  }
  stats: {
    total_games: number
    total_wins: number
    total_play_seconds: number
    best_by_level: Record<string, number>
  }
  props: Record<string, number>
  wallet: Record<string, number>
}

/** One row of GET /api/missions -> items. */
export interface MissionItem {
  mission_key: string
  scope: 'daily' | 'weekly' | 'achievement'
  period: string
  title: string
  target_type: string
  target_value: number
  progress: number
  completed: boolean
  claimed: boolean
  reward_prop_key: string
  reward_amount: number
}

/** One row of GET /api/levels -> items（远端关卡，D1）。 */
export interface RemoteLevel {
  level_id: number
  title: string
  icon_types: number
  regions: import('./game').RegionConfig[]
  version: number
}

/** One shop product row（C3）。 */
export interface ShopProduct {
  sku: string
  name: string
  currency: string
  amount: number
}

/** Unified backend response envelope: { code, message, data }. */
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}
