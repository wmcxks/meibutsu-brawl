import Phaser from "phaser";
import { GameEngine } from "../core/GameEngine";
import type { CardNode, LevelConfig } from "../types/game";
import { PropManager } from "../core/PropManager";
import { EventBus, GameEvents } from "../core/EventBus";
import { LEVELS } from "../core/levels";
import { getCurrentTheme } from "../core/themes";
import { startGameSession } from "../api/request";
import { BlockTransition } from "../core/BlockTransition";

/** Card drawing constants (mirror client/scenes/game/renders/cards.js). */
const CARD_SIZE_SCALE = 0.12;
const CARD_3D_DEPTH = 0.1;
const CARD_RADIUS = 8;
const CARD_ICON_PAD = 0.07;

/** Depth bands: board cards use card.z; tray bg sits above them (like the
 *  original render order: cards -> tray bg -> tray cards). */
const TRAY_BG_DEPTH = 900;
const TRAY_CARD_DEPTH = 1000;

/** Bottom slot tray layout (mirrors client/scenes/game/renders/slots.js). */
interface TrayLayout {
  slotSize: number;
  slotGap: number;
  startX: number;
  slotY: number;
  bgX: number;
  bgY: number;
  bgW: number;
  bgH: number;
}

/** Phaser objects of one card: frame (border + 3D side) + theme icon. */
interface CardView {
  root: Phaser.GameObjects.Container;
  frame: Phaser.GameObjects.Image;
  icon: Phaser.GameObjects.Image;
  /** Last clickable state written to the view. */
  clickable: boolean;
  /** true after the first refreshBoard pass has written the real state. */
  ready: boolean;
}

/**
 * GameScene
 * Wires the pure GameEngine (LevelManager / SlotManager / PropManager)
 * to Phaser rendering: cards are fixed-size rounded frames (gold border,
 * 3D side) with the theme icon inset, depth/tint by blocking state,
 * fly-in animations to the bottom slot tray, and the prop bar effects.
 * All dialogs/toasts live in the HTML overlay (Alpine.js + TailwindCSS),
 * communicated through the global EventBus.
 */
export default class GameScene extends Phaser.Scene {
  /** Pure model layer: board + tray. */
  private readonly engine = new GameEngine(7);
  /** Pure model layer: prop use counts. */
  private readonly props = new PropManager();

  /**
   * Theme in use for this run. Resolved lazily (getter, not a constructor
   * field): scenes are instantiated at game boot, BEFORE BootScene.preload()
   * runs pickTheme(), so a constructor-time capture would freeze the default
   * theme and mismatch the textures actually loaded.
   */
  private get theme(): { name: string; iconCount: number } {
    return getCurrentTheme();
  }
  /** cardId -> card view mapping for all spawned cards. */
  private readonly sprites = new Map<string, CardView>();
  /** Ids of cards currently interactive (clickable). */
  private readonly clickableIds = new Set<string>();
  /** true once GAME_OVER / GAME_WIN fired; blocks further input. */
  private paused = false;
  /** Timestamp (ms) of the current run start, used to compute the final score. */
  private startAt = 0;
  /** Backend session id for the current run (anti-cheat); null until fetched. */
  private currentSessionId: string | null = null;
  /** "关卡生成中..." overlay shown while the session request is in flight. */
  private loadingText: Phaser.GameObjects.Text | null = null;
  /** Guards stale session awaits after the scene is shut down / restarted. */
  private loadSeq = 0;
  /** Whether the revive opportunity has already been used this run. */
  private revived = false;
  /** Index of the level currently loaded (0-based). */
  private currentLevel = 0;
  /** Fixed card size (face width/height) in design pixels. */
  private cardSize = 0;
  /** 3D side thickness below the card face. */
  private cardDepth = 0;
  /** Icon inset from the card edge. */
  private cardPad = 0;
  /** Slot tray geometry (computed once per level). */
  private tray!: TrayLayout;
  /** Peek prop: waiting for the player to pick a card to reveal around. */
  private peekMode = false;
  /** Card views currently revealed by the peek effect. */
  private peekViews: CardView[] = [];
  /** Timer that restores the peek effect. */
  private peekTimer: Phaser.Time.TimerEvent | null = null;

