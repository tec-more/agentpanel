-- 事件中心订阅表（幂等建表，AC-PLR：事件订阅随插件启停装卸的唯一持久化表）
-- 背景：dev 下由 Tortoise generate_schemas(safe=True) 自动建表，但生产容器
--       RUN_DB_MIGRATIONS=false 时启动期既不跑迁移也不 generate_schemas，
--       若部署流程未单独执行 SQL 迁移，事件中心/插件订阅会因缺表不可用。
-- 本文件由 base/common/database.py 的 _run_sql_migrations() 执行：
--       core 前缀 => MigrationMeta.plugin_name=None => 恒执行（不依赖插件启用态）。
-- 字段/索引与 base/core/events/models/event_subscription.py + packages/common/models/base.py
-- 对齐（已按 dev 库 pg_indexes 实际定义核对，2026-11-12）。
-- 注意：SQL 迁移在 generate_schemas 之前执行，CREATE TABLE IF NOT EXISTS 保证
--       随后 generate_schemas(safe=True) 不会重建或覆盖本表。

CREATE TABLE IF NOT EXISTS event_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    name VARCHAR(120) NOT NULL UNIQUE,
    event_name VARCHAR(100) NOT NULL,
    subscriber VARCHAR(50) NOT NULL,
    handler_ref VARCHAR(300),
    source VARCHAR(20) NOT NULL DEFAULT 'declared',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    max_retries INT NOT NULL DEFAULT 3,
    timeout_ms INT NOT NULL DEFAULT 30000,
    description TEXT,
    extra JSONB NOT NULL
);

-- 与 Tortoise 自动生成的索引名保持一致，避免 dev 下 generate_schemas 重复建索引。
CREATE INDEX IF NOT EXISTS idx_event_subsc_created_bcd576 ON event_subscriptions (created_at);
CREATE INDEX IF NOT EXISTS idx_event_subsc_updated_a134ca ON event_subscriptions (updated_at);
CREATE INDEX IF NOT EXISTS idx_event_subsc_name_35f0d6 ON event_subscriptions (name);
CREATE INDEX IF NOT EXISTS idx_event_subsc_event_n_f65548 ON event_subscriptions (event_name);
CREATE INDEX IF NOT EXISTS idx_event_subsc_subscri_f744bc ON event_subscriptions (subscriber);
CREATE INDEX IF NOT EXISTS idx_event_subsc_source_71f6c0 ON event_subscriptions (source);
CREATE INDEX IF NOT EXISTS idx_event_subsc_is_enab_5c8907 ON event_subscriptions (is_enabled);
