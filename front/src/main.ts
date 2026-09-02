import Phaser from 'phaser'
import Alpine from 'alpinejs'
import './style.css'
import BootScene from './scenes/BootScene'
import MenuScene from './scenes/MenuScene'
import GameScene from './scenes/GameScene'
import { EventBus } from './core/EventBus'
import { initUiScaler } from './core/uiScaler'
import { setBgmMuted } from './core/BgmManager'
import { GAME_WIDTH, computeDesignHeight } from './core/viewport'
import { saveScore, getLeaderboard } from './api/request'
import { SDKManager } from './sdk/SDKManager'
import type { RankItem } from './types/api'

// 设计稿高度随设备宽高比动态取（1280~1600，见 core/viewport.ts），
// 全面屏手机画面铺满全屏，不再在道具栏下方留下大片空白。
const appHostEl = document.getElementById('app')
const hostW = appHostEl?.clientWidth || window.innerWidth
const hostH = appHostEl?.clientHeight || window.innerHeight
const DESIGN_HEIGHT = computeDesignHeight(hostW, hostH)

const config: Phaser.Types.Core.GameConfig = {
  type: Phaser.WEBGL,
  parent: 'app',
  width: GAME_WIDTH,
  height: DESIGN_HEIGHT,
  /* 画布完全透明：让底层的 CSS 旋转渐变背景(#bg-container)完美透视出来 */
  transparent: true,
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  scene: [BootScene, MenuScene, GameScene],
}

/**
 * Global Phaser game reference, exposed to the UI layer so it can drive the
 * engine directly: game.scene.pause('GameScene') / game.sound.mute = ...
 */
let gameInstance: Phaser.Game | null = null

/**
 * Bootstrap: platform init + login happen BEFORE the game boots.
 * Platform differences (web guest login / LINE LIFF) are fully hidden
 * behind the SDKManager adapter — the game layer never sees them.
 */
async function bootstrap(): Promise<void> {
  try {
    await SDKManager.adapter.init()
    await SDKManager.adapter.login()
  } catch (err) {
    // 登录失败不阻断游戏：游客匿名模式运行，成绩上报由 saveScore 空会话兜底
    console.warn('[sdk] 平台初始化/登录失败，以匿名模式启动:', err)
  }

  gameInstance = new Phaser.Game(config)

  // 首屏幕布：等 Phaser 启动、BootScene 资源加载完成（其 create 即将
  // 渲染 GameScene）后再移除，露出渲染完整的画布与 UI 层，杜绝闪烁。
  gameInstance.events.once(Phaser.Core.Events.READY, () => {
    const bootScene = gameInstance?.scene.getScene('BootScene')
    bootScene?.events.once(Phaser.Scenes.Events.CREATE, () => {
      document.getElementById('global-loading-mask')?.remove()
    })
  })

  window.Alpine = Alpine
  Alpine.start()

  // UI 层缩放对齐 Phaser FIT 画布（720×designH 设计稿 <-> #app 视口）
  const uiContainer = document.getElementById('ui-container')
  const appHost = document.getElementById('app')
  if (uiContainer && appHost) initUiScaler(uiContainer, appHost, DESIGN_HEIGHT)
}

void bootstrap()

