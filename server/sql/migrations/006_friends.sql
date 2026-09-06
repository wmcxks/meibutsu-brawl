-- ============================================================
-- 迁移 006：好友社交（E3）
-- 对已有库执行；全新安装直接跑 schema.sql 后无需本文件。
-- ============================================================

-- 1. hd_users 增列：邀请码（懒生成；UNIQUE，允许 NULL = 未生成过）
ALTER TABLE hd_users
    ADD COLUMN invite_code VARCHAR(16) NULL COMMENT '邀请码（好友互关，懒生成）' AFTER login_count,
    ADD UNIQUE INDEX uq_invite_code (invite_code);

-- 2. 好友关系表（每对好友存双向两行）
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
