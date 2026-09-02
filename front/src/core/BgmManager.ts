/**
 * BgmManager.ts
 * 游戏内循环背景音乐。用 DOM <audio> 管理,不经过 Phaser 的 decodeAudioData
 * 队列,避免把整首曲子解码进 WebAudio 内存;循环无缝且随声音开关即时启停。
 *
 * 行为(对齐原 client/utils/audio.js 的语义):
 *   - 首次进入 GameScene 时从 bg_game/ 三首里随机选一首;
 *   - 之后关卡重开/切换不再换曲(本局固定,同组不重复随机);
 *   - 静音开关(localStorage 'hd_sound_on' === '0')直接暂停/恢复;
 *   - 浏览器自动播放策略:create 时尝试播放,被拦截则挂一次 document
 *     pointerdown,在首次真实手势里补放。
 */
const BGM_POOL = [
  "audio/bg_game/bg_game.mp3",
  "audio/bg_game/bg_game_2.mp3",
  "audio/bg_game/bg_game_3.mp3",
];

const BGM_VOLUME = 0.5;

let audio: HTMLAudioElement | null = null;
let currentKey: string | null = null;
let unlockBound = false;

function musicMuted(): boolean {
  return localStorage.getItem("hd_sound_on") === "0";
}

function tryPlay(): void {
  if (!audio || musicMuted()) return;
  audio.play().catch(() => {
    // 自动播放仍被拦截:等待下一次手势重试(见 unlock)
    bindUnlock();
  });
}

/** 首次手势补放(Chrome/Safari 都需要用户交互后才能出声)。 */
function bindUnlock(): void {
  if (unlockBound) return;
  unlockBound = true;
  document.addEventListener(
    "pointerdown",
    () => {
      if (audio && audio.paused && !musicMuted()) {
        audio.play().catch(() => {});
      }
    },
    true,
  );
}

/**
 * 进入游戏场景时调用:随机选一首开始循环。
 * 已有曲目在播/被静音则保持现状,避免场景 restart 时反复换曲。
 */
export function startGameBgm(): void {
  if (currentKey) return;
  const pick = BGM_POOL[Math.floor(Math.random() * BGM_POOL.length)];
  currentKey = pick;

  if (audio) {
    audio.src = pick;
  } else {
    audio = new Audio(pick);
    audio.loop = true;
    audio.volume = BGM_VOLUME;
    audio.addEventListener("error", () => {
      console.warn("[bgm] 背景音乐加载失败:", pick);
    });
  }
  tryPlay();
  bindUnlock();
}

/** 声音开关联动:true = 静音(暂停),false = 恢复。 */
export function setBgmMuted(muted: boolean): void {
  if (muted) {
    audio?.pause();
  } else if (!currentKey) {
    // 静音状态下进入过游戏(未选曲),开声音后补启背景乐
    startGameBgm();
  } else {
    tryPlay();
  }
}

/** 页面隐藏时暂停、回到前台恢复(对齐原 wx.onHide/pauseBgm 行为)。 */
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    audio?.pause();
  } else if (!musicMuted()) {
    tryPlay();
  }
});
