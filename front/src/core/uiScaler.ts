/**
 * uiScaler.ts
 * 让 HTML UI 层与 Phaser Scale.FIT 画布严丝合缝对齐。
 *
 * 原理：UI 设计稿宽固定 720、高由视口宽高比动态决定(与游戏画布一致，
 * 见 core/viewport.ts)。按 Phaser FIT 的同一算法计算缩放比例
 * scale = min(容器宽 / 720, 容器高 / designH)，
 * 通过 transform: translate(-50%, -50%) scale(scale) 应用并居中。
 * 监听窗口尺寸变化 / 方向变化 / 页面重新可见，实时刷新。
 */

import { GAME_WIDTH } from './viewport'

/**
 * 初始化 UI 缩放：以 Phaser 挂载容器（#app）为基准，scale 逻辑与 Scale.FIT 相同。
 * @param container 720×designH 的 UI 容器（#ui-container）
 * @param parent Phaser 挂载容器（#app），其尺寸即 FIT 的适配基准
 * @param designH 本次运行的设计稿高度（与 Phaser 画布一致）
 */
export function initUiScaler(
  container: HTMLElement,
  parent: HTMLElement,
  designH: number,
): void {
  // 设计稿高度随设备动态变化：容器高度由 JS 写死，避免依赖 CSS 类
  container.style.width = `${GAME_WIDTH}px`
  container.style.height = `${designH}px`

  const apply = (): void => {
    const parentW = parent.clientWidth || window.innerWidth
    const parentH = parent.clientHeight || window.innerHeight
    const scale = Math.min(parentW / GAME_WIDTH, parentH / designH)
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
