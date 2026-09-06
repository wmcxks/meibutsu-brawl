import Phaser from 'phaser'
import Alpine from 'alpinejs'
import './style.css'
import BootScene from './scenes/BootScene'
import MenuScene from './scenes/MenuScene'
import GameScene from './scenes/GameScene'
import { EventBus } from './core/EventBus'
import { initUiScaler } from './core/uiScaler'
import { setBgmMuted } from './core/BgmManager'
import { setLocalEquippedTheme } from './core/themes'
import { initErrorReporting } from './core/clientErrors'
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
  fetchPublicConfigs,
  fetchProducts,
  createShopOrder,
  cancelShopOrder,
  fetchInviteCode,
  fetchFriends,
  bindFriend,
  removeFriend,
  getFriendRank,
  fetchCosmeticsMine,
  buyCosmetic,
  equipCosmetic,
} from './api/request'
import { SDKManager } from './sdk/SDKManager'
import type { MissionItem, PlayerSummary, RankItem, ShopProduct, FriendItem, CosmeticItem } from './types/api'

// 客户端版本（H3 强更判定；构建期 VITE_APP_VERSION 注入，默认 0.0.0）
const APP_VERSION: string = import.meta.env.VITE_APP_VERSION ?? '0.0.0'

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

  // F3：全局错误捕获（游戏创建前注册，覆盖 Phaser 运行时错误）
  initErrorReporting()

  // C5：启动前与服务端同步装备主题（本地缓存驱动 BootScene 卡面预加载）
  await syncEquippedTheme()

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

/** C5：把服务端装备主题同步进本地缓存（BootScene 预加载依据；失败静默） */
async function syncEquippedTheme(): Promise<void> {
  try {
    const items = await fetchCosmeticsMine()
    const equipped = items.find((it) => it.kind === 'theme' && it.equipped)
    if (equipped) setLocalEquippedTheme(equipped.item_key)
  } catch (err) {
    console.warn('[theme] 同步装备主题失败（沿用本地缓存）:', err)
  }
}

/** 语义化版本号比较：a>b 返回 1，a==b 返回 0，a<b 返回 -1 */
export function compareVersions(a: string, b: string): number {
  const pa = String(a).split('.').map((n) => parseInt(n, 10) || 0)
  const pb = String(b).split('.').map((n) => parseInt(n, 10) || 0)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] ?? 0
    const y = pb[i] ?? 0
    if (x !== y) return x > y ? 1 : -1
  }
  return 0
}

void bootstrap()

