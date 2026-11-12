import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from tortoise import Tortoise
from base.common import database
from base.common.setting import settings
from base.common.database import init_data
from base.common.middleware import register_middlewares
from base.common.exceptions import register_exceptions
from base.common.router import register_routers
from base.common.json_encoder import DateTimeEncoder
from base.common.jobs import job_scheduler
from base.common.logging_config import register_exceptions_with_logging
from base.plugins import get_plugin_manager, init_plugin_manager
import asyncio

# 共享套餐服务注入唯一 SQL 解析器（P4 B：原 base/common/gateway 兼容层已删除）。
# 共享网关运行时注入 app 的配置/上游/租约缓存 TTL provider 改由 lifespan 启动期惰性装配
# （见下方 lifespan），以移除启动入口对具体插件实现的顶层导入（AC-PLR-13-1 / W2-1 整改）。
import base.common.cache  # noqa: F401,E402
from packages.common.quota.services import plan_service as _shared_plan_service  # noqa: E402
from packages.common.quota.services.plan_resolver import SqlPlanResolver  # noqa: E402

_shared_plan_service.configure(SqlPlanResolver())

# 插件管理器显式注册（T4.10）：不再依赖 base.common.plugin_manager 的导入副作用。
init_plugin_manager()

# 配置日志 - 使用 Loguru 进行完整的日志配置
from base.common.log import setup_logging
setup_logging()

# 禁用websockets.client的调试日志
logging.getLogger('websockets.client').setLevel(logging.WARNING)


