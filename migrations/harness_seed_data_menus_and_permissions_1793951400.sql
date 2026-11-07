-- Harness 管理端 - 菜单与权限种子数据（幂等）

-- 权限（按 code 幂等重建，避免重复插入）
DELETE FROM permission WHERE code IN (
    'harness:client:manage', 'harness:identity:manage', 'harness:run:view',
    'harness:usage:view', 'harness:audit:view', 'harness:policy:manage',
    'harness:price:manage'
);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('Harness 客户端凭据管理', 'harness:client:manage', 'harness', '签发/吊销 Harness 客户端凭据', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('Harness 身份映射管理', 'harness:identity:manage', 'harness', '绑定/禁用外部身份到本地用户', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('Harness 会话与运行查看', 'harness:run:view', 'harness', '查看 Harness 会话、运行与步骤', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('Harness 用量看板', 'harness:usage:view', 'harness', '查看用量汇总与分组看板', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('Harness 审计查看', 'harness:audit:view', 'harness', '查看 Harness 安全审计事件', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('Harness 动作策略管理', 'harness:policy:manage', 'harness', '管理高危动作安全策略', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('Harness 模型价格管理', 'harness:price:manage', 'harness', '管理模型价格版本', true);

-- 菜单（按 path 幂等重建）
DELETE FROM menu WHERE path LIKE '/harness%';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
VALUES ('Harness 管控', '/harness', 'Cpu', '', NULL, 16, true, 'menu', NULL, true);

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '会话管理', '/harness/sessions', 'Connection', 'harness/Session', id, 1, true, 'menu', 'harness:run:view', true
FROM menu WHERE name = 'Harness 管控' AND path = '/harness';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '运行记录', '/harness/runs', 'List', 'harness/Run', id, 2, true, 'menu', 'harness:run:view', true
FROM menu WHERE name = 'Harness 管控' AND path = '/harness';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '用量看板', '/harness/usage', 'Odometer', 'harness/Usage', id, 3, true, 'menu', 'harness:usage:view', true
FROM menu WHERE name = 'Harness 管控' AND path = '/harness';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '审计检索', '/harness/audit', 'Search', 'harness/Audit', id, 4, true, 'menu', 'harness:audit:view', true
FROM menu WHERE name = 'Harness 管控' AND path = '/harness';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '客户端凭据', '/harness/clients', 'Key', 'harness/Client', id, 5, true, 'menu', 'harness:client:manage', true
FROM menu WHERE name = 'Harness 管控' AND path = '/harness';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '策略配置', '/harness/policies', 'Lock', 'harness/Policy', id, 6, true, 'menu', 'harness:policy:manage', true
FROM menu WHERE name = 'Harness 管控' AND path = '/harness';
