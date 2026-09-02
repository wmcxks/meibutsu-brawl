# Meibutsu Brawl（名物大乱斗）

> **English** | [中文文档](README.md)

A multi-layer card matching (消消乐) H5 game: stacked card boards + bottom-slot triple matching, multi-level progression, prop system, clear-time leaderboard, and a **block-sweep level transition animation**. The frontend is a modern **Phaser 4 + Vite + TypeScript** H5 project; the backend is **FastAPI + SQLAlchemy 2.x (async) + MySQL + Redis**.

> Architecture goal: **one codebase, multiple platforms** (Web now; LINE LIFF reserved via the SDK adapter layer).

## Run Demo

<video src="docs/demo.mp4" controls muted preload="metadata" width="360"></video>

(Screen recording of the actual game)

## Table of Contents

- [Run Demo](#run-demo)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [1. Backend (FastAPI)](#1-backend-fastapi)
  - [2. Frontend (H5)](#2-frontend-h5)
  - [3. LAN / Mobile Debugging](#3-lan--mobile-debugging)
- [API Overview](#api-overview)
- [Anti-Cheat Pipeline](#anti-cheat-pipeline)
- [Game Flow](#game-flow)
- [Environment Variables](#environment-variables)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vite 8 · TypeScript · Phaser 4 (scenes / rendering / Tweens) · Alpine.js (UI overlay) · Tailwind CSS 4 · Web Crypto (signing) |
| Frontend SDK | Adapter pattern: `SDKManager` + `WebAdapter` (guest silent login) / `LineAdapter` (LINE LIFF) |
| Backend | FastAPI · SQLAlchemy 2.x (async / asyncmy) · MySQL · redis-py (Upstash TLS) · PyJWT |
| Anti-Cheat | SHA-256 signature + timestamp anti-replay on the client; server-side session (Redis), timing & rate checks, cheat-log persistence |

## Project Structure

```
.
├── front/          # H5 frontend (Vite + Phaser 4)
│   ├── public/                   # Static assets (images / audio / loader.css splash animation)
│   ├── src/
│   │   ├── main.ts               # Entry: SDK login → Phaser boot → Alpine + UI scaling
│   │   ├── api/request.ts        # fetch wrapper: JWT, timeouts / exponential backoff retry, signing
│   │   ├── sdk/                  # Cross-platform SDK layer (SDKManager / WebAdapter / LineAdapter / ISDKAdapter)
│   │   ├── core/                 # Pure logic layer (no Phaser dependency)
│   │   │   ├── GameEngine.ts     # Engine facade (composes Level + Slot)
│   │   │   ├── LevelManager.ts   # Card generation, blocking detection
│   │   │   ├── SlotManager.ts    # Bottom slot triple matching
│   │   │   ├── PropManager.ts    # Props (move-out / undo / shuffle / peek)
│   │   │   ├── BlockTransition.ts# Level transition animation (native Phaser Tween)
│   │   │   ├── EventBus.ts       # Phaser ↔ Alpine event bus
│   │   │   ├── uiScaler.ts       # Aligns the HTML UI layer with the Phaser FIT canvas
│   │   │   └── levels.ts / themes.ts
│   │   ├── scenes/               # Phaser scenes (BootScene preload / GameScene / MenuScene)
│   │   └── types/                # Shared types (game.ts domain / api.ts transport)
│   └── index.html                # Splash mask + DOM grid background + UI overlay
│
├── server/                       # FastAPI backend
│   ├── main.py                   # Entry: python main.py (binds 0.0.0.0:8089)
│   ├── config.py                 # Settings (MySQL / Redis / JWT / anti-cheat / LINE)
│   ├── app/
│   │   ├── api/                  # Routes (auth.py: guest / LINE login; record.py: start / submit / rank)
│   │   ├── services/             # Business logic (auth / record / anti_cheat)
│   │   ├── models/               # ORM (user / record / cheat_log)
│   │   ├── schemas/              # Pydantic models
│   │   ├── core/                 # database.py (async MySQL session) / redis.py (TLS URL assembly)
│   │   └── middleware/           # JWT middleware
│   └── sql/schema.sql            # DDL (hd_ prefix, isolated within the shared MySQL instance)
│
├── scripts/                      # Ops scripts + backend virtualenv venv/
└── docs/                         # Run demo video (demo.mp4)
```

## Quick Start

### 1. Backend (FastAPI)

```bash
cd server

# First time only — use the repo's virtualenv at scripts/venv,
# or create a fresh one: python3 -m venv ../scripts/venv
# then: ../scripts/venv/bin/pip install -r requirements.txt
# Note: server/venv is a leftover empty environment — do not use it.

# Configuration: copy .env.example to .env, fill in MySQL / Redis / JWT / salt
cp .env.example .env

# Start (recommended): reads config.py, binds 0.0.0.0:8089, hot-reload when DEBUG=true
../scripts/venv/bin/python main.py

# Or via uvicorn explicitly
../scripts/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8089 --reload
```

Verify: `curl http://127.0.0.1:8089/health` → `{"status":"ok"}`.

**Dependencies**:
- **MySQL** — tables are auto-created with the `hd_` prefix (see `MYSQL_DATABASE` in `.env`)
- **Redis** — Upstash supported (host containing `.upstash.io` automatically uses TLS), or local `localhost:6379`; the server still boots without it (anti-cheat degrades with a warning)

### 2. Frontend (H5)

```bash
cd front
npm install

# Dev server: http://localhost:5173 (host: true — LAN devices can reach it too)
npm run dev

# Production build / preview
npm run build
npm run preview
```

See [Environment Variables](#environment-variables) for the `VITE_*` settings.

### 3. LAN / Mobile Debugging

```bash
# Terminal 1 (backend — must bind 0.0.0.0)
cd server && ../scripts/venv/bin/python main.py

# Terminal 2 (frontend)
cd front && npm run dev
```

Phone and computer on the same Wi-Fi: open `http://<computer-IP>:5173` shown in the terminal (the API is auto-derived to `http://<computer-IP>:8089`).

## API Overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/guest-login` | Guest silent login (`guest_uuid` → JWT) |
| POST | `/api/auth/line` | LINE LIFF login (id_token → JWT; requires `LINE_CHANNEL_ID`) |
| POST | `/api/record/start` | Start a round: create a session (start_time / level_id in Redis, TTL 1h) |
| POST | `/api/record/submit` | Settle: signature + session / timing / rate-limit checks, then persist |
| GET | `/api/record/list` | My clear records |
| GET | `/api/record/rank` | Leaderboard (best time per level) |

## Anti-Cheat Pipeline

The client signs `level_id + clear_time + timestamp + SALT` with SHA-256. The server then checks, in order:

1. Timestamp window (≤ 60s drift)
2. Session exists and `level_id` matches the start session
3. `clear_time` does not exceed the theoretical elapsed time and is not below the minimum (default 3s)
4. Rate limit: max 3 submissions per minute per user

Violations are written to the `hd_cheat_logs` table for auditing.

## Game Flow

Splash screen (CSS 3D loader, removed once assets are ready) → straight into the game → open a round session → match triples (props: move-out / undo / shuffle / peek) → on win, a **block-sweep transition** auto-advances to the next level (score is reported silently, no dialogs) → on a full slot tray you can revive once. Sound can be toggled with one tap in the top-right corner and persists via localStorage.

## Environment Variables

### Frontend (`front/.env`)

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend URL; when unset it is derived from the page origin (`http://<current-host>:8089`) | auto |
| `VITE_TARGET_PLATFORM` | Target platform: `web` (guest login) / `line` (LINE LIFF) | `web` |
| `VITE_LIFF_ID` | LINE LIFF App ID (line platform only) | empty |

### Backend (`server/.env`)

| Variable | Description |
|---|---|
| `MYSQL_HOST / PORT / USER / PASSWORD / DATABASE` | MySQL connection |
| `REDIS_URL` | Optional full Redis URL (e.g. `rediss://…`) |
| `REDIS_HOST / PORT / USERNAME / PASSWORD / DB` | Or segmented Redis config; `.upstash.io` hosts auto-enable TLS |
| `REDIS_SSL` | Force TLS for other cloud Redis providers |
| `JWT_SECRET / JWT_ALGORITHM / JWT_EXPIRE_HOURS` | JWT settings |
| `ANTI_CHEAT_SALT` | Signing salt — must match the frontend `SIGN_SALT` in `src/api/request.ts` |
| `ANTI_CHEAT_SKEW_SECONDS / MIN_CLEAR_TIME_SECONDS / CLEAR_TIME_TOLERANCE_SECONDS / SUBMIT_RATE_LIMIT_PER_MINUTE / SESSION_TTL_SECONDS` | Anti-cheat tuning |
| `LINE_CHANNEL_ID` | LINE LIFF channel ID (validates id_token `aud`) |
| `SERVER_HOST / SERVER_PORT` | `python main.py` bind settings (default `0.0.0.0:8089`) |
