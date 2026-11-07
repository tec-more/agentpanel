-- Harness 网关租约失效字段：续期失败降级时记录失效时间与原因（幂等）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='harness_gateway_lease') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='harness_gateway_lease'
              AND column_name='invalidated_at'
        ) THEN
            EXECUTE 'ALTER TABLE harness_gateway_lease ADD COLUMN invalidated_at TIMESTAMPTZ NULL';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='harness_gateway_lease'
              AND column_name='invalid_reason'
        ) THEN
            EXECUTE 'ALTER TABLE harness_gateway_lease ADD COLUMN invalid_reason VARCHAR(100) NULL';
        END IF;
    END IF;
END $$;
