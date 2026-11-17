"""持久启用 contentops 插件（本地开发态）。

与 regression_contentops.py 的区别：那个脚本临时启用后还原，本脚本让插件保持
manifest 双真 + DB 插件表 enabled，验证装配/菜单/权限/路由全部到位后**不还原**。

运行方式（激活 venv，项目根目录）：
    .venv/Scripts/python tests/enable_contentops.py

注意：只影响本地源码 + 本地连的真库；运行中的容器是旧镜像，需重新 build/copy 才会带上插件代码。
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from base.app_wrapper import real_app
from base.common.plugin_manager import get_plugin_manager

WORKDIR = Path(__file__).resolve().parent.parent
MANIFEST = WORKDIR / "base" / "plugins" / "contentops" / "manifest.json"

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


async def main():
    from tortoise import Tortoise

    # 确保 manifest 双真（幂等）
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    m["is_installed"] = True
    m["is_enabled"] = True
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=4), encoding="utf-8")

    async with real_app.router.lifespan_context(real_app):
        mgr = get_plugin_manager()
        inst = mgr._plugins.get("contentops")
        check("contentops 插件已加载", inst is not None)
        check("contentops 已启用（运行时）", bool(inst and inst.enabled))

        # 同步 DB 插件表：启动期 load_enabled_plugins 只认 manifest 双真 + DB 双真并集，
        # 这里补一条 DB 记录，使后台 /v1/plugins/list 也显示已启用。
        try:
            from base.core.extension.models.plugin import Plugin as PluginModel
            rec, _ = await PluginModel.get_or_create(
                name="contentops",
                defaults={
                    "display_name": m.get("display_name", "内容合规与自适应处理台"),
                    "version": m.get("version", "0.0.2"),
                    "description": m.get("description", ""),
                    "author": m.get("author", ""),
                    "dependencies": m.get("dependencies", []),
                    "is_installed": True,
                    "is_enabled": True,
                },
            )
            rec.is_installed = True
            rec.is_enabled = True
            await rec.save()
            check("DB 插件表已标记 installed+enabled", True)
        except Exception as e:
            check("DB 插件表同步", False, f"{type(e).__name__}: {str(e)[:120]}")

        # 路由装配验证
        spec = real_app.openapi()
        check("聚合路由含 /v1/contentops/contents", "/v1/contentops/contents" in spec["paths"])

        # 门控：is_plugin_active 应返回 True
        from base.common import plugin_gate
        check("plugin_gate 判定 contentops active", plugin_gate.is_plugin_active("contentops"))

        # 菜单/权限落库
        from base.core.users.models.rbac import Menu, Permission
        perm_count = await Permission.filter(code__startswith="contentops:").count()
        menu_count = await Menu.filter(path__startswith="/contentops").count()
        check("权限已下发（≥12）", perm_count >= 12, f"count={perm_count}")
        check("菜单已下发（≥1）", menu_count >= 1, f"count={menu_count}")

        # manifest 持久状态
        m2 = json.loads(MANIFEST.read_text(encoding="utf-8"))
        check("manifest 持久 is_installed+is_enabled", m2["is_installed"] and m2["is_enabled"])

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n断言总数={len(results)} PASS={passed} FAIL={len(results)-passed}")
    if any(not c for _, c, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
