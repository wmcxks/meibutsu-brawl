import Phaser from 'phaser'

/**
 * EventBus
 * Global event bus decoupling the Phaser scene layer from the Alpine UI layer.
 * Backed by Phaser's built-in event emitter for zero extra dependencies.
 */
export const EventBus = new Phaser.Events.EventEmitter()

/** All game events shared between scenes and the UI overlay. */
export const GameEvents = {
  /** Slot tray is full and the board is not cleared -> player lost. */
  GAME_OVER: 'GAME_OVER',
  /** Every card on the board has been removed -> player won. */
  GAME_WIN: 'GAME_WIN',
  /** UI asks the game scene to restart the current level. */
  RESTART_GAME: 'RESTART_GAME',
  /** First failure: the revive (复活) dialog should be offered. */
  REVIVE_OFFERED: 'REVIVE_OFFERED',
  /** Player confirmed the revive: pull a card out of the tray and resume. */
  REVIVE_GAME: 'REVIVE_GAME',
  /** UI clicked a prop button; payload: prop index (0=moveOut,1=undo,2=shuffle,3=peek). */
  USE_PROP: 'USE_PROP',
  /** Prop remaining counts changed; payload: number[4]. */
  PROPS_CHANGED: 'PROPS_CHANGED',
  /** Show a transient message (payload: string). */
  TOAST: 'TOAST',
  /** A level started; payload: (levelNumber: number, title: string). */
  LEVEL_STARTED: 'LEVEL_STARTED',
  /** Menu asked the game to begin (start button clicked). */
  START_GAME: 'START_GAME',
  /** In-game back button confirmed: return to the home menu. */
  BACK_TO_MENU: 'BACK_TO_MENU',
  /** Level loading failed (startGameSession fast-fail); UI shows a retry dialog. */
  NETWORK_ERROR: 'NETWORK_ERROR',
  /** Player clicked "重新连接" in the network-error dialog: retry session fetch. */
  RETRY_SESSION: 'RETRY_SESSION',
  /** BlockTransition 开始播放：HTML UI 层隐藏，保证转场遮罩全屏无遮挡。 */
  TRANSITION_START: 'TRANSITION_START',
  /** BlockTransition 播放完成：HTML UI 层恢复显示。 */
  TRANSITION_END: 'TRANSITION_END',
} as const
