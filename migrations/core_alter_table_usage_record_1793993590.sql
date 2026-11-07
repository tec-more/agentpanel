-- P3 组织级配额：usage_record 增补成员维度 member_id（只加列与索引，不改旧结构）
-- 语义：owner_type=org 时 member_id 记录组织成员；usr/cus 预留同口径，便于统一按成员拆分
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='usage_record') THEN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='usage_record' AND column_name='member_id') THEN
            EXECUTE 'ALTER TABLE usage_record ADD COLUMN member_id BIGINT';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_usage_record_member') THEN
            EXECUTE 'CREATE INDEX idx_usage_record_member ON usage_record (member_id)';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_usage_record_owner_member_created') THEN
            EXECUTE 'CREATE INDEX idx_usage_record_owner_member_created ON usage_record (owner_type, owner_id, member_id, created_at)';
        END IF;
    END IF;
    -- 配额账户/计划主体类型无需改列（owner_type 已有 3 位，可容纳 org）
END $$;
