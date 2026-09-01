import Phaser from 'phaser'
import { EventBus, GameEvents } from '../core/EventBus'

/**
 * MenuScene
 * Home page of the game: menu background + floating title + decor animals.
 * Buttons (start / rank) live in the HTML overlay (Alpine.js + TailwindCSS);
 * clicking start emits START_GAME and this scene hands over to the GameScene.
 */
export default class MenuScene extends Phaser.Scene {
  constructor() {
    super('MenuScene')
  }

  create(): void {
    EventBus.on(GameEvents.START_GAME, this.handleStartGame)
    this.events.on(Phaser.Scenes.Events.SHUTDOWN, this.handleShutdown, this)

    // Background (419x711 portrait art, stretched to the design space).
    this.add
      .image(0, 0, 'images/menu/bgs/menu_bg01.png')
      .setOrigin(0, 0)
      .setDisplaySize(this.scale.width, this.scale.height)
      .setDepth(-1000)

    // Title, gently floating (original menu animation).
    const titleW = this.scale.width * 0.62
    const title = this.add
      .image(this.scale.width / 2, this.scale.height * 0.3, 'images/menu/titles/title.png')
      .setDisplaySize(titleW, (titleW * 1075) / 1971)
    this.tweens.add({
      targets: title,
      y: title.y + 16,
      duration: 1800,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    })

    // Decor animals at the bottom corners.
    this.add
      .image(this.scale.width * 0.14, this.scale.height * 0.87, 'images/menu/elements/animal_left.png')
      .setDisplaySize(150, 150)
    this.add
      .image(this.scale.width * 0.86, this.scale.height * 0.87, 'images/menu/elements/animal_right.png')
      .setDisplaySize(150, 150)
  }

  /** Start button clicked in the HTML overlay: go to the game. */
  private readonly handleStartGame = (): void => {
    this.scene.start('GameScene')
  }

  private handleShutdown(): void {
    EventBus.off(GameEvents.START_GAME, this.handleStartGame)
  }
}
