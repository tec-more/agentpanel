-- ContentOps M4 规则灰度发布：给 contentops_compliance_rule 增加 status / rollout_percent。
-- openGauss 兼容：information_schema.columns 判列 + EXECUTE 动态 DDL；
-- 每次启动全量重跑，ADD COLUMN IF NOT EXISTS 保证幂等。
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'contentops_compliance_rule'
    ) THEN
        EXECUTE 'ALTER TABLE contentops_compliance_rule ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT ''active''';
        EXECUTE 'ALTER TABLE contentops_compliance_rule ADD COLUMN IF NOT EXISTS rollout_percent INT NOT NULL DEFAULT 100';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_cops_rule_gray ON contentops_compliance_rule (status, rollout_percent)';
    END IF;
END $$;
