/**
 * GameEngine.ts
 * Pure model-layer facade (the "algorithm brain").
 *
 * Composes LevelManager (board parsing + blocking rules) and SlotManager
 * (tray + match removal) into one entry point for the view layer.
 *
 * CRITICAL RULES:
 * - 100% framework-agnostic: NO Phaser, wx.*, Canvas or DOM code here.
 * - All interaction is data-in / data-out via plain types.
 */

import { LevelManager } from './LevelManager'
import { SlotManager } from './SlotManager'
import type { CardNode, EnginePushResult, LevelConfig } from '../types/game'

/**
 * GameEngine
 * Facade over the pure board/tray models, exposing the API the scenes need:
 * loadLevel -> pushCard(cardId) -> { status, removes }.
 */
export class GameEngine {
  /** Board model: level layout + clickability rules. */
  readonly levels: LevelManager
  /** Tray model: insertion order + three-in-a-row removal. */
  readonly slots: SlotManager

  /** Card ids in push order (undo history); cleared whenever a match happens. */
  private readonly pushHistory: string[] = []

  /**
   * @param maxSlots Tray capacity (default 7).
   */
  constructor(maxSlots = 7) {
    this.levels = new LevelManager()
    this.slots = new SlotManager(maxSlots)
  }

  /**
   * Parse a level config and rebuild the 3D card node graph.
   * @param levelData Level configuration.
   * @returns The generated card nodes (x, y, z, status, ...).
   */
  loadLevel(levelData: LevelConfig): CardNode[] {
    return this.levels.loadLevel(levelData)
  }

  /**
   * Assign card types from a pre-shuffled deck (every type in triples).
   * @param deck Ordered type list matching the generated card order.
   */
  deal(deck: string[]): void {
    this.levels.assignTypes(deck)
  }

  /**
   * CORE ALGORITHM: is the card free of blocking cards above it?
   * @param cardId Target card id.
   * @returns true when the card is alive and exposed at the top.
   */
  isCardClickable(cardId: string): boolean {
    return this.levels.isCardClickable(cardId)
  }

  /**
   * Player picks a card into the tray:
   *   1. mark the card removed from the board,
   *   2. push it into the tray,
   *   3. auto-remove any triple and report the outcome.
   * @param cardId Id of the picked card.
   * @returns { status, removes } — removes holds the matched card ids.
   */
  pushCard(cardId: string): EnginePushResult {
    const card = this.levels.getCard(cardId)
    if (!card || card.status !== 'ALIVE') {
      return { status: 'ADDED' }
    }
    this.levels.removeCard(cardId)
    const result = this.slots.pushCard(card)
    if (result.status === 'MATCHED') {
      // A matched triple can no longer be undone.
      this.pushHistory.length = 0
    } else if (result.status === 'ADDED') {
      this.pushHistory.push(cardId)
    }
    return { status: result.status, removes: result.removedCards }
  }

  /**
   * Undo prop: pull the most recently pushed card back onto the board.
   * @returns The restored card node, or null when there is nothing to undo.
   */
  undo(): CardNode | null {
    const cardId = this.pushHistory.pop()
    if (!cardId) return null
    const card = this.slots.removeById(cardId)
    if (!card) {
      // History out of sync with the tray: discard the rest defensively.
      this.pushHistory.length = 0
      return null
    }
    this.levels.restoreCard(card.id)
    return card
  }

  /**
   * Shuffle prop: randomly re-assign types among the alive board cards
   * (positions and layers stay untouched; type totals are preserved).
   * @param maxY Optional threshold: only cards with y < maxY are shuffled,
   *   so the move-out zone below the board keeps its cards.
   * @returns true when at least one card was shuffled.
   */
  shuffle(maxY?: number): boolean {
    const candidates = this.levels.getCards().filter(
      (c) => c.status === 'ALIVE' && (maxY === undefined || c.y < maxY),
    )
    if (candidates.length === 0) return false

    const types = candidates.map((c) => c.type)
    for (let i = types.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[types[i], types[j]] = [types[j], types[i]]
    }
    candidates.forEach((card, i) => {
      card.type = types[i]
    })
    return true
  }

  /**
   * Take up to `count` cards out of the tray and put them back on the board
   * (revive / move-out prop). Returns the restored card nodes.
   * @param count Max cards to pull out (default 1).
   */
  moveOut(count = 1): CardNode[] {
    const moved = this.slots.moveOut(count)
    for (const card of moved) {
      this.levels.restoreCard(card.id)
    }
    return moved
  }

  /** Cards still alive on the board. */
  getAliveCards(): CardNode[] {
    return this.levels.getAliveCards()
  }

  /** Clear board and tray (fresh level). */
  reset(): void {
    this.levels.reset()
    this.slots.reset()
    this.pushHistory.length = 0
  }
}