Alpine.data('gameUI', () => ({
  /** Sound on/off; initial value persisted in localStorage('hd_sound_on'). */
  isSoundOn: localStorage.getItem('hd_sound_on') !== '0',
  /** Network-error dialog visibility (startGameSession fast-fail). */
  isNetworkError: false,
  isGameOver: false,
  isReviveVisible: false,
  /** 关卡转场播放中：隐藏 HTML UI（道具栏/按钮/toast），保证遮罩全屏。 */
  isTransitioning: false,
  /** Last run duration in seconds (the "score" reported to the backend). */
  score: 0,
  /** Rows rendered by the leaderboard panel. */
  leaderboard: [] as RankItem[],
  leaderboardVisible: false,
  /** Prop bar: icon keys + remaining use counts (mirrors original order). */
  propIcons: ['moveOut', 'undo', 'shuffle', 'peek'],
  propCounts: [3, 3, 3, 3],
  /** Transient toast message. */
  toastText: '',
  toastVisible: false,
  _toastTimer: 0,
  /** 最近一局的结算上下文（复活弹窗「放弃」时用它按 fail 上报时长） */
  _lastRun: { score: 0, level: 1, sessionId: '' },

  init() {
    EventBus.on('GAME_OVER', (elapsed: number, level: number, sessionId: string) => {
      this.score = elapsed
      this.isGameOver = true
      if (elapsed != null && level != null && sessionId) {
        this.reportScore(level, sessionId, 'fail')
      }
    })
    EventBus.on('GAME_WIN', (elapsed: number, level: number, sessionId: string) => {
      // 胜利不再弹窗：成绩静默上报，关卡切换由 GameScene 的转场动画完成
      this.score = elapsed
      this.reportScore(level, sessionId, 'win')
    })
    EventBus.on('REVIVE_OFFERED', (score: number, level: number, sessionId: string) => {
      this._lastRun = { score: score ?? 0, level: level ?? 1, sessionId: sessionId ?? '' }
      this.isReviveVisible = true
    })
    EventBus.on('NETWORK_ERROR', () => {
      this.isNetworkError = true
    })
    EventBus.on('TRANSITION_START', () => {
      this.isTransitioning = true
    })
    EventBus.on('TRANSITION_END', () => {
      this.isTransitioning = false
    })
    EventBus.on('PROPS_CHANGED', (counts: number[]) => {
      this.propCounts = counts
    })
    EventBus.on('TOAST', (text: string) => {
      this.showToast(text)
    })
    EventBus.on('LEVEL_STARTED', (level: number, title: string) => {
      if (level === 1) {
        this.showToast('チュートリアル：光るカードをタップして、同じ絵柄を3つそろえましょう', 2600)
      } else {
        this.showToast(`第${level}ステージ · ${title || ''}`, 2000)
      }
    })
  },

  /** 道具按钮：通知场景执行对应效果。 */
  useProp(index: number) {
    EventBus.emit('USE_PROP', index)
  },

  /**
   * 一键静音：直接驱动 Phaser 全局声音管理器 + DOM 背景乐 + localStorage 持久化。
   * @param isMuted 期望的静音状态（点击时传当前 isSoundOn：开→关 传 true）
   */
  toggleSound(isMuted: boolean) {
    this.isSoundOn = !isMuted
    localStorage.setItem('hd_sound_on', this.isSoundOn ? '1' : '0')
    if (gameInstance) gameInstance.sound.mute = isMuted
    setBgmMuted(isMuted)
  },

  /** 网络异常弹窗「重新连接」：关闭弹窗并通知场景重新拉取开局会话。 */
  retryConnection() {
    this.isNetworkError = false
    EventBus.emit('RETRY_SESSION')
  },

  /** Show a transient centered message (auto-hides). */
  showToast(text: string, duration = 1500) {
    this.toastText = text
    this.toastVisible = true
    clearTimeout(this._toastTimer)
    this._toastTimer = window.setTimeout(() => {
      this.toastVisible = false
    }, duration)
  },

  /** 复活按钮：通知场景把槽位 1 张牌放回棋盘并继续游戏。 */
  handleRevive() {
    this.isReviveVisible = false
    EventBus.emit('REVIVE_GAME')
  },

  /** 放弃复活：真正进入失败流程，按 fail 结算本局时长。 */
  cancelRevive() {
    this.isReviveVisible = false
    EventBus.emit('GAME_OVER', this._lastRun.score, this._lastRun.level, this._lastRun.sessionId)
  },

  /** Async-submit the current run; failures are non-blocking. */
  reportScore(level: number, sessionId: string, outcome: 'win' | 'fail' | 'quit' = 'win') {
    saveScore(this.score, level, sessionId, outcome)
      .then(() => {
        console.log('[report] 成绩已上报:', this.score, '关卡:', level, '结局:', outcome)
      })
      .catch((err: unknown) => {
        console.warn('[report] 成绩上报失败:', err)
      })
  },

  /** Fetch the leaderboard and show the panel. */
  showLeaderboard() {
    this.leaderboardVisible = true
    this.leaderboard = []
    getLeaderboard()
      .then((data) => {
        this.leaderboard = data
      })
      .catch((err: unknown) => {
        console.warn('[rank] 获取排行榜失败:', err)
      })
  },

  closeLeaderboard() {
    this.leaderboardVisible = false
  },

  /** Format a best_time value for display. */
  formatTime(seconds: number) {
    return `${seconds.toFixed(1)}s`
  },

  restartGame() {
    this.isGameOver = false
    this.isReviveVisible = false
    this.leaderboardVisible = false
    EventBus.emit('RESTART_GAME')
  },
}))

Alpine.start()
