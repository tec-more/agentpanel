"""只读加载业务侧 base/common/gateway/service.py，验证真实出网白名单判定。

通过 docker run 把业务源码文件只读挂到 /opt/project_gateway_service.py；
这里注入最小 stub 依赖，不修改业务代码，不发起真实出网请求。
"""
from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any, Dict


def _install_stubs(config_holder: Dict[str, Any]) -> None:
    modules = {
        "base": types.ModuleType("base"),
        "base.common": types.ModuleType("base.common"),
        "base.common.gateway": types.ModuleType("base.common.gateway"),
        "base.common.quota": types.ModuleType("base.common.quota"),
        "base.common.quota.models": types.ModuleType("base.common.quota.models"),
    }
    logging_mod = types.ModuleType("base.common.gateway.logging")
    logging_mod.gateway_logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )
    config_mod = types.ModuleType("base.common.gateway.config")
    config_mod.gateway_config = lambda: config_holder["config"]
    quota_mod = types.ModuleType("base.common.quota.models.quota")
    quota_mod.UsageRecord = type("UsageRecord", (), {})

    modules["base.common.gateway.logging"] = logging_mod
    modules["base.common.gateway.config"] = config_mod
    modules["base.common.quota.models.quota"] = quota_mod
    for name, module in modules.items():
        sys.modules[name] = module
    sys.modules["base"].common = sys.modules["base.common"]
    sys.modules["base.common"].gateway = sys.modules["base.common.gateway"]
    sys.modules["base.common"].quota = sys.modules["base.common.quota"]
    sys.modules["base.common.quota"].models = sys.modules["base.common.quota.models"]


def run_check(service_path: str) -> Dict[str, Any]:
    config_holder = {
        "config": {
            "provider_domain_allowlist": ["api.deepseek.com"],
            "allow_loopback": False,
            "strip_request_fields": ["dsh_session_log"],
        }
    }
    _install_stubs(config_holder)
    spec = importlib.util.spec_from_file_location("agentpanel_gateway_service", service_path)
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
