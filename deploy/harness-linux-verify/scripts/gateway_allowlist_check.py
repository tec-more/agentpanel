"""只读加载共享网关 service.py，验证真实出网白名单判定。

通过 docker run 把共享包源码只读挂到 /opt/project_gateway_service.py 与
/opt/project_gateway_egress.py；这里注入最小 stub 依赖（运行时配置/日志/ORM 模型），
不修改业务代码，不发起真实出网请求。
"""
from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any, Dict

GATEWAY_MODULE = "packages.agentpanel_common.gateway.service_probe"
EGRESS_PATH = "/opt/project_gateway_egress.py"


def _install_stubs(config_holder: Dict[str, Any]) -> None:
    packages = types.ModuleType("packages")
    packages.__path__ = []  # type: ignore[attr-defined]
    common = types.ModuleType("packages.agentpanel_common")
    common.__path__ = []  # type: ignore[attr-defined]
    gateway = types.ModuleType("packages.agentpanel_common.gateway")
    gateway.__path__ = []  # type: ignore[attr-defined]
    models = types.ModuleType("packages.agentpanel_common.models")
    models.__path__ = []  # type: ignore[attr-defined]
    upstream = types.ModuleType("packages.agentpanel_common.upstream")
    upstream.__path__ = []  # type: ignore[attr-defined]

    logging_mod = types.ModuleType("packages.agentpanel_common.gateway.logging")
    logging_mod.gateway_logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    runtime_mod = types.ModuleType("packages.agentpanel_common.gateway.runtime")
    runtime_mod.gateway_config = lambda: config_holder["config"]
    quota_mod = types.ModuleType("packages.agentpanel_common.models.quota")
    quota_mod.UsageRecord = type("UsageRecord", (), {})

    sys.modules["packages"] = packages
    sys.modules["packages.agentpanel_common"] = common
    sys.modules["packages.agentpanel_common.gateway"] = gateway
    sys.modules["packages.agentpanel_common.models"] = models
    sys.modules["packages.agentpanel_common.upstream"] = upstream
    sys.modules["packages.agentpanel_common.gateway.logging"] = logging_mod
    sys.modules["packages.agentpanel_common.gateway.runtime"] = runtime_mod
    sys.modules["packages.agentpanel_common.models.quota"] = quota_mod

    packages.agentpanel_common = common  # type: ignore[attr-defined]
    common.gateway = gateway  # type: ignore[attr-defined]
    common.models = models  # type: ignore[attr-defined]
    common.upstream = upstream  # type: ignore[attr-defined]


def _load_egress(egress_path: str) -> None:
    spec = importlib.util.spec_from_file_location(
        "packages.agentpanel_common.upstream.egress", egress_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    upstream = sys.modules["packages.agentpanel_common.upstream"]
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
