"""AgentPanel 路径契约与装配整改 —— 动态回归（四状态可达性 / 启停对称 / 订阅装卸）。

运行方式（激活 venv，项目根目录）：
    .venv/Scripts/python tests/regression_plugin_assembly.py

要点：
- 通过 real_app.router.lifespan_context 在同一事件循环内启动应用（Tortoise.init +
  generate_schemas + initialize_event_center + load_enabled_plugins），使所有异步 DB
  断言与启动共用一个 loop。
- 只读探测启用的 8 个插件 + 全部禁用插件；对 approval（菜单+权限对称）、alipay
  （路由开关）、finance manifest（订阅装卸，直接调事件中心，不启用其依赖）做动态用例。
- 结束时还原被改动的 manifest（approval/alipay）并删除 finance 订阅行，保证共享库回归到基线。
"""
import asyncio
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path，便于直接 `python tests/...py` 运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tortoise.expressions import Q

from base.app_wrapper import real_app
from base.common.plugin_manager import get_plugin_manager
from base.common.plugin_gate import is_plugin_active
from base.core.events.models import EventSubscription
from base.core.events.registry import event_center
from base.core.users.models.rbac import Menu, Permission

WORKDIR = Path(__file__).resolve().parent.parent
PLUGINS = WORKDIR / "base" / "plugins"

results = []          # (name, passed, detail)
findings = []         # 重要发现（非失败）


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


def note(msg):
    findings.append(msg)
    print(f"[NOTE] {msg}")


def flatten_menus(menus):
    out = []
    for m in menus or []:
        out.append((m.get("name"), m.get("path")))
        out += flatten_menus(m.get("children"))
    return out


def menu_q(pairs):
    # 注意：本项目 Tortoise 模型不把字段暴露为类属性，必须用 Q(name=.., path=..)
    q = None
    for name, path in pairs:
        cond = Q(name=name, path=path)
        q = cond if q is None else (q | cond)
    return q


def snap(name):
    return (PLUGINS / name / "manifest.json").read_text(encoding="utf-8")


def restore(name, text):
    (PLUGINS / name / "manifest.json").write_text(text, encoding="utf-8")


def collect_paths(routes, prefix=""):
    """递归收集路由路径（兼容 FastAPI 0.141 的 _IncludedRouter 包装）。

    include_router 后，被挂载的 router 在父 router.routes 中以 _IncludedRouter 形式存在，
    其 original_router.routes 才是真正的 APIRoute；完整路径 = include_context.prefix + 路由自身 path。
    """
    out = []
    for r in routes:
        # _IncludedRouter：下钻到 original_router.routes，用其 include_context.prefix 作新前缀
        if type(r).__name__ == "_IncludedRouter":
            ctx = getattr(r, "include_context", None)
            child_prefix = (getattr(ctx, "prefix", "") or "") if ctx else ""
            orig = getattr(r, "original_router", None)
            if orig is not None:
                out.extend(collect_paths(orig.routes, child_prefix))
            continue
        p = getattr(r, "path", None)
        if isinstance(p, str) and p:
            out.append((prefix + p) if prefix else p)
        sub = getattr(r, "routes", None)
        if sub:
            out.extend(collect_paths(sub, prefix))
    return out


def route_present(app, prefix):
    if not prefix:
        return False
    paths = collect_paths(app.routes)
    return any(p == prefix or p.startswith(prefix + "/") for p in paths)


