"""共享 Redis 缓存工具（app 与 网关共用同一实现）。

与 app 历史 `base/common/cache.py` 行为一致，差异仅在配置来源：
- 不读取 `config.conf` / `settings`，由入口显式调用 `configure(...)`；
- app 的 `base/common/cache.py` 为 shim：导入时用 settings 调用本模块的 configure。
"""
from typing import Optional, Any, List
import asyncio
import json
import time

# 可选导入Redis，避免没有安装时导入失败
try:
    import redis.asyncio as redis
except ImportError:
    redis = None
    print("Redis模块未安装，将禁用Redis缓存功能")


class _RedisConfig:
    __slots__ = ("enabled", "host", "port", "password", "db")

    def __init__(self, enabled: bool, host: str, port: int, password: Optional[str], db: int):
        self.enabled = bool(enabled)
        self.host = host or "127.0.0.1"
        self.port = int(port or 6379)
        self.password = password or None
        self.db = int(db or 0)


_config: Optional[_RedisConfig] = None


def configure(*, enabled: bool, host: str, port: int,
              password: Optional[str] = None, db: int = 0) -> None:
    """注入 Redis 连接参数（入口启动时调用一次）。"""
    global _config
    _config = _RedisConfig(enabled, host, port, password, db)


def configure_from(config_obj: Any) -> None:
    """按对象属性（enabled/host/port/password/db）注入配置。"""
    configure(
        enabled=bool(getattr(config_obj, "enabled", False)),
        host=str(getattr(config_obj, "host", "127.0.0.1")),
        port=int(getattr(config_obj, "port", 6379)),
        password=getattr(config_obj, "password", None),
        db=int(getattr(config_obj, "db", 0)),
    )


def is_configured() -> bool:
    return _config is not None


