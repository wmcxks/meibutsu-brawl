/**
 * themes.ts
 * Card theme registry — pure data, no Phaser / DOM code.
 * Mirrors the original client/scenes/game/renders/themes.js: a global
 * "current theme" is picked once at boot, so BootScene only preloads the
 * icons of the theme actually used this run.
 * 当前只启用 irasutoya（いらすとや）一个图片包；如需重新启用多包，
 * 将更多 { name, iconCount } 加回 CARD_THEMES 即可（iconCount 必须与
 * public/images/game/cards/themes/<name>/ 下的图片数一致）。
 */

export interface CardTheme {
  name: string
  iconCount: number
}

export const CARD_THEMES: CardTheme[] = [
  { name: 'irasutoya', iconCount: 30 },
]

/** Default theme (fallback before pickRandom). */
const DEFAULT_THEME = CARD_THEMES[0]

let currentTheme: CardTheme = DEFAULT_THEME

/** Pick a random theme as the current one (call once at boot). */
export function pickTheme(): CardTheme {
  currentTheme = CARD_THEMES[Math.floor(Math.random() * CARD_THEMES.length)]
  return currentTheme
}

/** The theme in use for this run. */
export function getCurrentTheme(): CardTheme {
  return currentTheme
}
