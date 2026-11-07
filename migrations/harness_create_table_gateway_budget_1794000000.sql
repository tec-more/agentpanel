-- Harness 网关额度耗尽中断：共享兜底账本与并发计数（幂等）
-- Redis 不可用时的权威事实源；多副本通过行锁串行扣减。

CREATE TABLE IF NOT EXISTS harness_gateway_budget (
    id BIGSERIAL PRIMARY KEY,
    lease_id VARCHAR(64) NOT NULL,
    owner_type VARCHAR(8),
    owner_id BIGINT,
    budget_tokens DOUBLE PRECISION NOT NULL DEFAULT 0,
    used_tokens DOUBLE PRECISION NOT NULL DEFAULT 0,
    reserved_tokens DOUBLE PRECISION NOT NULL DEFAULT 0,
    request_count BIGINT NOT NULL DEFAULT 0,
    rejected_count BIGINT NOT NULL DEFAULT 0,
    truncated_count BIGINT NOT NULL DEFAULT 0,
    over_budget_count BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    last_settled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_harness_gateway_budget_lease_id
    ON harness_gateway_budget (lease_id);
CREATE INDEX IF NOT EXISTS idx_harness_gateway_budget_owner
    ON harness_gateway_budget (owner_type, owner_id);

CREATE TABLE IF NOT EXISTS harness_gateway_concurrency (
    id BIGSERIAL PRIMARY KEY,
    owner_type VARCHAR(8) NOT NULL,
    owner_id BIGINT NOT NULL,
    inflight INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_harness_gateway_concurrency_owner
    ON harness_gateway_concurrency (owner_type, owner_id);
