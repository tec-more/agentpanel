"""
Harness 运行时启动器：dsh 子进程环境注入

安全约定：
- 只从 HarnessModelCredentialService 解析凭据，不写死 provider/base_url/key；
- 子进程环境只复制安全白名单 OS 变量，父进程的 DEEPSEEK_* / DSH_* 一律不继承，
  避免“环境变量兜底”；
- 日志/审计只允许出现遮蔽值与指纹；
- 未配置凭据时在启动前 fail-closed。
"""
import asyncio
import importlib.util
import json
import platform
import site
import sys
import sysconfig
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from base.common.gateway.config import gateway_config, gateway_enabled
from base.common.masking import fingerprint, mask_secret
from base.plugins.harness.services.audit_service import HarnessAuditService
from base.plugins.harness.services.model_credential_service import (
    HarnessModelCredentialService,
    ModelCredential,
    _credential_defaults,
    _env_names,
    _runtime_config,
)

# 仅允许继承的无害 OS 变量；任何凭据相关变量都不在此列
_ENV_ALLOWLIST = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ",
}

# 父进程中绝不能带入子进程的凭据变量前缀
_ENV_DENY_PREFIXES = ("DEEPSEEK_", "DSH_")

def _platform_tag() -> str:
    return "win" if sys.platform.startswith("win") else sys.platform


def _machine() -> str:
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return machine


_PROBE_CODE = r"""
import hashlib, json, os, sys
names = sys.argv[1:5]
key = os.environ.get(names[0], "")
payload = {
    "has_key": bool(key),
    "key_fingerprint": hashlib.sha256(key.encode("utf-8")).hexdigest()[:12] if key else "",
    "base_url": os.environ.get(names[1], ""),
    "provider": os.environ.get(names[2], ""),
    "model": os.environ.get(names[3], ""),
}
print(json.dumps(payload, ensure_ascii=False))
"""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _dsh_home() -> Optional[str]:
    """按 manifest 配置解析 DSH_HOME；相对路径以项目根为基准，不写死盘符。"""
    runtime = _runtime_config()
    home = runtime.get("dsh_home")
    if not home:
        return None
    path = Path(str(home)).expanduser()
    if not path.is_absolute():
        path = _project_root() / path
    return str(path)


