-- P1.1 服务间凭据：L3 编排内部 API 认证（additive，仅新增表）
-- 明文密钥不入库，只存 SHA-256；由 L2 启动流程应用本迁移。

CREATE TABLE IF NOT EXISTS service_credential (
    id BIGSERIAL PRIMARY KEY,
    service_id VARCHAR(64) NOT NULL,
    secret_hash VARCHAR(128) NOT NULL,
    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_service_credential_service_id
    ON service_credential (service_id);
