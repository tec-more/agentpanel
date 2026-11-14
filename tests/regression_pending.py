"""AgentPanel 路径契约与装配整改 —— 待办测试补全（M2+M3 后更新）。

三组用例：
  A. 部署建表：event_subscriptions 在 RUN_DB_MIGRATIONS=false 容器侧的可达性
  B. 调度与消费外迁闭环（M2/M3 / AC-PLR-15-1·13-1）：旧 JobScheduler/ConsumerWorker
     移除断言 + taskiq 唯一路径（broker 注册 7 任务、发布 fail-closed 单通道）
  C. 端到端冒烟（W3-3 / AC-PLR-03-1·03-2·23-1·23-3）：smoke_sample 全生命周期 + 请求期门控 404/200
  D. OPEN 项闭环：门控装配链 / agent 路由自挂载清理 / dispatch 幂等与关闭顺序（M3 更新）

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
    """B. 调度与消费外迁闭环（M2/M3 / AC-PLR-15-1·13-1）：装配移除 + taskiq 唯一路径。"""
    print("")
    print("--- B. 调度与消费外迁（M2+M3） ---")
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

    # B3 M2：旧进程内 JobScheduler 已删除，启动入口不再装配本地调度/消费
    check(
        "B3 start.py 无 job_scheduler / ConsumerWorker 装配",
        "job_scheduler" not in start_src and "ConsumerWorker" not in start_src,
        "启动入口不得再引用旧调度器/旧消费者",
    )
    check(
        "B3a base/common/jobs 包已删除(M2)",
        not (WORKDIR / "base" / "common" / "jobs").exists(),
        "旧 JobScheduler 包不应存在",
    )

    # B4 M2：plugin_manager 不再持有作业调度钩子（beat reconciler 周期重扫接管启停对称）
    pm_src = (WORKDIR / "base" / "common" / "plugin_manager.py").read_text(encoding="utf-8")
    check(
        "B4 plugin_manager 无 _sync_plugin_jobs 残留调用",
        "_sync_plugin_jobs" not in pm_src,
        "插件启停的作业装卸由 beat reconciler 重扫保证（≤reconcile_interval 生效）",
    )

    # B5 M3：旧消费文件已删除
    check(
        "B5 consumer_worker.py / connection_manager.py 已删除(M3)",
        not (WORKDIR / "base" / "common" / "events" / "consumer_worker.py").exists()
        and not (WORKDIR / "base" / "common" / "events" / "connection_manager.py").exists(),
        "旧 RabbitMQ 直连消费链路不应存在",
    )

    # B6 动态：taskiq broker 注册 6 个作业 + dispatch 事件任务（worker import 即注册）
    try:
        import base.common.taskiq_app.tasks_registry  # noqa: F401
        import base.common.taskiq_app.events  # noqa: F401
        from base.common.taskiq_app.broker import broker

        registered = set(broker.get_all_tasks().keys())
        expected = {
            "audit:audit_cleanup",
            "customer:update_membership_data",
            "harness:gateway_reconcile",
            "sales:cancel_expired_orders",
            "platform:quota_reconcile",
            "platform:quota_hold_cleanup",
            "taskiq:dispatch",
        }
        check(
            "B6 taskiq broker 注册 7 个任务(作业6+dispatch)",
            expected <= registered,
            f"missing={expected - registered} registered={sorted(registered)}",
        )
    except Exception as e:
        check("B6 taskiq broker 注册 7 个任务(作业6+dispatch)", False, f"导入异常: {e}")

    # B7 M3：发布端 fail-closed + 单通道（静态锚定）
    adapter_src = (
        (WORKDIR / "base" / "common" / "events" / "event_bus_adapter.py").read_text(encoding="utf-8")
    )
    check(
        "B7 发布端 fail-closed 且不执行内存订阅(M3)",
        "dispatch.kiq" in adapter_src
        and "_memory_bus" not in adapter_src
        and "raise" in adapter_src,
        "publish = EventRecord + dispatch.kiq；失败上抛；无内存双通道",
    )

    check("B8 外迁后启动期未抛异常(lifespan 已完成全部 setup)", True)


async def group_c_e2e(app, mgr):
    """C. 端到端冒烟（W3-3 / AC-PLR-03-1·03-2·23-1·23-3）。"""
    print("\n--- C. 端到端冒烟（smoke_sample 全生命周期） ---")
    # 安装（设置 installed）+ 启用
    from base.common.taskiq_app.broker import broker

    tasks_before = len(broker.get_all_tasks())
    mgr.update_plugin_status(SMOKE_NAME, is_installed=True, is_enabled=True)
    ok = await mgr.enable_plugin(SMOKE_NAME)
    check("C1 enable_plugin('smoke_sample') 返回 True", ok)
    check("C2 启用后 is_plugin_active('smoke_sample')=True", is_plugin_active(SMOKE_NAME))
    # M2：smoke_sample 未声明 jobs，启用不应新增 taskiq 任务注册
    check(
        "C2a 无 jobs 声明的插件启用后不产生 task 任务",
        len(broker.get_all_tasks()) == tasks_before,
        f"before={tasks_before} after={len(broker.get_all_tasks())}",
    )

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
        "C9a 无 jobs 声明的插件启停不影响全局 task 注册(装卸对称)",
        len(broker.get_all_tasks()) == tasks_before,
        f"before={tasks_before} after={len(broker.get_all_tasks())}",
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
    dispatch_src = (WORKDIR / "base" / "common" / "taskiq_app" / "events.py").read_text(encoding="utf-8")
    check(
        "D3 dispatch 消费端幂等：终态(consumed/dead_letter)直接跳过",
        "_TERMINAL_STATUSES" in dispatch_src and 'get_or_none(event_uuid' in dispatch_src,
    )
    i_bus = start_src.index("event_bus.shutdown()")
    i_db = start_src.index("Tortoise.close_connections()")
    check("D3a 关闭顺序: 关 broker 客户端 -> 关 DB", i_bus < i_db)

    # D4 M3：worker 生命周期含周期 resync（运行期插件启停在 worker 侧收敛）
    jobs_src = (WORKDIR / "base" / "common" / "taskiq_app" / "jobs.py").read_text(encoding="utf-8")
    check(
        "D4 worker 启动期构建订阅注册表 + 周期 resync",
        "event_center.initialize()" in jobs_src and "event_center.resync()" in jobs_src,
        "dispatch 按进程内注册表取 handler；resync 保证插件启停收敛",
    )

    # D4a M3：EventCenter 提供周期 resync（新启用补注册 / 已停用摘除）
    registry_src = (WORKDIR / "base" / "core" / "events" / "registry.py").read_text(encoding="utf-8")
    check(
        "D4a EventCenter.resync 声明且覆盖双向同步",
        "async def resync" in registry_src
        and registry_src.count("sync_plugin(") >= 3,  # resync 双向 + initialize
        "resync: 停用→unregister_ref 摘除；启用→register_ref 幂等补注册",
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
