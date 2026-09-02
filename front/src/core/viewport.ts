/**
 * viewport.ts
 * 游戏设计稿视口约定(Phaser 画布与 HTML UI 层共用)。
 *
 * 宽固定 720;高按运行设备的宽高比动态取值:
 *   designH = 720 * (视口高 / 视口宽),clamp 到 [1280, 1600]
 * - 16:9 及更方的屏幕(旧手机/平板竖屏/横屏)保持经典 1280,行为不变;
 * - 19.5:9 ~ 20:9 的全面屏手机取 1350~1600,配合 Scale.FIT 正好铺满全屏,
 *   消除画布上下方的留白(此前底部道具栏下方空出一大截的原因)。
 */

export const GAME_WIDTH = 720;
/** 经典高度(16:9);小于等于它的宽高比沿用,避免横屏/方屏布局异常。 */
const GAME_HEIGHT_MIN = 1280;
/** 最高高度(≈20:9),再长的屏幕仍按 FIT 等比留极小黑边。 */
const GAME_HEIGHT_MAX = 1600;

/**
 * 计算设计稿高度。
 * @param parentW 挂载容器宽(实际像素)
 * @param parentH 挂载容器高(实际像素)
 */
export function computeDesignHeight(parentW: number, parentH: number): number {
  if (parentW <= 0 || parentH <= 0) return GAME_HEIGHT_MIN;
  const raw = (GAME_WIDTH * parentH) / parentW;
  return Math.round(Math.min(GAME_HEIGHT_MAX, Math.max(GAME_HEIGHT_MIN, raw)));
}
