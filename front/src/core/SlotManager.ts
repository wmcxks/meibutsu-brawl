/**
 * SlotManager.ts
 * Pure data-model layer for the bottom slot tray (三消槽位) of the game.
 *
 * This class MUST stay framework-agnostic:
 * - NO Phaser, wx.*, Canvas or DOM code.
 * - It only manages the slot array and the match-removal algorithm.
 */

import type { CardNode, PushStatus } from '../types/game'

/** Operation result of pushing a card into the slot tray. */
export interface PushResult {
  /** What happened after pushing the card. */
  status: PushStatus
  /** Ids of cards removed by a match (only set when status === 'MATCHED'). */
  removedCards?: string[]
}

/**
 * SlotManager
 * Maintains the bottom slot tray (max 7 by default). Each push adds a card,
 * then automatically removes any triple of the same type, shifting the rest.
 */
export class SlotManager {
  /** Maximum number of cards the tray can hold. */
  private readonly maxSlots: number

  /** Current cards in the tray, in insertion order. */
  private slots: CardNode[] = []

  /**
   * @param maxSlots Maximum tray capacity (default 7).
   */
  constructor(maxSlots = 7) {
    this.maxSlots = maxSlots
  }

  /**
   * Simulate the player picking a card into the tray:
   *   1. guard against pushing into a full tray,
   *   2. append the card,
   *   3. run the match check and remove any triple,
   *   4. report the outcome.
   * @param card The card node being picked (its status is untouched here).
   * @returns The operation result: ADDED, MATCHED or FULL_GAME_OVER.
   */
  pushCard(card: CardNode): PushResult {
    if (this.slots.length >= this.maxSlots) {
      return { status: 'FULL_GAME_OVER' }
    }

    this.slots.push(card)

    const removed = this.checkMatch()
    if (removed.length > 0) {
      return { status: 'MATCHED', removedCards: removed }
    }

    if (this.slots.length >= this.maxSlots) {
      return { status: 'FULL_GAME_OVER' }
    }

    return { status: 'ADDED' }
  }

  /**
   * PRIVATE MATCH CHECK: scan the tray for any type appearing 3 or more
   * times; remove the first 3 occurrences of each matched type and shift
   * the remaining cards to fill the gap.
   * @returns Ids of the removed cards (empty when no match).
   */
  private checkMatch(): string[] {
    const counts = new Map<string, number>()
    for (const slot of this.slots) {
      counts.set(slot.type, (counts.get(slot.type) ?? 0) + 1)
    }

    const removedIds: string[] = []
    for (const [type, count] of counts) {
      if (count < 3) continue

      let removed = 0
      this.slots = this.slots.filter((slot) => {
        if (slot.type === type && removed < 3) {
          removed++
          removedIds.push(slot.id)
          return false
        }
        return true
      })
    }

    return removedIds
  }

  /**
   * Take up to `count` cards out of the front of the tray (move-out / revive).
   * The returned cards can be placed back onto the board.
   * @param count Max number of cards to pull out (default 1).
   * @returns The cards removed from the tray.
   */
  moveOut(count = 1): CardNode[] {
    const removed = this.slots.splice(0, Math.min(count, this.slots.length))
    return removed
  }

  /**
   * Remove one specific card from the tray, searched from the end
   * (undo prop: the most recently pushed card of a given id).
   * @param cardId Target card id.
   * @returns The removed card, or undefined when not found.
   */
  removeById(cardId: string): CardNode | undefined {
    for (let i = this.slots.length - 1; i >= 0; i--) {
      if (this.slots[i].id === cardId) {
        return this.slots.splice(i, 1)[0]
      }
    }
    return undefined
  }

  /** Snapshot of the tray contents, in insertion order. */
  getSlots(): CardNode[] {
    return [...this.slots]
  }

  /** Number of cards currently in the tray. */
  get size(): number {
    return this.slots.length
  }

  /** Empty the tray (start of a new level). */
  reset(): void {
    this.slots = []
  }
}