async def initialize_event_center():
    """按 manifest.events 声明初始化事件订阅。

    替代此前在启动入口硬编码的 5 条审计订阅：处理器由事件中心按声明动态解析，
    核心层不再静态导入插件实现（PLR-13），订阅随插件启停装卸（PLR-14）。
    必须在 init_data() 之后调用，插件 handler 依赖 Tortoise 已初始化。
    """
    try:
        from base.core.events.registry import event_center
        await event_center.initialize()
        print("[事件中心] 声明订阅同步完成")
    except Exception as e:
        print(f"[事件中心] 初始化失败: {e}")
        import traceback
        traceback.print_exc()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动逻辑
    print("Application starting up...")

    # 安装检查：未安装时只启动最小化 HTTP 服务，跳过数据库和插件初始化
    from base.core.install.services.install_service import InstallService
    if not InstallService.is_installed():
        print("[安装检查] 系统未安装，跳过数据库和插件初始化（仅提供安装向导服务）")
        print("[安装检查] 请访问前端安装向导或 POST /api/v1/install/execute 完成安装")
        yield
        return

    # 存储后台任务引用，便于清理
    background_tasks = []

    # 共享网关运行时注入已迁至 harness 插件 on_startup 钩子
    # （W2-1 整改：base/start.py 不再 import 具体插件实现，AC-PLR-13-1）。

    try:
        await init_data()

        # Redis 预热（BUG-OPS-001 根修）：启动时建立连接，使所有 is_enabled() 判断点生效；
        # 否则惰性连接下首次调用方见 _instance=None 恒走降级，Redis 启用配置形同虚设
        from base.common.cache import RedisCache
        await RedisCache.get_instance()

        # 事件中心必须在 Tortoise.init 之后初始化
        # （否则插件 handler 中的 model 的 default_connection 为 None）
        await initialize_event_center()

        # 初始化EventBusAdapter（RabbitMQ事件总线）
        try:
            from base.common.events.event_bus import event_bus
            if hasattr(event_bus, 'initialize'):
                await event_bus.initialize()
                print("EventBusAdapter初始化完成")
        except Exception as e:
            print(f"EventBusAdapter初始化失败(将使用内存模式): {e}")

        # 启动ConsumerWorker
        try:
            from base.common.events.event_bus import event_bus
            from base.common.events.consumer_worker import ConsumerWorker
            if hasattr(event_bus, 'is_rabbitmq_available') and event_bus.is_rabbitmq_available():
                consumer_worker = ConsumerWorker(event_bus)
                await consumer_worker.start()
                app.state.consumer_worker = consumer_worker
                event_bus._consumer_worker = consumer_worker
                print("ConsumerWorker已启动")
            else:
                app.state.consumer_worker = None
                print("ConsumerWorker未启动(RabbitMQ不可用)")
        except Exception as e:
            print(f"ConsumerWorker启动失败: {e}")
            app.state.consumer_worker = None

        # 事件订阅已在 init_data() 之后由事件中心按 manifest 声明初始化；
        # 插件启用/禁用时由 plugin_manager 调用事件中心做装卸，不再依赖 on_startup。

        # 初始化插件系统
        manager = get_plugin_manager()
        manager.set_app(app)
        await manager.load_enabled_plugins()
        await manager.startup()
        print("插件系统初始化完成")

        # W2-3：定时任务统一装配（平台 quota 作业 + 已启用插件的 manifest.jobs 声明）。
        # 作业随插件运行期启停由 plugin_manager 钩子同步装卸，启动入口不再感知具体插件。
        await job_scheduler.start_all()
        print("定时任务装配完成")

        # 启动 Prometheus 推送工作器（W2-1 整改：删除 ImportError 兜底，base/common 模块始终存在）
        if getattr(settings, 'PROMETHEUS_PUSH_ENABLED', False):
            from base.common.prometheus import start_push_worker
            task3 = asyncio.create_task(start_push_worker())
            background_tasks.append(task3)
            print("Prometheus 推送工作器已启动")
        else:
            print("Prometheus 推送工作器已禁用（PROMETHEUS_PUSH_ENABLED=false）")

        yield

    finally:
        # 清理逻辑
        print("Application shutting down...")

        # 0. W2-3：先取消平台/插件作业（先于插件 shutdown 与 DB 关闭）
        try:
            await job_scheduler.shutdown()
        except Exception as e:
            print(f"关闭作业调度器时出错: {e}")

        # 1. 取消所有后台任务
        print("正在取消后台任务...")
        for task in background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

        # 1.5 停止ConsumerWorker和EventBusAdapter
        try:
            if hasattr(app.state, 'consumer_worker') and app.state.consumer_worker:
                # W3-3：stop() 内部要排空在途消息（drain_timeout=8s），
                # 外层超时须留足余量，否则取消 stop() 会让 drain 半途而废。
                await asyncio.wait_for(app.state.consumer_worker.stop(), timeout=12.0)
                print("ConsumerWorker已停止")
        except Exception as e:
            print(f"停止ConsumerWorker时出错: {e}")
        try:
            from base.common.events.event_bus import event_bus
            if hasattr(event_bus, 'shutdown'):
                await event_bus.shutdown()
                print("EventBusAdapter已关闭")
        except Exception as e:
            print(f"关闭EventBusAdapter时出错: {e}")

        # 2. 关闭插件系统
        print("正在关闭插件系统...")
        try:
            await get_plugin_manager().shutdown()
        except Exception as e:
            print(f"关闭插件系统时出错: {e}")

        # 3. 关闭数据库连接
        print("正在关闭数据库连接...")
        try:
            await Tortoise.close_connections()
        except Exception as e:
            print(f"关闭数据库连接时出错: {e}")

        # 4. 清理WebSocket连接
        print("正在清理WebSocket连接...")
        try:
            # 获取所有活动连接并关闭
            if hasattr(app, 'state') and hasattr(app.state, 'websockets'):
                for ws in app.state.websockets.copy():
                    try:
                        await ws.close(code=1001, reason="Server shutdown")
                    except Exception:
                        pass
        except Exception as e:
            print(f"清理WebSocket连接时出错: {e}")

        print("所有资源已清理完成，端口9998已释放")


