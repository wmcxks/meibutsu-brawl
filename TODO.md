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

---

# V2 · 商业化游戏升级规划（2026-09）

> 现状结论：现有 `hd_users/openid` 已是可靠的用户唯一标识（guest:/line: 前缀），
> 但只有基础登录 + 通关记录，道具/数值全部在客户端本地，无账号体系、无经济系统、
> 无运营数据。以下按「数据 → 结构 → 商业化 → 合规」分块列 TODO，
> 每块标注了依赖关系；建议按 P0 顺序推进。

## A. 玩家数据模型扩展（P0，其余功能的地基）

| # | 任务 | 价值 / 说明 |
|---|------|-------------|
| A1 | `hd_users` 增列：`country_code`、`region_code`（ISO 3166-1 + 都道府県 JIS）、`platform`、`client_ver`、`status`(normal/banned)、`first_login_at`、`last_login_at`、`login_count` | 区域排名、平台统计、封禁、活跃度分析都依赖这些列 |
| A2 | 统一时间基准：DB/API 全部 UTC，客户端只传时区偏移 | 时长统计、每日重置、排名按日/周切分的正确性 |
| A3 | 新增 `hd_player_daily`(user_id, stat_date, play_seconds, games, wins, ads, rewards, uv_pk) | 按日汇总，是时长/留存/疲劳管控的唯一权威来源 |
| A4 | 新增 `hd_wallet` + `hd_wallet_logs`(幂等 event_id + 流水) | 一切货币/道具变动走流水账（对账、审计、补发），严禁散落 UPDATE |
| A5 | 新增 `hd_user_props`(user_id, prop_key, balance) 替代客户端 PropManager 内存数 | 道具余额服务端权威，广告奖励/商店购买才能成立 |
| A6 | 新增 `hd_configs`(k/v + 生效版本) 与 `hd_items_catalog` | 数值/关卡/道具价格全部远端下发，不发版改平衡、做 AB |
| A7 | 新增 `hd_user_missions`(user_id, mission_key, progress, claim_state) + 任务模板表 | 签到/每日任务/成就的通用结构 |
| A8 | 账号体系：昵称修改、头像、游客→LINE 绑定（防丢号）、账号注销（合规必需） | 商业游戏基本盘 |

## B. 游戏时间 / 疲劳管理（P1）

| # | 任务 | 说明 |
|---|------|------|
| B1 | 结算口径统一：`win / fail / quit` 三种结局都回传时长（当前 quit 直接丢） | 时长统计的前提 |
| B2 | 时长累计改为「会话真实经过时间」（Redis start_time 已具备）并防挂机（心跳/无操作判定） | 现在 score= 前端计时，可被改 |
| B3 | 每日时长/局数上限配置（默认 ∞，供防沉迷或"精力值"玩法复用） | 上线可关，架构先留 |
| B4 | 精力(energy)系统：开局消耗、定时/道具恢复 — 先做成配置项开关 | 留存与付费的核心杠杆之一，属"想好再开" |

## C. 商业化（P1-P2，架构先行）

| # | 任务 | 说明 |
|---|------|------|
| C1 | 通用奖励服务 `POST /api/rewards/grant`（placement + 幂等 nonce + 每日上限），收口三类来源：广告 / 分享邀请 / 运营补偿 | 所有"+1 道具"必须走这唯一入口，防刷只写一处 |
| C2 | `RewardedAdProvider` 抽象（仿 SDKManager）：web 可接激励视频 SDK，LINE 无官方激励视频 → 先接「分享/邀请助力」，接口预留 | LINE 上广告政策必须先查 LINE Ads 准入 |
| C3 | 商店/订单通用层：`hd_orders` + `hd_receipts`（商品模板驱动），支付渠道(web: 无；LINE: LINE Pay/商店) 走适配器 | 渠道未定也先落订单表，避免以后推倒 |
| C4 | 双货币设计：soft（通关/签到产出）+ premium（充值/奖励），明确兑换比与消耗点 | 单货币无法支撑皮肤/道具双重定价 |
| C5 | 内容付费：主题/卡背/头像框（现有 themes 架构天然支持，扩展为商城商品） | 低开发成本高收益点 |

## D. 关卡内容与成长（P2）

| # | 任务 | 说明 |
|---|------|------|
| D1 | 关卡 DSL/编辑器：把 levels.ts 配置化下发（当前只 2 关且写死） | 周更内容的前提，编辑验证器保证可解/难度曲线 |
| D2 | 主线关卡 + 难度曲线 + 3 星评价（时间/无道具等条件） | 现有 rank 按最快时间，扩展为星级制评价体系 |
| D3 | 每日挑战/限时活动关（复用 D1 生成器 + 排行榜新维度） | 老玩家回流钩子 |
| D4 | 成就/称号系统（基于 hd_player_daily + 任务表聚合） | 低成本高留存 |

