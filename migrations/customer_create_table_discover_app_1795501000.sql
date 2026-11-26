-- 发现应用面板的应用目录（后台配置，CUS 只读下发）
CREATE TABLE IF NOT EXISTS customer_discover_app (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(160) NOT NULL DEFAULT '',
    icon_text VARCHAR(4) NOT NULL DEFAULT '',
    icon_color VARCHAR(16),
    open_mode VARCHAR(16) NOT NULL DEFAULT 'portal',
    target VARCHAR(512) NOT NULL,
    sort INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_discover_app_visible ON customer_discover_app (is_active, sort, id);
