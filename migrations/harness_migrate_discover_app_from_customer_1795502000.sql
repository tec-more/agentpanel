-- 应用配置（原「发现应用配置」）从 customer 插件完整迁入 harness（2026-11-26）
--
-- 背景：菜单 /customer/discover-apps 与权限 customer:discover_app 原由 customer
-- manifest 同步，现改由 harness manifest + harness seed SQL 维护。plugin_manager
-- 的菜单/权限同步是「按 name+path / code upsert」，不会清理 manifest 中已移除的
-- 旧项，故需在此显式删除旧行，避免后台出现两个「应用配置」入口。
--
-- 幂等：DELETE ... WHERE 重复执行无副作用；本文件随每次启动全量重跑。
-- 角色授权：本部署角色表为空（超管直连），不涉及角色-权限绑定迁移；若其他
-- 部署存在 role_permission，需在新权限重新授权（超管走 is_superuser 不受影响）。

DELETE FROM menu WHERE path = '/customer/discover-apps';

DELETE FROM permission WHERE code = 'customer:discover_app';
