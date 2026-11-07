-- Harness P1：usage_record 预留网关归因与用量类别（普通回合/压缩/子代理不得混算）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='usage_record') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='gateway_key') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN gateway_key VARCHAR(128)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='usage_kind') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN usage_kind VARCHAR(20) NOT NULL DEFAULT ''normal''';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_usage_record_gateway_key') THEN
            EXECUTE 'CREATE INDEX idx_usage_record_gateway_key ON usage_record (gateway_key)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_usage_record_kind_source') THEN
            EXECUTE 'CREATE INDEX idx_usage_record_kind_source ON usage_record (usage_kind, source)';
        END IF;
    END IF;
END $$;
