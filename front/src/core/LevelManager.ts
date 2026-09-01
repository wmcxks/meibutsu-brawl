/**
 * LevelManager.ts
 * Pure data-model layer for level loading and card interaction rules.
 *
 * This class MUST stay framework-agnostic:
 * - NO Phaser, wx.*, Canvas or DOM code.
 * - It only stores card state and implements pure geometric/state logic,
 *   so it can run in any environment (unit tests, Node, H5, WeChat).
 */

import type { CardNode, LevelConfig } from '../types/game'

/**
 * Blocking threshold: a card is considered blocked when the overlap area
 * with a higher card exceeds this ratio of its own area.
 */
const BLOCKED_THRESHOLD = 0.1

/** Playable-area margins (relative to board size), mirroring the original design. */
const BOARD_TOP = 0.1
const BOARD_SIDE = 0.07
const BOARD_BOTTOM = 0.65
/** Default card size = board width * 0.12. */
const CARD_SIZE_SCALE = 0.12

/**
 * LevelManager
 * Parses a level config into 3D card nodes and answers interaction
 * questions (e.g. "can this card be clicked?").
 */
export class LevelManager {
  /** All card nodes of the current level (flat node list of the graph). */
  private cards: CardNode[] = []

  /** Monotonic id counter for generated card ids. */
  private nextId = 1

  /**
   * Parse a level config and (re)build the card node list.
   * Cards are placed on a 3D grid: x/y from grid cells, z from layer depth.
   * @param levelData Level configuration to load.
   * @returns The generated card nodes.
   */
  loadLevel(levelData: LevelConfig): CardNode[] {
    this.cards = []
    this.nextId = 1

    const width = levelData.width ?? 720
    const height = levelData.height ?? 1280
    const size = levelData.cardSize ?? Math.round(width * CARD_SIZE_SCALE)
    const areaTop = height * BOARD_TOP
    const areaBottom = height * BOARD_BOTTOM
    const areaLeft = width * BOARD_SIDE
    const areaRight = width * (1 - BOARD_SIDE)
    const areaW = areaRight - areaLeft
    const areaH = areaBottom - areaTop

    for (const region of levelData.regions) {
      const originX = areaLeft + areaW * region.x
      const originY = areaTop + areaH * region.y

      for (const layerCfg of region.layers) {
        const gap = Math.round(size * layerCfg.gapRatio)
        const cellW = size + gap
        const cellH = size + gap
        const offC = layerCfg.offsetCol ?? 0
        const offR = layerCfg.offsetRow ?? 0

        for (const pos of layerCfg.cards) {
          this.cards.push({
            id: `card-${this.nextId++}`,
            type: '', // placeholder; the caller (or a deck-builder) fills real types
            x: originX + (pos.col + offC) * cellW,
            y: originY + (pos.row + offR) * cellH,
            z: layerCfg.layer,
            width: size,
            height: size,
            status: 'ALIVE',
          })
        }
      }
    }

    return this.cards
  }

  /**
   * Assign card types from a deck. The deck length must be >= card count;
   * the deck is assumed to be pre-shuffled (every type appearing in triples).
   * @param deck Ordered list of types to assign in card order.
   */
  assignTypes(deck: string[]): void {
    this.cards.forEach((card, i) => {
      card.type = deck[i] ?? ''
    })
  }

  /**
   * All card nodes of the current level (flat node list).
   */
  getCards(): CardNode[] {
    return this.cards
  }

  /**
   * Cards that are still on the board (not removed yet).
   */
  getAliveCards(): CardNode[] {
    return this.cards.filter((c) => c.status === 'ALIVE')
  }

  /**
   * Look up a single card node by id.
   * @param cardId Target card id.
   */
  getCard(cardId: string): CardNode | undefined {
    return this.cards.find((c) => c.id === cardId)
  }

  /**
   * Mark a card as removed (e.g. after it is picked into the slot tray).
   * @param cardId Target card id.
   * @returns true if the card existed and was alive.
   */
  removeCard(cardId: string): boolean {
    const card = this.getCard(cardId)
    if (!card || card.status !== 'ALIVE') return false
    card.status = 'REMOVED'
    return true
  }

  /**
   * Mark a removed card as alive again (revive / move-out back to the board).
   * @param cardId Target card id.
   * @returns true if the card existed and was removed.
   */
  restoreCard(cardId: string): boolean {
    const card = this.getCard(cardId)
    if (!card || card.status !== 'REMOVED') return false
    card.status = 'ALIVE'
    return true
  }

  /**
   * CORE ALGORITHM: decide whether a card can be clicked.
   * A card is clickable when it is alive and NO higher card (larger z)
   * overlaps it by more than BLOCKED_THRESHOLD of its own area.
   * @param cardId Target card id.
   * @returns true when the card is free to be picked.
   */
  isCardClickable(cardId: string): boolean {
    const card = this.getCard(cardId)
    if (!card || card.status !== 'ALIVE') return false

    const threshold = card.width * card.height * BLOCKED_THRESHOLD
    for (const other of this.cards) {
      if (other.id === cardId) continue
      if (other.status !== 'ALIVE') continue
      // Only strictly higher layers can block.
      if (other.z <= card.z) continue

      const overlapX = Math.max(
        0,
        Math.min(card.x + card.width, other.x + other.width) - Math.max(card.x, other.x),
      )
      const overlapY = Math.max(
        0,
        Math.min(card.y + card.height, other.y + other.height) - Math.max(card.y, other.y),
      )
      if (overlapX * overlapY > threshold) {
        return false
      }
    }
    return true
  }

  /** Clear all cards (start of a new level). */
  reset(): void {
    this.cards = []
    this.nextId = 1
  }
}
