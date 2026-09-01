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
  best_time: number
}

/** Unified backend response envelope: { code, message, data }. */
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}