class HarnessRuntimeLauncher:
    @classmethod
    async def _assert_gateway_reachable(cls) -> None:
        """网关不可达时拒绝执行（fail-closed），不得退回内置 key 直连。"""
        import httpx

        base = str(gateway_config().get("public_base_url") or "").rstrip("/")
        if not base:
            raise RuntimeError("网关 public_base_url 未配置，拒绝启动 dsh（fail-closed）")
        timeout = float(gateway_config().get("health_check_timeout_seconds") or 3)
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.get(base + "/health")
                resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                f"网关不可达，拒绝执行 dsh（fail-closed）: {type(exc).__name__}"
            ) from exc

    @classmethod
    def _gateway_env(cls, gateway_lease: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """网关模式环境：只注入租约虚拟 key，不注入任何真实 provider key。"""
        if not gateway_lease or not gateway_lease.get("virtual_key"):
            raise RuntimeError(
                "网关模式必须先签发租约，禁止使用内置 provider key 直连（fail-closed）"
            )
        cfg = gateway_config()
        base_url = str(
            gateway_lease.get("base_url") or cfg.get("public_base_url") or ""
        ).rstrip("/")
        if not base_url:
            raise RuntimeError("网关 public_base_url 未配置，拒绝启动 dsh（fail-closed）")
        names = _env_names()
        env: Dict[str, str] = {
            names["api_key"]: gateway_lease["virtual_key"],
            names["base_url"]: base_url,
        }
        provider = gateway_lease.get("provider")
        model = gateway_lease.get("model")
        if not provider or not model:
            defaults = _credential_defaults()
            provider = provider or defaults.get("provider")
            model = model or defaults.get("model")
        if provider:
            env[names["provider"]] = str(provider)
        if model:
            env[names["model"]] = str(model)
        return env

    @classmethod
    async def build_env(
        cls,
        credential: Optional[ModelCredential] = None,
        gateway_lease: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """构造 dsh 子进程环境：白名单继承 + 显式注入，不含父进程凭据变量"""
        import os
        env: Dict[str, str] = {}
        for name in _ENV_ALLOWLIST:
            value = os.environ.get(name)
            if value is not None:
                env[name] = value
        # 即使白名单被后续扩展，也强制剔除凭据变量
        for name in list(env.keys()):
            if name.startswith(_ENV_DENY_PREFIXES):
                env.pop(name, None)

        dsh_home = _dsh_home()
        if dsh_home:
            env["DSH_HOME"] = dsh_home

        if gateway_enabled():
            await cls._assert_gateway_reachable()
            env.update(cls._gateway_env(gateway_lease))
            return env

        if credential is None:
            raise RuntimeError("未解析到模型凭据，拒绝启动 dsh（fail-closed）")
        names = _env_names()
        env[names["api_key"]] = credential.api_key
        env[names["base_url"]] = credential.base_url
        env[names["provider"]] = credential.provider
        env[names["model"]] = credential.model
        return env

    @classmethod
    def sdk_runtime_executable(cls) -> Optional[str]:
        """解析项目 .venv 中 deepseek-harness-sdk 自带的 runtime 可执行文件。

        只按当前解释器的 site-packages 相对定位，不在代码里写死盘符/绝对路径。
        """
        roots: List[Path] = []
        spec = importlib.util.find_spec("deepseek_harness_runtime")
        if spec and spec.submodule_search_locations:
            for location in spec.submodule_search_locations:
                roots.append(Path(location) / "runtime")
        try:
            for location in site.getsitepackages():
                roots.append(Path(location) / "deepseek_harness_runtime" / "runtime")
        except Exception:
            pass
        purelib = sysconfig.get_paths().get("purelib")
        if purelib:
            roots.append(Path(purelib) / "deepseek_harness_runtime" / "runtime")
        roots.append(
            Path(sys.executable).resolve().parent.parent
            / "Lib"
            / "site-packages"
            / "deepseek_harness_runtime"
            / "runtime"
        )

        seen: set[str] = set()
        for root in roots:
            key = str(root.resolve()) if root.exists() else str(root)
            if key in seen:
                continue
            seen.add(key)
            if not root.is_dir():
                continue
            preferred = root / f"deepseek-harness-sdk-runtime-{_platform_tag()}-{_machine()}.exe"
            if preferred.is_file():
                return str(preferred)
            candidates = sorted(
                p for p in root.glob("deepseek-harness-sdk-runtime-*")
                if p.is_file() and not p.name.endswith("-rg.exe")
            )
            if candidates:
                return str(candidates[0])
        return None

    @classmethod
    def _dsh_command(cls) -> List[str]:
        runtime = _runtime_config()
        command = runtime.get("dsh_command")
        if command:
            if isinstance(command, str):
                return [command]
            return [str(part) for part in command]

        mode = str(runtime.get("dsh_command_mode") or "").strip().lower()
        if mode in ("sdk_runtime", "sdk"):
            executable = cls.sdk_runtime_executable()
            if executable:
                return [executable]
            raise RuntimeError(
                "未找到 dsh SDK runtime 可执行文件，请确认 deepseek-harness-sdk 已安装到项目 .venv"
            )
        return ["dsh"]

    @classmethod
    async def launch(
        cls,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        cwd: Optional[str] = None,
        command: Optional[Sequence[str]] = None,
        extra_env: Optional[Dict[str, str]] = None,
        gateway_lease: Optional[Dict[str, Any]] = None,
    ) -> Tuple[asyncio.subprocess.Process, ModelCredential]:
        """启动 dsh 子进程；网关模式下必须携带租约，否则 fail-closed 不启动"""
        if gateway_enabled():
            env = await cls.build_env(None, gateway_lease)
            provider_name = env.get(_env_names()["provider"]) or (gateway_lease or {}).get("provider") or ""
            model_name = env.get(_env_names()["model"]) or (gateway_lease or {}).get("model") or ""
            credential = ModelCredential(
                provider=str(provider_name),
                provider_name=str(provider_name),
                model=str(model_name),
                model_name=str(model_name),
                base_url=env.get(_env_names()["base_url"], ""),
                api_key="",
            )
            audit_detail = {
                "mode": "gateway",
                "lease_id": (gateway_lease or {}).get("lease_id"),
                "key_fingerprint": (gateway_lease or {}).get("key_fingerprint"),
                "base_url": credential.base_url,
                "provider": credential.provider,
                "model": credential.model,
            }
        else:
            credential = await HarnessModelCredentialService.resolve(provider, model)
            env = await cls.build_env(credential)
            audit_detail = {
                "mode": "direct",
                "provider": credential.provider,
                "model": credential.model,
                "base_url": credential.base_url,
                "api_key": mask_secret(credential.api_key),
                "key_fingerprint": fingerprint(credential.api_key),
            }

        if extra_env:
            env.update({k: v for k, v in extra_env.items()})
        argv = list(command) if command else cls._dsh_command()

        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise RuntimeError(f"启动 dsh 失败: {exc}") from exc

        await HarnessAuditService.record(
            "runtime.launch",
            risk_level="medium",
            target_type="provider",
            target_id=credential.provider,
            detail={**audit_detail, "pid": process.pid, "command": argv[0]},
        )
        return process, credential

    @classmethod
    async def verify_injection(
        cls,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        gateway_lease: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """用真实子进程验证注入：子进程只回传指纹/非敏感配置，不回传明文 key"""
        names = _env_names()
        lease_info: Dict[str, Any] = {}
        if gateway_enabled():
            env = await cls.build_env(None, gateway_lease)
            mode = "gateway"
            lease_info = {
                "lease_id": (gateway_lease or {}).get("lease_id"),
                "key_fingerprint": (gateway_lease or {}).get("key_fingerprint"),
            }
            expected_key = env.get(names["api_key"], "")
            expected_base_url = env.get(names["base_url"], "")
            expected_provider = env.get(names["provider"], "")
            expected_model = env.get(names["model"], "")
        else:
            credential = await HarnessModelCredentialService.resolve(provider, model)
            env = await cls.build_env(credential)
            mode = "direct"
            expected_key = credential.api_key
            expected_base_url = credential.base_url
            expected_provider = credential.provider
            expected_model = credential.model

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _PROBE_CODE,
            names["api_key"],
            names["base_url"],
            names["provider"],
            names["model"],
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("模型凭据注入验证超时")

        payload: Dict[str, Any] = {}
        if stdout:
            try:
                payload = json.loads(stdout.decode("utf-8", errors="replace").strip())
            except Exception:
                payload = {}

        expected = fingerprint(expected_key)
        match = (
            process.returncode == 0
            and bool(payload.get("has_key"))
            and payload.get("key_fingerprint") == expected
            and payload.get("base_url") == expected_base_url
            and payload.get("provider") == expected_provider
            and payload.get("model") == expected_model
        )

        result = {
            "configured": True,
            "injected": bool(payload.get("has_key")),
            "key_fingerprint_match": match,
            "exit_code": process.returncode,
            "env_names": names,
            "mode": mode,
            "provider": expected_provider,
            "model": expected_model,
            "base_url": expected_base_url,
            "api_key": mask_secret(expected_key),
            "key_fingerprint": expected,
            **lease_info,
        }
        await HarnessAuditService.record(
            "runtime.verify_injection",
            risk_level="low",
            target_type="provider",
            target_id=expected_provider,
            detail={k: v for k, v in result.items() if k != "configured"},
        )
        return result
