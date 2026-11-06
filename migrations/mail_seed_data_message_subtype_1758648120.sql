-- 消息模块（mail）初始化种子数据
-- 表结构由 Tortoise.generate_schemas(safe=True) 自动创建，本文件仅做幂等种子数据
-- 注意：所有语句用 WHERE NOT EXISTS 保证可重复执行幂等
-- "default" 是 PostgreSQL 保留字，需用双引号包裹

-- ==================== 默认通用子类型 ====================

INSERT INTO mail_message_subtype (name, code, description, model, "default", internal, sequence, is_active, is_system, created_at, updated_at)
SELECT '评论', 'mt_comment', '用户评论/日志', NULL, TRUE, FALSE, 10, TRUE, TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM mail_message_subtype WHERE code = 'mt_comment');

INSERT INTO mail_message_subtype (name, code, description, model, "default", internal, sequence, is_active, is_system, created_at, updated_at)
SELECT '系统通知', 'mt_notification', '系统自动通知', NULL, FALSE, FALSE, 20, TRUE, TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM mail_message_subtype WHERE code = 'mt_notification');

-- ==================== 业务模块子类型 ====================

INSERT INTO mail_message_subtype (name, code, description, model, "default", internal, sequence, is_active, is_system, created_at, updated_at)
SELECT '采购订单已创建', 'purchase.mt_order_created', '采购订单创建时通知', 'purchase_order', FALSE, FALSE, 30, TRUE, TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM mail_message_subtype WHERE code = 'purchase.mt_order_created');

INSERT INTO mail_message_subtype (name, code, description, model, "default", internal, sequence, is_active, is_system, created_at, updated_at)
SELECT '销售订单已创建', 'sales.mt_order_created', '销售订单创建时通知', 'sales_order', FALSE, FALSE, 40, TRUE, TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM mail_message_subtype WHERE code = 'sales.mt_order_created');

-- ==================== 审批实例子类型 ====================

INSERT INTO mail_message_subtype (name, code, description, model, "default", internal, sequence, is_active, is_system, created_at, updated_at)
SELECT '审批已提交', 'approval.mt_instance_submitted', '审批实例提交', 'approval_instance', FALSE, FALSE, 50, TRUE, TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM mail_message_subtype WHERE code = 'approval.mt_instance_submitted');

INSERT INTO mail_message_subtype (name, code, description, model, "default", internal, sequence, is_active, is_system, created_at, updated_at)
SELECT '审批已通过', 'approval.mt_instance_approved', '审批实例通过', 'approval_instance', FALSE, FALSE, 51, TRUE, TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM mail_message_subtype WHERE code = 'approval.mt_instance_approved');

INSERT INTO mail_message_subtype (name, code, description, model, "default", internal, sequence, is_active, is_system, created_at, updated_at)
SELECT '审批已拒绝', 'approval.mt_instance_rejected', '审批实例拒绝', 'approval_instance', FALSE, FALSE, 52, TRUE, TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM mail_message_subtype WHERE code = 'approval.mt_instance_rejected');

-- ==================== 默认事件→消息映射 ====================
-- 用子查询取 subtype_id，避免硬编码 ID

INSERT INTO mail_model_mapping (model, action, subtype_id, condition_field, condition_value, name_template, body_template, is_active, notify_followers, notify_creator, created_at, updated_at)
SELECT 'purchase_order', 'create', s.id, NULL, NULL,
       '采购订单 #{record_id} 已创建', '采购订单 #{record_id} 已创建', TRUE, TRUE, TRUE, NOW(), NOW()
FROM mail_message_subtype s WHERE s.code = 'purchase.mt_order_created'
AND NOT EXISTS (SELECT 1 FROM mail_model_mapping WHERE model='purchase_order' AND action='create' AND condition_field IS NULL);

INSERT INTO mail_model_mapping (model, action, subtype_id, condition_field, condition_value, name_template, body_template, is_active, notify_followers, notify_creator, created_at, updated_at)
SELECT 'sales_order', 'create', s.id, NULL, NULL,
       '销售订单 #{record_id} 已创建', '销售订单 #{record_id} 已创建', TRUE, TRUE, TRUE, NOW(), NOW()
FROM mail_message_subtype s WHERE s.code = 'sales.mt_order_created'
AND NOT EXISTS (SELECT 1 FROM mail_model_mapping WHERE model='sales_order' AND action='create' AND condition_field IS NULL);

INSERT INTO mail_model_mapping (model, action, subtype_id, condition_field, condition_value, name_template, body_template, is_active, notify_followers, notify_creator, created_at, updated_at)
SELECT 'approval_instance', 'create', s.id, NULL, NULL,
       '审批 #{record_id} 已提交', '审批 #{record_id} 已提交', TRUE, FALSE, TRUE, NOW(), NOW()
FROM mail_message_subtype s WHERE s.code = 'approval.mt_instance_submitted'
AND NOT EXISTS (SELECT 1 FROM mail_model_mapping WHERE model='approval_instance' AND action='create' AND condition_field IS NULL);

INSERT INTO mail_model_mapping (model, action, subtype_id, condition_field, condition_value, name_template, body_template, is_active, notify_followers, notify_creator, created_at, updated_at)
SELECT 'approval_instance', 'update', s.id, 'status', 'approved',
       '审批 #{record_id} 已通过', '审批 #{record_id} 已通过', TRUE, TRUE, TRUE, NOW(), NOW()
FROM mail_message_subtype s WHERE s.code = 'approval.mt_instance_approved'
AND NOT EXISTS (SELECT 1 FROM mail_model_mapping WHERE model='approval_instance' AND action='update' AND condition_field='status' AND condition_value='approved');

INSERT INTO mail_model_mapping (model, action, subtype_id, condition_field, condition_value, name_template, body_template, is_active, notify_followers, notify_creator, created_at, updated_at)
SELECT 'approval_instance', 'update', s.id, 'status', 'rejected',
       '审批 #{record_id} 已拒绝', '审批 #{record_id} 已拒绝', TRUE, TRUE, TRUE, NOW(), NOW()
FROM mail_message_subtype s WHERE s.code = 'approval.mt_instance_rejected'
AND NOT EXISTS (SELECT 1 FROM mail_model_mapping WHERE model='approval_instance' AND action='update' AND condition_field='status' AND condition_value='rejected');