def init_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        json_dumps=lambda data, **kwargs: json.dumps(data, **kwargs, cls=DateTimeEncoder, ensure_ascii=False)
    )

    # 设置服务器 URL（用于文档页面的 "Try it out" 功能）
    app.state.servers = [
        {"url": "http://127.0.0.1:9998/api", "description": "本地开发服务器"},
    ]

    # 立即保存并替换 openapi 方法（在路由注册之前）
    _original_openapi = app.openapi

    def custom_openapi():
        import sys
        # 总是重新生成 schema（包含所有已注册的路由）
        openapi_schema = _original_openapi()

        # 设置服务器 URL
        if hasattr(app.state, 'servers'):
            openapi_schema["servers"] = app.state.servers

        paths = openapi_schema.get('paths', {})
        customer_auth_count = len([p for p in paths.keys() if 'customer/auth' in p])
        print(f"[custom_openapi] Generated schema with {customer_auth_count} customer/auth paths, total {len(paths)} paths", file=sys.stderr, flush=True)
        return openapi_schema

    app.openapi = custom_openapi

    # 注册监控功能
    setup_monitoring(app)

    # 注册中间件、路由和异常处理
    register_exceptions_with_logging(app)  # 使用带详细日志的异常处理器
    register_middlewares(app)
    
    # 审计事件处理器推迟到 lifespan 中 init_data() 之后注册
    # （Tortoise.init 必须先完成，否则 model 的 default_connection 为 None）

    # 使用自动路由注册机制
    register_routers(app)

    # 上传文件静态目录：与 /api/v1/upload/* 读取同一批文件。
    # 修复裸 /uploads/... 被 SPA fallback 吞成 index.html 的问题。
    try:
        from pathlib import Path
        from fastapi.staticfiles import StaticFiles

        upload_root = Path(settings.base_path) / "uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads")
        print("[静态资源] /uploads 已挂载")
    except Exception as e:
        print(f"[警告] 挂载 /uploads 失败: {e}")

    # WebSocket 路由（llm voice / mail ws）位于各自插件 manifest.routes 声明的
    # api/v1 目录内，由 plugin_manager 在启动时按声明装配；此处不再手动注册，
    # 避免同一路由被注册两次且脱离插件启用门控（AC-PLR-01-2 / AC-PLR-03-1）。

    # 事件系统 / M9 配额路由已集中到 base/common/router.py::register_routers
    # （W2-1 整改：删除 init_app 手动注册 + try/except ImportError 兜底）。

    # Harness 内部接口由 manifest.internal_routes 声明，随插件启用一并装配，
    # 门控统一走 plugin_gate；不再为单个插件写专用判定（AC-PLR-01-2 / PLR-03）。

    # 内部网关数据面（W2-1 整改）：deployment 配置决定部署形态，切换不改代码。
    # - standalone（默认）：由 `services/gateway/run.py` 作为独立进程服务，
    #   业务 API 不挂载 /v1/gateway；
    # - embedded：以独立子应用挂载到 /v1/gateway（自带独立 OpenAPI，不继承业务鉴权中间件），
    #   作为可选退回方式。
    # 部署形态读取 harness manifest（经 plugin_manager 读 JSON，不 import 具体插件实现，
    # AC-PLR-13-1）；enabled 缺省 True、deployment 缺省 standalone，与
    # gateway_config.DEFAULTS 语义一致。
    from base.common.plugin_manager import get_plugin_manager
    _harness_cfg = ((get_plugin_manager().get_manifest("harness") or {}).get("config") or {}).get("gateway_issuance") or {}
    _gw_enabled = _harness_cfg.get("enabled")
    _gw_enabled = True if _gw_enabled is None else bool(_gw_enabled)
    _gw_deployment = str(_harness_cfg.get("deployment") or "standalone")
    if _gw_enabled and _gw_deployment == "embedded":
        from packages.common.gateway_constants import GATEWAY_DEPLOY_PREFIX
        from services.gateway.common.app import gateway_app
        app.mount(GATEWAY_DEPLOY_PREFIX, gateway_app)
        print(
            f"[手动注册] 内部网关数据面子应用已挂载: {GATEWAY_DEPLOY_PREFIX}/chat/completions"
            f"（独立文档: {GATEWAY_DEPLOY_PREFIX}/docs）"
        )
    else:
        print("[跳过] 网关配置为 standalone 或未启用，业务 API 不挂载 /v1/gateway")

    return app


def setup_monitoring(app: FastAPI):
    """设置监控功能"""

    # 注册健康检查端点（base/common 模块始终存在，W2-1 整改：删除 ImportError 兜底）
    from base.common.health import router as health_router
    app.include_router(health_router, prefix="/health")
    print("[监控] 健康检查端点已注册: /health")

    # 注册Prometheus中间件和指标端点
    if getattr(settings, 'PROMETHEUS_ENABLED', False):
        from base.common.prometheus import PrometheusMiddleware, metrics_endpoint
        app.add_middleware(PrometheusMiddleware)
        app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
        print("[监控] Prometheus监控已启用: /metrics")

    # 初始化Jaeger分布式追踪
    if getattr(settings, 'JAEGER_ENABLED', False):
        from base.common.tracing import setup_jaeger, instrument_app
        setup_jaeger()
        instrument_app(app)
        print(f"[监控] Jaeger追踪已启用: {settings.JAEGER_HOST}:{settings.JAEGER_PORT}")
