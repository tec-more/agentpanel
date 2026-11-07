-- Harness P1：会话补 JSONL 路径与网关虚拟 key 归属
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='harness_session') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='harness_session' AND column_name='session_log_path') THEN
            EXECUTE 'ALTER TABLE harness_session ADD COLUMN session_log_path VARCHAR(500)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='harness_session' AND column_name='gateway_key') THEN
            EXECUTE 'ALTER TABLE harness_session ADD COLUMN gateway_key VARCHAR(128)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_harness_session_gateway_key') THEN
            EXECUTE 'CREATE INDEX idx_harness_session_gateway_key ON harness_session (gateway_key)';
        END IF;
    END IF;
END $$;
