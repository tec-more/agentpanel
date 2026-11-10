"""共享配置契约与解析器。

三个入口共用同一套解析/校验规则：
- app（`run.py`）：`load_app_config(config.conf)`；
- 网关/编排：`load_services_common()`（环境变量 + `_FILE` 密钥）+ 各自 manifest 默认值
  （`apply_env_overrides()`）。

任何必填缺失或类型不符都会抛 `ConfigError`（消息只列出字段名，不含值），
由入口在启动阶段捕获并以退出码 2 终止（fail-closed）。
"""
from __future__ import annotations

import configparser
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

_BOOL_TRUE = {"1", "true", "yes", "on", "y"}
_BOOL_FALSE = {"0", "false", "no", "off", "n"}


class ConfigError(Exception):
    """配置校验失败（fail-closed）。"""

    def __init__(
        self,
        source: str,
        *,
        missing: Iterable[str] = (),
        invalid: Iterable[str] = (),
        detail: str | None = None,
    ):
        self.source = source
        self.missing = list(missing)
        self.invalid = list(invalid)
        self.detail = detail
        parts: List[str] = []
        if self.missing:
            parts.append(f"缺少必填字段 [{', '.join(self.missing)}]")
        if self.invalid:
            parts.append(f"字段类型/取值非法 [{', '.join(self.invalid)}]")
        if detail:
            parts.append(detail)
        message = f"{source} 配置校验失败: " + "; ".join(parts)
        super().__init__(message)


# --------------------------------------------------------------------------- #
# 类型转换
# --------------------------------------------------------------------------- #

def coerce(value: Any, value_type: str) -> Any:
    if value_type == "str":
        return str(value)
    if value_type == "int":
        if isinstance(value, bool):
            raise ValueError("bool 不能作为 int")
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _BOOL_TRUE:
            return True
        if text in _BOOL_FALSE:
            return False
        raise ValueError(f"无法解析为 bool: {value!r}")
    if value_type == "list":
        if isinstance(value, (list, tuple)):
            return list(value)
        text = str(value).strip()
        if not text:
            return []
        return [item.strip() for item in text.split(",") if item.strip()]
    if value_type == "int_list":
        if isinstance(value, (list, tuple)):
            return [int(item) for item in value]
        text = str(value).strip()
        if not text:
            return []
        return [int(item.strip()) for item in text.split(",") if item.strip()]
    if value_type == "json":
        if isinstance(value, (dict, list)):
            return value
        return json.loads(str(value))
    raise ValueError(f"未知字段类型: {value_type}")


# --------------------------------------------------------------------------- #
# 环境变量 / secret 文件
# --------------------------------------------------------------------------- #

def read_secret_file(env_name: str, environ: Mapping[str, str] = os.environ) -> str | None:
    """`<ENV>_FILE` 优先：读取 secret 文件内容（去首尾空白）。"""
    file_path = environ.get(f"{env_name}_FILE")
    if not file_path:
        return None
    path = Path(file_path)
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigError(env_name, invalid=[f"{env_name}_FILE"], detail=f"secret 文件不可读: {path}") from exc


def read_env_value(
    env_name: str,
    value_type: str = "str",
    *,
    secret: bool = False,
    environ: Mapping[str, str] = os.environ,
    default: Any = None,
) -> Any:
    """读取单个环境变量（secret 支持 `_FILE`）；未设置时返回 default。"""
    if secret:
        file_value = read_secret_file(env_name, environ)
        if file_value is not None:
            return coerce(file_value, value_type)
    raw = environ.get(env_name)
    if raw is None or (secret and raw == ""):
        return default
    return coerce(raw, value_type)


@dataclass(frozen=True)
class EnvOverride:
    key: str
    env: str
    type: str = "str"
    secret: bool = False


def apply_env_overrides(
    values: Dict[str, Any],
    overrides: Sequence[EnvOverride],
    *,
    source: str,
    environ: Mapping[str, str] = os.environ,
) -> Dict[str, Any]:
    """manifest 默认值 ← 环境变量覆盖；类型非法一次性聚合抛出。"""
    merged = dict(values)
    invalid: List[str] = []
    for item in overrides:
        known = item.env in environ or (item.secret and f"{item.env}_FILE" in environ)
        if not known:
            continue
        try:
            merged[item.key] = read_env_value(
                item.env, item.type, secret=item.secret, environ=environ
            )
        except ConfigError:
            raise
        except (TypeError, ValueError):
            invalid.append(f"{item.env}({item.type})")
    if invalid:
        raise ConfigError(source, invalid=invalid)
    return merged


# --------------------------------------------------------------------------- #
# manifest 读取（独立于 plugin_manager）
# --------------------------------------------------------------------------- #

_MANIFEST_CACHE: Dict[str, dict] = {}


