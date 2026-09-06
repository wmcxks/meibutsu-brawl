/**
 * themes.ts
 * Card theme registry — pure data, no Phaser / DOM code.
 *
 * C5（装扮商店）：CARD_THEMES 里每个名字对应一组卡面图，目录种子在服务端
 * hd_cosmetics 中按相同 name 定价（irasutoya = 免费默认款，其余 gem 购买）。
 * 装备的主题写 localStorage('hd_theme')，BootScene 启动时按它预加载卡面；
 * 未装备任何主题（或本地缓存被清）时回退免费默认款。
 */

export interface CardTheme {
  name: string
  iconCount: number
}

/** 全部可用卡面包（名字必须与 public/images/game/cards/themes/<name>/ 及
 *  服务端 hd_cosmetics.item_key 一致；iconCount = 该目录下图片数）。 */
export const CARD_THEMES: CardTheme[] = [
  { name: 'irasutoya', iconCount: 30 },   // 免费默认款
  { name: 'animals', iconCount: 18 },
  { name: 'fruits', iconCount: 14 },
  { name: 'vegetable', iconCount: 14 },
  { name: 'childhood', iconCount: 14 },
  { name: 'work', iconCount: 14 },
  { name: 'beach', iconCount: 14 },
]

/** Default theme（未装备时的兜底）。 */
const DEFAULT_THEME = CARD_THEMES[0]

/** localStorage 键：装备中的主题名（main.ts 启动时与服务端装备态同步）。 */
const THEME_STORAGE_KEY = 'hd_theme'

/** 图标资源格式：public 下已统一转 WebP（见 scripts/convert_webp.py） */
export const THEME_ICON_EXT = 'webp'

/** 已预加载到的图标序号（本局资源管理器内，供按需懒加载计算缺口）。 */
let iconsLoadedThrough = 0

/** 构造主题图标路径（key 与 URL 相同，Boot/Game 场景共用）。 */
export function themeIconPath(themeName: string, iconNo: number): string {
  return `images/game/cards/themes/${themeName}/${iconNo}.${THEME_ICON_EXT}`
}

/** 当前已加载到第几个图标（0 = 未加载）。 */
export function getIconsLoadedThrough(): number {
  return iconsLoadedThrough
}

/** 记录已加载到第几个图标（懒加载开始前先占位，防重复入队）。 */
export function markIconsLoadedThrough(iconNo: number): void {
  if (iconNo > iconsLoadedThrough) iconsLoadedThrough = iconNo
}

let currentTheme: CardTheme = DEFAULT_THEME

function findTheme(name: string): CardTheme | null {
  return CARD_THEMES.find((t) => t.name === name) ?? null
}

/** 本地装备中的主题（localStorage；无效值返回 null）。 */
export function getLocalEquippedTheme(): CardTheme | null {
  try {
    const name = localStorage.getItem(THEME_STORAGE_KEY)
    return name ? findTheme(name) : null
  } catch {
    return null
  }
}

/** 写本地装备主题（装备/购买成功后由 UI 层调用）。 */
export function setLocalEquippedTheme(name: string): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, name)
  } catch {
    /* 隐私模式下静默失败 */
  }
}

/** 确定本局使用的主题：优先本地装备，其次免费默认款。 */
export function pickTheme(): CardTheme {
  currentTheme = getLocalEquippedTheme() ?? DEFAULT_THEME
  return currentTheme
}

/** The theme in use for this run. */
export function getCurrentTheme(): CardTheme {
  return currentTheme
}