  constructor() {
    super("GameScene");
  }

  create(): void {
    EventBus.on(GameEvents.RESTART_GAME, this.handleRestart);
    EventBus.on(GameEvents.REVIVE_GAME, this.handleRevive);
    EventBus.on(GameEvents.USE_PROP, this.handleUseProp);
    EventBus.on(GameEvents.RETRY_SESSION, this.handleRetrySession);
    this.events.on(Phaser.Scenes.Events.SHUTDOWN, this.handleShutdown, this);

    // 应用持久化的音效开关（与 main.ts toggleSound 的 localStorage 键一致）
    this.sound.mute = localStorage.getItem("hd_sound_on") === "0";

    // scene.restart() reuses THIS instance, so all per-run state must be reset
    // here; otherwise the previous run's pause/revive/sprites leak into the new one.
    if (this.peekTimer) {
      this.peekTimer.remove(false);
      this.peekTimer = null;
    }
    this.sprites.clear();
    this.clickableIds.clear();
    this.paused = false;
    this.revived = false;
    this.peekMode = false;
    this.peekViews = [];
    this.engine.reset();
    this.props.reset();

    this.cardSize = Math.round(this.scale.width * CARD_SIZE_SCALE);
    this.cardDepth = Math.round(this.cardSize * CARD_3D_DEPTH);
    this.cardPad = Math.round(this.cardSize * CARD_ICON_PAD);

    this.buildCardTextures();
    this.buildTray();
    this.buildLevelAsync();
    EventBus.emit(GameEvents.PROPS_CHANGED, this.props.getCounts());
  }

  /**
   * Fetch the backend session first, THEN render the level:
   * cards must not exist until the server-side anti-cheat baseline is ready.
   */
  private async buildLevelAsync(): Promise<void> {
    // Invalidate any previous in-flight request (e.g. from a fast restart).
    const runToken = ++this.loadSeq;
    this.currentSessionId = null;

    if (this.loadingText) this.loadingText.destroy();
    this.loadingText = this.add
      .text(this.scale.width / 2, this.scale.height / 2, "关卡生成中...", {
        fontSize: "28px",
        color: "#ffffff",
      })
      .setOrigin(0.5)
      .setDepth(5000)
      .setBackgroundColor("rgba(0,0,0,0.5)")
      .setPadding(16, 10);

    try {
      const sessionId = await startGameSession(this.currentLevel + 1);
      if (runToken !== this.loadSeq) return; // scene was restarted/stopped meanwhile
      this.currentSessionId = sessionId;
    } catch (err) {
      if (runToken !== this.loadSeq) return;
      // Fast-fail: ask the player to retry manually through the Alpine dialog.
      console.warn("[session] 开局会话失败，等待玩家手动重连:", err);
      this.loadingText.destroy();
      this.loadingText = null;
      EventBus.emit(GameEvents.NETWORK_ERROR);
      return;
    }

    this.loadingText.destroy();
    this.loadingText = null;

    // The score timer starts when gameplay actually begins (not during loading).
    this.startAt = this.time.now;
    this.buildLevel();
    EventBus.emit(
      GameEvents.LEVEL_STARTED,
      this.currentLevel + 1,
      LEVELS[this.currentLevel].title ?? "",
    );
  }

