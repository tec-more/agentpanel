-- 修复：恢复系统核心菜单（仪表盘/系统管理/用户管理/部门管理/角色管理/权限管理/菜单管理/插件管理/系统设置）
-- 原种子数据使用硬编码 ID（52/53/58-63）会在财务插件先建菜单时冲突丢失
-- 本脚本幂等：已有同名同路径菜单则跳过，不存在的则按正确层级关系创建

-- 1. 系统管理（目录，无 component）
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '系统管理', '/system', 'Setting', NULL, NULL, 1, TRUE, TRUE, 'directory', NULL, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE name='系统管理' AND path='/system');

-- 2. 用户管理
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '用户管理', '/users', 'User', 'user/Index', m.id, 1, TRUE, TRUE, 'menu', 'user:list', NOW(), NOW()
FROM menu m WHERE m.name='系统管理' AND m.path='/system'
AND NOT EXISTS (SELECT 1 FROM menu WHERE name='用户管理' AND path='/users');

-- 3. 部门管理
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '部门管理', '/departments', 'OfficeBuilding', 'department/Index', m.id, 2, TRUE, TRUE, 'menu', 'dept:list', NOW(), NOW()
FROM menu m WHERE m.name='系统管理' AND m.path='/system'
AND NOT EXISTS (SELECT 1 FROM menu WHERE name='部门管理' AND path='/departments');

-- 4. 角色管理
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '角色管理', '/roles', 'UserFilled', 'role/Index', m.id, 3, TRUE, TRUE, 'menu', 'role:list', NOW(), NOW()
FROM menu m WHERE m.name='系统管理' AND m.path='/system'
AND NOT EXISTS (SELECT 1 FROM menu WHERE name='角色管理' AND path='/roles');

-- 5. 权限管理
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '权限管理', '/permissions', 'Key', 'permission/Index', m.id, 4, TRUE, TRUE, 'menu', 'permission:list', NOW(), NOW()
FROM menu m WHERE m.name='系统管理' AND m.path='/system'
AND NOT EXISTS (SELECT 1 FROM menu WHERE name='权限管理' AND path='/permissions');

-- 6. 菜单管理
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '菜单管理', '/menus', 'Menu', 'menu/Index', m.id, 5, TRUE, TRUE, 'menu', 'menu:list', NOW(), NOW()
FROM menu m WHERE m.name='系统管理' AND m.path='/system'
AND NOT EXISTS (SELECT 1 FROM menu WHERE name='菜单管理' AND path='/menus');

-- 7. 插件管理
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '插件管理', '/plugins', 'Connection', 'plugin/Index', m.id, 6, TRUE, TRUE, 'menu', NULL, NOW(), NOW()
FROM menu m WHERE m.name='系统管理' AND m.path='/system'
AND NOT EXISTS (SELECT 1 FROM menu WHERE name='插件管理' AND path='/plugins');

-- 8. 仪表盘
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '仪表盘', '/dashboard', 'Odometer', 'dashboard/Index', NULL, 0, TRUE, TRUE, 'menu', NULL, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE name='仪表盘' AND path='/dashboard');

-- 9. 系统设置
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '系统设置', '/system-setting', 'Setting', 'systemSetting/index', m.id, 10, TRUE, TRUE, 'menu', 'system:setting', NOW(), NOW()
FROM menu m WHERE m.name='系统管理' AND m.path='/system'
AND NOT EXISTS (SELECT 1 FROM menu WHERE name='系统设置' AND path='/system-setting');