/** 排行榜维度（E3：加入「友だち」档） */
type RankScope = 'national' | 'my' | 'friends'

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
  /** 远端公告文案（空 = 无公告；运营经后台配置下发） */
  announcementText: '',
  _announcementShown: false,
  /** 当前所在关卡（LEVEL_STARTED 时更新，供排行榜默认维度使用） */
  currentLevel: 1,
  /** 我的资料 + 累计统计（/api/user/me，启动后拉取一次） */
  me: null as PlayerSummary | null,
  /** 都道府県选项（资料面板区域选择） */
  prefectures: JP_PREFECTURES,
  /** 排行榜显示维度：national 全国 / my 我的区域 / friends 友だち */
  rankScope: 'national' as RankScope,
  /** 我的名次（服务端返回，可能为 null） */
  myRank: null as number | null,
  /** 排行榜区域榜是否可用（尚未选择区域时为 false） */
  rankScopeReady: false,
  /** E3 好友邀请面板状态 */
  inviteOpen: false,
  inviteCode: '',
  inviteInput: '',
  inviteBusy: false,
  myFriends: [] as FriendItem[],
  /** E3 好友榜加载中 */
  friendRankLoading: false,
  /** C5 装扮商店（shopTab：gem 充值 / skin 装扮） */
  cosmetics: [] as CosmeticItem[],
  cosmeticBusy: false,
  /** H3 强更遮罩：需要更新时全屏拦截 */
  updateRequired: false,
  updateLatestUrl: '',
  updateMinVer: '',
  updateCurrentVer: APP_VERSION,
  /** E3 邀请链接（含 ?invite=CODE，分享用） */
  inviteLink: '',
  profileOpen: false,
  profileNickname: '',
  profileRegion: '',
  profileSaving: false,
  missionsOpen: false,
  missions: [] as MissionItem[],
  missionsLoading: false,
  missionsScope: 'daily' as 'daily' | 'weekly' | 'achievement',
  shopOpen: false,
  shopTab: 'gem' as 'gem' | 'skin',
  shopProducts: [] as ShopProduct[],
  shopBuying: false,

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
        if (this.announcementText && !this._announcementShown) {
          this._announcementShown = true
          this.showToast(`📣 ${this.announcementText}`, 4200)
        } else {
          this.showToast('チュートリアル：光るカードをタップして、同じ絵柄を3つそろえましょう', 2600)
        }
      } else {
        this.showToast(`第${level}ステージ · ${title || ''}`, 2000)
      }
    })

    // 拉取远端公告（G2：运营后台配置即下发，无需发版）
    void this.loadAnnouncement()

    // H3：版本门槛检查（配置 min_client_ver 且高于当前版本 → 强更遮罩）
    void this.checkVersionGate()

    // E3：分享链接带 ?invite=CODE → 启动后自动绑定好友（幂等）
    this.autoBindInvite()

    // 启动后拉取我的资料/统计（登录已在 bootstrap 完成）
    void this.refreshMe()
  },

  /** H3：读取公开配置的 app.min_client_ver / app.latest_url 并比对当前版本 */
  async checkVersionGate() {
    try {
      const cfg = await fetchPublicConfigs()
      const min = cfg['app.min_client_ver']
      const minVer = typeof min === 'string' ? min.trim() : ''
      if (minVer && compareVersions(APP_VERSION, minVer) < 0) {
        this.updateMinVer = minVer
        this.updateCurrentVer = APP_VERSION
        const url = cfg['app.latest_url']
        this.updateLatestUrl = typeof url === 'string' ? url : ''
        this.updateRequired = true
        track('version_gate', { current: APP_VERSION, min: minVer })
      }
    } catch (err) {
      console.warn('[version] 版本检查失败（跳过强更）:', err)
    }
  },

  /** E3：读取 ?invite=CODE 并自动建立互关（成功/失败仅 toast，清掉 URL 参数） */
  autoBindInvite() {
    try {
      const params = new URLSearchParams(location.search)
      const code = (params.get('invite') ?? '').trim().toUpperCase()
      const clean = location.pathname + location.search.replace(/[?&]invite=[^&]*/i, '')
      history.replaceState(null, '', clean || location.pathname)
      if (!code) return
      bindFriend(code)
        .then((res) => {
          const name = res.friend?.nickname ?? ''
          this.showToast(name ? `「${name}」と友達になりました！` : '友達になりました！', 3000)
          track('friend_bind', { ok: true })
        })
        .catch((err: unknown) => {
          console.warn('[friends] 邀请码绑定失败:', err)
          this.showToast('招待コードを利用できませんでした')
        })
    } catch {
      /* 非标准 URL 环境静默跳过 */
    }
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

  /** 打开排行榜（默认全国；可传 'my' 区域榜 / 'friends' 好友榜） */
  showLeaderboard(scope: RankScope = 'national') {
    this.leaderboardVisible = true
    this.setRankScope(scope)
  },

  /** 维度 Tab 切换（区域榜需已设置区域；好友榜随时可用） */
  setRankScope(scope: RankScope) {
    if (scope === 'my' && !this.rankScopeReady) return
    this.rankScope = scope
    if (scope === 'friends') {
      void this.loadFriendBoard()
    } else {
      this.loadLeaderboard(scope)
    }
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

  /** E3：好友榜加载（互关 + 自己，每关最快） */
  async loadFriendBoard() {
    this.friendRankLoading = true
    try {
      const res = await getFriendRank(this.currentLevel)
      this.leaderboard = res.rank as unknown as RankItem[]
      this.myRank = res.my_rank
      if (this.myFriends.length === 0) void this.loadMyFriends()
    } catch (err) {
      console.warn('[rank] 好友榜加载失败:', err)
      this.leaderboard = []
      this.myRank = null
    } finally {
      this.friendRankLoading = false
    }
  },

  /** E3：打开邀请/好友管理面板 */
  async openInvite() {
    this.inviteOpen = true
    try {
      if (!this.inviteCode) {
        this.inviteCode = await fetchInviteCode()
      }
      this.inviteLink = `${location.origin}${location.pathname}?invite=${this.inviteCode}`
    } catch (err) {
      console.warn('[friends] 获取邀请码失败:', err)
      this.inviteCode = ''
    }
    await this.loadMyFriends()
  },

  /** E3：刷新好友列表 */
  async loadMyFriends() {
    try {
      this.myFriends = await fetchFriends()
    } catch (err) {
      console.warn('[friends] 好友列表加载失败:', err)
      this.myFriends = []
    }
  },

  /** E3：复制邀请码/链接到剪贴板（失败时降级提示） */
  async copyText(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text)
      this.showToast(`${label}をコピーしました`)
    } catch {
      this.showToast(text)
    }
  },

  /** E3：平台分享邀请（LINE shareTargetPicker / Web Share API） */
  shareInvite() {
    const code = this.inviteCode
    const link = this.inviteLink
    if (!code) {
      this.showToast('招待コードを取得できません')
      return
    }
    const text = `名物大乱斗で一緒に遊ぼう！私の招待コードは ${code}\n${link}`
    SDKManager.adapter.share(
      SDKManager.adapter.platform === 'line'
        ? [{ type: 'text', text }]
        : { title: '名物大乱斗（邀请）', text, url: link },
    )
  },

  /** E3：输入对方的邀请码手动绑定 */
  async submitBindCode() {
    const code = this.inviteInput.trim().toUpperCase()
    if (!code) return
    if (this.inviteBusy) return
    this.inviteBusy = true
    try {
      await bindFriend(code)
      this.inviteInput = ''
      this.showToast('友達になりました！')
      await this.loadMyFriends()
      if (this.rankScope === 'friends') void this.loadFriendBoard()
    } catch (err) {
      console.warn('[friends] 绑定失败:', err)
      this.showToast('コードが無効です')
    } finally {
      this.inviteBusy = false
    }
  },

  /** E3：解除好友 */
  async removeMyFriend(friend: FriendItem) {
    try {
      await removeFriend(friend.user_id)
      this.myFriends = this.myFriends.filter((f) => f.user_id !== friend.user_id)
      this.showToast('友達を削除しました')
      if (this.rankScope === 'friends') void this.loadFriendBoard()
    } catch (err) {
      console.warn('[friends] 删除失败:', err)
      this.showToast('削除に失敗しました')
    }
  },

  closeLeaderboard() {
    this.leaderboardVisible = false
    this.inviteOpen = false
  },

  async loadAnnouncement() {
    try {
      const cfg = await fetchPublicConfigs()
      const text = cfg['announcement.text']
      this.announcementText = typeof text === 'string' ? text.trim() : ''
    } catch (err) {
      console.warn('[config] 获取公告失败:', err)
    }
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

  /** 打开任务面板（默认每日） */
  async openMissions() {
    this.missionsOpen = true
    this.missionsScope = 'daily'
    await this.reloadMissions()
  },

  /** 切换每日/每周/成就 Tab */
  async setMissionsScope(scope: 'daily' | 'weekly' | 'achievement') {
    this.missionsScope = scope
    await this.reloadMissions()
  },

  async reloadMissions() {
    this.missionsLoading = true
    try {
      this.missions = await fetchMissions(this.missionsScope)
    } catch (err) {
      console.warn('[missions] 获取任务失败:', err)
      this.missions = []
    } finally {
      this.missionsLoading = false
    }
  },

  /** 资源地址（H3：叠加构建期 base，CDN 部署时 HTML UI 图片同样生效） */
  assetUrl(path: string) {
    const base: string = import.meta.env.BASE_URL ?? '/'
    return base === '/' ? path : `${base.replace(/\/$/, '')}${path}`
  },

  /** 商店：打开（默认 gem 充值 Tab；商品只拉一次，装扮每次进面板刷新） */
  async openShop() {
    this.shopOpen = true
    if (this.shopProducts.length === 0) {
      try {
        this.shopProducts = await fetchProducts()
      } catch (err) {
        console.warn('[shop] 商品目录加载失败:', err)
        this.shopProducts = []
      }
    }
    if (this.shopTab === 'skin' || this.cosmetics.length === 0) {
      await this.reloadCosmetics()
    }
  },

  /** 商店 Tab 切换：gem 充值 / skin 装扮 */
  async setShopTab(tab: 'gem' | 'skin') {
    this.shopTab = tab
    if (tab === 'skin') await this.reloadCosmetics()
  },

  /** C5：拉取装扮商店列表（含拥有/装备态） */
  async reloadCosmetics() {
    try {
      this.cosmetics = await fetchCosmeticsMine()
    } catch (err) {
      console.warn('[shop] 装扮列表加载失败:', err)
      this.cosmetics = []
    }
  },

  /** C5：购买装扮（gem 扣款成功后本地写主题缓存并刷新页面生效） */
  async buySkin(item: CosmeticItem) {
    if (this.cosmeticBusy) return
    this.cosmeticBusy = true
    try {
      await buyCosmetic(item.item_key)
      setLocalEquippedTheme(item.item_key)
      await this.refreshMe()
      this.showToast('購入して装着しました')
      window.setTimeout(() => location.reload(), 600)
    } catch (err) {
      console.warn('[shop] 购买装扮失败:', err)
      this.showToast('購入できませんでした（ジェム不足？）')
      await this.refreshMe()
    } finally {
      this.cosmeticBusy = false
    }
  },

  /** C5：装备已拥有装扮（免费款/已购均可；写本地缓存后刷新页面生效） */
  async equipSkin(item: CosmeticItem) {
    if (this.cosmeticBusy) return
    this.cosmeticBusy = true
    try {
      await equipCosmetic(item.item_key)
      setLocalEquippedTheme(item.item_key)
      this.showToast('装着しました')
      window.setTimeout(() => location.reload(), 600)
    } catch (err) {
      console.warn('[shop] 装备失败:', err)
      this.showToast('装着に失敗しました')
    } finally {
      this.cosmeticBusy = false
    }
  },

  /** 下单（人工确认收款前仅占位；后端限制单笔 pending） */
  async buyProduct(p: ShopProduct) {
    if (this.shopBuying) return
    this.shopBuying = true
    try {
      await createShopOrder(p.sku)
      this.showToast('注文を受け付けました（運営確認後にお届け）')
    } catch (err) {
      console.warn('[shop] 下单失败:', err)
      this.showToast('注文できませんでした（未完了の注文があります）')
    } finally {
      this.shopBuying = false
    }
  },

  /** 取消待支付订单 */
  async cancelPendingOrder() {
    try {
      await cancelShopOrder()
      this.showToast('注文をキャンセルしました')
    } catch (err) {
      console.warn('[shop] 取消失败:', err)
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

  /** 货币/奖励文案（商店/任务共用） */
  currencyName(cur: string) {
    const map: Record<string, string> = { gem: 'ジェム', coin: 'コイン' }
    return map[cur] ?? cur
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