  /** Bake the two card-frame textures (normal / blocked) once per run. */
  private buildCardTextures(): void {
    // Textures live in the global texture manager: skip re-baking on restarts.
    if (this.textures.exists("card_frame")) return;

    const w = this.cardSize;
    const h = this.cardSize;
    const depth = this.cardDepth;
    const texH = h + depth;

    const g = this.make.graphics({ x: 0, y: 0 });
    g.setVisible(false);

    // Normal frame: gold 3D side, cream face, gold border.
    g.clear();
    g.fillStyle(0xb8923a, 1);
    g.fillRoundedRect(1, depth, w, h, CARD_RADIUS);
    g.fillStyle(0xfffdf5, 1);
    g.fillRoundedRect(0, 0, w, h, CARD_RADIUS);
    g.lineStyle(1.5, 0xc8a96e, 1);
    g.strokeRoundedRect(0, 0, w, h, CARD_RADIUS);
    g.generateTexture("card_frame", w, texH);

    // Blocked frame: dark 3D side, dull face, gray border.
    g.clear();
    g.fillStyle(0x4a5354, 1);
    g.fillRoundedRect(1, depth, w, h, CARD_RADIUS);
    g.fillStyle(0xd2cdb6, 1);
    g.fillRoundedRect(0, 0, w, h, CARD_RADIUS);
    g.lineStyle(1.5, 0x999999, 1);
    g.strokeRoundedRect(0, 0, w, h, CARD_RADIUS);
    g.generateTexture("card_frame_blocked", w, texH);

    g.destroy();
  }

  /** Rebuild the whole board from scratch (fresh level, fresh slot tray). */
  private buildLevel(): void {
    const cards = this.engine.loadLevel(this.buildLevelConfig());
    this.engine.deal(this.buildDeck(cards.length));
    // 背景不再由 Phaser 绘制：由 DOM 层的 #bg-container 旋转渐变垫底

    const iconSize = this.cardSize - this.cardPad * 2;
    const texH = this.cardSize + this.cardDepth;

    for (const card of cards) {
      card.texture = `images/game/cards/themes/${this.theme.name}/${card.type}.png`;

      // Container is anchored at the face center: hit-testing adds
      // displayOrigin (size*0.5), so x/y must be the visual center.
      const root = this.add.container(
        card.x + this.cardSize / 2,
        card.y + this.cardSize / 2,
      );
      root.setSize(this.cardSize, texH);

      const frame = this.add.image(0, 0, "card_frame");
      const icon = this.add
        .image(0, 0, card.texture)
        .setDisplaySize(iconSize, iconSize);
      root.add([frame, icon]);

      root.setDepth(card.z);
      // NOTE: do NOT setInteractive here — refreshBoard() is the single
      // source of truth for the interactive state (blocked cards stay inert).
      root.on(Phaser.Input.Events.POINTER_DOWN, () =>
        this.onCardPicked(root, card),
      );

      this.sprites.set(card.id, {
        root,
        frame,
        icon,
        clickable: false,
        ready: false,
      });
    }

    this.refreshBoard();
  }

  /** Bottom slot tray background (slots.png), sized for 7 slots. */
  private buildTray(): void {
    const slotSize = Math.round(this.scale.width * 0.11);
    const slotGap = Math.round(this.scale.width * 0.014);
    const maxSlots = 7;
    const totalSlotWidth = maxSlots * (slotSize + slotGap);
    const startX = (this.scale.width - totalSlotWidth) / 2;
    const slotY = Math.round(this.scale.height * 0.82);
    const padding = Math.round(this.scale.width * 0.02);

    this.tray = {
      slotSize,
      slotGap,
      startX,
      slotY,
      bgX: startX - padding,
      bgY: slotY - padding,
      bgW: totalSlotWidth + padding * 2,
      bgH: slotSize + padding * 2,
    };

    // The tray panel is interactive so it swallows clicks over its area:
    // board cards tucked underneath (e.g. level 2 corner stacks) can no longer
    // be picked "through" the panel — only their exposed parts stay clickable.
    // 托盘几何跨关固定，此背景只需创建一次，换关时复用。
    this.add
      .image(
        this.tray.bgX + this.tray.bgW / 2,
        this.tray.bgY + this.tray.bgH / 2,
        "images/game/cards/slots.png",
      )
      .setDisplaySize(this.tray.bgW, this.tray.bgH)
      .setDepth(TRAY_BG_DEPTH)
      .setInteractive();
  }

  /** Center of the n-th slot cell. */
  private getSlotCenter(index: number): { x: number; y: number } {
    return {
      x:
        this.tray.startX +
        index * (this.tray.slotSize + this.tray.slotGap) +
        this.tray.slotSize / 2,
      y: this.tray.slotY + this.tray.slotSize / 2,
    };
  }

