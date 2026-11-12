"""控制台 500/401/404 事故回归（2026-11-12）。

复现并锁死三类问题：
  1. 登录时用户密码哈希为旧明文/损坏值 → passlib UnknownHashError → 500。
     现在 verify_password 必须返回 False，让 /v1/auth/login 得到干净的 401。
  2. 启动期 DB 抖动使插件 on_enable 抛异常 → 旧实现整段 abort，
     插件路由永久缺失（/v1/mail/* 与 /v1/crm/* 在进程存活期一直 404）。
     现在 DB 依赖步骤降级不得阻断纯内存路由装配。
  3. 浏览器侧启动链路各接口在带 /api 前缀与合法 token 下必须可达。

运行：.venv/Scripts/python tests/regression_startup_resilience.py
"""
import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from base.app_wrapper import app as browser_app, real_app
from base.common.security import create_access_token, verify_password

WORKDIR = Path(__file__).resolve().parent.parent
PROBE_NAME = "_resilience_probe"
PROBE_DIR = WORKDIR / "base" / "plugins" / PROBE_NAME
ROUTE_PREFIX = "/v1/_resilience"

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


def build_probe():
    if PROBE_DIR.exists():
        shutil.rmtree(PROBE_DIR)
    (PROBE_DIR / "api" / "v1").mkdir(parents=True)
    (PROBE_DIR / "__init__.py").write_text(
        '"""启动韧性回归夹具：on_enable 模拟 DB 抖动。"""\n'
        "async def on_enable(app):\n"
        '    raise RuntimeError("simulated DB outage during startup")\n\n'
        "async def on_disable():\n"
        "    return True\n",
        encoding="utf-8",
    )
    (PROBE_DIR / "api" / "v1" / "ping_router.py").write_text(
        "from fastapi import APIRouter\n"
        "ping_router = APIRouter()\n\n"
        '@ping_router.get("/ping")\n'
        "async def ping():\n"
        '    return {"ok": True}\n',
        encoding="utf-8",
    )
    (PROBE_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "name": PROBE_NAME,
                "display_name": "启动韧性回归夹具",
                "version": "0.0.1",
                "is_installed": True,
                "is_enabled": True,
                "route_prefix": ROUTE_PREFIX,
                "routes": ["api/v1"],
                "models": [],
                "menus": [],
                "permissions": [],
                "dependencies": [],
                "config": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _collect_paths(routes, prefix=""):
    """兼容 FastAPI 新版 _IncludedRouter（路由表并非完全扁平）。"""
    out = []
    for r in routes:
        if type(r).__name__ == "_IncludedRouter":
            ctx = getattr(r, "include_context", None)
            child_prefix = (getattr(ctx, "prefix", "") or "") if ctx else ""
            orig = getattr(r, "original_router", None)
            if orig is not None:
                out.extend(_collect_paths(orig.routes, child_prefix))
            continue
        p = getattr(r, "path", None)
        if isinstance(p, str) and p:
            out.append((prefix + p) if prefix else p)
        sub = getattr(r, "routes", None)
        if sub:
            out.extend(_collect_paths(sub, prefix))
    return out


def route_present(app, prefix):
    return any(
        p == prefix or p.startswith(prefix + "/")
        for p in _collect_paths(app.routes)
    )


async def main():
    # --- 1. 非法哈希不再抛异常 ---
    for bad in ("123456", "", None, "$2b$truncated", "plain-text-password"):
        try:
            check(f"verify_password 对非法哈希返回 False (repr={bad!r})", verify_password("admin", bad) is False)
        except Exception as e:
            check(f"verify_password 对非法哈希返回 False (repr={bad!r})", False, f"抛出 {type(e).__name__}")

    build_probe()
    try:
        async with real_app.router.lifespan_context(real_app):
            from base.common.plugin_manager import get_plugin_manager
            mgr = get_plugin_manager()

            ok = await mgr.enable_plugin(PROBE_NAME)
            check("on_enable 抛异常时 enable_plugin 仍返回 True", ok)
            check("降级插件路由仍被注册", route_present(real_app, ROUTE_PREFIX))
            check("降级步骤已登记（hooks）", PROBE_NAME in mgr._degraded_hooks)

            transport = httpx.ASGITransport(app=real_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                r = await client.get(ROUTE_PREFIX + "/ping")
            check("降级插件接口可达 (GET /v1/_resilience/ping = 200)", r.status_code == 200,
                  f"status={r.status_code} body={r.text[:80]}")
            # 事故中缺失的两个业务插件路由前缀必须都在
            check("mail 路由前缀已装配", route_present(real_app, "/v1/mail"))
            check("crm 路由前缀已装配", route_present(real_app, "/v1/crm"))

            # --- 3. 浏览器启动链路（带 /api 前缀） ---
            from base.core.users.models.users import User
            u = await User.filter(is_active=True).order_by("id").first()
            token = create_access_token(data={"sub": str(u.id), "typ": "usr", "username": u.username})
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            btransport = httpx.ASGITransport(app=browser_app)
            endpoints = [
                "/api/v1/install/status",
                "/api/v1/common/system-config",
                "/api/v1/auth/me",
                "/api/v1/menus/user-menus",
                "/api/v1/mail/notifications/unread-count",
                "/api/v1/mail/notifications/inbox?page=1&page_size=5",
            ]
            async with httpx.AsyncClient(transport=btransport, base_url="http://testserver") as client:
                for path in endpoints:
                    r = await client.get(path, headers=headers)
                    check(f"浏览器路径可达 {path}", r.status_code == 200, f"status={r.status_code}")
    finally:
        try:
            from base.common.plugin_manager import get_plugin_manager
            await get_plugin_manager().disable_plugin(PROBE_NAME)
        except Exception:
            pass
        shutil.rmtree(PROBE_DIR, ignore_errors=True)

    passed = sum(results)
    print(f"\n==================== 启动韧性回归汇总 ====================\n断言总数={len(results)}  PASS={passed}  FAIL={len(results) - passed}")
    if passed != len(results):
        sys.exit(1)
    print("全部断言通过。")


if __name__ == "__main__":
    asyncio.run(main())
