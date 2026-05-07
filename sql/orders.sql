-- OrderAgent 依赖的团队 schema 片段（完整库见仓库内 schema 文档或协作方提供的 schema.sql）
-- 表：orders + order_addresses（收货地址独立表，is_current 表示当前生效地址）

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    phone         TEXT,
    email         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    product_id    TEXT PRIMARY KEY,
    product_name  TEXT NOT NULL,
    product_price NUMERIC(10, 2) NOT NULL,
    category      TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    order_id            TEXT PRIMARY KEY,
    user_id             TEXT REFERENCES users(user_id),
    product_id          TEXT REFERENCES products(product_id),
    product_name        TEXT NOT NULL,
    product_price       NUMERIC(10, 2) NOT NULL,
    quantity            INT NOT NULL DEFAULT 1,
    total_amount        NUMERIC(10, 2) NOT NULL,
    shipping_fee        NUMERIC(10, 2) DEFAULT 0,
    status              TEXT NOT NULL
                        CHECK (status IN ('待发货','已发货','已完成','已取消')),
    can_modify_address  BOOLEAN DEFAULT TRUE,
    can_cancel          BOOLEAN DEFAULT TRUE,
    tracking_number     TEXT,
    create_time         TIMESTAMPTZ DEFAULT NOW(),
    ship_time           TIMESTAMPTZ,
    receive_time        TIMESTAMPTZ,
    cancel_time         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS order_addresses (
    address_id    SERIAL PRIMARY KEY,
    order_id      TEXT REFERENCES orders(order_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    phone         TEXT NOT NULL,
    province      TEXT NOT NULL,
    city          TEXT NOT NULL,
    district      TEXT NOT NULL,
    detail        TEXT NOT NULL,
    is_current    BOOLEAN DEFAULT TRUE,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_create_time ON orders (create_time DESC);
CREATE INDEX IF NOT EXISTS idx_order_addresses_order_current ON order_addresses (order_id) WHERE is_current = TRUE;
