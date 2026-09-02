-- ============================================================
-- 迁移 004：商店订单（C3）—— 仅新增表；已执行 schema.sql 的库跳过
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
