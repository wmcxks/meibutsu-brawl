/**
 * BlockTransition.ts
 * 游戏关卡转场特效（Phaser 4 原生实现）：大量游戏方块像一群羊一样，
 * 以整体队形从屏幕左侧连续跑到右侧 —— 中途完全遮挡屏幕的瞬间触发
 * onCovered（底层在此销毁旧关卡并渲染新关卡），全程无停顿，
 * 跑出屏幕后触发 onComplete 并彻底清理。
 *
 * 防闪烁设计：
 *   1. 方块尺寸加大（默认 128px）；
 *   2. 方块互相堆叠（间距 = blockSize * (1 - overlap) < blockSize），
 *      网格任意位置都无缝隙，底层换关过程完全不可见；
 *   3. 起始/结束位置精确对齐屏幕边缘，t=0 不会有方块瞬间弹出。
 *
 * 时间轴：单段 Sweep ≈ 1.4s（可配 totalDuration，1.2 ~ 1.5s 区间）：
 *   - 前段：方块群从屏幕左侧外跑入
 *   - 中段：完全遮挡（此时触发 onCovered，底层换关）
 *   - 后段：继续跑向右侧外，露出新关卡，触发 onComplete
 */

import Phaser from "phaser";

/** 构造参数（均可选，带默认值） */
export interface BlockTransitionOptions {
  /** 舞台宽度（设计稿像素，默认 720） */
  width?: number;
  /** 舞台高度（设计稿像素，默认 1280） */
  height?: number;
  /** 单个方块尺寸（默认 128，越大遮挡越严实） */
  blockSize?: number;
  /** 方块堆叠率（0~1，默认 0.2 = 相邻方块重叠 20%，保证零缝隙） */
  overlap?: number;
  /** 整段横跑动画时长（秒，默认 1.4，区间 1.2 ~ 1.5） */
  totalDuration?: number;
  /** 左右两侧的额外“牧群”列数（默认 2，越大遮挡窗口越长、换关越从容） */
  paddingColumns?: number;
  /** 转场容器的 depth（默认 1e6，压过一切游戏实体与 UI） */
  depth?: number;
}

/** 统一配置类型：所有字段必填（内部使用） */
type ResolvedOptions = Required<BlockTransitionOptions>;

export class BlockTransition {
  /** 当前转场所在的 Phaser 场景 */
  private readonly scene: Phaser.Scene;
  /** 转场容器：整群方块由其统一位移，保证“一起出现一起消失” */
  private readonly container: Phaser.GameObjects.Container;
  /** 解析后的配置 */
  private readonly opts: ResolvedOptions;
  /** 横跑 Tween 引用（供销毁时 kill） */
  private sweepTween: Phaser.Tweens.Tween | null = null;
  /** 是否已触发过 onCovered（遮挡瞬间只回调一次） */
  private coveredFired = false;
  /** 是否已彻底销毁（防止重复调用） */
  private destroyed = false;

  constructor(scene: Phaser.Scene, options: BlockTransitionOptions = {}) {
    this.scene = scene;
    this.opts = {
      width: 720,
      height: 1280,
      blockSize: 256,
      overlap: 0.35,
      totalDuration: 2.1,
      paddingColumns: 2,
      depth: 1_000_000,
      ...options,
    };

    this.container = scene.add.container(0, 0);
    this.container.setDepth(this.opts.depth); // 极高 depth：遮挡所有 UI 与实体
    this.container.setScrollFactor(0); // 不随相机滚动（防御性，保证永远贴住屏幕）
  }