  /**
   * Re-sync every in-tray card sprite to its model slot index.
   * Called after any tray mutation (push, match, move-out, undo, revive):
   * remaining cards shift left into the gaps and land at the correct cell,
   * so no visual duplicates or empty holes appear.
   */
  private refreshTray(): void {
    this.engine.slots.getSlots().forEach((card, index) => {
      const view = this.sprites.get(card.id);
      if (!view) return;
      const target = this.getSlotCenter(index);
      view.root.setDepth(TRAY_CARD_DEPTH);
      this.tweens.add({
        targets: view.root,
        x: target.x,
        y: target.y,
        duration: 150,
        ease: "Quad.easeOut",
      });
    });
  }

  /** Pick handler: lock the card, play SFX and tween it toward the slot tray. */
  private onCardPicked(
    root: Phaser.GameObjects.Container,
    card: CardNode,
  ): void {
    if (this.paused) return;

    // Peek mode: clicking a top card reveals the 3x3 area around it.
    if (this.peekMode) {
      this.activatePeek(card);
      return;
    }

    root.disableInteractive();
    this.clickableIds.delete(card.id);
    this.playClickSfx(card);

    // Landing: container x/y is the visual center (face center).
    const target = this.getSlotCenter(this.engine.slots.size);
    const slotScale = this.tray.slotSize / this.cardSize;

    this.tweens.add({
      targets: root,
      x: target.x,
      y: target.y,
      scale: slotScale,
      duration: 250,
      ease: "Quad.easeIn",
      onComplete: () => {
        const result = this.engine.pushCard(card.id);

        if (result.status === "MATCHED" && result.removes) {
          for (const id of result.removes) {
            this.sprites.get(id)?.root.destroy();
            this.sprites.delete(id);
          }
          this.sound.play("audio/game/merge.mp3");
        }

        // Re-sort the tray visuals to the model order (fills gaps, no overlaps).
        this.refreshTray();

        // Resolve the round outcome; the score is the run duration in seconds.
        const score = Number(
          ((this.time.now - this.startAt) / 1000).toFixed(1),
        );
        const levelId = this.currentLevel + 1;
        const sessionId = this.currentSessionId ?? "";
        if (result.status === "FULL_GAME_OVER") {
          this.pauseGame();
          if (!this.revived) {
            // First failure: offer the revive dialog instead of game over.
            this.revived = true;
            EventBus.emit(GameEvents.REVIVE_OFFERED);
          } else {
            this.sound.play("audio/game/defeat.mp3");
            EventBus.emit(GameEvents.GAME_OVER, score, levelId, sessionId);
          }
          return;
        }
        if (this.engine.getAliveCards().length === 0) {
          this.pauseGame();
          this.sound.play("audio/game/success.mp3");
          // 胜利：不再弹窗，用转场动画遮挡并自动进入下一关
          this.startWinTransition(score, levelId, sessionId);
          return;
        }

        this.refreshBoard();
      },
    });
  }

  /** Original click SFX: icon 1 = cow, icon 2 = horse, else normal. */
  private playClickSfx(card: CardNode): void {
    if (card.type === "1") this.sound.play("audio/game/click/cow.mp3");
    else if (card.type === "2") this.sound.play("audio/game/click/horse.mp3");
    else this.sound.play("audio/game/click/normal.mp3");
  }

  /** Stop all board input so the paused game cannot be clicked underneath the dialog. */
  private pauseGame(): void {
    this.paused = true;
    for (const id of this.clickableIds) {
      this.sprites.get(id)?.root.disableInteractive();
    }
    this.clickableIds.clear();
  }

  /** UI requested a restart: rebuild the current level from scratch. */
  private readonly handleRestart = (): void => {
    this.scene.restart();
  };

