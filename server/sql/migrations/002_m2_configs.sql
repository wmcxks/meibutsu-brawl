-- ============================================================
-- 迁移 002：M2 阶段（配置中心 / 账号 / 管理后台）
-- 对已有库执行；全新安装直接跑 schema.sql 即可（本文件仅含新增表）。
-- ============================================================

-- 1. 远端配置表（A6）
CREATE TABLE IF NOT EXISTS hd_configs (
    cfg_key VARCHAR(64) PRIMARY KEY COMMENT '配置键（如 play.daily_max_minutes）',
    value TEXT NOT NULL COMMENT '值（JSON 编码文本）',
    remark VARCHAR(128) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-远端配置表';

-- 2. 初始配置（可留空，代码内 CONFIG_DEFAULTS 兜底）
INSERT IGNORE INTO hd_configs (cfg_key, value, remark) VALUES
    ('play.daily_max_minutes', '0', '每日游戏时长上限（分钟，0=不限）'),
    ('play.daily_max_games',   '0', '每日对局上限（0=不限）');
