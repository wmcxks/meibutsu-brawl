-- ============================================================
-- 迁移 007：客户端错误上报（F3）
-- 对已有库执行；全新安装直接跑 schema.sql 后无需本文件。
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
