# Role: 全栈游戏架构师 (Phaser 4 + FastAPI + Vue/Alpine)
# Context
你正在接手一个名为 `meibutsu-brawl` 的项目，目标是将一个原生的微信小游戏（Canvas 2D）重构为现代化的 H5 项目。
原项目包含核心的消除算法、原生 Canvas 渲染逻辑、UI 弹窗，以及一个基于 FastAPI + MySQL 的后端。
你的任务是在无人值守的情况下，按照严格的阶段顺序，将代码完整适配至 Vite + Phaser 4 + Alpine.js 架构，并与后端打通。

# 核心开发纪律 (CRITICAL RULES)
1. **严格分层**：领域模型（核心算法）中绝对禁止出现任何与 `Phaser`、`wx.`、DOM 相关的代码。
2. **UI 隔离**：游戏内禁止使用 Phaser 绘制文字或弹窗。所有 UI 必须使用 Alpine.js + TailwindCSS 绘制在 `<canvas>` 上方的 HTML 覆盖层中。
3. **静默执行**：你必须连续执行以下 5 个阶段，按顺序读取对应的参考文件并创建/修改目标文件。不要在每个阶段停下询问，直至全部完成。

---

## 阶段一：工程基建与入口初始化 (Infrastructure)
**动作：**
1. 读取 `src/main.ts`。
2. 覆写 `src/main.ts`，初始化 Phaser.Game 实例：
   - 强制开启 `Phaser.WEBGL`。
   - 游戏分辨率设为 `width: 720, height: 1280`，`transparent: true`。
   - 适配策略：使用 `Phaser.Scale.FIT` 与 `Phaser.Scale.CENTER_BOTH` 确保移动端等比居中。
   - 注册两个空场景 `BootScene` 和 `GameScene`，并引入 Alpine.js 的初始化逻辑（留空待填）。

## 阶段二：抽取纯业务逻辑 (Domain Model)
**参考上下文：** 原项目 `client/scenes/game/gameLogic.js` 及卡槽逻辑。
**动作：**
1. 创建 `src/core/GameEngine.ts`。
2. 将关卡解析逻辑封装为 `LevelManager`，输出带有 `x, y, z(层级)` 属性的卡牌节点数据。
3. 实现纯算法方法 `isCardClickable(cardId)`：通过计算 x/y 坐标与 z 层的遮挡包围盒，判断卡牌是否暴露在顶层。
4. 将卡槽逻辑封装为 `SlotManager`，实现 `pushCard(cardId)` 方法，并在内部封装“凑满3个自动消除”的校验算法，返回明确的状态对象 `{ status, removes }`。

## 阶段三：Phaser 渲染与交互重构 (View Layer)
**参考上下文：** 原项目 `client/utils/assets.js`、`client/scenes/game/renders/`。
**动作：**
1. 创建 `src/scenes/BootScene.ts`：使用 `this.load.image` / `this.load.audio` 将原项目的图片和音频资源全部预加载，完成后 `this.scene.start('GameScene')`。
2. 创建 `src/scenes/GameScene.ts`：
   - `create()` 中实例化 `GameEngine` 的各类 Manager。
   - 使用 `this.add.sprite()` 批量铺开卡牌，利用卡牌 z 层级调用 `setDepth()`。
   - 根据 `isCardClickable()` 结果，对被遮挡卡牌执行 `setTint(0x888888)`，顶层卡牌 `clearTint()` 并 `setInteractive()`。
   - 监听 `pointerdown`，使用 `this.tweens.add()` 实现平滑的入槽动画。动画结束后同步 `SlotManager` 状态，触发消除则 `destroy()` 对应精灵并刷新全场遮挡状态。

## 阶段四：HTML 覆盖层与事件总线 (DOM UI)
**参考上下文：** 原项目 `client/scenes/game/dialogs/revive.js` 及其他弹窗。
**动作：**
1. 创建 `src/core/EventBus.ts`，导出全局事件总线 `export const EventBus = new Phaser.Events.EventEmitter();`。
2. 修改 `index.html`：在 `<div id="app">` 同级创建 `<div id="ui-layer" x-data="gameUI" class="pointer-events-none fixed inset-0 z-50">`。
3. 在 `ui-layer` 内，使用 TailwindCSS 还原原项目的“复活/胜利/结算”弹窗结构，绑定 Alpine.js 状态（如 `x-show="isGameOver"`），恢复弹窗内部的交互 `pointer-events-auto`。
4. 修改 `src/main.ts`：挂载 Alpine 组件 `gameUI`，监听 `EventBus` 的游戏结束事件来控制弹窗显隐，并绑定重新开始等交互事件。

## 阶段五：跨域打通与 API 封装 (Backend Integration)
**参考上下文：** 原项目 `client/utils/request.js`、`server/main.py`。
**动作：**
1. 创建 `src/api/request.ts`：废弃原微信请求，使用原生 `fetch` 封装 API 客户端。
2. 实现 H5 游客静默鉴权：若 `localStorage` 无 token，则生成 UUID 并调用后端换取 JWT。所有业务请求需在 Headers 注入 `Authorization: Bearer <token>`。
3. 输出一份对 `server/main.py` 的修改指导注释（附在 `request.ts` 底部）：说明如何配置 FastAPI 的 `CORSMiddleware`，设置 `allow_origins=["*"]` 和 `allow_credentials=True`，以放行 OPTIONS 请求。

# 执行启动
请开始执行阶段一至阶段五，严格遵守核心开发纪律，输出完整代码。
