"""L3 模型数据面独立进程入口（standalone）

启动方式：
    python -m base.common.gateway.server
    uvicorn base.common.gateway.server:app --host 127.0.0.1 --port 9999

职责边界：
- 只做租约校验、上游转发、额度预检/结算与记账；
- 不提供租约签发/续期/吊销（这些留在 L2 业务 API 的 /v1/harness/gateway/leases）；
- 只读写共享 PostgreSQL / Redis，不执行迁移、不生成表结构；
- 启动即执行 fail-closed 配置校验，不合规直接拒绝启动。
"""
import io
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple

from fastapi import FastAPI

from packages.agentpanel_common.config import ConfigError, load_l3_common
from packages.agentpanel_common.db import (
    GATEWAY_DEPENDENCY_MODEL_MODULES,
    build_tortoise_orm,
    shared_model_modules,
    stabilize_shared_model_fields,
)

from base.common.gateway.app import create_gateway_app
from base.common.gateway.config import (
    GatewayConfigError,
    gateway_config,
    validate_gateway_config,
)

# P1：L3 入口从环境变量读取 DB/Redis（必填缺失/类型非法 → 退出码 2）
try:
    _L3_CONFIG = load_l3_common(source="gateway")
except ConfigError as exc:
    print(f"❌ [gateway] {exc}", flush=True)
    raise SystemExit(2)


def _configure_stdout() -> None:
    """Windows 控制台默认 GBK；统一 UTF-8，避免中文启动日志乱码。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        buffer = getattr(stream, "buffer", None)
        if buffer is None:
            continue
        try:
            setattr(sys, name, io.TextIOWrapper(buffer, encoding="utf-8"))
        except Exception:
            pass


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """连接共享库与 Redis；退出时释放连接。"""
    from tortoise import Tortoise

    # C1/C2：这两个服务在数据面是懒加载的，但它们的导入会定义未注册的 L2 领域模型；
    # 必须在 Tortoise.init 之前预热，否则共享字段会在 init 之后被重新绑定。
    import base.plugins.harness.services.audit_service  # noqa: F401
    import base.plugins.harness.services.model_credential_service  # noqa: F401

    # P1：DB 连接使用 L3 环境变量配置；模型 = 共享包 + 网关依赖（C1：llm 凭据模型）
    models = shared_model_modules() + list(GATEWAY_DEPENDENCY_MODEL_MODULES)
    await Tortoise.init(config=build_tortoise_orm(_L3_CONFIG.db, models))
    # C1/C2 导入的 L2 领域模型未注册，需把共享字段重绑回已注册模型
    stabilize_shared_model_fields()
    try:
        from base.common.cache import RedisCache

        await RedisCache.get_instance()
    except Exception as exc:
        print(
            f"[gateway-l3] Redis 预热失败，租约缓存/额度计数回落 DB: {type(exc).__name__}: {exc}",
            flush=True,
        )
    try:
        yield
    finally:
        await Tortoise.close_connections()


def build_app() -> FastAPI:
    """fail-closed 校验通过后构建数据面应用。"""
    cfg = validate_gateway_config()
    deployment = str(cfg.get("deployment") or "")
    if deployment != "standalone":
        raise GatewayConfigError(
            f"当前 gateway.deployment={deployment}；独立入口仅在 standalone 下启动。"
            "embedded 形态请用 `python run.py` 由业务 API 挂载 /v1/gateway。"
        )
    return create_gateway_app(lifespan=_lifespan)


def listen_address() -> Tuple[str, int]:
    cfg = gateway_config()
    host = str(cfg.get("host") or "127.0.0.1")
    port = int(cfg.get("port") or 9999)
    return host, port


app = build_app()


def main() -> None:
    _configure_stdout()
    cfg = gateway_config()
    host, port = listen_address()
    print("=" * 70, flush=True)
    print("L3 模型数据面（standalone）启动中...", flush=True)
    print(f"监听地址: http://{host}:{port}", flush=True)
    print(f"deployment: {cfg.get('deployment')}", flush=True)
    print(f"fail_closed: {bool(cfg.get('fail_closed'))}", flush=True)
    print(f"public_base_url: {cfg.get('public_base_url')}", flush=True)
    print("=" * 70, flush=True)

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=True)


if __name__ == "__main__":
    main()
