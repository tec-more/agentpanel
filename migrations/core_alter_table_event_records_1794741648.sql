-- Transactional Outbox：event_records 补投递态字段（幂等，core 前缀恒执行）
-- 背景：发布端改为「业务 + 消息记录同事务落库」，relay 异步投递到 ap.events。
--       原表由 Tortoise generate_schemas(safe=True) 建立，生产 RUN_DB_MIGRATIONS=false
--       时须单独执行本文件；表尚不存在（全新库）时跳过，字段由 generate_schemas 建全。
-- 幂等键必须靠 DB 唯一约束：替代原 Redis 300s 键，使「幂等判定 + 消息落库」同事务。
-- 索引与 ORM Meta 自动生成的索引名不同但语义等价，CREATE ... IF NOT EXISTS 保证可重复执行。

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'event_records'
    ) THEN
        EXECUTE 'ALTER TABLE event_records ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(200)';
        EXECUTE 'ALTER TABLE event_records ADD COLUMN IF NOT EXISTS dispatch_attempts INT NOT NULL DEFAULT 0';
        EXECUTE 'ALTER TABLE event_records ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ';
        EXECUTE 'ALTER TABLE event_records ADD COLUMN IF NOT EXISTS dispatched_at TIMESTAMPTZ';
        EXECUTE 'ALTER TABLE event_records ADD COLUMN IF NOT EXISTS consuming_started_at TIMESTAMPTZ';
        -- 2026-11-15 追加：跨模块串联审计请求/响应的 trace_id
        EXECUTE 'ALTER TABLE event_records ADD COLUMN IF NOT EXISTS trace_id VARCHAR(100)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_event_records_trace_id ON event_records (trace_id) WHERE trace_id IS NOT NULL';
        EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS uq_event_records_idempotency_key ON event_records (idempotency_key) WHERE idempotency_key IS NOT NULL';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_event_records_outbox ON event_records (status, locked_until, published_at)';
    END IF;
END $$;