  /**
   * 胜利转场：成绩静默上报（Alpine 监听 GAME_WIN），同时用 BlockTransition
   * 方块波浪遮罩屏幕 —— 完全遮挡后原地切换到下一关（不重启场景，
   * 转场 tween 与方块得以存活到退场结束），退场露出新关卡。
   * 使用当前主题的卡牌图标作为方块贴图，随关卡轮换不单调。
   */
  private startWinTransition(score: number, levelId: number, sessionId: string): void {
    // 1. 成绩照常上报（UI 不再弹窗）
    EventBus.emit(GameEvents.GAME_WIN, score, levelId, sessionId);
    // 2. 转场期间隐藏 HTML UI 层，保证方块遮罩铺满全屏无悬浮遮挡
    EventBus.emit(GameEvents.TRANSITION_START);

    // 3. 取当前主题的一张卡牌图标作为方块贴图（随关卡轮换，视觉不单调）
    const theme = this.theme;
    const iconNo = ((levelId - 1) % theme.iconCount) + 1;
    const textureKey = `images/game/cards/themes/${theme.name}/${iconNo}.png`;

    // 4. 播放转场：遮挡瞬间原地换关，退场完成自动销毁释放资源
    const transition = new BlockTransition(this, {
      width: this.scale.width,
      height: this.scale.height,
    });
    transition.play(
      textureKey,
      () => this.swapToNextLevel(),
      () => {
        transition.destroy();
        EventBus.emit(GameEvents.TRANSITION_END);
      },
    );
  }

  /**
   * 在转场遮罩下原地切换关卡：销毁旧棋盘的全部渲染对象并重建，
   * 不调用 scene.restart()（否则转场层随场景销毁）。
   */
  private swapToNextLevel(): void {
    if (this.peekTimer) {
      this.peekTimer.remove(false);
      this.peekTimer = null;
    }
    for (const view of this.sprites.values()) view.root.destroy();
    this.sprites.clear();
    this.clickableIds.clear();
    this.peekViews = [];
    this.peekMode = false;
    // 托盘背景跨关复用（几何固定），此处不销毁

    this.paused = false;
    this.revived = false;
    this.engine.reset();
    this.props.reset();
    this.currentLevel = (this.currentLevel + 1) % LEVELS.length; // 最后一关通关后回到第一关
    EventBus.emit(GameEvents.PROPS_CHANGED, this.props.getCounts());

    this.buildLevelAsync();
  }

  /** Network-error dialog "重新连接": re-fetch the session and continue. */
  private readonly handleRetrySession = (): void => {
    this.buildLevelAsync();
  };

  /**
   * Revive: pull one card out of the tray and place it below the board
   * (mirrors the original moveOut prop), grant +1 move-out, then resume.
   */
  private readonly handleRevive = (): void => {
    const card = this.engine.moveOut(1)[0];
    if (!card) return;

    const view = this.sprites.get(card.id);
    if (!view) return;

    const size = this.cardSize;
    let maxZ = 0;
    for (const c of this.engine.getAliveCards()) {
      if (c.z > maxZ) maxZ = c.z;
    }
    card.x = (this.scale.width - size) / 2;
    card.y = this.scale.height * 0.68;
    card.z = maxZ + 1;

    view.root.setDepth(card.z);
    // The view left the board: force the next refresh to rewrite its state
    // (re-enable interactivity when the card is exposed again).
    view.ready = false;
    this.props.addCount(0, 1);
    EventBus.emit(GameEvents.PROPS_CHANGED, this.props.getCounts());

    this.paused = false;
    this.refreshTray();
    this.tweens.add({
      targets: view.root,
      x: card.x + size / 2,
      y: card.y + size / 2,
      scale: 1,
      duration: 300,
      ease: "Quad.easeOut",
    });

    // pauseGame() 时整板被 disableInteractive()，但 view.ready/clickable 仍为 true，
    // refreshBoard 的增量优化会跳过这些卡导致无法重新点击；
    // 复活后强制全板视图重写真实交互状态。
    for (const c of this.engine.getAliveCards()) {
      const v = this.sprites.get(c.id);
      if (v) v.ready = false;
    }
    this.refreshBoard();
  };

