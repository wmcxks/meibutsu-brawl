import Phaser from 'phaser'
import { pickTheme } from '../core/themes'

/**
 * BootScene
 * First scene of the game: preloads the assets actually used this run
 * (one randomly picked card theme, game/menu art and SFX), shows a progress
 * bar, then starts the GameScene directly (no home menu in the start flow).
 */
export default class BootScene extends Phaser.Scene {
  /** Graphics object used to draw the loading progress bar. */
  private gfx!: Phaser.GameObjects.Graphics

  constructor() {
    super('BootScene')
  }

  preload(): void {
    // Reserved: configure a global CDN/OSS base URL here when needed.
    this.load.setBaseURL('')

    // Only the theme picked for this run is loaded (~7MB instead of 40MB).
    const theme = pickTheme()

    this.loadImages(theme)
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

  /** All actually-used images (unused originals like loading/rank/win art are
   *  skipped: dialogs and the leaderboard are HTML overlays, not Canvas art). */
  private loadImages(theme: { name: string; iconCount: number }): void {
    // Menu screen
    this.load.image('images/menu/bgs/menu_bg01.png', 'images/menu/bgs/menu_bg01.png')
    this.load.image('images/menu/buttons/button_rank.png', 'images/menu/buttons/button_rank.png')
    this.load.image('images/menu/buttons/button_start.png', 'images/menu/buttons/button_start.png')
    this.load.image('images/menu/elements/animal_left.png', 'images/menu/elements/animal_left.png')
    this.load.image('images/menu/elements/animal_right.png', 'images/menu/elements/animal_right.png')
    this.load.image('images/menu/titles/title.png', 'images/menu/titles/title.png')

    // In-game UI（背景由 DOM 层 #bg-container 渐变垫底，不再加载图片背景）
    this.load.image('images/game/cards/slots.png', 'images/game/cards/slots.png')

    // Props
    this.load.image('images/game/props/moveOut.png', 'images/game/props/moveOut.png')
    this.load.image('images/game/props/peek.png', 'images/game/props/peek.png')
    this.load.image('images/game/props/shuffle.png', 'images/game/props/shuffle.png')
    this.load.image('images/game/props/undo.png', 'images/game/props/undo.png')

    // Card theme icons of this run: images/game/cards/themes/<name>/<1..iconCount>.png
    for (let i = 1; i <= theme.iconCount; i++) {
      const key = `images/game/cards/themes/${theme.name}/${i}.png`
      this.load.image(key, key)
    }
  }

  /** All used SFX (BGM files are intentionally not loaded: they are unused
   *  in this port and would add ~13MB to the initial load). */
  private loadAudio(): void {
    this.load.audio('audio/game/click/normal.mp3', 'audio/game/click/normal.mp3')
    this.load.audio('audio/game/click/cow.mp3', 'audio/game/click/cow.mp3')
    this.load.audio('audio/game/click/horse.mp3', 'audio/game/click/horse.mp3')
    this.load.audio('audio/game/merge.mp3', 'audio/game/merge.mp3')
    this.load.audio('audio/game/success.mp3', 'audio/game/success.mp3')
    this.load.audio('audio/game/defeat.mp3', 'audio/game/defeat.mp3')
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
