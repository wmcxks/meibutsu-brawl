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
import {
  saveScore,
  getLeaderboard,
  track,
  fetchMe,
  updateMe,
  deleteAccount,
  fetchMissions,
  claimMission,
} from './api/request'
import { SDKManager } from './sdk/SDKManager'
import type { MissionItem, PlayerSummary, RankItem } from './types/api'

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

  // 埋点：页面加载完成（此时已完成 SDK 登录，可归因到用户）
  track('page_load', { platform: SDKManager.adapter.platform })
}

void bootstrap()

/** 日本都道府県（JIS X 0401）— 区域排行与资料选择共用 */
const JP_PREFECTURES: Array<{ code: string; name: string }> = [
  ['jp-01','北海道'],['jp-02','青森県'],['jp-03','岩手県'],['jp-04','宮城県'],['jp-05','秋田県'],
  ['jp-06','山形県'],['jp-07','福島県'],['jp-08','茨城県'],['jp-09','栃木県'],['jp-10','群馬県'],
  ['jp-11','埼玉県'],['jp-12','千葉県'],['jp-13','東京都'],['jp-14','神奈川県'],['jp-15','新潟県'],
  ['jp-16','富山県'],['jp-17','石川県'],['jp-18','福井県'],['jp-19','山梨県'],['jp-20','長野県'],
  ['jp-21','岐阜県'],['jp-22','静岡県'],['jp-23','愛知県'],['jp-24','三重県'],['jp-25','滋賀県'],
  ['jp-26','京都府'],['jp-27','大阪府'],['jp-28','兵庫県'],['jp-29','奈良県'],['jp-30','和歌山県'],
  ['jp-31','鳥取県'],['jp-32','島根県'],['jp-33','岡山県'],['jp-34','広島県'],['jp-35','山口県'],
  ['jp-36','徳島県'],['jp-37','香川県'],['jp-38','愛媛県'],['jp-39','高知県'],['jp-40','福岡県'],
  ['jp-41','佐賀県'],['jp-42','長崎県'],['jp-43','熊本県'],['jp-44','大分県'],['jp-45','宮崎県'],
  ['jp-46','鹿児島県'],['jp-47','沖縄県'],
].map(([code, name]) => ({ code, name }))

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
  /** 当前所在关卡（LEVEL_STARTED 时更新，供排行榜默认维度使用） */
  currentLevel: 1,
  /** 我的资料 + 累计统计（/api/user/me，启动后拉取一次） */
  me: null as PlayerSummary | null,
  /** 都道府県选项（资料面板区域选择） */
  prefectures: JP_PREFECTURES,
  /** 排行榜显示维度：national 全国 / my 我的区域 */
  rankScope: 'national' as 'national' | 'my',
  /** 我的名次（服务端返回，可能为 null） */
  myRank: null as number | null,
  /** 排行榜区域榜是否可用（尚未选择区域时为 false） */
  rankScopeReady: false,
  profileOpen: false,
  profileNickname: '',
  profileRegion: '',
  profileSaving: false,
  missionsOpen: false,
  missions: [] as MissionItem[],
  missionsLoading: false,

  init() {
    EventBus.on('GAME_OVER', (elapsed: number, level: number, sessionId: string) => {
      this.score = elapsed
      this.isGameOver = true
      if (elapsed != null && level != null && sessionId) {
        track('level_fail', { level, duration: elapsed })
        this.reportScore(level, sessionId, 'fail')
      }
    })
    EventBus.on('GAME_WIN', (elapsed: number, level: number, sessionId: string) => {
      // 胜利不再弹窗：成绩静默上报，关卡切换由 GameScene 的转场动画完成
      this.score = elapsed
      track('level_win', { level, duration: elapsed })
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
      this.currentLevel = level
      if (level === 1) {
        this.showToast('チュートリアル：光るカードをタップして、同じ絵柄を3つそろえましょう', 2600)
      } else {
        this.showToast(`第${level}ステージ · ${title || ''}`, 2000)
      }
    })

    // 启动后拉取我的资料/统计（登录已在 bootstrap 完成）
    void this.refreshMe()
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

  /** 打开排行榜（默认全国；可传 'my' 切换我的区域榜） */
  showLeaderboard(scope: 'national' | 'my' = 'national') {
    this.leaderboardVisible = true
    this.loadLeaderboard(scope)
  },

  /** 区域 Tab 切换 */
  setRankScope(scope: 'national' | 'my') {
    if (scope === 'my' && !this.rankScopeReady) return
    this.rankScope = scope
    this.loadLeaderboard(scope)
  },

  loadLeaderboard(scope: 'national' | 'my') {
    const region =
      scope === 'my' ? (this.me?.user.region_code ?? '') : ''
    if (scope === 'my' && !region) return
    getLeaderboard(this.currentLevel, region)
      .then((res) => {
        this.leaderboard = res.rank
        this.myRank = res.my_rank
      })
      .catch((err: unknown) => {
        console.warn('[rank] 获取排行榜失败:', err)
      })
  },

  closeLeaderboard() {
    this.leaderboardVisible = false
  },

  /** 拉取我的资料（profileOpen 时补全；统计用于弹窗展示） */
  async refreshMe() {
    try {
      this.me = await fetchMe()
      this.rankScopeReady = Boolean(this.me?.user.region_code)
    } catch (err) {
      console.warn('[me] 获取玩家信息失败:', err)
    }
  },

  openProfile() {
    this.profileOpen = true
    this.profileNickname = this.me?.user.nickname ?? ''
    this.profileRegion = this.me?.user.region_code ?? ''
  },

  async saveProfile() {
    const nickname = this.profileNickname.trim()
    if (!nickname) return
    this.profileSaving = true
    try {
      const user = await updateMe({ nickname, region_code: this.profileRegion })
      if (this.me) this.me.user = { ...this.me.user, ...user }
      this.rankScopeReady = Boolean(user.region_code)
      this.showToast('保存しました')
    } catch (err) {
      console.warn('[me] 保存资料失败:', err)
      this.showToast('保存に失敗しました')
    } finally {
      this.profileSaving = false
    }
  },

  async requestDeleteAccount() {
    const ok = window.confirm('本当にアカウントを削除しますか？\nすべてのデータが削除され、取り消せません。')
    if (!ok) return
    try {
      await deleteAccount()
      location.reload()
    } catch (err) {
      console.warn('[me] 注销失败:', err)
      this.showToast('削除に失敗しました')
    }
  },

  /** 打开每日任务面板 */
  async openMissions() {
    this.missionsOpen = true
    await this.reloadMissions()
  },

  async reloadMissions() {
    this.missionsLoading = true
    try {
      this.missions = await fetchMissions('daily')
    } catch (err) {
      console.warn('[missions] 获取任务失败:', err)
      this.missions = []
    } finally {
      this.missionsLoading = false
    }
  },

  /** 领取任务奖励并刷新列表 */
  async claimMissionItem(m: MissionItem) {
    try {
      await claimMission(m.mission_key, m.period)
      this.showToast(`「${m.reward_prop_key}」+${m.reward_amount} を受け取りました`)
      await this.reloadMissions()
      void this.refreshMe()
    } catch (err) {
      console.warn('[missions] 领取失败:', err)
      this.showToast('受け取りに失敗しました')
    }
  },

  /** 区域名显示（区域榜 Tab） */
  regionName(code: string) {
    return JP_PREFECTURES.find((p) => p.code === code)?.name ?? code
  },

  /** 道具奖励文案（任务面板） */
  rewardName(key: string) {
    const map: Record<string, string> = {
      move_out: '移出',
      undo: '撤回',
      shuffle: 'シャッフル',
      peek: '透視',
    }
    return map[key] ?? key
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
