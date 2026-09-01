/**
 * types/game.ts
 * Shared game-domain types (cards, levels, slot tray).
 * Pure data contracts — NO framework code (no Phaser/wx/DOM).
 */

/** Lifecycle status of a single card node. */
export type CardStatus = 'ALIVE' | 'REMOVED'

/**
 * A single card node placed on a 3D board.
 * x/y = top-left position in design-space pixels,
 * z   = stacking depth (higher z renders above / can block lower cards).
 */
export interface CardNode {
  /** Unique card id, assigned by LevelManager during loadLevel(). */
  id: string
  /** Matching key: cards sharing the same type can form a triple. */
  type: string
  /** Optional texture/key used by the renderer. Kept as plain data here. */
  texture?: string
  /** Horizontal position (top-left) in design-space pixels. */
  x: number
  /** Vertical position (top-left) in design-space pixels. */
  y: number
  /** Stacking layer (depth). Cards with a larger z sit above. */
  z: number
  /** Card width in design-space pixels. */
  width: number
  /** Card height in design-space pixels. */
  height: number
  /** Current lifecycle status. */
  status: CardStatus
}

/** Position of a card inside its layer grid. */
export interface CardPos {
  col: number
  row: number
}

/** One stacking layer of a region. */
export interface LayerConfig {
  /** Depth of this layer (used as z). */
  layer: number
  /** Gap between cells as a ratio of the card size. */
  gapRatio: number
  /** Optional grid offset (in cells) to stagger layers. */
  offsetCol?: number
  /** Optional grid offset (in cells) to stagger layers. */
  offsetRow?: number
  /** Card positions in this layer. */
  cards: CardPos[]
}

/** A board region, positioned relative to the playable area (0~1). */
export interface RegionConfig {
  /** Left-top x of the region, relative to the playable area (0~1). */
  x: number
  /** Left-top y of the region, relative to the playable area (0~1). */
  y: number
  /** Stacking layers of this region. */
  layers: LayerConfig[]
}

/** Full level definition. */
export interface LevelConfig {
  /** Design-space board width in pixels (default 720). */
  width?: number
  /** Design-space board height in pixels (default 1280). */
  height?: number
  /** Number of distinct card types used by this level. */
  iconTypes: number
  /** Optional explicit card size; defaults to width * CARD_SIZE_SCALE. */
  cardSize?: number
  /** Optional display title (used by the UI layer). */
  title?: string
  /** Board regions. */
  regions: RegionConfig[]
}

/** Result status of pushing a card into the slot tray. */
export type PushStatus = 'MATCHED' | 'FULL_GAME_OVER' | 'ADDED'

/** Result of pushing a card into the tray. */
export interface EnginePushResult {
  /** ADDED: card in tray; MATCHED: a triple was removed; FULL_GAME_OVER: tray full. */
  status: PushStatus
  /** Ids of cards removed by the match (only when status === 'MATCHED'). */
  removes?: string[]
}
