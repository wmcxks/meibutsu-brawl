/**
 * themes.ts
 * Card theme registry — pure data, no Phaser / DOM code.
 * Mirrors the original client/scenes/game/renders/themes.js: a global
 * "current theme" is picked once at boot, so BootScene only preloads the
 * icons of the theme actually used this run (instead of all 6 themes).
 */

export interface CardTheme {
  name: string
  iconCount: number
}

export const CARD_THEMES: CardTheme[] = [
  { name: 'animals', iconCount: 18 },
  { name: 'beach', iconCount: 14 },
  { name: 'childhood', iconCount: 14 },
  { name: 'fruits', iconCount: 14 },
  { name: 'vegetable', iconCount: 14 },
  { name: 'work', iconCount: 14 },
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
