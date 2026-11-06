-- 审计配置（audit_config）预置 data_change 模块行
-- 目的：让后台「审计配置」页存在可编辑的 module_name='data_change' 行，
--       使保留天数清理任务（audit_cleanup_task）读取 audit_config.retention_days 时能命中配置。
-- 幂等：module_name 唯一 + NOT EXISTS 防重，可重复执行
-- 表存在性兜底：自定义 SQL 迁移在 Tortoise.generate_schemas(safe=True) 之前执行，
--       全新部署首轮该表可能尚未创建，此处在 information_schema 判定存在后才插入，缺失时静默跳过，
--       待下一次启动（表已存在）时自动补插；openGauss 兼容（未使用 ON CONFLICT / ON DUPLICATE KEY）
-- 字段与 base/plugins/audit/models/audit_log.py::AuditConfig 保持一致：
--       module_name / display_name / enabled / log_create / log_update / log_delete / log_query
--       retention_days / alert_enabled / created_at / updated_at
--       可空列（sensitive_fields / exclude_paths / alert_rules / remark）不显式写入
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'audit_config'
    ) THEN
        INSERT INTO audit_config (
            module_name, display_name, enabled,
            log_create, log_update, log_delete, log_query,
            retention_days, alert_enabled, created_at, updated_at
        )
        SELECT
            'data_change', '数据变更', TRUE,
            TRUE, TRUE, TRUE, FALSE,
            90, FALSE, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM audit_config WHERE module_name = 'data_change'
        );
    END IF;
END $$;
