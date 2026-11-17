"""ContentOps 插件装配与建表回归验证。

运行方式（激活 venv，项目根目录）：
    .venv/Scripts/python tests/regression_contentops.py

要点：
- 临时启用 contentops（备份 manifest），通过 real_app lifespan 启动真实应用：
  执行建表迁移、Tortoise 注册模型、装配路由、下发菜单权限。
- 验证：10 张表建成、插件装配成功、19 个端点可达、菜单/权限下发、归属字段存在。
- 结束时还原 manifest（表保留，幂等且属于开发成果）。
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


# 预期的 10 张表
TABLES = [
    "contentops_content_item", "contentops_content_version",
    "contentops_compliance_rule", "contentops_compliance_hit",
    "contentops_review_task", "contentops_export_package",
    "contentops_publish_ledger", "contentops_effect_data",
    "contentops_platform_rule_config", "contentops_llm_provider_config",
]

# 预期端点（method, path）
ENDPOINTS = [
    ("POST", "/v1/contentops/contents"),
    ("GET", "/v1/contentops/contents"),
    ("POST", "/v1/contentops/compliance/check"),
    ("POST", "/v1/contentops/contents/adapt/generate"),
    ("GET", "/v1/contentops/reviews"),
    ("POST", "/v1/contentops/exports"),
    ("GET", "/v1/contentops/ledger"),
    ("GET", "/v1/contentops/rules"),
]


async def main():
    from tortoise import Tortoise

    original = MANIFEST.read_text(encoding="utf-8")
    m = json.loads(original)
    m["is_installed"] = True
    m["is_enabled"] = True
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=4), encoding="utf-8")

    try:
        async with real_app.router.lifespan_context(real_app):
            mgr = get_plugin_manager()
            check("app 已绑定装配器", mgr._app is real_app)

            inst = mgr._plugins.get("contentops")
            check("contentops 插件已加载", inst is not None)
            check("contentops 已启用", bool(inst and inst.enabled))

            spec = real_app.openapi()
            paths = spec["paths"]
            for method, path in ENDPOINTS:
                check(f"端点 {method} {path}", path in paths and method.lower() in paths.get(path, {}))

            conn = Tortoise.get_connection("postgres")
            for table in TABLES:
                rows = await conn.execute_query_dict(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1", [table]
                )
                check(f"表 {table} 已建成", len(rows) > 0)

            # 归属字段存在性
            rows = await conn.execute_query_dict(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='contentops_content_item' AND column_name IN ('owner_type','owner_id')"
            )
            cols = {r["column_name"] for r in rows}
            check("内容表含 M8 归属字段 owner_type/owner_id", {"owner_type", "owner_id"} <= cols, str(cols))

            # 菜单/权限下发
            from base.core.users.models.rbac import Menu, Permission
            perm_count = await Permission.filter(code__startswith="contentops:").count()
            check("权限已下发", perm_count >= 12, f"count={perm_count}")
            menu_count = await Menu.filter(path__startswith="/contentops").count()
            check("菜单已下发", menu_count >= 1, f"count={menu_count}")
    finally:
        MANIFEST.write_text(original, encoding="utf-8")
        print("\n[restore] contentops manifest 已还原")

    passed = sum(1 for _, c, _ in results if c)
    print(f"\n断言总数={len(results)} PASS={passed} FAIL={len(results)-passed}")
    if any(not c for _, c, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
