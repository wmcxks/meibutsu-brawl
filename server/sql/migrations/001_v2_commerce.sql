-- ============================================================
-- 迁移 001：V2 商业版数据模型（对已有库执行，全新安装直接跑 schema.sql）
-- 执行：mysql -u<user> -p <database> < 001_v2_commerce.sql
-- 幂等说明：ALTER 部分仅适用于尚未升级的库；已升级库重复执行会报错，
-- 属预期行为（可用 DROP 重建或忽略 Duplicate column 错误）。
-- ============================================================

-- 1. hd_users 扩展画像字段
ALTER TABLE hd_users
    ADD COLUMN platform VARCHAR(16) DEFAULT '' COMMENT '注册平台（web / line）' AFTER avatar_url,
    ADD COLUMN client_ver VARCHAR(32) DEFAULT '' COMMENT '最近登录客户端版本' AFTER platform,
    ADD COLUMN country_code VARCHAR(4) DEFAULT '' COMMENT '国家/地区码（ISO 3166-1 alpha-2）' AFTER client_ver,
    ADD COLUMN region_code VARCHAR(16) DEFAULT '' COMMENT '区域码（日本都道府県 JIS X 0401，如 jp-13）' AFTER country_code,
    ADD COLUMN status SMALLINT DEFAULT 0 COMMENT '账号状态：0 正常 / 1 封禁' AFTER region_code,
    ADD COLUMN first_login_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '首次登录时间' AFTER status,
    ADD COLUMN last_login_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '最近登录时间' AFTER first_login_at,
    ADD COLUMN login_count INT DEFAULT 0 COMMENT '累计登录次数' AFTER last_login_at;

-- 2. 玩家每日汇总表
CREATE TABLE IF NOT EXISTS hd_player_daily (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    stat_date DATE NOT NULL COMMENT '统计日（UTC）',
    play_seconds DOUBLE DEFAULT 0 COMMENT '当日游戏时长（秒，服务端按会话真实经过时间累计）',
    games INT DEFAULT 0 COMMENT '当日对局数（含失败/中途退出）',
    wins INT DEFAULT 0 COMMENT '当日通关局数',
    ads_watched INT DEFAULT 0 COMMENT '当日观看激励广告次数',
    rewards INT DEFAULT 0 COMMENT '当日获得奖励次数（广告/分享/运营）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '首次创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近更新时间',
    PRIMARY KEY (user_id, stat_date),
    INDEX idx_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-玩家每日汇总表';

-- 3. 钱包表 + 流水表
CREATE TABLE IF NOT EXISTS hd_wallets (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    currency VARCHAR(16) NOT NULL COMMENT '币种：coin / gem',
    balance BIGINT DEFAULT 0 COMMENT '余额',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (user_id, currency),
    FOREIGN KEY (user_id) REFERENCES hd_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-钱包表';

CREATE TABLE IF NOT EXISTS hd_wallet_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    currency VARCHAR(16) NOT NULL COMMENT '币种',
    delta BIGINT NOT NULL COMMENT '变动量（正=收入，负=支出）',
    balance_after BIGINT NOT NULL COMMENT '变动后余额',
    event_type VARCHAR(48) NOT NULL COMMENT '变动类型（reward / purchase / consume / refund）',
    event_id VARCHAR(64) UNIQUE NOT NULL COMMENT '幂等事件ID（同一奖励只生效一次）',
    detail VARCHAR(512) DEFAULT '' COMMENT '详情（placement / 订单号等）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '流水时间',
    FOREIGN KEY (user_id) REFERENCES hd_users(id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-钱包流水表';

-- 4. 用户道具余额表
CREATE TABLE IF NOT EXISTS hd_user_props (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    prop_key VARCHAR(32) NOT NULL COMMENT '道具键（move_out / undo / shuffle / peek）',
    balance INT DEFAULT 0 COMMENT '当前余额',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (user_id, prop_key),
    FOREIGN KEY (user_id) REFERENCES hd_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-用户道具余额表';

-- 5. 埋点事件表
CREATE TABLE IF NOT EXISTS hd_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT DEFAULT -1 COMMENT '用户ID（-1 表示未登录）',
    event VARCHAR(48) NOT NULL COMMENT '事件名（page_load / level_start / level_win / ...）',
    props TEXT DEFAULT NULL COMMENT '事件属性 JSON（level_id / clear_time / outcome 等）',
    client_ts INT DEFAULT 0 COMMENT '客户端秒级时间戳（可选）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '接收时间',
    INDEX idx_user (user_id),
    INDEX idx_event (event),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-埋点事件表';
