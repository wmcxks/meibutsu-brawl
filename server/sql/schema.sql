-- 名物大乱斗（多层卡牌消消乐）数据库初始化脚本
-- 与「金毛大战波斯猫」项目共用同一个 MySQL 库：
--   本地：golden_vs_persian
--   线上：ai_golden_vs_persian
-- 本项目所有表统一使用 hd_ 前缀（hd = hustle diary），避免与金毛项目的 users/levels/rankings 等表冲突。

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    openid VARCHAR(64) UNIQUE NOT NULL COMMENT '平台用户标识（guest:/line: 前缀命名空间）',
    nickname VARCHAR(128) DEFAULT '' COMMENT '昵称',
    avatar_url VARCHAR(512) DEFAULT '' COMMENT '头像地址',
    platform VARCHAR(16) DEFAULT '' COMMENT '注册平台（web / line）',
    client_ver VARCHAR(32) DEFAULT '' COMMENT '最近登录客户端版本',
    country_code VARCHAR(4) DEFAULT '' COMMENT '国家/地区码（ISO 3166-1 alpha-2）',
    region_code VARCHAR(16) DEFAULT '' COMMENT '区域码（日本都道府県 JIS X 0401，如 jp-13）',
    status SMALLINT DEFAULT 0 COMMENT '账号状态：0 正常 / 1 封禁',
    first_login_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '首次登录时间',
    last_login_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '最近登录时间',
    login_count INT DEFAULT 0 COMMENT '累计登录次数',
    invite_code VARCHAR(16) NULL COMMENT '邀请码（好友互关，懒生成）',
    UNIQUE KEY uq_invite_code (invite_code),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_openid (openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-用户表';

-- ============================================================
-- 2. 通关记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    level_id INT NOT NULL COMMENT '关卡ID',
    clear_time DOUBLE NOT NULL COMMENT '通关时间（秒）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    FOREIGN KEY (user_id) REFERENCES hd_users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_level_id (level_id),
    INDEX idx_level_time (level_id, clear_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-通关记录表';

-- ============================================================
-- 3. 作弊日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_cheat_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    session_id VARCHAR(64) DEFAULT '' COMMENT '开局会话ID',
    level_id INT NOT NULL COMMENT '关卡ID',
    reason VARCHAR(64) NOT NULL COMMENT '作弊原因（level_mismatch / impossible_time / too_fast）',
    detail VARCHAR(512) DEFAULT '' COMMENT '详情（如 clear_time / elapsed）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    FOREIGN KEY (user_id) REFERENCES hd_users(id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-作弊日志表';

-- ============================================================
-- 4. 玩家每日汇总表（A3）
-- ============================================================
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

-- ============================================================
-- 5. 钱包表 + 流水表（A4）
-- ============================================================
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

-- ============================================================
-- 6. 用户道具余额表（A5）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_user_props (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    prop_key VARCHAR(32) NOT NULL COMMENT '道具键（move_out / undo / shuffle / peek）',
    balance INT DEFAULT 0 COMMENT '当前余额',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (user_id, prop_key),
    FOREIGN KEY (user_id) REFERENCES hd_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-用户道具余额表';

-- ============================================================
-- 7. 埋点事件表（F1）
-- ============================================================
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

-- ============================================================
-- 8. 远端配置表（A6）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_configs (
    cfg_key VARCHAR(64) PRIMARY KEY COMMENT '配置键（如 play.daily_max_minutes）',
    value TEXT NOT NULL COMMENT '值（JSON 编码文本）',
    remark VARCHAR(128) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-远端配置表';

-- ============================================================
-- 9. 任务模板表（A7）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_mission_templates (
    mission_key VARCHAR(48) PRIMARY KEY COMMENT '任务键（唯一）',
    scope VARCHAR(16) NOT NULL DEFAULT 'daily' COMMENT '周期：daily / weekly / achievement',
    title VARCHAR(64) DEFAULT '' COMMENT '任务标题（客户端展示文案）',
    target_type VARCHAR(24) NOT NULL COMMENT '进度口径：games / wins / play_minutes / login_days',
    target_value INT NOT NULL COMMENT '目标值',
    reward_prop_key VARCHAR(32) NOT NULL COMMENT '奖励道具键',
    reward_amount INT DEFAULT 1 COMMENT '奖励数量',
    enabled TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    sort_order INT DEFAULT 0 COMMENT '排序',
    remark VARCHAR(128) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-任务模板表';

-- ============================================================
-- 10. 用户任务进度/领取表（A7）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_user_missions (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    mission_key VARCHAR(48) NOT NULL COMMENT '任务键',
    period VARCHAR(16) NOT NULL COMMENT '任务周期（UTC；daily=YYYY-MM-DD / weekly=YYYY-Www / achievement=all）',
    claimed_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '领取时间',
    PRIMARY KEY (user_id, mission_key, period),
    FOREIGN KEY (user_id) REFERENCES hd_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-用户任务领取表';

-- ============================================================
-- 11. 订单表（C3）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no VARCHAR(40) UNIQUE NOT NULL COMMENT '订单号（业务幂等键）',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    sku VARCHAR(48) NOT NULL COMMENT '商品 SKU',
    currency VARCHAR(8) NOT NULL COMMENT '发放币种（gem / coin）',
    amount INT NOT NULL COMMENT '发放数量',
    status VARCHAR(12) DEFAULT 'pending' COMMENT 'pending / paid / cancelled',
    channel VARCHAR(16) DEFAULT 'manual' COMMENT '支付渠道：manual / line_pay / ...',
    provider_receipt VARCHAR(512) DEFAULT '' COMMENT '渠道回执/交易号',
    remark VARCHAR(128) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    paid_at DATETIME DEFAULT NULL COMMENT '支付/发货时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES hd_users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-订单表';

-- ============================================================
-- 12. 远端关卡表（D1）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_levels (
    level_id INT PRIMARY KEY COMMENT '关卡ID（1 起）',
    title VARCHAR(64) DEFAULT '' COMMENT '关卡标题',
    icon_types INT DEFAULT 12 COMMENT '本关使用的图标种类数',
    layout TEXT NOT NULL COMMENT '棋盘布局 JSON（RegionConfig[]）',
    enabled TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    version INT DEFAULT 1 COMMENT '配置版本（每次更新 +1）',
    remark VARCHAR(128) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-远端关卡表';

-- ============================================================
-- 13. 好友关系表（E3）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_relations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '发起方用户ID',
    friend_id BIGINT NOT NULL COMMENT '好友用户ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '结为好友时间',
    UNIQUE KEY uq_rel_pair (user_id, friend_id),
    INDEX idx_friend (friend_id),
    FOREIGN KEY (user_id) REFERENCES hd_users(id),
    FOREIGN KEY (friend_id) REFERENCES hd_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-好友关系表';

-- ============================================================
-- 14. 客户端错误表（F3）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_client_errors (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT DEFAULT -1 COMMENT '用户ID（-1 未登录）',
    platform VARCHAR(16) DEFAULT '' COMMENT '平台（web / line）',
    client_ver VARCHAR(32) DEFAULT '' COMMENT '客户端版本',
    page_url VARCHAR(512) DEFAULT '' COMMENT '页面 URL（去 query）',
    message VARCHAR(512) DEFAULT '' COMMENT '错误摘要',
    stack TEXT NULL COMMENT '错误堆栈',
    extras TEXT NULL COMMENT '附加 JSON',
    client_ts INT DEFAULT 0 COMMENT '客户端秒级时间戳',
    acknowledged TINYINT(1) DEFAULT 0 COMMENT '0 未处理 / 1 已确认',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '接收时间',
    INDEX idx_created (created_at),
    INDEX idx_ack (acknowledged),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-客户端错误表';

-- ============================================================
-- 15. 装扮商店（C5）
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_cosmetics (
    item_key VARCHAR(48) PRIMARY KEY COMMENT '商品键（theme 名 / cardback 名）',
    kind VARCHAR(16) NOT NULL COMMENT '类别：theme / cardback / ...',
    name VARCHAR(64) DEFAULT '' COMMENT '商品名（客户端展示文案）',
    price_gem INT DEFAULT 0 COMMENT '售价（gem；0 = 免费默认款）',
    enabled TINYINT(1) DEFAULT 1 COMMENT '是否上架',
    sort_order INT DEFAULT 0 COMMENT '排序',
    extra TEXT NULL COMMENT '附加 JSON（如 iconCount）',
    remark VARCHAR(128) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-装扮目录表';

CREATE TABLE IF NOT EXISTS hd_user_cosmetics (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    item_key VARCHAR(48) NOT NULL COMMENT '商品键',
    equipped TINYINT(1) DEFAULT 0 COMMENT '0 未装备 / 1 已装备',
    acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '获得时间',
    PRIMARY KEY (user_id, item_key),
    FOREIGN KEY (user_id) REFERENCES hd_users(id),
    FOREIGN KEY (item_key) REFERENCES hd_cosmetics(item_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-用户装扮表';

