-- 客户门户一次性 Web 登录票据（dsh 入口免登）
-- 明文票据不入库，只存 SHA-256；60 秒有效、单次消费。

CREATE TABLE IF NOT EXISTS customer_web_ticket (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255),
    redirect_to VARCHAR(512) NOT NULL DEFAULT '/dashboard',
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    request_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_web_ticket_customer ON customer_web_ticket (customer_id);
