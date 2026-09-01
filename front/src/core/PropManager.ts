/**
 * PropManager.ts
 * Pure data-model for the bottom prop bar (道具栏) counts.
 *
 * Framework-agnostic: NO Phaser, wx.*, Canvas or DOM code.
 * The actual effects are applied by the view layer; this class only
 * tracks remaining uses per prop and enforces consumption rules.
 */

/** Prop slots, in the original bar order. */
export const PROP_NAMES = ['moveOut', 'undo', 'shuffle', 'peek'] as const

/** Default use limits per prop: 移出 / 撤回 / 洗牌 / 透视. */
export const DEFAULT_LIMITS = [3, 3, 3, 3] as const

/** PropManager */
export class PropManager {
  /** Remaining uses per prop index (0..3). */
  private counts: number[]

  /**
   * @param limits Optional custom limits; defaults to [3, 3, 3, 3].
   */
  constructor(limits: readonly number[] = DEFAULT_LIMITS) {
    this.counts = [...limits]
  }

  /** Snapshot of remaining uses per prop. */
  getCounts(): number[] {
    return [...this.counts]
  }

  /** Remaining uses of a single prop. */
  getCount(index: number): number {
    return this.counts[index] ?? 0
  }

  /**
   * Consume one use of a prop.
   * @param index Prop index (0..3).
   * @returns true when a use was available and consumed.
   */
  use(index: number): boolean {
    if (index < 0 || index >= this.counts.length || this.counts[index] <= 0) {
      return false
    }
    this.counts[index]--
    return true
  }

  /** Add uses to a prop (e.g. revive grants one move-out). */
  addCount(index: number, amount = 1): void {
    if (index < 0 || index >= this.counts.length) return
    this.counts[index] += amount
  }

  /** Reset all counts (new level), optionally with custom limits. */
  reset(limits?: readonly number[]): void {
    this.counts = limits ? [...limits] : [...DEFAULT_LIMITS]
  }
}
