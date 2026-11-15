-- 后台「事件详情」需要展示每个 handler 的返回值与执行摘要，给 event_inbox 补列。
-- core_ 前缀恒执行、每次启动全量重跑：用 ADD COLUMN IF NOT EXISTS 保证幂等。
-- 目标库是 openGauss（不是原生 PostgreSQL）：没有 to_regclass()，必须用
-- information_schema.tables 判表、用 EXECUTE 动态执行 DDL，与
-- core_alter_table_event_records_1794741648.sql 保持同一套兼容写法。
-- 表可能尚未建立（SQL 迁移在 generate_schemas 之前执行），故外层判表；
-- 全新库由 core_create_table_event_inbox_1794741649.sql 直接建出全部列。

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'event_inbox'
    ) THEN
        EXECUTE 'ALTER TABLE event_inbox ADD COLUMN IF NOT EXISTS return_value JSONB';
        EXECUTE 'ALTER TABLE event_inbox ADD COLUMN IF NOT EXISTS error_detail TEXT';
        EXECUTE 'ALTER TABLE event_inbox ADD COLUMN IF NOT EXISTS execution_time_ms INT';
    END IF;
END $$;
