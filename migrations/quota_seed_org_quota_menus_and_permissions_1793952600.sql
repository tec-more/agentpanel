-- 组织配额界面 - 菜单与权限种子数据（幂等）

-- 权限（按 code 幂等重建）
DELETE FROM permission WHERE code IN ('quota:org:view', 'quota:org:manage');

INSERT INTO permission (name, code, module, description, is_active) VALUES
('组织配额查看', 'quota:org:view', 'quota', '查看组织配额账户、看板与计量流水', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('组织配额操作', 'quota:org:manage', 'quota', '分配/解绑组织套餐、启用/停用配额账户', true);

-- 菜单（按 path 幂等重建）
DELETE FROM menu WHERE path LIKE '/quota%';
DELETE FROM menu WHERE menu_type = 'button' AND permission IN ('quota:org:manage');

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
VALUES ('配额管理', '/quota', 'Coin', '', NULL, 18, true, 'menu', NULL, true);

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '组织配额', '/quota/organizations', 'OfficeBuilding', 'quota/organizations/Index', id, 1, true, 'menu', 'quota:org:view', true
FROM menu WHERE path = '/quota' AND name = '配额管理';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '计量流水', '/quota/usage', 'Tickets', 'quota/usage/Index', id, 2, true, 'menu', 'quota:org:view', true
FROM menu WHERE path = '/quota' AND name = '配额管理';

-- 按钮级权限点（仅用于角色授权，不在导航显示）
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '分配/调整套餐', NULL, NULL, NULL, id, 1, false, 'button', 'quota:org:manage', true
FROM menu WHERE path = '/quota' AND name = '配额管理';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '解绑套餐', NULL, NULL, NULL, id, 2, false, 'button', 'quota:org:manage', true
FROM menu WHERE path = '/quota' AND name = '配额管理';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '启用/停用账户', NULL, NULL, NULL, id, 3, false, 'button', 'quota:org:manage', true
FROM menu WHERE path = '/quota' AND name = '配额管理';
