-- 事件中心后台菜单与权限（幂等）
-- 由 base/common/database.py 在启动期执行；表名 menu / permission 已由 aerich 创建。
-- 约定：菜单 component 必须对应 web/src/views/<component>.vue，path 为裸路径，
-- 前端 stores/menu.js 会自动归一到 /panel/<path>。

INSERT INTO permission (name, code, module, description, is_active, created_at, updated_at)
SELECT '事件中心查看', 'events:admin:view', 'events', '查看事件订阅、发布记录与规则', TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE code = 'events:admin:view');

INSERT INTO permission (name, code, module, description, is_active, created_at, updated_at)
SELECT '事件中心管理', 'events:admin:manage', 'events', '新增/启停订阅、手动发布与重放事件', TRUE, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE code = 'events:admin:manage');

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '事件中心', '/events', 'Bell', NULL, NULL, 20, TRUE, TRUE, 'directory', NULL, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE name = '事件中心' AND path = '/events');

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, is_active, menu_type, permission, created_at, updated_at)
SELECT '订阅与发布', '/events/index', 'Connection', 'events/Index', m.id, 1, TRUE, TRUE, 'menu', 'events:admin:view', NOW(), NOW()
FROM menu m
WHERE m.name = '事件中心' AND m.path = '/events'
  AND NOT EXISTS (SELECT 1 FROM menu WHERE name = '订阅与发布' AND path = '/events/index');
