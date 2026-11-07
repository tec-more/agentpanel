-- Harness P1：会话日志格式版本以 header.version 为准（未识别时允许为空）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='harness_session') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='harness_session' AND column_name='format_version' AND is_nullable='NO') THEN
            EXECUTE 'ALTER TABLE harness_session ALTER COLUMN format_version DROP NOT NULL';
        END IF;
    END IF;
END $$;
