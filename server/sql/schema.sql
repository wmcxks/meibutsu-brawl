-- 名物大乱斗（羊了个羊玩法）数据库初始化脚本
-- 与「金毛大战波斯猫」项目共用同一个 MySQL 库：
--   本地：golden_vs_persian
--   线上：ai_golden_vs_persian
-- 本项目所有表统一使用 hd_ 前缀（hd = hustle diary），避免与金毛项目的 users/levels/rankings 等表冲突。

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS hd_users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    openid VARCHAR(64) UNIQUE NOT NULL COMMENT '平台用户标识（H5 游客 UUID，guest: 前缀）',
    nickname VARCHAR(128) DEFAULT '' COMMENT '昵称',
    avatar_url VARCHAR(512) DEFAULT '' COMMENT '头像地址',
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
