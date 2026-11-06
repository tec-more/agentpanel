-- 消息模块 - 菜单与权限种子数据（幂等）

-- 删除 mail 权限
DELETE FROM permission WHERE module = 'mail';

-- 插入 9 个 mail 权限
INSERT INTO permission (name, code, module, description, is_active) VALUES
('消息查看', 'mail:message:view', 'mail', '查看业务记录的消息线程', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('消息发布', 'mail:message:post', 'mail', '在业务记录上发布评论/消息', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('消息管理', 'mail:message:manage', 'mail', '编辑/删除任意消息', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('关注管理', 'mail:follower:manage', 'mail', '关注/取消关注业务记录', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('通知查看', 'mail:notification:view', 'mail', '查看自己的收件箱和未读数', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('子类型查看', 'mail:subtype:view', 'mail', '查看消息子类型', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('子类型管理', 'mail:subtype:manage', 'mail', '创建/编辑消息子类型', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('事件映射查看', 'mail:mapping:view', 'mail', '查看模型事件→消息映射', true);

INSERT INTO permission (name, code, module, description, is_active) VALUES
('事件映射管理', 'mail:mapping:manage', 'mail', '配置模型事件→消息映射', true);

-- 删除 mail 菜单
DELETE FROM menu WHERE path LIKE '/mail%';

-- 插入消息中心父菜单
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
VALUES ('消息中心', '/mail', 'Bell', '', NULL, 15, true, 'menu', NULL, true);

-- 插入子菜单（使用 INSERT ... SELECT 获取父菜单 ID）
INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '收件箱', '/mail/inbox', 'Message', 'mail/Inbox', id, 1, true, 'menu', 'mail:notification:view', true
FROM menu WHERE name = '消息中心';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '消息子类型', '/mail/subtypes', 'Collection', 'mail/Subtype', id, 2, true, 'menu', 'mail:subtype:view', true
FROM menu WHERE name = '消息中心';

INSERT INTO menu (name, path, icon, component, parent_id, sort, is_visible, menu_type, permission, is_active)
SELECT '事件映射', '/mail/mappings', 'Connection', 'mail/Mapping', id, 3, true, 'menu', 'mail:mapping:view', true
FROM menu WHERE name = '消息中心';
