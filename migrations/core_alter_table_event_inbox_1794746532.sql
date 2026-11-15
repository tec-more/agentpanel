-- 后台「事件详情」需要展示每个 handler 的返回值与执行摘要，给 event_inbox 补列。
-- core_ 前缀恒执行、每次启动全量重跑：用 IF NOT EXISTS 保证幂等。
-- 表可能尚未建立（SQL 迁移在 generate_schemas 之前执行），故外层再套一层
-- to_regclass 判断，与 core_alter_table_event_records_*.sql 的处理方式一致。
-- 全新库由 core_create_table_event_inbox_1794741649.sql 直接建出该列。

DO $$
BEGIN
    IF to_regclass('public.event_inbox') IS NOT NULL THEN
        ALTER TABLE event_inbox ADD COLUMN IF NOT EXISTS return_value JSONB;
        ALTER TABLE event_inbox ADD COLUMN IF NOT EXISTS error_detail TEXT;
        ALTER TABLE event_inbox ADD COLUMN IF NOT EXISTS execution_time_ms INT;
    END IF;
END $$;
