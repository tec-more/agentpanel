-- Harness P0：usage_record 增补用量来源/明细/幂等键（只加列与索引，不改旧结构）
-- 幂等键口径：harness:{run_id}:{node_id}:{seq}（旧路径回退 exec:{execution_id}:{node_id}:{seq}）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='usage_record') THEN
        -- 用量来源：provider / gateway / estimated / legacy（不同来源数值不得混算）
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='source') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN source VARCHAR(30) NOT NULL DEFAULT ''provider''';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='idem_key') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN idem_key VARCHAR(180)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='session_ref') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN session_ref VARCHAR(128)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='model') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN model VARCHAR(100)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='provider') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN provider VARCHAR(50)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='cache_read_tokens') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN cache_read_tokens BIGINT NOT NULL DEFAULT 0';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='cache_write_tokens') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN cache_write_tokens BIGINT NOT NULL DEFAULT 0';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='reasoning_tokens') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN reasoning_tokens BIGINT NOT NULL DEFAULT 0';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='currency') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN currency VARCHAR(8) NOT NULL DEFAULT ''CNY''';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='price_snapshot') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN price_snapshot JSONB';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='raw_seq') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN raw_seq BIGINT NOT NULL DEFAULT 0';
        END IF;

        -- 确定性幂等键唯一索引（多次结算不会双计）
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ux_usage_record_idem_key') THEN
            EXECUTE 'CREATE UNIQUE INDEX ux_usage_record_idem_key ON usage_record (idem_key)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_usage_record_source_created') THEN
            EXECUTE 'CREATE INDEX idx_usage_record_source_created ON usage_record (source, created_at)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_usage_record_session_ref') THEN
            EXECUTE 'CREATE INDEX idx_usage_record_session_ref ON usage_record (session_ref)';
        END IF;
    END IF;
END $$;
