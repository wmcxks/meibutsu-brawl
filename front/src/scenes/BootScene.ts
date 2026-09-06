import Phaser from 'phaser'
import { pickTheme, themeIconPath, markIconsLoadedThrough } from '../core/themes'
import { LEVELS } from '../core/levels'
import { getPrefetchedFirstIconTypes } from '../core/bootPrefetch'

/**
 * BootScene
 * First scene: preloads only the assets actually needed at startup —
 * the equipped/fallback card theme icons for LEVEL 1 (a few files instead
 * of the whole pack; later levels lazy-load their icons behind the level
 * transition overlay), the slot tray, prop icons and click/merge SFX.
 * Victory/defeat SFX load lazily on first use (GameScene.ensureAudioAndPlay).
 */
export default class BootScene extends Phaser.Scene {
  /** Graphics object used to draw the loading progress bar. */
  private gfx!: Phaser.GameObjects.Graphics

  constructor() {
    super('BootScene')
  }

  preload(): void {
    // H3：资源走 CDN/OSS。构建期 VITE_CDN_BASE 注入（如 https://cdn.example.com/meibutsu/），
    // 未配置时按站内相对路径加载（index.html 与资源同域）。
    this.load.setBaseURL(import.meta.env.VITE_CDN_BASE ?? '')

    // 只预载当前主题里第一关会用到的最少图标（其余随关卡懒加载）。
    const theme = pickTheme()
    const firstTypes = Math.max(1, getPrefetchedFirstIconTypes() ?? LEVELS[0]?.iconTypes ?? 3)
    const preloadCount = Math.min(firstTypes, theme.iconCount)

    this.loadImages(theme, preloadCount)
    this.loadAudio()

    // Draw the initial bar, then keep it updated while files load.
    this.gfx = this.add.graphics()
    this.drawProgressBar(0)
    this.load.on(Phaser.Loader.Events.PROGRESS, (value: number) => {
      this.drawProgressBar(value)
    })
  }

  create(): void {
    // All assets loaded — skip the home menu and enter the game directly.
    this.scene.start('GameScene')
  }

  /** All actually-used images (menu art is unused: the game boots straight
   *  into GameScene; dialogs and the leaderboard are HTML overlays). */
  private loadImages(theme: { name: string; iconCount: number }, firstCount: number): void {
    // In-game UI（背景由 DOM 层 #bg-container 渐变垫底，不再加载图片背景）
    this.load.image('images/game/cards/slots.webp', 'images/game/cards/slots.webp')

    // Props
    this.load.image('images/game/props/moveOut.webp', 'images/game/props/moveOut.webp')
    this.load.image('images/game/props/peek.webp', 'images/game/props/peek.webp')
    this.load.image('images/game/props/shuffle.webp', 'images/game/props/shuffle.webp')
    this.load.image('images/game/props/undo.webp', 'images/game/props/undo.webp')

    // 仅第一关需要的图标（本次运行的主题；后需图标在切关转场时懒加载）
    for (let i = 1; i <= firstCount; i++) {
      const key = themeIconPath(theme.name, i)
      this.load.image(key, key)
    }
    markIconsLoadedThrough(firstCount)
  }

  /** 首屏只加载点按/消除音；胜利/失败音由 GameScene 首用时懒加载。 */
  private loadAudio(): void {
    this.load.audio('audio/game/click/normal.mp3', 'audio/game/click/normal.mp3')
    this.load.audio('audio/game/click/cow.mp3', 'audio/game/click/cow.mp3')
    this.load.audio('audio/game/click/horse.mp3', 'audio/game/click/horse.mp3')
    this.load.audio('audio/game/merge.mp3', 'audio/game/merge.mp3')
  }

  /**
   * Redraw the centered progress bar at the given progress ratio (0~1).
   * @param value Loading progress ratio.
   */
  private drawProgressBar(value: number): void {
    const width = this.scale.width
    const height = this.scale.height

    const barWidth = width * 0.6
    const barHeight = 24
    const barX = (width - barWidth) / 2
    const barY = height / 2

    this.gfx.clear()

    // Bar background (dark, with a subtle border).
    this.gfx.fillStyle(0x000000, 0.5)
    this.gfx.fillRoundedRect(barX - 2, barY - 2, barWidth + 4, barHeight + 4, 6)

    // Filled portion, growing with the load progress.
    this.gfx.fillStyle(0x00c853, 1)
    this.gfx.fillRoundedRect(barX, barY, barWidth * Math.min(1, Math.max(0, value)), barHeight, 4)
  }
}