class RedisCache:
    """Redis缓存单例类（D2 修复：操作级硬超时 + 连续失败熔断，宕机时快速降级而非黑洞挂起）"""
    _instance: Optional["RedisCache"] = None
    _client: Optional[Any] = None
    _enabled: bool = False

    # D2：单次缓存操作硬超时（socket_timeout 管不住死连接写路径的 TCP 重传，必须应用层 wait_for）
    _OP_TIMEOUT = 2.0
    # 熔断：连续失败次数阈值与冷却时长（冷却期内 is_enabled() 返回 False，全站调用方自动降级）
    _CIRCUIT_FAIL_THRESHOLD = 3
    _CIRCUIT_COOLDOWN = 30.0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._fail_count = 0
            cls._instance._circuit_open_until = 0.0
        return cls._instance

    @classmethod
    async def get_instance(cls) -> "RedisCache":
        """获取缓存实例"""
        if cls._instance is None:
            cls._instance = cls()
        if _config is not None and _config.enabled and cls._instance._client is None:
            await cls._instance.connect()
        return cls._instance

    @classmethod
    def is_enabled(cls) -> bool:
        """检查Redis是否启用且连接成功（熔断冷却期内视为不可用，调用方降级）"""
        inst = cls._instance
        if inst is None or inst._client is None:
            return False
        return not inst._circuit_open()

    def _circuit_open(self) -> bool:
        return time.monotonic() < self._circuit_open_until

    def _on_ok(self):
        self._fail_count = 0

    def _on_error(self):
        self._fail_count += 1
        if self._fail_count >= self._CIRCUIT_FAIL_THRESHOLD:
            self._circuit_open_until = time.monotonic() + self._CIRCUIT_COOLDOWN
            self._fail_count = 0
            print(f"Redis连续操作失败，熔断{int(self._CIRCUIT_COOLDOWN)}s，期间降级为数据库直查")

    async def _exec(self, coro) -> Any:
        """单次 Redis 操作硬超时包装（D2 核心）"""
        return await asyncio.wait_for(coro, timeout=self._OP_TIMEOUT)

    def _available(self) -> bool:
        return self._client is not None and not self._circuit_open()

    async def connect(self):
        """连接Redis"""
        if _config is None or not _config.enabled or redis is None:
            print("Redis已禁用或模块未安装，使用数据库直接查询")
            return

        password = _config.password if _config.password else None
        try:
            self._client = redis.Redis(
                host=_config.host,
                port=_config.port,
                password=password,
                db=_config.db,
                decode_responses=True,
                # D2 修复：socket 级超时作为第一层防护（recv/send 快速报错），health_check 定期探活剔除坏连接
                socket_timeout=5,
                socket_connect_timeout=3,
                socket_keepalive=True,
                health_check_interval=30,
            )
            # 测试连接
            await self._client.ping()
            self._enabled = True
            print("Redis连接成功")
        except Exception as e:
            print(f"Redis连接失败: {e}，将使用数据库直接查询")
            self._client = None
            self._enabled = False

    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值；不存在返回 None"""
        if not self._available():
            return None
        try:
            data = await self._exec(self._client.get(key))
            self._on_ok()
            return json.loads(data) if data else None
        except Exception:
            self._on_error()
            return None

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存值"""
        if not self._available():
            return False
        try:
            await self._exec(self._client.set(key, json.dumps(value, ensure_ascii=False), ex=expire))
            self._on_ok()
            return True
        except Exception:
            self._on_error()
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self._available():
            return False
        try:
            await self._exec(self._client.delete(key))
            self._on_ok()
            return True
        except Exception:
            self._on_error()
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """根据模式删除缓存"""
        if not self._available():
            return 0
        try:
            keys = await self._exec(self._client.keys(pattern))
            if keys:
                result = await self._exec(self._client.delete(*keys))
                self._on_ok()
                return result
            self._on_ok()
            return 0
        except Exception:
            self._on_error()
            return 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self._available():
            return False
        try:
            result = await self._exec(self._client.exists(key)) > 0
            self._on_ok()
            return result
        except Exception:
            self._on_error()
            return False

    async def expire(self, key: str, seconds: int) -> bool:
        """设置键的过期时间"""
        if not self._available():
            return False
        try:
            result = await self._exec(self._client.expire(key, seconds))
            self._on_ok()
            return result
        except Exception:
            self._on_error()
            return False

    async def get_list(self, key: str) -> List[Any]:
        """获取列表缓存"""
        if not self._available():
            return []
        try:
            data = await self._exec(self._client.lrange(key, 0, -1))
            self._on_ok()
            return [json.loads(item) for item in data] if data else []
        except Exception:
            self._on_error()
            return []

    async def push_list(self, key: str, *values: Any, expire: int = 3600) -> bool:
        """向列表添加值"""
        if not self._available():
            return False
        try:
            serialized = [json.dumps(v, ensure_ascii=False) for v in values]
            await self._exec(self._client.rpush(key, *serialized))
            await self._exec(self._client.expire(key, expire))
            self._on_ok()
            return True
        except Exception:
            self._on_error()
            return False

    async def get_hash(self, key: str, field: str = None) -> Optional[Any]:
        """获取哈希缓存"""
        if not self._available():
            return None
        try:
            if field:
                data = await self._exec(self._client.hget(key, field))
                self._on_ok()
                return json.loads(data) if data else None
            else:
                data = await self._exec(self._client.hgetall(key))
                self._on_ok()
                return {k: json.loads(v) for k, v in data.items()} if data else None
        except Exception:
            self._on_error()
            return None

    async def set_hash(self, key: str, mapping: dict, expire: int = 3600) -> bool:
        """设置哈希缓存"""
        if not self._available():
            return False
        try:
            serialized = {k: json.dumps(v, ensure_ascii=False) for k, v in mapping.items()}
            await self._exec(self._client.hset(key, mapping=serialized))
            await self._exec(self._client.expire(key, expire))
            self._on_ok()
            return True
        except Exception:
            self._on_error()
            return False

    async def incr(self, key: str, expire: Optional[int] = None) -> Optional[int]:
        """自增计数；count==1 且传 expire 时设置过期。失败返回 None（调用方降级）"""
        if not self._available():
            return None
        try:
            count = await self._exec(self._client.incr(key))
            if count == 1 and expire:
                await self._exec(self._client.expire(key, expire))
            self._on_ok()
            return int(count)
        except Exception:
            self._on_error()
            return None

    async def ttl(self, key: str) -> Optional[int]:
        """剩余秒数；失败返回 None"""
        if not self._available():
            return None
        try:
            result = await self._exec(self._client.ttl(key))
            self._on_ok()
            return int(result)
        except Exception:
            self._on_error()
            return None

    async def set_nx(self, key: str, expire: int = 3600) -> Optional[bool]:
        """SET NX 占位；成功 True / 已存在 False / 失败 None"""
        if not self._available():
            return None
        try:
            ok = await self._exec(self._client.set(key, "1", ex=expire, nx=True))
            self._on_ok()
            return bool(ok)
        except Exception:
            self._on_error()
            return None


async def get_cache() -> RedisCache:
    """获取缓存实例的便捷函数"""
    return await RedisCache.get_instance()
