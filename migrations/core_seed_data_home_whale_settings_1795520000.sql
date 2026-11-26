-- dsh Web UI 首页背景鲸鱼动画的后台开关与自定义图片（幂等）
-- 由 base/common/database.py 在启动期执行；客户端 brand store 解析 true/false 与图片回退。

INSERT INTO system_setting ("key", value, name, description, setting_type, is_active, sort, created_at, updated_at)
SELECT 'home_whale_enabled', 'true', '首页鲸鱼动画', 'dsh Web UI 首页背景鲸鱼动画开关；关闭后首页不显示背景装饰', 'boolean', TRUE, 12, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM system_setting WHERE "key" = 'home_whale_enabled');

INSERT INTO system_setting ("key", value, name, description, setting_type, is_active, sort, created_at, updated_at)
SELECT 'home_whale_image', '', '首页背景图片', '替换首页鲸鱼动画的自定义背景图片URL，支持后台上传；留空使用内置鲸鱼动画', 'image', TRUE, 13, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM system_setting WHERE "key" = 'home_whale_image');
