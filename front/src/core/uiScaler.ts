/**
 * uiScaler.ts
 * 让 HTML UI 层与 Phaser Scale.FIT 画布严丝合缝对齐。
 *
 * 原理：UI 设计稿为固定 720x1280（与游戏画布一致），按照 Phaser FIT 的
 * 同一算法计算缩放比例 scale = min(容器宽 / 720, 容器高 / 1280)，
 * 通过 transform: translate(-50%, -50%) scale(scale) 应用并居中。
 * 监听窗口尺寸变化 / 方向变化 / 页面重新可见，实时刷新。
 */

const GAME_WIDTH = 720
const GAME_HEIGHT = 1280

/**
 * 初始化 UI 缩放：以 Phaser 挂载容器（#app）为基准，scale 逻辑与 Scale.FIT 相同。
 * @param container 720x1280 的 UI 容器（#ui-container）
 * @param parent Phaser 挂载容器（#app），其尺寸即 FIT 的适配基准
 */
export function initUiScaler(container: HTMLElement, parent: HTMLElement): void {
  const apply = (): void => {
    const parentW = parent.clientWidth || window.innerWidth
    const parentH = parent.clientHeight || window.innerHeight
    const scale = Math.min(parentW / GAME_WIDTH, parentH / GAME_HEIGHT)
    container.style.transform = `translate(-50%, -50%) scale(${scale})`
  }

  apply()

  // 移动端地址栏收展 / 桌面窗口缩放 / 屏幕方向变化都会改变视口尺寸
  window.addEventListener('resize', apply)
  window.addEventListener('orientationchange', apply)

  // 从后台切回时视口尺寸可能已变化（如浏览器 UI 恢复），做一次兜底刷新
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) apply()
  })
}