def load_manifest(path: str | Path) -> dict:
    """读取组件 manifest（进程内缓存）。文件缺失/JSON 非法均 fail-closed。"""
    file_path = Path(path).resolve()
    key = str(file_path)
    if key in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[key]
    if not file_path.exists():
        raise ConfigError("manifest", missing=[key], detail="组件 manifest 不存在")
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("manifest", invalid=[key], detail=f"组件 manifest 不可读: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise ConfigError("manifest", invalid=[key], detail="组件 manifest 顶层必须为对象")
    _MANIFEST_CACHE[key] = data
    return data


def manifest_section(manifest: Mapping[str, Any], section: str) -> Dict[str, Any]:
    value = (manifest.get("config") or {}).get(section)
    return dict(value) if isinstance(value, dict) else {}


# --------------------------------------------------------------------------- #
# app：config.conf
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class AppConfig:
    db_host: str
    db_name: str
    db_user: str
    db_password: str
    db_port: int
    minsize: int
    maxsize: int
    timeout: int
    command_timeout: int
    redis_enabled: bool
    redis_host: str
    redis_port: int
    redis_password: str
    redis_db: int
    deploy_env: str
    strict_startup: bool
    log_dir: str
    storage_dir: str
    debug: bool


def load_app_config(
    path: str | Path = REPO_ROOT / "config.conf",
    *,
    environ: Mapping[str, str] = os.environ,
) -> AppConfig:
    """app 本地配置（config.conf）；保持原有 section/fallback，不新增必填。"""
    parser = configparser.ConfigParser()
    parser.read(Path(path), encoding="utf-8")

    def _get(section: str, key: str, fallback: str) -> str:
        return parser.get(section, key, fallback=fallback)

    def _getint(section: str, key: str, fallback: int) -> int:
        return parser.getint(section, key, fallback=fallback)

    def _getbool(section: str, key: str, fallback: bool) -> bool:
        return parser.getboolean(section, key, fallback=fallback)

    base_path = REPO_ROOT
    deploy_env = environ.get("DEPLOY_ENV", _get("deploy", "env", "dev"))
    strict_startup = environ.get(
        "STRICT_STARTUP", _get("deploy", "strict_startup", "true")
    ).lower() == "true"
    return AppConfig(
        db_host=_get("db", "db_host", "127.0.0.1"),
        db_name=_get("db", "db_name", "aipaneladmin"),
        db_user=_get("db", "db_user", "admin"),
        db_password=_get("db", "db_password", "123456"),
        db_port=_getint("db", "db_port", 15432),
        minsize=_getint("db", "minsize", 5),
        maxsize=_getint("db", "maxsize", 20),
        timeout=_getint("db", "timeout", 30),
        command_timeout=_getint("db", "command_timeout", 30),
        redis_enabled=_getbool("redis", "enabled", False),
        redis_host=_get("redis", "host", "127.0.0.1"),
        redis_port=_getint("redis", "port", 6379),
        redis_password=_get("redis", "password", ""),
        redis_db=_getint("redis", "db", 0),
        deploy_env=deploy_env,
        strict_startup=strict_startup,
        log_dir=_get("log", "path", str(base_path / "logs")),
        storage_dir=_get("storage", "path", str(base_path / "storage")),
        debug=_getbool("app", "debug", True),
    )


# --------------------------------------------------------------------------- #
# 独立服务：环境变量（通用 DB / Redis / 日志）
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    name: str
    minsize: int
    maxsize: int
    timeout: int
    command_timeout: int


@dataclass(frozen=True)
class RedisConfig:
    enabled: bool
    host: str
    port: int
    password: str
    db: int


@dataclass(frozen=True)
class LogConfig:
    level: str
    dir: str


@dataclass(frozen=True)
class ServicesCommonConfig:
    db: DbConfig
    redis: RedisConfig
    log: LogConfig
    deploy_env: str


def load_services_common(
    *,
    environ: Mapping[str, str] = os.environ,
    source: str = "services",
) -> ServicesCommonConfig:
    """两个入口共用配置；密钥支持 `DB_PASSWORD_FILE` / `REDIS_PASSWORD_FILE`。"""
    missing: List[str] = []
    invalid: List[str] = []

    def _read(env: str, value_type: str, *, secret: bool = False, required: bool = False,
              default: Any = None) -> Any:
        try:
            value = read_env_value(env, value_type, secret=secret, environ=environ, default=default)
        except ConfigError as exc:
            invalid.extend(exc.invalid or [env])
            return default
        except (TypeError, ValueError):
            invalid.append(f"{env}({value_type})")
            return default
        if required and (value is None or (isinstance(value, str) and not value.strip())):
            missing.append(env)
        return value

    db_host = _read("DB_HOST", "str", required=True)
    db_name = _read("DB_NAME", "str", required=True)
    db_user = _read("DB_USER", "str", required=True)
    db_password = _read("DB_PASSWORD", "str", secret=True, required=True)
    db_port = _read("DB_PORT", "int", default=15432)
    minsize = _read("DB_MINSIZE", "int", default=5)
    maxsize = _read("DB_MAXSIZE", "int", default=20)
    timeout = _read("DB_TIMEOUT", "int", default=30)
    command_timeout = _read("DB_COMMAND_TIMEOUT", "int", default=30)

    redis_enabled = _read("REDIS_ENABLED", "bool", default=True)
    redis_host = _read("REDIS_HOST", "str", default="127.0.0.1")
    redis_port = _read("REDIS_PORT", "int", default=6379)
    redis_db = _read("REDIS_DB", "int", default=0)
    redis_password = _read(
        "REDIS_PASSWORD", "str", secret=True, required=bool(redis_enabled), default=""
    )

    log_level = _read("LOG_LEVEL", "str", default="INFO")
    log_dir = _read("LOG_DIR", "str", default=str(REPO_ROOT / "logs"))
    deploy_env = _read("DEPLOY_ENV", "str", default="prod")

    if invalid or missing:
        raise ConfigError(source, missing=missing, invalid=invalid)

    return ServicesCommonConfig(
        db=DbConfig(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            name=db_name,
            minsize=minsize,
            maxsize=maxsize,
            timeout=timeout,
            command_timeout=command_timeout,
        ),
        redis=RedisConfig(
            enabled=redis_enabled,
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
        ),
        log=LogConfig(level=str(log_level).upper(), dir=log_dir),
        deploy_env=deploy_env,
    )
