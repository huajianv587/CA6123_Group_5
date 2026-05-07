-- ============================================================
-- 智能客服 Agent 系统 · Supabase 数据库表结构
-- 对应：OrderAgent / RefundAgent / LogisticsAgent / ComplaintAgent
-- ============================================================

-- ── 1. 用户表 ─────────────────────────────────────────────
CREATE TABLE users (
    user_id       TEXT PRIMARY KEY,                -- 用户唯一ID
    name          TEXT NOT NULL,
    phone         TEXT,
    email         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── 2. 商品表 ─────────────────────────────────────────────
CREATE TABLE products (
    product_id    TEXT PRIMARY KEY,
    product_name  TEXT NOT NULL,
    product_price NUMERIC(10, 2) NOT NULL,
    category      TEXT                             -- 商品类目（用于退款规则判断）
);

-- ── 3. 订单表（OrderAgent / RefundAgent 共用）────────────
CREATE TABLE orders (
    order_id            TEXT PRIMARY KEY,          -- 如 202404160001
    user_id             TEXT REFERENCES users(user_id),
    product_id          TEXT REFERENCES products(product_id),
    product_name        TEXT NOT NULL,             -- 冗余存储，避免联表
    product_price       NUMERIC(10, 2) NOT NULL,
    quantity            INT NOT NULL DEFAULT 1,
    total_amount        NUMERIC(10, 2) NOT NULL,
    shipping_fee        NUMERIC(10, 2) DEFAULT 0,
    status              TEXT NOT NULL              -- 待发货/已发货/已完成/已取消
                        CHECK (status IN ('待发货','已发货','已完成','已取消')),
    can_modify_address  BOOLEAN DEFAULT TRUE,
    can_cancel          BOOLEAN DEFAULT TRUE,
    tracking_number     TEXT,                      -- 关联 logistics 表
    create_time         TIMESTAMPTZ DEFAULT NOW(),
    ship_time           TIMESTAMPTZ,
    receive_time        TIMESTAMPTZ,
    cancel_time         TIMESTAMPTZ
);

-- ── 4. 收货地址表 ─────────────────────────────────────────
CREATE TABLE order_addresses (
    address_id    SERIAL PRIMARY KEY,
    order_id      TEXT REFERENCES orders(order_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    phone         TEXT NOT NULL,
    province      TEXT NOT NULL,
    city          TEXT NOT NULL,
    district      TEXT NOT NULL,
    detail        TEXT NOT NULL,
    is_current    BOOLEAN DEFAULT TRUE,            -- 支持地址变更历史
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── 5. 物流表（LogisticsAgent）────────────────────────────
CREATE TABLE logistics (
    tracking_number     TEXT PRIMARY KEY,          -- 如 SF1234567890
    order_id            TEXT REFERENCES orders(order_id),
    carrier_code        TEXT NOT NULL,             -- SF / JD / YT / ZT / YD
    carrier_name        TEXT NOT NULL,
    status              TEXT NOT NULL,             -- 已揽收/运输中/派送中/已签收
    estimated_delivery  DATE,
    signed_time         TIMESTAMPTZ,
    signed_by           TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── 6. 物流轨迹表（timeline，一对多）─────────────────────
CREATE TABLE logistics_timeline (
    id              SERIAL PRIMARY KEY,
    tracking_number TEXT REFERENCES logistics(tracking_number) ON DELETE CASCADE,
    event_time      TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL,
    detail          TEXT NOT NULL,
    location        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── 7. 退款申请表（RefundAgent）──────────────────────────
CREATE TABLE refund_records (
    refund_id       TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    order_id        TEXT REFERENCES orders(order_id),
    user_id         TEXT REFERENCES users(user_id),
    refund_reason   TEXT NOT NULL,                 -- quality_issue/seven_day/wrong_item 等
    responsibility  TEXT NOT NULL                  -- seller / buyer
                    CHECK (responsibility IN ('seller','buyer')),
    product_amount  NUMERIC(10, 2) NOT NULL,
    shipping_fee    NUMERIC(10, 2) DEFAULT 0,
    total_amount    NUMERIC(10, 2) NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected','completed')),
    rag_sources     TEXT[],                        -- RAG 召回的知识文档 ID
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── 8. 投诉记录表（ComplaintAgent）───────────────────────
CREATE TABLE complaint_records (
    complaint_id        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    session_id          TEXT NOT NULL,
    user_id             TEXT REFERENCES users(user_id),
    content             TEXT NOT NULL,             -- 用户原始投诉内容
    emotion_level       TEXT NOT NULL              -- low / medium / high
                        CHECK (emotion_level IN ('low','medium','high')),
    emotion_score       NUMERIC(5, 1),             -- 加权情绪分
    dominant_emotion    TEXT,                      -- angry / urgent / disappointed 等
    scenario            TEXT,                      -- 命中的场景类型（quality_issue 等）
    status              TEXT NOT NULL DEFAULT 'handled'
                        CHECK (status IN ('handled','escalated')),
    escalate_reason     TEXT,                      -- 升级原因（如有）
    guard_triggered     BOOLEAN DEFAULT FALSE,     -- 是否触发护栏
    guard_rules         TEXT[],                    -- 命中的护栏规则列表
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── 9. 会话表（Orchestrator session）─────────────────────
CREATE TABLE sessions (
    session_id      TEXT PRIMARY KEY,
    user_id         TEXT REFERENCES users(user_id),
    status          TEXT DEFAULT 'active'
                    CHECK (status IN ('active','escalated','closed')),
    intent_sequence TEXT[],                        -- 本会话意图历史
    context         JSONB,                         -- session context 缓存（订单号等）
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── 10. 对话消息表（完整对话记录）────────────────────────
CREATE TABLE messages (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content         TEXT NOT NULL,
    agent           TEXT,                          -- 处理该轮的 Agent 名称
    intent          TEXT,
    emotion_score   NUMERIC(5, 1),
    rag_used        BOOLEAN DEFAULT FALSE,
    rag_sources     TEXT[],
    latency_ms      NUMERIC(8, 1),
    fallback        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 种子数据（对应现有 mock 数据）
-- ============================================================

INSERT INTO users VALUES
    ('user_001', '张三', '138****8888', 'zhangsan@example.com', NOW());

INSERT INTO products VALUES
    ('prod_iphone', 'iPhone 15 Pro Max', 9999.00, '数码'),
    ('prod_airpods', 'AirPods Pro 2',    1899.00, '数码'),
    ('prod_ipad',   'iPad Air 5',        4799.00, '数码'),
    ('prod_macbook','MacBook Pro',       14999.00, '数码');

INSERT INTO orders (order_id, user_id, product_id, product_name, product_price,
                    quantity, total_amount, shipping_fee, status,
                    can_modify_address, can_cancel, tracking_number,
                    create_time, ship_time, receive_time) VALUES
    ('202404160001','user_001','prod_iphone','iPhone 15 Pro Max',9999,
     1,9999,0,'已发货',FALSE,FALSE,'SF1234567890',
     NOW()-INTERVAL'3 days', NOW()-INTERVAL'2 days', NULL),
    ('202404150002','user_001','prod_airpods','AirPods Pro 2',1899,
     2,3798,0,'待发货',TRUE,TRUE,NULL,
     NOW()-INTERVAL'5 hours', NULL, NULL),
    ('202404100003','user_001','prod_ipad','iPad Air 5',4799,
     1,4799,0,'已完成',FALSE,FALSE,'SF0987654321',
     NOW()-INTERVAL'10 days', NOW()-INTERVAL'9 days', NOW()-INTERVAL'6 days'),
    ('202404010004','user_001','prod_macbook','MacBook Pro',14999,
     1,14999,0,'已完成',FALSE,FALSE,NULL,
     NOW()-INTERVAL'20 days', NOW()-INTERVAL'19 days', NOW()-INTERVAL'16 days');

INSERT INTO order_addresses (order_id, name, phone, province, city, district, detail) VALUES
    ('202404160001','张三','138****8888','广东省','深圳市','南山区','科技园南区XX栋XX室'),
    ('202404150002','张三','138****8888','广东省','深圳市','福田区','华强北路XX号XX室'),
    ('202404100003','张三','138****8888','广东省','深圳市','罗湖区','人民南路XX号XX室'),
    ('202404010004','张三','138****8888','广东省','深圳市','南山区','科技园南区XX栋XX室');

INSERT INTO logistics (tracking_number, order_id, carrier_code, carrier_name, status, estimated_delivery) VALUES
    ('SF1234567890','202404160001','SF','顺丰速运','派送中', CURRENT_DATE+1),
    ('SF0987654321','202404100003','SF','顺丰速运','已签收', NULL);

INSERT INTO logistics_timeline (tracking_number, event_time, status, detail, location) VALUES
    ('SF1234567890', NOW()-INTERVAL'2 hours',  '派送中', '快递员正在派送中，请保持电话畅通', '北京市朝阳区'),
    ('SF1234567890', NOW()-INTERVAL'6 hours',  '运输中', '快件已到达【北京朝阳营业点】',      '北京市朝阳区'),
    ('SF1234567890', NOW()-INTERVAL'1 day',    '运输中', '快件已发往【北京朝阳营业点】',      '深圳市'),
    ('SF1234567890', NOW()-INTERVAL'2 days',   '已揽收', '顺丰速运已收取快件',               '深圳市南山区'),
    ('SF0987654321', NOW()-INTERVAL'3 days',   '已签收', '您的快件已签收，签收人：本人',      '深圳市南山区'),
    ('SF0987654321', NOW()-INTERVAL'3 days 2 hours', '派送中', '快递员正在派送中',           '深圳市南山区'),
    ('SF0987654321', NOW()-INTERVAL'4 days',   '运输中', '快件已到达【深圳南山营业点】',      '深圳市南山区'),
    ('SF0987654321', NOW()-INTERVAL'5 days',   '已揽收', '顺丰速运已收取快件',               '上海市');
