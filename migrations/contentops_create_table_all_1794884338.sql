-- ContentOps 内容合规与自适应处理台：全表建表迁移
-- 目标库 openGauss（非原生 PG）：禁用 to_regclass / ON CONFLICT，一律 IF NOT EXISTS
-- 归属隔离复用 M8：owner_type VARCHAR(3) + owner_id BIGINT

-- 源内容
CREATE TABLE IF NOT EXISTS contentops_content_item (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    body TEXT NOT NULL,
    summary TEXT,
    media JSONB NOT NULL DEFAULT '[]',
    topics JSONB NOT NULL DEFAULT '[]',
    cover VARCHAR(512),
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    creator_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_item_owner ON contentops_content_item (owner_type, owner_id, status);
CREATE INDEX IF NOT EXISTS idx_cops_item_created ON contentops_content_item (created_at);

-- 平台成品版本
CREATE TABLE IF NOT EXISTS contentops_content_version (
    id BIGSERIAL PRIMARY KEY,
    content_id BIGINT NOT NULL,
    platform VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    is_adapted BOOLEAN NOT NULL DEFAULT FALSE,
    parent_id BIGINT,
    diff JSONB NOT NULL DEFAULT '[]',
    rule_version VARCHAR(64),
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_ver_owner ON contentops_content_version (owner_type, owner_id, content_id);
CREATE INDEX IF NOT EXISTS idx_cops_ver_content_platform ON contentops_content_version (content_id, platform);

-- 合规规则
CREATE TABLE IF NOT EXISTS contentops_compliance_rule (
    id BIGSERIAL PRIMARY KEY,
    layer VARCHAR(8) NOT NULL,
    type VARCHAR(32) NOT NULL DEFAULT 'keyword',
    pattern VARCHAR(1024) NOT NULL,
    risk_level VARCHAR(4) NOT NULL DEFAULT 'P1',
    action VARCHAR(32) NOT NULL DEFAULT 'warn',
    basis TEXT,
    suggestion TEXT,
    category VARCHAR(64),
    version VARCHAR(64) NOT NULL DEFAULT '1',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    source VARCHAR(16) NOT NULL DEFAULT 'opensource',
    platform VARCHAR(32),
    owner_type VARCHAR(3),
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_rule_layer ON contentops_compliance_rule (layer, enabled);
CREATE INDEX IF NOT EXISTS idx_cops_rule_owner ON contentops_compliance_rule (owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_cops_rule_risk ON contentops_compliance_rule (risk_level, enabled);

-- 合规命中
CREATE TABLE IF NOT EXISTS contentops_compliance_hit (
    id BIGSERIAL PRIMARY KEY,
    content_version_id BIGINT NOT NULL,
    rule_id BIGINT,
    matched_text TEXT,
    position INTEGER,
    level VARCHAR(4) NOT NULL DEFAULT 'P2',
    basis TEXT,
    suggestion TEXT,
    confidence DOUBLE PRECISION,
    channel VARCHAR(16) NOT NULL DEFAULT 'text',
    rule_version VARCHAR(64),
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    handled_by BIGINT,
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_hit_owner ON contentops_compliance_hit (owner_type, owner_id, content_version_id);
CREATE INDEX IF NOT EXISTS idx_cops_hit_ver_level ON contentops_compliance_hit (content_version_id, level);

-- 审核任务
CREATE TABLE IF NOT EXISTS contentops_review_task (
    id BIGSERIAL PRIMARY KEY,
    content_version_id BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    reviewer_id BIGINT,
    decision VARCHAR(16),
    reason TEXT,
    hit_count INTEGER NOT NULL DEFAULT 0,
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_review_owner ON contentops_review_task (owner_type, owner_id, status);
CREATE INDEX IF NOT EXISTS idx_cops_review_ver ON contentops_review_task (content_version_id, status);

-- 导出快照
CREATE TABLE IF NOT EXISTS contentops_export_package (
    id BIGSERIAL PRIMARY KEY,
    content_id BIGINT NOT NULL,
    platforms JSONB NOT NULL DEFAULT '[]',
    version_ids JSONB NOT NULL DEFAULT '[]',
    file_keys JSONB NOT NULL DEFAULT '{}',
    rule_version VARCHAR(64),
    expires_at TIMESTAMPTZ,
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    creator_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_export_owner ON contentops_export_package (owner_type, owner_id, content_id);

-- 发布台账
CREATE TABLE IF NOT EXISTS contentops_publish_ledger (
    id BIGSERIAL PRIMARY KEY,
    version_id BIGINT NOT NULL,
    platform VARCHAR(32) NOT NULL,
    planned_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    note TEXT,
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_ledger_owner ON contentops_publish_ledger (owner_type, owner_id, status);
CREATE INDEX IF NOT EXISTS idx_cops_ledger_ver_platform ON contentops_publish_ledger (version_id, platform);

-- 效果数据
CREATE TABLE IF NOT EXISTS contentops_effect_data (
    id BIGSERIAL PRIMARY KEY,
    ledger_id BIGINT NOT NULL,
    views BIGINT NOT NULL DEFAULT 0,
    likes BIGINT NOT NULL DEFAULT 0,
    comments BIGINT NOT NULL DEFAULT 0,
    favorites BIGINT NOT NULL DEFAULT 0,
    source VARCHAR(16) NOT NULL DEFAULT 'manual',
    stat_date DATE,
    owner_type VARCHAR(3) NOT NULL DEFAULT 'usr',
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_effect_owner ON contentops_effect_data (owner_type, owner_id, ledger_id);

-- 平台适配规则配置
CREATE TABLE IF NOT EXISTS contentops_platform_rule_config (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    key VARCHAR(64) NOT NULL,
    value JSONB NOT NULL DEFAULT '{}',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    owner_type VARCHAR(3),
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_platform_rule ON contentops_platform_rule_config (platform, key);
CREATE INDEX IF NOT EXISTS idx_cops_platform_rule_owner ON contentops_platform_rule_config (owner_type, owner_id);

-- LLM 供应商配置
CREATE TABLE IF NOT EXISTS contentops_llm_provider_config (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    model VARCHAR(128) NOT NULL,
    endpoint VARCHAR(512),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    purpose VARCHAR(32) NOT NULL DEFAULT 'rewrite',
    owner_type VARCHAR(3),
    owner_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cops_llm_purpose ON contentops_llm_provider_config (purpose, enabled);
CREATE INDEX IF NOT EXISTS idx_cops_llm_owner ON contentops_llm_provider_config (owner_type, owner_id);
