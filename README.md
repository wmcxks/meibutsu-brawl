# 名物大乱斗（Meibutsu Brawl）

> **中文** | [English](README.en.md)

一款多层卡牌消消乐 H5 游戏：多层堆叠卡牌 + 底部槽位三消、多关卡进阶、道具系统、通关计时、排行榜，以及**关卡转场动画**（方块横扫遮屏）。前端为 **Phaser 4 + Vite + TypeScript** 的现代化 H5 项目，后端为 **FastAPI + SQLAlchemy 2.x（异步）+ MySQL + Redis**。

> 架构目标：一套代码、多端发布（当前支持 Web，预留 LINE LIFF 平台，通过 SDK 适配层切换）。

## 运行演示

<video src="docs/demo.mp4" controls muted preload="metadata" width="360"></video>

（实际运行录屏，点击播放）

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | Vite 8 · TypeScript · Phaser 4（场景/渲染/Tween）· Alpine.js（UI 层）· Tailwind CSS 4 · Web Crypto（签名） |
| 前端 SDK | 适配器模式：`SDKManager` + `WebAdapter`（游客静默登录）/ `LineAdapter`（LINE LIFF） |
| 后端 | FastAPI · SQLAlchemy 2.x（async/asyncmy）· MySQL · redis-py（Upstash TLS）· PyJWT |
| 防刷 | 前端 SHA-256 签名 + 时间戳防重放；后端开局会话（Redis）+ 时序/限频校验 + 作弊日志落库 |

## 项目结构

```
.
├── front/          # H5 前端（Vite + Phaser 4）
│   ├── public/                   # 静态资源（图片/音频/loader.css 加载动画）
│   ├── src/
│   │   ├── main.ts               # 入口：SDK 登录 → Phaser 启动 → Alpine + UI 缩放
│   │   ├── api/request.ts        # fetch 封装：JWT 携带、超时/指数退避重试、签名
│   │   ├── sdk/                  # 跨平台 SDK 适配层（SDKManager / WebAdapter / LineAdapter / ISDKAdapter）
│   │   ├── core/                 # 纯逻辑层（无 Phaser 依赖）
│   │   │   ├── GameEngine.ts     # 引擎门面（组合 Level + Slot）
│   │   │   ├── LevelManager.ts   # 卡牌生成、遮挡判定
│   │   │   ├── SlotManager.ts    # 底部槽位三消
│   │   │   ├── PropManager.ts    # 道具
│   │   │   ├── BlockTransition.ts# 关卡转场动画（Phaser 原生 Tween）
│   │   │   ├── EventBus.ts       # Phaser ↔ Alpine 事件总线
│   │   │   ├── uiScaler.ts       # UI 层与 Phaser FIT 画布对齐
│   │   │   └── levels.ts / themes.ts
│   │   ├── scenes/               # Phaser 场景（BootScene 预加载 / GameScene 主玩法 / MenuScene）
│   │   └── types/                # 共享类型（game.ts 领域类型 / api.ts 通信类型）
│   └── index.html                # 首屏遮罩 + DOM 网格背景 + UI 层
│
├── server/                       # FastAPI 后端
│   ├── main.py                   # 入口：python main.py 直启（0.0.0.0:8089）
│   ├── config.py                 # 配置（MySQL/Redis/JWT/防刷/LINE）
│   ├── app/
│   │   ├── api/                  # 路由（auth.py：游客/LINE 登录；record.py：开局/结算/排行）
│   │   ├── services/             # 业务逻辑（auth / record / anti_cheat）
│   │   ├── models/               # ORM（user / record / cheat_log）
│   │   ├── schemas/              # Pydantic 模型
│   │   ├── core/                 # database.py（MySQL 异步会话）/ redis.py（TLS 连接串组装）
│   │   └── middleware/           # JWT 中间件
│   └── sql/schema.sql            # 建表 SQL（hd_ 前缀，与金毛项目共库隔离）
│
├── scripts/                      # 运维脚本 + 后端虚拟环境 venv/
└── docs/                         # 运行演示视频（demo.mp4）
```

## 快速启动

### 1. 后端（FastAPI）

```bash
# 进入后端目录
cd server

# 准备环境（首次）：使用仓库内已有的虚拟环境 scripts/venv
# 或全新安装：python3 -m venv ../scripts/venv && ../scripts/venv/bin/pip install -r requirements.txt
# 注意：server/venv 为残留空环境，请勿使用

# 配置环境变量：复制 .env.example 为 .env，填写 MySQL / Redis / JWT / 防刷盐值
cp .env.example .env

# 启动（推荐）：读取 config.py，自动绑定 0.0.0.0:8089（局域网可访问），DEBUG 下带热重载
../scripts/venv/bin/python main.py

# 或使用 uvicorn 显式指定
../scripts/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8089 --reload
```

验证：`curl http://127.0.0.1:8089/health` 返回 `{"status":"ok"}`。

**依赖环境**：
- **MySQL**：`hd_` 前缀表（自动建表），库名见 `.env` 的 `MYSQL_DATABASE`
- **Redis**：支持 Upstash（`REDIS_HOST` 含 `.upstash.io` 自动走 TLS），或本地 `localhost:6379`；未配置也可启动（防刷功能降级告警）

### 2. 前端（H5）

```bash
cd front
npm install

# 开发模式：默认 http://localhost:5173（host: true 已开启，局域网设备可访问）
npm run dev

# 生产构建 / 预览
npm run build
npm run preview
```

**前端环境变量**（`.env`，参考 `.env.example`）：

| 变量 | 说明 | 默认 |
|---|---|---|
| `VITE_API_BASE_URL` | 后端地址；不设置时按页面访问来源自动推导（`http://<当前host>:8089`） | 自动 |
| `VITE_TARGET_PLATFORM` | 发布平台：`web`（游客登录）/ `line`（LINE LIFF） | `web` |
| `VITE_LIFF_ID` | LINE LIFF App ID（仅 line 平台需要） | 空 |

### 3. 局域网联调

```bash
# 终端 1（后端，必须绑定 0.0.0.0）
cd server && ../scripts/venv/bin/python main.py

# 终端 2（前端）
cd front && npm run dev
```

手机与电脑同一 Wi-Fi，访问终端打印的 `http://<电脑IP>:5173` 即可（API 自动指向 `<电脑IP>:8089`）。

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/guest-login` | 游客静默登录（`guest_uuid` 换 JWT） |
| POST | `/api/auth/line` | LINE LIFF 登录（id_token 换 JWT，需配置 `LINE_CHANNEL_ID`） |
| POST | `/api/record/start` | 开局：生成会话（Redis 存 start_time/level_id，TTL 1h） |
| POST | `/api/record/submit` | 结算：签名校验 + 会话/时序/限频校验 + 落库 |
| GET | `/api/record/list` | 我的通关记录 |
| GET | `/api/record/rank` | 排行榜（每关最快成绩） |

**防刷链路**：前端对 `level_id + clear_time + timestamp + SALT` 做 SHA-256 签名；后端依次校验时间戳窗口（60s）、会话存在与关卡匹配、`clear_time` 不超理论耗时且不低于最短通关时间（默认 3s）、每分钟结算 ≤3 次，违规记录到 `hd_cheat_logs` 表。

## 游戏流程

首屏加载（CSS 3D 加载动画，遮罩在资源就绪后移除）→ 直接进入游戏 → 开局拉取会话 → 三消闯关（道具：移出/撤回/洗牌/透视）→ 通关触发方块横扫转场自动进入下一关（成绩静默上报，无弹窗）→ 卡槽满失败可复活一次。音效开关右上角一键控制并持久化到 localStorage。
