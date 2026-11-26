-- dsh Web UI 浏览器标题与明暗主题 favicon 的后台设置（幂等）
-- 由 base/common/database.py 在启动期执行；留空回退逻辑在客户端 brand store 中实现。

INSERT INTO system_setting ("key", value, name, description, setting_type, is_active, sort, created_at, updated_at)
SELECT 'browser_title', '', '浏览器标题', 'dsh Web UI 浏览器标签标题，留空使用品牌文字', 'string', TRUE, 9, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM system_setting WHERE "key" = 'browser_title');

INSERT INTO system_setting ("key", value, name, description, setting_type, is_active, sort, created_at, updated_at)
SELECT 'favicon_light', '', '浅色模式图标', 'dsh Web UI 浅色主题 favicon 图片URL，支持后台上传；留空使用品牌Logo', 'image', TRUE, 10, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM system_setting WHERE "key" = 'favicon_light');

INSERT INTO system_setting ("key", value, name, description, setting_type, is_active, sort, created_at, updated_at)
SELECT 'favicon_dark', '', '深色模式图标', 'dsh Web UI 深色主题 favicon 图片URL，支持后台上传；留空使用浅色图标', 'image', TRUE, 11, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM system_setting WHERE "key" = 'favicon_dark');
