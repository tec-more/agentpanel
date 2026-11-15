-- Inbox：消费端「一条消息 × 一个 handler」执行凭据（幂等去重，core 前缀恒执行）
-- 字段与 base/common/events/models/event_inbox.py 对齐；SQL 迁移在 generate_schemas
-- 之前执行，CREATE TABLE IF NOT EXISTS 保证随后 generate_schemas(safe=True) 不重建。
-- dedup_key 单列唯一（不依赖 ORM 联合唯一特性），重投时 done 的 handler 直接跳过。

CREATE TABLE IF NOT EXISTS event_inbox (
    id BIGSERIAL PRIMARY KEY,
    dedup_key VARCHAR(300) NOT NULL UNIQUE,
    event_uuid VARCHAR(36) NOT NULL,
    handler_key VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'processing',
    attempts INT NOT NULL DEFAULT 1,
    error_message TEXT,
    error_detail TEXT,
    execution_time_ms INT,
    return_value JSONB,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_inbox_event_uuid ON event_inbox (event_uuid);
CREATE INDEX IF NOT EXISTS idx_event_inbox_event_uuid_status ON event_inbox (event_uuid, status);
CREATE INDEX IF NOT EXISTS idx_event_inbox_created_at ON event_inbox (created_at);
CREATE INDEX IF NOT EXISTS idx_event_inbox_updated_at ON event_inbox (updated_at);
