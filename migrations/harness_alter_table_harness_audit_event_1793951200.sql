-- Harness P1：审计事件补采集来源与原始事件类型
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='harness_audit_event') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='harness_audit_event' AND column_name='event_source') THEN
            EXECUTE 'ALTER TABLE harness_audit_event ADD COLUMN event_source VARCHAR(20) NOT NULL DEFAULT ''api''';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='harness_audit_event' AND column_name='raw_type') THEN
            EXECUTE 'ALTER TABLE harness_audit_event ADD COLUMN raw_type VARCHAR(100)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_harness_audit_source_type') THEN
            EXECUTE 'CREATE INDEX idx_harness_audit_source_type ON harness_audit_event (event_source, raw_type)';
        END IF;
    END IF;
END $$;
