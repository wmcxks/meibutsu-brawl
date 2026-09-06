-- ============================================================
-- 迁移 008：装扮商店（C5）
-- 对已有库执行；全新安装 schema.sql 建表后仍需执行本文件（目录种子）。
-- 目录种子键必须与前端 core/themes.ts 的 CARD_THEMES 名称一致。
-- ============================================================

-- 1. 装扮目录表
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

-- 2. 用户拥有/装备表
CREATE TABLE IF NOT EXISTS hd_user_cosmetics (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    item_key VARCHAR(48) NOT NULL COMMENT '商品键',
    equipped TINYINT(1) DEFAULT 0 COMMENT '0 未装备 / 1 已装备',
    acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '获得时间',
    PRIMARY KEY (user_id, item_key),
    FOREIGN KEY (user_id) REFERENCES hd_users(id),
    FOREIGN KEY (item_key) REFERENCES hd_cosmetics(item_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='名物大乱斗-用户装扮表';

-- 3. 目录种子（图标数量与 front/public/images/game/cards/themes/<name>/ 下文件数一致）
INSERT IGNORE INTO hd_cosmetics
    (item_key, kind, name, price_gem, sort_order, extra, remark) VALUES
    ('irasutoya',  'theme', 'クラシック（いらすとや）', 0,   1, '{"iconCount":30}', '免费默认款'),
    ('animals',    'theme', 'どうぶつ',                 120, 2, '{"iconCount":18}', ''),
    ('fruits',     'theme', 'くだもの',                 120, 3, '{"iconCount":14}', ''),
    ('vegetable',  'theme', 'やさい',                   120, 4, '{"iconCount":14}', ''),
    ('childhood',  'theme', 'こども',                   120, 5, '{"iconCount":14}', ''),
    ('work',       'theme', 'しごと',                   120, 6, '{"iconCount":14}', ''),
    ('beach',      'theme', 'ビーチ',                   120, 7, '{"iconCount":14}', '');