## E. 排行榜商业化（P2）

| # | 任务 | 说明 |
|---|------|------|
| E1 | 赛季化：`hd_seasons` + 赛季快照表，全国/区域/好友 多维度 + Top100 | 现在只有"每关最快"，无竞争窗口 |
| E2 | 排行写路径：异步队列重算 + Redis 缓存 + 定时快照（结算发奖） | 避免直查大表拖垮 record 写入 |
| E3 | 好友榜：LINE 可用 getFriendship 能力(需朋友 API 审核)，先做邀请码互相关注 | 社交传播是 LINE 场景最大杠杆 |

## F. 埋点 / 分析 / 运营（P1）

| # | 任务 | 说明 |
|---|------|------|
| F1 | 统一埋点：`POST /api/events`（批量、Redis 缓冲异步落库）事件：session_start/level_start/level_end/level_fail/prop_use/ad_start/ad_complete/pay_* | 一切漏斗/留存决策的数据源 |
| F2 | 关键指标看板：D1/D7/D30 留存、单局时长、通关率、付费率、ARPPU | 决定"要不要调难度/改经济" |
| F3 | 崩溃/错误监控（sentry 或自建）与性能指标（首屏耗时、卡顿率） | 商业质量底线 |

## G. 运营后台（P2）

| # | 任务 | 说明 |
|---|------|------|
| G1 | 管理端：用户查询/封禁、道具补偿（走 C1）、配置热更新（A6）、公告/活动开关 | 独立 admin API + 角色权限，与游戏服务隔离 |
| G2 | 补偿与公告能力下发（前端弹公告入口） | 事故处理和运营活动的必备通道 |

## H. 工程 / 发布结构（P0 部分先行）

| # | 任务 | 说明 |
|---|------|------|
| H1 | DB migration 换成 alembic（现 schema.sql 手工），加索引评审 | 加列/加表会成为常态 |
| H2 | 环境拆分 dev/staging/prod + CI（lint/test/build）+ 一键回滚 | 商业发布的基础 |
| H3 | 静态资源全量 CDN + 版本哈希 + 客户端版本校验/强更开关 | 目前图片音频打进包内 |
| H4 | 并发/压测：start/submit/rank 三个热点接口 的容量基准 | 单机 FastAPI + MySQL 的边界要摸清 |
| H5 | 部署形态：uvicorn worker 数、Redis 高可用、MySQL 备份与恢复演练 | 事故 = 丢数据 = 丢信任 |

## I. 合规与安全（上线前必做）

| # | 任务 | 说明 |
|---|------|------|
| I1 | 隐私政策：数据清单（openid/设备/地区/时长/日志）、第三方(广告/LINE)、注销流程页 | LINE 控制台与商店都强制 |
| I2 | 未成年人保护选项（时长上限/支付开关），按目标市场规则适配 | 日本市场需留意青少年保护自律规范 |
| I3 | 服务端权威校验加强：道具使用/奖励领取/通关时长全链路签名 + 限额 | 游客可无限换 uuid，防刷必须在服务端用户维度 |
| I4 | 数据库/接口层审计日志（管理员操作、导出） | 商用合规要求 |

## 建议里程碑

- **M1（1-2 周）**：A1-A5 + B1-B2 + C1（奖励服务收口）+ F1 埋点 + H1/H3
- **M2（2-4 周）**：A6-A8 + B3 + E1-E2 + G1（最小后台）+ I1
- **M3（长期）**：D 内容生成器 + E3 社交 + C3 订单 + F2 看板

> 核心原则：**钱和道具在服务端，奖励入口只有一个，流水只增不改，数值全部远端下发。**

---

# 进度快照（2026-09 · 下次续接从这里开始）

## 已完成

- **M1 全部**：A1-A5（用户画像/每日汇总/钱包流水/道具余额）+ B1-B2（win/fail/quit 统一结算与时长收敛）+ C1（/api/rewards/grant 幂等发放）+ F1（批量埋点 + 前端打点）；含迁移 001
- **M2 全部**：A6 配置中心 + B3 每日限玩（远端配置）+ A8（改名/区域/注销 + 游客→LINE 并入）+ E1-E2（区域排行榜 + Redis 缓存 + my_rank）+ G1 管理后台（用户/封禁/补偿/配置）+ I1 隐私模板；含迁移 002/003
- **M3 部分**：
  - D1 关卡远端化（hd_levels + GET /api/levels + 客户端动态加载/本地回退；种子迁移 005 由 levels.ts 生成）
  - C3 订单层（hd_orders + 商品目录 + mark-paid 发货走钱包账本；单笔 pending 防刷 + 客户端商店页）
  - C4 钱包账本服务（credit/debit，event_id 幂等）
  - F2 后台指标概览（/api/admin/stats/overview 近 N 天序列）
  - G2 公告下发（announcement.text → /api/configs/public → 客户端 📣）
  - D4 成就 UI（任务面板 毎日/今週/実績 Tab）