  /** Prop bar clicked by the UI overlay; payload is the prop index. */
  private readonly handleUseProp = (index: number): void => {
    if (this.paused) return;
    if (this.props.getCount(index) <= 0) {
      EventBus.emit(GameEvents.TOAST, "次数已用完");
      return;
    }

    let ok = false;
    switch (index) {
      case 0:
        ok = this.useMoveOut();
        break;
      case 1:
        ok = this.useUndo();
        break;
      case 2:
        ok = this.useShuffle();
        break;
      case 3:
        ok = this.usePeek();
        break;
    }

    if (ok) {
      this.props.use(index);
      EventBus.emit(GameEvents.PROPS_CHANGED, this.props.getCounts());
    }
  };

  /** Prop 0 (移出): take up to 3 tray cards below the board, stacked in rows. */
  private useMoveOut(): boolean {
    const moved = this.engine.moveOut(3);
    if (moved.length === 0) {
      EventBus.emit(GameEvents.TOAST, "槽位为空");
      return false;
    }

    const height = this.scale.height;
    const size = this.cardSize;
    const texH = size + this.cardDepth;
    const gap = Math.round(size * 0.15);
    const totalW = moved.length * (size + gap) - gap;
    const startX = (this.scale.width - totalW) / 2;
    const baseY = Math.round(height * 0.68);

    let maxExistY = -1;
    for (const c of this.engine.getAliveCards()) {
      if (c.y >= baseY && c.y > maxExistY) maxExistY = c.y;
    }
    const posY = Math.min(
      maxExistY >= 0 ? maxExistY + Math.round(height * 0.015) : baseY,
      height - texH,
    );

    let maxZ = 0;
    for (const c of this.engine.getAliveCards()) {
      if (c.z > maxZ) maxZ = c.z;
    }

    moved.forEach((card, i) => {
      card.x = startX + i * (size + gap);
      card.y = posY;
      card.z = maxZ + 1;
      const view = this.sprites.get(card.id);
      if (view) {
        view.root.setDepth(card.z);
        view.ready = false;
        this.tweens.add({
          targets: view.root,
          x: card.x + size / 2,
          y: card.y + size / 2,
          scale: 1,
          duration: 300,
          ease: "Quad.easeOut",
        });
      }
    });

    this.refreshTray();
    this.refreshBoard();
    return true;
  }

  /** Prop 1 (撤回): put the last picked card back to its board position. */
  private useUndo(): boolean {
    const card = this.engine.undo();
    if (!card) {
      EventBus.emit(GameEvents.TOAST, "无可撤回的操作");
      return false;
    }
    const view = this.sprites.get(card.id);
    if (view) {
      view.root.setDepth(card.z);
      view.ready = false;
      this.tweens.add({
        targets: view.root,
        x: card.x + this.cardSize / 2,
        y: card.y + this.cardSize / 2,
        scale: 1,
        duration: 250,
        ease: "Quad.easeOut",
      });
    }
    this.refreshTray();
    this.refreshBoard();
    return true;
  }

  /** Prop 2 (洗牌): reshuffle types among board cards, updating textures. */
  private useShuffle(): boolean {
    if (!this.engine.shuffle(this.scale.height * 0.68)) {
      EventBus.emit(GameEvents.TOAST, "无可洗的卡牌");
      return false;
    }
    const iconSize = this.cardSize - this.cardPad * 2;
    for (const card of this.engine.getAliveCards()) {
      const view = this.sprites.get(card.id);
      if (!view || !card.type) continue;
      view.icon
        .setTexture(
          `images/game/cards/themes/${this.theme.name}/${card.type}.png`,
        )
        .setDisplaySize(iconSize, iconSize);
    }
    this.refreshBoard();
    return true;
  }

  /** Prop 3 (透视): enter peek mode — next top-card click reveals its 3x3 area. */
  private usePeek(): boolean {
    if (this.engine.getAliveCards().length === 0) {
      EventBus.emit(GameEvents.TOAST, "无可透视的卡牌");
      return false;
    }
    this.peekMode = true;
    EventBus.emit(GameEvents.TOAST, "请点击一张顶层卡牌");
    return true;
  }

