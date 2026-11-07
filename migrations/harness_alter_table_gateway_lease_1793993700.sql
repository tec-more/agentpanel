-- Harness 网关租约：key_prefix 存 "dgw.<lease_id>"（约 31 字符），放宽列长度（幂等）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='harness_gateway_lease') THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='harness_gateway_lease'
              AND column_name='key_prefix' AND character_maximum_length < 64
        ) THEN
            EXECUTE 'ALTER TABLE harness_gateway_lease ALTER COLUMN key_prefix TYPE VARCHAR(64)';
        END IF;
    END IF;
END $$;
