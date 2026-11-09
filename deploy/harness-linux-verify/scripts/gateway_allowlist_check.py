"""只读加载网关领域包 service.py，验证真实出网白名单判定。

通过 docker run 把 `services/gateway/common/service.py` 与
`packages/common/upstream/egress.py` 只读挂到
/opt/project_gateway_service.py 与 /opt/project_gateway_egress.py；
这里注入最小 stub 依赖（运行时配置/日志/ORM 模型/计价服务），
不修改业务代码，不发起真实出网请求。
"""
from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any, Dict

GATEWAY_MODULE = "services.gateway.common.service_probe"
EGRESS_PATH = "/opt/project_gateway_egress.py"


def _stub(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = mod
    return mod


def _install_stubs(config_holder: Dict[str, Any]) -> None:
    """伪造 service.py 顶层依赖，保证只读加载时不引入真实 DB / 插件栈。

    service.py 迁移到 `services.gateway.common` 后，跨包依赖改为绝对导入
    `packages.common.*`，同包依赖仍是相对导入 `.logging` / `.runtime`；
    两侧模块链都要预置，否则 spec_from_file_location 加载会 ImportError。
    """
    packages = _stub("packages")
    common = _stub("packages.common")
    domain = _stub("packages.common.domain")
    models = _stub("packages.common.models")
    upstream = _stub("packages.common.upstream")

    services = _stub("services")
    gw_service = _stub("services.gateway")
    gateway = _stub("services.gateway.common")

    logging_mod = _stub("services.gateway.common.logging")
    logging_mod.gateway_logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    runtime_mod = _stub("services.gateway.common.runtime")
    runtime_mod.gateway_config = lambda: config_holder["config"]

    pricing_mod = _stub("packages.common.domain.pricing_service")
    pricing_mod.ModelPriceService = type("ModelPriceService", (), {})
    quota_mod = _stub("packages.common.models.quota")
    quota_mod.UsageRecord = type("UsageRecord", (), {})

    # 父包属性链：绝对路径与相对导入都依赖 sys.modules 中的完整模块名
    packages.common = common  # type: ignore[attr-defined]
    common.domain = domain  # type: ignore[attr-defined]
    common.models = models  # type: ignore[attr-defined]
    common.upstream = upstream  # type: ignore[attr-defined]
    services.gateway = gw_service  # type: ignore[attr-defined]
    gw_service.common = gateway  # type: ignore[attr-defined]


def _load_egress(egress_path: str) -> None:
    spec = importlib.util.spec_from_file_location(
        "packages.common.upstream.egress", egress_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    upstream = sys.modules["packages.common.upstream"]
    upstream.EgressPolicy = module.EgressPolicy
    upstream.UpstreamEgressError = module.UpstreamEgressError


def run_check(service_path: str) -> Dict[str, Any]:
    config_holder = {
        "config": {
            "provider_domain_allowlist": ["api.deepseek.com"],
            "allow_loopback": False,
            "strip_request_fields": ["dsh_session_log"],
        }
    }
    _install_stubs(config_holder)
    _load_egress(EGRESS_PATH)
    spec = importlib.util.spec_from_file_location(GATEWAY_MODULE, service_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    cases = []
    for url, expected in [
        ("https://api.deepseek.com/v1/chat/completions", True),
        ("https://example.com/v1/chat/completions", False),
        ("http://127.0.0.1:18080/v1/chat/completions", False),
        ("ftp://api.deepseek.com/v1/chat/completions", False),
    ]:
        try:
            module.assert_egress_allowed(url)
            actual = True
            detail = "allowed"
        except module.GatewayProxyError as exc:
            actual = False
            detail = f"{exc.status_code}: {exc.message}"
        cases.append({"url": url, "expected": expected, "actual": actual, "detail": detail})

    config_holder["config"]["allow_loopback"] = True
    try:
        module.assert_egress_allowed("http://127.0.0.1:18080/v1/chat/completions")
        loopback_actual = True
        loopback_detail = "allowed"
    except module.GatewayProxyError as exc:
        loopback_actual = False
        loopback_detail = f"{exc.status_code}: {exc.message}"
    cases.append({
        "url": "http://127.0.0.1:18080/v1/chat/completions",
        "expected": True,
        "actual": loopback_actual,
        "detail": loopback_detail,
        "config": "allow_loopback=true",
    })

    return {
        "pass": all(c["expected"] == c["actual"] for c in cases),
        "cases": cases,
    }
