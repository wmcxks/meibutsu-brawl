-- ============================================================
-- 迁移 003：任务体系（A7）
-- 对已有库执行；全新安装直接跑 schema.sql 后仍需执行本文件（种子数据）。
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

CREATE TABLE IF NOT EXISTS hd_user_missions (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    mission_key VARCHAR(48) NOT NULL COMMENT '任务键',
    period VARCHAR(16) NOT NULL COMMENT '任务周期（UTC；daily=YYYY-MM-DD / weekly=YYYY-Www / achievement=all）',
    claimed_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '领取时间',
    PRIMARY KEY (user_id, mission_key, period),
    FOREIGN KEY (user_id) REFERENCES hd_users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-用户任务领取表';

-- 种子任务（文案/数值均可通过管理端改模板后热更新）
INSERT IGNORE INTO hd_mission_templates
    (mission_key, scope, title, target_type, target_value, reward_prop_key, reward_amount, sort_order) VALUES
    ('daily_login_1',      'daily',       'ログインしよう',                 'login_days',    1,  'shuffle',  1, 1),
    ('daily_games_3',      'daily',       '3回プレイしよう',                'games',         3,  'undo',     1, 2),
    ('daily_win_1',        'daily',       '1回クリアしよう',                'wins',          1,  'move_out', 1, 3),
    ('weekly_play_30m',    'weekly',      '今週30分プレイしよう',           'play_minutes', 30,  'move_out', 2, 1),
    ('achieve_games_100',  'achievement', '累計100回プレイ',                'games',       100,  'shuffle',  5, 1),
    ('achieve_wins_50',    'achievement', '累計50回クリア',                 'wins',         50,  'undo',     5, 2);
