-- T1 变更表：memory 仅补建复合索引（Q5：不动列）
-- 溯源：docs/arch/02 §4.3；索引策略 03 §4：(customer_id, agent_id) / (user_id, agent_id) 记忆召回
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='memory') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_memory_customer_agent ON memory (customer_id, agent_id)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_memory_user_agent ON memory (user_id, agent_id)';
    END IF;
END $$;
