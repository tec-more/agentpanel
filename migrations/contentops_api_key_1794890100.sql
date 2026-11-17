-- ContentOps M4 对外 OpenAPI 专属 API Key 表。
-- openGauss 兼容：IF NOT EXISTS / JSONB / 无 to_regclass / 无 ON CONFLICT。
CREATE TABLE IF NOT EXISTS contentops_api_key (
    id BIGSERIAL PRIMARY KEY,
    key_id VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    secret_hash VARCHAR(128) NOT NULL,
    secret_prefix VARCHAR(24) NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    scopes JSONB NOT NULL DEFAULT '[]',
    owner_type VARCHAR(3) NOT NULL DEFAULT 'cus',
    owner_id BIGINT,
    allowed_ips JSONB,
    expires_at TIMESTAMPTZ,
    rate_limit_rpm INT NOT NULL DEFAULT 60,
    rate_window_started TIMESTAMPTZ,
    rate_window_count INT NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_by BIGINT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_apikey_owner ON contentops_api_key (owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_cops_apikey_status ON contentops_api_key (status);