  /**
   * 播放关卡转场：方块群从左侧连续跑到右侧。
   * @param blockTextureKey 游戏方块贴图在 TextureManager 中的 key
   * @param onCovered   屏幕被完全遮挡的瞬间触发（仅一次）；底层应在此销毁旧关卡、渲染新关卡。
   *                    返回 Promise 时，方块群会停在完全遮挡位等待其完成再继续退场
   *                    （用于换关前懒加载新关卡素材，杜绝露出缺贴图的瞬间）。
   * @param onComplete  方块群跑出屏幕、新关卡可见后触发；内部已自动清理全部资源
   */
  play(
    blockTextureKey: string,
    onCovered: () => void | Promise<void>,
    onComplete: () => void,
  ): void {
    if (this.destroyed) {
      console.warn("[BlockTransition] 实例已销毁，请新建实例");
      return;
    }

    // 防重入：若上一次转场还在播放，先杀 tween 并清场
    this.reset();

    const { width, height, blockSize, overlap, paddingColumns } = this.opts;
    // 堆叠网格：列/行间距小于方块尺寸，相邻方块重叠，任意位置零缝隙
    const step = blockSize * (1 - overlap);
    const cols = Math.ceil(width / step);
    const rows = Math.ceil(height / step);

    // 1. 生成网格:左右各 paddingColumns 列“牧群余量”,上下各补 1 行,
    //    加宽加高队形可拉长完全遮挡的时间窗口,且素材边缘若带透明像素
    //    也不会在屏幕顶部/底部露出缝隙。
    for (let row = -1; row <= rows; row++) {
      for (let col = -paddingColumns; col < cols + paddingColumns; col++) {
        const sprite = this.scene.add.sprite(
          0,
          row * step + blockSize / 2,
          blockTextureKey,
        );
        sprite.setOrigin(0.5);
        sprite.setDisplaySize(blockSize, blockSize); // 统一方块尺寸（素材可能非正方形）
        sprite.x = col * step + blockSize / 2;
        this.container.add(sprite);
      }
    }

    // 2. 几何计算（相对容器坐标）：
    //    - 左侧第一列左边缘 = -paddingColumns * step
    //    - 右侧最后一列右边缘 = (cols + paddingColumns) * step
    //    - 完全遮挡判定窗口：[width - (cols+paddingColumns)*step, paddingColumns*step]
    const flockWidth = (cols + paddingColumns * 2) * step;
    const startX = -flockWidth; // 右缘恰好贴住屏幕左缘：t=0 无方块弹出
    const endX = width + paddingColumns * step; // 左缘恰好越过屏幕右缘：完全退场
    const coverStartX = width - (cols + paddingColumns) * step; // 刚完全遮挡时的容器 x

    // 3. 起点就位后，用一条连续 Tween 驱动整群方块左→右横跑：
    //    中段完全遮挡瞬间回调 onCovered（仅一次），全程无停顿。
    this.container.setX(startX);
    this.coveredFired = false;

    this.sweepTween = this.scene.tweens.add({
      targets: this.container,
      x: endX,
      duration: this.opts.totalDuration * 1000,
      ease: "Sine.easeInOut", // 起止轻柔、中段匀速，奔跑感连贯
      onUpdate: (tween: Phaser.Tweens.Tween) => {
        if (
          !this.coveredFired &&
          (tween.targets[0] as Phaser.GameObjects.Container).x >= coverStartX
        ) {
          this.coveredFired = true;
          const result = onCovered();
          // onCovered 异步（懒加载素材等）：暂停方块群停在完全遮挡位，
          // 完成后继续退场；场景已销毁则不恢复（tween 随场景销毁）。
          if (result && typeof (result as Promise<void>).then === "function") {
            this.sweepTween?.pause();
            Promise.resolve(result)
              .then(() => {
                if (!this.destroyed) this.sweepTween?.resume();
              })
              .catch(() => {
                if (!this.destroyed) this.sweepTween?.resume();
              });
          }
        }
      },
      onComplete: () => {
        this.sweepTween = null;
        onComplete();
        this.destroy();
      },
    });
  }

  /** 转场容器（若需外部调整层级/可见性） */
  get view(): Phaser.GameObjects.Container {
    return this.container;
  }

  /**
   * 清场：杀掉 tween，销毁容器内全部方块并清空。
   * 公开暴露，供外部在异常路径（如场景切换）时主动兜底调用。
   */
  reset(): void {
    if (this.sweepTween) {
      this.sweepTween.destroy();
      this.sweepTween = null;
    }
    this.coveredFired = false;
    if (this.container.length > 0) {
      // Phaser 4 的 removeAll(destroyChild=true)：摘除并销毁全部方块 Sprite
      this.container.removeAll(true);
    }
  }

  /**
   * 彻底销毁：先清场，再销毁容器并自显示列表摘除。
   * 注意：Phaser 的 Container.destroy() 不会递归销毁子项，
   * 因此方块已在 reset() 中显式销毁，此处销毁容器本身。
   * 调用后实例不可复用（再次 play 会告警）。
   */
  destroy(): void {
    if (this.destroyed) return;
    this.reset();
    this.container.destroy(true);
    this.destroyed = true;
  }
}