- **E3 社交**（迁移 006）：邀请码互关（hd_users.invite_code 懒生成 + hd_relations 双向行）+ 好友榜（/api/friends/rank Redis 缓存）+ 分享（?invite= 自动绑定 / LINE shareTargetPicker / Web Share）+ 好友管理与解除 + 注销/并户清理关系
- **F3 错误上报与监控**（迁移 007）：前端全局捕获（window.onerror/unhandledrejection/pagehide keepalive）→ POST /api/errors（限流 60/h）+ 管理端错误列表/确认；服务端 Monitor 中间件（慢请求阈值 + 分钟错误率告警 + 可选 Webhook）+ /api/admin/monitor 概览
- **C3 真实支付回调骨架**：payments.py 渠道适配器（LinePay 凭据校验占位 + 待接 HMAC 注释）+ POST /api/payments/{provider}/callback（验签→resolve_order→mark_paid 同发货路径；未配置返回 501）
- **C5 装扮商店**（迁移 008）：7 套卡面目录（前端已有图片包启用）+ hd_cosmetics/hd_user_cosmetics + gem 账本购买/装备（买即装、同 kind 互斥）；前端商店「テーマ」Tab + 装备后本地缓存生效；主题按装备态预加载（不再纯随机）
- **H1 alembic 迁移体系**：server/alembic + 基线迁移（0001_baseline 等价 schema.sql，老库幂等）；新结构变更一律 alembic，不再新增 sql/migrations 手工文件
- **H3 CDN/版本化**：vite base 支持 VITE_CDN_BASE（哈希产物 + immutable 缓存）+ upload_web.py（OSS 版本目录 + latest.json）+ 强更（app.min_client_ver/app.latest_url → 客户端版本门槛遮罩）
- 远端库已升级至 17 张 hd_* 表（006/007/008 已执行）

## 待办（下次续接，按优先级）

| # | 内容 | 备注 |
|---|------|------|
| 1 | E3 LINE 好友列表 API（需商务审核） | 目前走邀请码互关路径 |
| 2 | F3 接入 sentry 或正式告警通道 | 自建日志 + Webhook + scripts/ops_check.py 已可接 cron |
| 3 | C3 真实验签随凭据启用（HMAC 已实现 + 5 个单元测试；接口层 501 待渠道配置） | 需渠道商务资质 |
| 4 | C5 卡背/头像框（需先有客户端资源与渲染）与主题预览图 | 预览图已完成；kind 结构已支持扩展 |
| 5 | H3 接入 CI（GitHub Actions）跑 deploy_web.sh | 本地一键命令已就绪 |
| 6 | H4 压测执行并记录容量基线 | 脚本 scripts/bench_load.py 已就绪（连联调环境跑） |

## 本轮收尾补充（2026-09-06 第二波）

- C3：LINE Pay HMAC 验签按官方算法落地（Base64(HMAC-SHA256(channelSecret, 签名原文))；
  X-LINE-Authorization 内嵌原文解析），tests/test_payments.py 5 例全过
- C5：商店主题 Tab 加卡面预览图（取各主题前 3 图标）
- H3 补漏：index.html 公共资源改 %BASE_URL%（CDN 构建生效）、UI 图片统一走 assetUrl()；
  新增 scripts/deploy_web.sh 一键发布（build→OSS 上传→可选自动配 app.latest_url）
- F3 运维：scripts/ops_check.py 健康巡检（health/monitor/错误数/待支付订单/活跃），cron 友好退出码
- H4 基准：scripts/bench_load.py（start/submit/rank 三热点，RPS+P50/P95/P99）

## 部署备忘

- 老库按序执行 `server/sql/migrations/001~008_*.sql`（脚本：`python scripts/migrate_remote.py`）
- 新结构变更一律走 alembic（`cd server && python -m alembic upgrade head`；详见 server/alembic/README.md）
- `server/.env` 必配：`ADMIN_TOKEN`；告警/支付/版本变量见 `.env.example`
- 前端自检：`npm run build`；后端自检：`compileall` + 导入 main（openapi 41 个路径）
- 版本发布：`front` 构建注入 `VITE_APP_VERSION` / `VITE_CDN_BASE` → `scripts/oss_upload/upload_web.py --version vX.Y.Z`