  /** Reveal the clickable cards in the 3x3 area around a card for 3 seconds. */
  private activatePeek(centerCard: CardNode): void {
    this.peekMode = false;
    this.clearPeek();

    const size = this.cardSize;
    const cx = centerCard.x + size / 2;
    const cy = centerCard.y + size / 2;
    const range = size * 1.5;

    const revealed: CardView[] = [];
    for (const card of this.engine.getAliveCards()) {
      const cardCx = card.x + card.width / 2;
      const cardCy = card.y + card.height / 2;
      if (
        Math.abs(cardCx - cx) < range &&
        Math.abs(cardCy - cy) < range &&
        this.engine.isCardClickable(card.id)
      ) {
        const view = this.sprites.get(card.id);
        if (view) revealed.push(view);
      }
    }

    this.peekViews = revealed;
    for (const view of this.peekViews) view.root.setAlpha(0.35);
    this.peekTimer = this.time.delayedCall(3000, () => this.clearPeek());
  }

  /** Restore alpha after the peek effect expires. */
  private clearPeek(): void {
    for (const view of this.peekViews) view.root.setAlpha(1);
    this.peekViews = [];
    if (this.peekTimer) {
      this.peekTimer.remove(false);
      this.peekTimer = null;
    }
  }

  /** Cleanup before the scene is destroyed, to avoid duplicated listeners. */
  private handleShutdown(): void {
    // Invalidate any in-flight session request; its result must not be applied.
    this.loadSeq++;
    EventBus.off(GameEvents.RESTART_GAME, this.handleRestart);
    EventBus.off(GameEvents.REVIVE_GAME, this.handleRevive);
    EventBus.off(GameEvents.USE_PROP, this.handleUseProp);
    EventBus.off(GameEvents.RETRY_SESSION, this.handleRetrySession);
  }

  /**
   * Re-sync every surviving card's visual/interactive state.
   * The first pass always writes the real state (views start uninitialized);
   * later passes only write on clickable <-> blocked transitions, so picking a
   * card doesn't churn textures/alpha on all 200+ cards every time.
   */
  private refreshBoard(): void {
    for (const card of this.engine.getAliveCards()) {
      const view = this.sprites.get(card.id);
      if (!view) continue;

      const clickable = this.engine.isCardClickable(card.id);
      if (view.ready && clickable === view.clickable) continue;

      view.ready = true;
      view.clickable = clickable;
      if (clickable) {
        view.frame.setTexture("card_frame");
        view.icon.setAlpha(1);
        if (!this.clickableIds.has(card.id)) {
          view.root.setInteractive({ useHandCursor: true });
          this.clickableIds.add(card.id);
        }
      } else {
        view.frame.setTexture("card_frame_blocked");
        view.icon.setAlpha(0.5);
        if (this.clickableIds.has(card.id)) {
          view.root.disableInteractive();
          this.clickableIds.delete(card.id);
        } else if (view.root.input?.enabled) {
          // Defensive: a blocked card must never remain interactive.
          view.root.disableInteractive();
        }
      }
    }
  }

  /** Current level definition (design-space sizes applied on load). */
  private buildLevelConfig(): LevelConfig {
    return {
      ...LEVELS[this.currentLevel],
      width: this.scale.width,
      height: this.scale.height,
    };
  }

  /**
   * Build a deck of triples from `iconTypes` random theme icons, then shuffle
   * (Fisher-Yates). The type value doubles as the icon file number: <theme>/<type>.png
   */
  private buildDeck(totalCards: number): string[] {
    const iconTypes = Math.min(
      LEVELS[this.currentLevel].iconTypes,
      this.theme.iconCount,
    );
    const pool = Array.from({ length: this.theme.iconCount }, (_, i) => i + 1);
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    const types = pool.slice(0, iconTypes);

    const deck: string[] = [];
    const triplets = Math.floor(totalCards / 3);
    for (let i = 0; i < triplets; i++) {
      const type = types[i % types.length];
      deck.push(String(type), String(type), String(type));
    }
    for (let i = deck.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [deck[i], deck[j]] = [deck[j], deck[i]];
    }
    return deck;
  }
}
