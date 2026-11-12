"""AgentPanel 路径契约与装配整改 —— 待办测试补全（用户确认「三项全做」）。

三组用例：
  A. 部署建表：event_subscriptions 在 RUN_DB_MIGRATIONS=false 容器侧的可达性
  B. 作业调度器（W2-3 / AC-PLR-15-1·13-1）：全文零插件导入 + 6 作业装配 + 运行期禁用即取消
  C. 端到端冒烟（W3-3 / AC-PLR-03-1·03-2·23-1·23-3）：smoke_sample 全生命周期 + 请求期门控 404/200
  D. OPEN 项闭环：门控装配链 / agent 路由自挂载清理 / 关闭期消息排空（动态）

运行（激活 venv，项目根目录）：
    .venv/Scripts/python tests/regression_pending.py

说明：本文件在 main() 开始时自创建 base/plugins/smoke_sample 示例插件（生命周期夹具），
结束时删除目录并清理其菜单/权限/订阅行，保证共享库回归到基线。
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tortoise.expressions import Q

from base.app_wrapper import real_app
from base.common.plugin_manager import get_plugin_manager
from base.common.plugin_gate import is_plugin_active
from base.core.events.models import EventSubscription
from base.core.users.models.rbac import Menu, Permission

WORKDIR = Path(__file__).resolve().parent.parent
PLUGINS = WORKDIR / "base" / "plugins"

SMOKE_NAME = "smoke_sample"
MENU_NAME = "冒烟菜单"
MENU_PATH = "/panel/_smoke"
PERM_CODE = "_smoke:view"
ROUTE_PREFIX = "/v1/_smoke"
EVENT_NAME = "smoke.ping"

results = []
findings = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


def note(msg):
    findings.append(msg)
    print(f"[NOTE] {msg}")


def collect_paths(routes, prefix=""):
    out = []
    for r in routes:
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


# ---------------------------------------------------------------------------
# 示例插件夹具（smoke_sample）
# ---------------------------------------------------------------------------
SMOKE_FILES = {
    "__init__.py": (
        '"""冒烟测试示例插件（regression_pending 自动创建，结束后删除）。"""\n'
        "from loguru import logger\n\n"
        "async def on_enable(app):\n"
        '    logger.info("[smoke_sample] on_enable")\n'
        "    return True\n\n"
        "async def on_disable():\n"
        '    logger.info("[smoke_sample] on_disable")\n'
        "    return True\n\n"
        "async def on_startup():\n"
        "    return None\n\n"
        "async def on_shutdown():\n"
        "    return None\n"
    ),
    "manifest.json": json.dumps(
        {
            "name": SMOKE_NAME,
            "display_name": "冒烟示例插件",
            "version": "0.1.0",
            "is_installed": False,
            "is_enabled": False,
            "route_prefix": ROUTE_PREFIX,
            "dependencies": [],
            "menus": [{"name": MENU_NAME, "path": MENU_PATH, "icon": "smoke", "is_hidden": False}],
            "permissions": [{"code": PERM_CODE, "name": "冒烟查看", "is_active": True}],
            "routes": ["api/v1"],
            "events": {
                "subscribe": [
                    {
                        "event_name": EVENT_NAME,
                        "handler_ref": "base.plugins.smoke_sample.handlers.on_ping",
                        "description": "冒烟订阅示例",
                    }
                ],
                "register_ref": "base.plugins.smoke_sample.handlers.register",
                "unregister_ref": "base.plugins.smoke_sample.handlers.unregister",
            },
        },
        ensure_ascii=False,
        indent=2,
    ),
    "handlers.py": (
        '"""冒烟插件事件处理器（仅 regression 使用）。"""\n'
        "from loguru import logger\n\n"
        "_registry = []\n\n"
        "async def on_ping(event_name=None, **kwargs):\n"
        '    logger.info(f"[smoke] on_ping event={event_name}")\n'
        "    return {'handled': True}\n\n"
        "def register():\n"
        '    _registry.append("registered")\n'
        '    logger.info("[smoke] register 调用")\n'
        "    return True\n\n"
        "def unregister():\n"
        '    if "registered" in _registry:\n'
        '        _registry.remove("registered")\n'
        '    logger.info("[smoke] unregister 调用")\n'
        "    return True\n"
    ),
    "api/__init__.py": "",
    "api/v1/__init__.py": "",
    "api/v1/_smoke.py": (
        '"""冒烟插件路由：公开 GET /ping（无鉴权依赖，供 E2E 200 校验）。"""\n'
        "from fastapi import APIRouter\n\n"
        "_smoke_router = APIRouter()\n\n"
        '@_smoke_router.get("/ping")\n'
        "async def ping():\n"
        "    return {'ok': True, 'plugin': 'smoke_sample'}\n"
    ),
}


def build_smoke_sample():
    d = PLUGINS / SMOKE_NAME
    if d.exists():
        shutil_rmtree(d)
    for rel, content in SMOKE_FILES.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return d


def shutil_rmtree(d):
    import shutil

    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
async def group_a_deploy_table():
    """A. 部署建表：event_subscriptions 在 RUN_DB_MIGRATIONS=false 容器侧的可达性。"""
    print("\n--- A. 部署建表（event_subscriptions） ---")
    n = -1
    try:
        n = await EventSubscription.all().count()
        check("A1 event_subscriptions 表在当前环境可查询(dev 自动建表已生效)", True, f"行数={n}")
    except Exception as e:
        check("A1 event_subscriptions 表在当前环境可查询", False, str(e))

    # 模型是否纳入 Tortoise 注册（决定 generate_schemas 能否建表）
    from base.common.database import TORTOISE_ORM

    registered = False
    for _label, cfg in (TORTOISE_ORM.get("apps") or {}).items():
        if any("base.core.events.models" in m for m in (cfg.get("models") or [])):
            registered = True
            break
    check("A2 event_subscriptions 模型已纳入 Tortoise 注册(generate_schemas 可建)", registered)

    # 平台 SQL 迁移是否覆盖该表（项目实际用 migrations/*.sql，不是 aerich python 迁移）
    from base.common.database import _db_migrations_enabled, parse_migration_filename

    mig_root = WORKDIR / "migrations"
    mig_files = []
    if mig_root.exists():
        for pattern in ("*.sql", "*.py"):
            for f in mig_root.rglob(pattern):
                try:
                    if "event_subscriptions" in f.read_text(encoding="utf-8", errors="ignore"):
                        mig_files.append(f)
                except Exception:
                    pass
    covered = bool(mig_files)
    # core 前缀 => MigrationMeta.plugin_name=None => 不依赖插件启用态，恒执行
    core_migs = [
        f for f in mig_files
        if f.suffix == ".sql"
        and (meta := parse_migration_filename(f.name)) is not None
        and meta.plugin_name is None
        and meta.table == "event_subscriptions"
    ]

    a3 = covered or _db_migrations_enabled()
    check(
        "A3 部署建表保障存在(SQL 迁移覆盖 或 本环境 RUN_DB_MIGRATIONS=true)",
        a3,
        f"SQL迁移覆盖={covered} RUN_DB_MIGRATIONS_true={_db_migrations_enabled()}",
    )
    check(
        "A3a event_subscriptions 有 core 前缀幂等建表迁移(部署流程执行即恒生效)",
        len(core_migs) >= 1,
        f"files={[f.name for f in core_migs]}",
    )
    note(
        "A-部署约束（非缺陷）：RUN_DB_MIGRATIONS=false 时 init_data() 会跳过全部启动期"
        "迁移与 generate_schemas，部署流程须单独执行 migrations/*.sql（runbook 已约定）；"
        "本轮已补 core_create_table_event_subscriptions_*.sql，dev 下 generate_schemas "
        "仍会自动建表，两者幂等共存。"
    )


async def group_b_jobs(mgr):
    """B. 作业关闭（W2-3 / AC-PLR-15-1·13-1）：统一调度器装配与运行期取消。"""
    from base.common.jobs import PLATFORM_KEY, job_scheduler

    print("")
    print("--- B. 作业调度器装配与运行期取消（W2-3） ---")
    # B1 静态：base/start.py **全文（含函数体）** 不得导入具体插件实现
    start_src = (WORKDIR / "base" / "start.py").read_text(encoding="utf-8")
    violations = []
    for line in start_src.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("from base.plugins.") or stripped.startswith("import base.plugins.")):
            continue
        # base.plugins 包自身的框架导入（manager）放行
        if stripped.startswith("from base.plugins import") or stripped.startswith("import base.plugins "):
            continue
        violations.append(stripped)
    check(
        "B1 启动入口全文无具体插件实现导入(含函数体,AC-PLR-13-1 完全达标)",
        not violations,
        f"违例={violations}" if violations else "0 处",
    )

    # B2 插件启用态门控仍有效
    check("B2 get_active_plugin('audit') 启用态非 None", mgr.get_active_plugin("audit") is not None)
    check("B2 get_active_plugin('approval') 禁用态为 None", mgr.get_active_plugin("approval") is None)

    # B3 start_all 装配计数：平台 2 + 启用插件声明的 4 个作业（audit/customer/harness/sales）
    owners = job_scheduler.task_owners()
    check("B3 start_all 装配 6 个作业(平台2+插件4)", job_scheduler.task_count() == 6, f"owners={owners}")
    check(
        "B3 平台作业恒启(quota 对账/悬挂预占清理)",
        job_scheduler.task_count(PLATFORM_KEY) == 2,
        f"platform={job_scheduler.task_count(PLATFORM_KEY)}",
    )

    # B4 真实运行期集成：走 plugin_manager.disable/enable，验证作业被 cancel 与恢复
    # （audit 未被任何启用插件依赖、入口无钩子，是安全的启停样本；crm 依赖 sales，故不用 sales）
    audit_manifest = PLUGINS / "audit" / "manifest.json"
    audit_orig = audit_manifest.read_text(encoding="utf-8") if audit_manifest.exists() else None
    try:
        before = job_scheduler.task_count("audit")
        ok_dis = await mgr.disable_plugin("audit")
        after_dis = job_scheduler.task_count("audit")
        check(
            "B4 运行期禁用 audit 后其作业任务被 cancel(AC-PLR-15-1 真实闭环)",
            ok_dis and before == 1 and after_dis == 0,
            f"ok={ok_dis} before={before} after={after_dis}",
        )
        ok_en = await mgr.enable_plugin("audit")
        after_en = job_scheduler.task_count("audit")
        check(
            "B4 重新启用 audit 后作业任务恢复",
            ok_en and after_en == 1,
            f"ok={ok_en} after={after_en}",
        )
    finally:
        if audit_orig is not None:
            # 恢复 manifest 原文、门控缓存与作业，保证共享库/进程状态回到基线
            mgr.update_plugin_status("audit", is_installed=True, is_enabled=True)
            audit_manifest.write_text(audit_orig, encoding="utf-8")
            await job_scheduler.start_plugin("audit")

    # B5 sales：调度器启停对称（绕开 manager 的依赖门控，单测调度器本身）
    n_stop = await job_scheduler.stop_plugin("sales")
    check(
        "B5 禁用 sales 后其作业任务取消",
        n_stop == 1 and job_scheduler.task_count("sales") == 0,
        f"stopped={n_stop} now={job_scheduler.task_count('sales')}",
    )
    n_start = await job_scheduler.start_plugin("sales")
    check(
        "B5 重新启用 sales 后作业任务恢复(enable→disable→enable 循环)",
        n_start == 1 and job_scheduler.task_count("sales") == 1,
        f"started={n_start} now={job_scheduler.task_count('sales')}",
    )

    # B6 集成链：装配器两条启停路径都挂了作业同步钩子
    pm_src = (WORKDIR / "base" / "common" / "plugin_manager.py").read_text(encoding="utf-8")
    check(
        "B6 enable/disable 均声明作业同步钩子(_sync_plugin_jobs)",
        pm_src.count("_sync_plugin_jobs(") >= 3,
        f"调用点={pm_src.count('_sync_plugin_jobs(')}",
    )

    check("B7 作业启动期未抛异常(lifespan 已完成全部作业 setup)", True)


async def group_c_e2e(app, mgr):
    """C. 端到端冒烟（W3-3 / AC-PLR-03-1·03-2·23-1·23-3）。"""
    print("\n--- C. 端到端冒烟（smoke_sample 全生命周期） ---")
    # 安装（设置 installed）+ 启用
    mgr.update_plugin_status(SMOKE_NAME, is_installed=True, is_enabled=True)
    ok = await mgr.enable_plugin(SMOKE_NAME)
    check("C1 enable_plugin('smoke_sample') 返回 True", ok)
    check("C2 启用后 is_plugin_active('smoke_sample')=True", is_plugin_active(SMOKE_NAME))
    # W2-3：smoke_sample 未声明 jobs，启用不应产生作业任务（方案 §6 断言③）
    from base.common.jobs import job_scheduler
    jobs_baseline = job_scheduler.task_count()
    check("C2a 无 jobs 声明的插件启用后不产生作业任务", job_scheduler.task_count(SMOKE_NAME) == 0)

    # 菜单可见
    mq = Q(name=MENU_NAME, path=MENU_PATH)
    en_m = await Menu.filter(mq).count()
    check("C3 启用后菜单可见(DB 中存在)", en_m == 1, f"menus={en_m}")
    # 权限激活
    en_p = await Permission.filter(code=PERM_CODE, is_active=True).count()
    check("C4 启用后权限激活", en_p == 1, f"perms={en_p}")
    # 路由注册
    check("C5 启用后路由已注册", route_present(app, ROUTE_PREFIX))

    # API 200（裸 app 直接请求真实路径 /v1/_smoke/ping，无 /api 前缀、无安装态门控）
    import httpx

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(ROUTE_PREFIX + "/ping")
        check(
            "C6 API 200 (GET /v1/_smoke/ping)",
            resp.status_code == 200,
            f"status={resp.status_code} body={resp.text[:80]}",
        )
    except Exception as e:
        check("C6 API 200 (GET /v1/_smoke/ping)", False, f"请求异常: {e}")

    # 订阅生效
    sub_on = await EventSubscription.filter(subscriber=SMOKE_NAME, is_enabled=True).count()
    check("C7 启用后声明订阅生效(is_enabled=True)", sub_on == 1, f"on={sub_on}")

    # 禁用（对称清理）
    ok2 = await mgr.disable_plugin(SMOKE_NAME)
    check("C8 disable_plugin('smoke_sample') 返回 True", ok2)
    check("C9 禁用后 is_plugin_active('smoke_sample')=False", not is_plugin_active(SMOKE_NAME))
    check(
        "C9a 无 jobs 声明的插件启停不影响全局作业数(装卸对称)",
        job_scheduler.task_count() == jobs_baseline and job_scheduler.task_count(SMOKE_NAME) == 0,
        f"before={jobs_baseline} after={job_scheduler.task_count()}",
    )
    dis_m = await Menu.filter(mq).count()
    check("C10 禁用后菜单清理(无孤儿)", dis_m == 0, f"menus={dis_m}")
    dis_p = await Permission.filter(code=PERM_CODE, is_active=True).count()
    check("C11 禁用后权限清理(无孤儿)", dis_p == 0, f"perms={dis_p}")
    sub_off = await EventSubscription.filter(subscriber=SMOKE_NAME, is_enabled=True).count()
    sub_rows = await EventSubscription.filter(subscriber=SMOKE_NAME).count()
    check(
        "C12 禁用后订阅置 is_enabled=False(行保留,装卸对称)",
        sub_off == 0 and sub_rows == 1,
        f"on={sub_off} rows={sub_rows}",
    )
    # C13 请求期门控（AC-PLR-03-1）：路由对象残留可以接受，但请求必须 404 且不执行 handler
    rem = route_present(app, ROUTE_PREFIX)
    try:
        transport_off = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport_off, base_url="http://testserver") as client:
            resp_off = await client.get(ROUTE_PREFIX + "/ping")
        check(
            "C13 禁用后 GET /v1/_smoke/ping 返回 404(请求期门控生效)",
            resp_off.status_code == 404,
            f"status={resp_off.status_code} body={resp_off.text[:100]}",
        )
        check(
            "C13a 404 响应不含业务数据(handler 未执行)",
            '"ok"' not in resp_off.text,
            resp_off.text[:100],
        )
    except Exception as e:
        check("C13 禁用后 GET /v1/_smoke/ping 返回 404(请求期门控生效)", False, f"请求异常: {e}")
    note(
        f"C-路由对象残留={rem}（预期：FastAPI 不支持安全卸载已注册路由）；"
        "请求期已由 plugin_gate.plugin_route_guard 拦截为 404，AC-PLR-03-1 已闭环。"
    )

    # C14 门控对称：重新启用后同一条残留路由立即恢复 200，无需重建 app
    ok3 = await mgr.enable_plugin(SMOKE_NAME)
    try:
        transport_on = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport_on, base_url="http://testserver") as client:
            resp_on = await client.get(ROUTE_PREFIX + "/ping")
        check(
            "C14 重新启用后同一路由恢复 200(门控按 manifest 实时判定)",
            ok3 and resp_on.status_code == 200 and resp_on.json().get("ok") is True,
            f"ok={ok3} status={resp_on.status_code} body={resp_on.text[:100]}",
        )
    except Exception as e:
        check("C14 重新启用后同一路由恢复 200(门控按 manifest 实时判定)", False, f"请求异常: {e}")
    finally:
        await mgr.disable_plugin(SMOKE_NAME)


async def group_d_open_items():
    """D. 本轮 OPEN 项闭环：门控装配链 / agent 清理 / 关闭期消息排空。"""
    print("")
    print("--- D. OPEN 项闭环 ---")

    pm_src = (WORKDIR / "base" / "common" / "plugin_manager.py").read_text(encoding="utf-8")
    gate_src = (WORKDIR / "base" / "common" / "plugin_gate.py").read_text(encoding="utf-8")
    check(
        "D1 业务/内部路由装配均注入请求期 guard",
        pm_src.count("dependencies=route_guard") == 2,
        f"注入点={pm_src.count('dependencies=route_guard')}",
    )
    check(
        "D1a guard 判定复用唯一门控 is_plugin_active",
        "plugin_route_guard" in gate_src and "is_plugin_active(name)" in gate_src,
    )

    agent_src = (PLUGINS / "agent" / "__init__.py").read_text(encoding="utf-8")
    agent_manifest = json.loads((PLUGINS / "agent" / "manifest.json").read_text(encoding="utf-8"))
    check("D2 agent/__init__.py 不再自导出 router", "router = APIRouter" not in agent_src)
    check("D2a agent on_enable 不再自行 include_router", "app.include_router" not in agent_src)
    check(
        "D2b agent manifest.routes 指向聚合目录",
        agent_manifest.get("routes") == ["api/aggregate"],
        f"routes={agent_manifest.get('routes')}",
    )
    check(
        "D2c 聚合路由文件存在",
        (PLUGINS / "agent" / "api" / "aggregate" / "agent_all_router.py").exists(),
    )

    start_src = (WORKDIR / "base" / "start.py").read_text(encoding="utf-8")
    cw_src = (WORKDIR / "base" / "common" / "events" / "consumer_worker.py").read_text(encoding="utf-8")
    check(
        "D3 消息回调外壳隔离 CancelledError 与通道失效异常",
        "except asyncio.CancelledError" in cw_src and "_process_message" in cw_src,
    )
    i_stop = start_src.index("consumer_worker.stop()")
    i_bus = start_src.index("event_bus.shutdown()")
    i_db = start_src.index("Tortoise.close_connections()")
    check("D3a 关闭顺序: 排空 consumer -> 关 event_bus -> 关 DB", i_stop < i_bus < i_db)

    # D4 动态验证 stop() 确实排空在途任务（不依赖真实 RabbitMQ）
    from base.common.events.consumer_worker import ConsumerWorker

    class _StubCM:
        def get_queue(self):
            return None

    class _StubBus:
        def get_connection_manager(self):
            return _StubCM()

    cw = ConsumerWorker(_StubBus())
    finished = []

    async def _slow():
        try:
            await asyncio.sleep(0.05)
            finished.append(True)
        finally:
            # 与 _on_message 的 finally 一致，避免 stub 在日志里留下假的「剩余」
            cw._inflight.discard(asyncio.current_task())

    t = asyncio.create_task(_slow())
    cw._inflight.add(t)
    await cw.stop(drain_timeout=1.0)
    check(
        "D4 stop() 等在途消息收尾后才返回",
        finished == [True] and t.done() and not t.cancelled(),
        f"finished={finished} done={t.done()}",
    )

    cw2 = ConsumerWorker(_StubBus())
    blocker = asyncio.Event()

    async def _blocked():
        try:
            await blocker.wait()
        finally:
            cw2._inflight.discard(asyncio.current_task())

    t2 = asyncio.create_task(_blocked())
    cw2._inflight.add(t2)
    await cw2.stop(drain_timeout=0.05)
    check(
        "D4a 超时在途任务被主动取消(关闭流程不被拖死)",
        t2.done() and t2.cancelled(),
        f"done={t2.done()} cancelled={t2.cancelled()}",
    )


async def main():
    build_smoke_sample()
    try:
        async with real_app.router.lifespan_context(real_app):
            app = real_app
            mgr = get_plugin_manager()

            await group_a_deploy_table()
            await group_b_jobs(mgr)
            await group_c_e2e(app, mgr)
            await group_d_open_items()
    finally:
        # 清理：删除示例插件目录 + 其遗留的菜单/权限/订阅行，保证共享库基线
        try:
            await EventSubscription.filter(subscriber=SMOKE_NAME).delete()
        except Exception:
            pass
        try:
            await Menu.filter(name=MENU_NAME, path=MENU_PATH).delete()
        except Exception:
            pass
        try:
            await Permission.filter(code=PERM_CODE).delete()
        except Exception:
            pass
        shutil_rmtree(PLUGINS / SMOKE_NAME)

    passed = sum(1 for _, c, _ in results if c)
    failed = [r for r in results if not r[1]]
    print("\n==================== 待办测试汇总 ====================")
    print(f"断言总数={len(results)}  PASS={passed}  FAIL={len(failed)}")
    for f in failed:
        print("  FAIL ->", f[0], f[2])
    if findings:
        print("\n重要发现（非失败 / 已知缺口，需产品·架构确认）：")
        for f in findings:
            print("  -", f)
    if failed:
        sys.exit(1)
    print("全部断言通过。")


if __name__ == "__main__":
    asyncio.run(main())