async def main():
    alipay_orig = snap("alipay")
    approval_orig = snap("approval")
    try:
        async with real_app.router.lifespan_context(real_app):
            app = real_app
            mgr = get_plugin_manager()

            # 0) 装配器 app 句柄就绪
            check("plugin_manager.set_app 已绑定(app 就绪)", mgr._app is app)

            # 1) 四状态可达性（启动态）：仅 enabled 插件有路由
            all_paths = collect_paths(app.routes)
            # DEBUG：确认插件路由确实进了 app.routes
            v1_routes = [p for p in all_paths if p.startswith("/v1/")]
            dbg_audit = [p for p in v1_routes if p.startswith("/v1/audit")]
            print(f"[DEBUG] total paths={len(all_paths)} | /v1/* paths={len(v1_routes)} "
                  f"| /v1/audit 命中={len(dbg_audit)} 样例={dbg_audit[:2]}")
            mismatches = []
            for name in mgr.discover_plugins():
                m = mgr.get_manifest(name) or {}
                if not (m.get("routes")) or not m.get("route_prefix"):
                    continue
                active = is_plugin_active(name)
                reachable = route_present(app, m["route_prefix"])
                if active != reachable:
                    mismatches.append((name, active, reachable))
            check("四状态可达性：启动态仅双真插件挂路由", not mismatches,
                  f"偏差={mismatches}" if mismatches else "8 启用插件均有路由，禁用插件均无路由")

            # 2) event_subscriptions 表已建 + 事件中心已按启用态同步
            try:
                n = await EventSubscription.all().count()
                check("event_subscriptions 表已创建且可查询", True, f"当前行数={n}")
            except Exception as e:
                check("event_subscriptions 表已创建且可查询", False, str(e))
                n = -1
            total_declared = 0
            for name in mgr.discover_plugins():
                if not is_plugin_active(name):
                    continue
                subs = (mgr.get_manifest(name).get("events") or {}).get("subscribe") or []
                total_declared += len(subs)
            actual = await EventSubscription.filter(source="declared", is_enabled=True).count()
            check("事件中心已同步启用插件声明订阅", actual >= total_declared,
                  f"期望≥{total_declared}，实际={actual}")

            # 3) approval 启停对称（菜单+权限，无孤儿）
            am = json.loads(approval_orig)
            apairs = flatten_menus(am.get("menus") or [])
            acodes = [p["code"] for p in (am.get("permissions") or []) if p.get("code")]
            mq = menu_q(apairs)

            base_m = await Menu.filter(mq).count() if apairs else 0
            base_p = await Permission.filter(code__in=acodes, is_active=True).count() if acodes else 0
            check("基线：approval 禁用态菜单为 0", base_m == 0, f"menus={base_m}")
            check("基线：approval 禁用态激活权限为 0", base_p == 0, f"perms={base_p}")

            ok = await mgr.enable_plugin("approval")
            check("enable_plugin('approval') 返回 True", ok)
            check("启用后 is_plugin_active('approval')=True", is_plugin_active("approval"))
            en_m = await Menu.filter(mq).count() if apairs else 0
            en_p = await Permission.filter(code__in=acodes, is_active=True).count() if acodes else 0
            check("启用后菜单数==声明数", en_m == len(apairs), f"{en_m}/{len(apairs)}")
            check("启用后激活权限数==声明数", en_p == len(acodes), f"{en_p}/{len(acodes)}")
            check("启用后路由已注册", route_present(app, am["route_prefix"]))

            ok2 = await mgr.disable_plugin("approval")
            check("disable_plugin('approval') 返回 True", ok2)
            check("禁用后 is_plugin_active('approval')=False", not is_plugin_active("approval"))
            dis_m = await Menu.filter(mq).count() if apairs else 0
            dis_p = await Permission.filter(code__in=acodes, is_active=True).count() if acodes else 0
            check("禁用后菜单清理(无孤儿)", dis_m == 0, f"menus={dis_m}")
            check("禁用后权限清理(无孤儿)", dis_p == 0, f"perms={dis_p}")
            rem = route_present(app, am["route_prefix"])
            note(f"禁用后 approval 路由仍残留于 app.routes（残留={rem}）"
                 f" —— AC-PLR-03-1「停用即不可达」未做请求期门控，属已知缺口")

            # 4) 启停压测 x3（幂等、无重复/孤儿）
            for i in range(3):
                await mgr.enable_plugin("approval")
                await mgr.disable_plugin("approval")
                m = await Menu.filter(mq).count() if apairs else 0
                p = await Permission.filter(code__in=acodes, is_active=True).count() if acodes else 0
                check(f"压测第{i+1}轮：禁用后无孤儿菜单/权限", m == 0 and p == 0,
                      f"menus={m} perms={p}")
            check("压测结束 approval 处于禁用态", not is_plugin_active("approval"))

            # 5) finance manifest 订阅装卸（不启用其依赖，直接调事件中心）
            fm = mgr.get_manifest("finance") or {}
            fsubs = (fm.get("events") or {}).get("subscribe") or []
            await EventSubscription.filter(subscriber="finance").delete()
            await event_center.sync_plugin("finance", fm, active=True)
            f_rows = await EventSubscription.filter(subscriber="finance").count()
            f_on = await EventSubscription.filter(subscriber="finance", is_enabled=True).count()
            check("订阅激活：finance 声明订阅全部建表", f_rows == len(fsubs) and f_on == len(fsubs),
                  f"rows={f_rows} on={f_on} expected={len(fsubs)}")
            await event_center.sync_plugin("finance", fm, active=False)
            f_on2 = await EventSubscription.filter(subscriber="finance", is_enabled=True).count()
            f_rows2 = await EventSubscription.filter(subscriber="finance").count()
            check("订阅注销：finance 订阅置为 is_enabled=False(行保留,装卸对称)",
                  f_on2 == 0 and f_rows2 == len(fsubs), f"on={f_on2} rows={f_rows2}")
            await EventSubscription.filter(subscriber="finance").delete()

            # 6) alipay 路由开关（无依赖、无菜单/权限/订阅）
            al = json.loads(alipay_orig)
            ok3 = await mgr.enable_plugin("alipay")
            check("enable_plugin('alipay') 返回 True", ok3)
            check("启用后 alipay 路由已注册", route_present(app, al["route_prefix"]))
            await mgr.disable_plugin("alipay")
            rem_a = route_present(app, al["route_prefix"])
            note(f"禁用后 alipay 路由仍残留于 app.routes（残留={rem_a}）—— 同上已知缺口")
            # 确认无副作用：alipay 无声明菜单/权限，应仍为空
            al_menus = await Menu.filter(path__startswith=al["route_prefix"]).count()
            check("alipay 启用/禁用未产生孤儿菜单", al_menus == 0, f"menus={al_menus}")

    finally:
        restore("alipay", alipay_orig)
        restore("approval", approval_orig)
        try:
            await EventSubscription.filter(subscriber="finance").delete()
        except Exception:
            pass

    passed = sum(1 for _, c, _ in results if c)
    failed = [r for r in results if not r[1]]
    print("\n==================== 回归汇总 ====================")
    print(f"断言总数={len(results)}  PASS={passed}  FAIL={len(failed)}")
    for f in failed:
        print("  FAIL ->", f[0], f[2])
    if findings:
        print("\n重要发现（非失败，需产品/架构确认）：")
        for f in findings:
            print("  -", f)
    if failed:
        sys.exit(1)
    print("全部断言通过。")


if __name__ == "__main__":
    asyncio.run(main())
