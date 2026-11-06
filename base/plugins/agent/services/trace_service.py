"""
M10 Trace 事件写入服务（批量缓冲，R-11）

溯源：
- docs/arch/03 §3.3：执行中批量缓冲（每 20 条或 1s flush），避免逐条写库占用连接池（C-11）；
  运行中状态入 Redis exec:state:{execution_id}（Hash，结束后 1h TTL）
- docs/arch/04 §5：seq 全局单调递增；断线经 GET trace?cursor=seq 补齐
- docs/arch/05 §1.3：flush 失败重试 3 次后丢弃并告警（Trace 可部分丢失，不阻断运行）
- docs/arch/06 R-11：Trace 批量缓冲写入；禁止逐条 INSERT

设计：
- 每个执行实例一个 TraceWriter：进程内 seq 计数器（恢复执行时以 DB max(seq) 播种），
  事件先入内存缓冲，达到 20 条立即 flush，否则由 1s 周期任务兜底 flush
- flush 用 bulk_create 一次落库；失败重试 3 次（退避 0.2/0.4/0.8s），仍失败丢弃并 critical 日志
- Redis exec:state 为运行中实时态（status/current_node/last_seq），PG trace_event 为持久事实源
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from base.common.cache import RedisCache
from base.plugins.agent.models.trace_event import TraceEvent

# flush 触发阈值（§03-3.3）
FLUSH_SIZE = 20
FLUSH_INTERVAL_SECONDS = 1.0
# flush 失败重试（§05-1.3：3 次后丢弃并告警）
FLUSH_MAX_RETRIES = 3
# 运行中执行状态 TTL（结束后 1h）
EXEC_STATE_TTL_SECONDS = 3600


def _exec_state_key(execution_id: int) -> str:
    return f"exec:state:{execution_id}"


class TraceWriter:
    """单执行实例的事件缓冲写入器（seq 分配 + 批量落库 + Redis 实时态）"""

    def __init__(self, execution_id: int, *, seed_seq: int = 0):
        self.execution_id = execution_id
        self._seq = seed_seq
        self._buffer: List[Dict[str, Any]] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._dropped = 0

    # ---------------- seq ----------------
    @property
    def last_seq(self) -> int:
        return self._seq

    def next_seq(self) -> int:
        """分配全局单调递增 seq（执行实例内）"""
        self._seq += 1
        return self._seq

    # ---------------- 缓冲写入 ----------------
    async def emit(self, event_type: str, node_id: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        记录一条事件：分配 seq、入缓冲（满 20 立即 flush）、更新 Redis 实时态。
        返回完整事件 dict（含 seq），供 SSE 直接使用。
        """
        seq = self.next_seq()
        event = {
            "execution_id": self.execution_id,
            "seq": seq,
            "event_type": event_type,
            "node_id": node_id,
            "payload": payload,
        }
        async with self._lock:
            self._buffer.append(event)
            should_flush = len(self._buffer) >= FLUSH_SIZE
        if should_flush:
            await self.flush()
        # Redis 实时态更新失败不阻断执行
        await self._update_redis_state(event)
        return event

    async def flush(self) -> None:
        """将缓冲事件批量落库（bulk_create，一次占连接）"""
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []
        delay = 0.2
        for attempt in range(1, FLUSH_MAX_RETRIES + 1):
            try:
                await TraceEvent.bulk_create([TraceEvent(**item) for item in batch])
                return
            except Exception as e:
                logger.warning(
                    f"[trace] flush 失败(第{attempt}次) execution_id={self.execution_id} "
                    f"batch={len(batch)}: {e}"
                )
                if attempt < FLUSH_MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
        # §05-1.3：重试耗尽丢弃并告警（不阻断运行）
        self._dropped += len(batch)
        logger.critical(
            f"[trace] flush 连续失败，丢弃 {len(batch)} 条事件 execution_id={self.execution_id} "
            f"（trace_buffer_flush_failed）"
        )

    # ---------------- 周期任务 ----------------
    def start_periodic_flush(self) -> None:
        """启动 1s 周期 flush 兜底任务"""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._periodic_flush())

    async def _periodic_flush(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
                await self.flush()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[trace] 周期 flush 任务异常 execution_id={self.execution_id}: {e}")

    async def close(self) -> None:
        """执行结束：停周期任务 + 最终 flush + Redis 状态置终态"""
        self._closed = True
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._flush_task), timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
        await self.flush()

    # ---------------- Redis 运行态 ----------------
    async def _redis(self):
        try:
            if not RedisCache.is_enabled():
                return None
            cache = await RedisCache.get_instance()
            return cache._client  # noqa: SLF001（与 quota/authz 相同用法）
        except Exception:
            return None

    async def _update_redis_state(self, event: Dict[str, Any]) -> None:
        redis = await self._redis()
        if redis is None:
            return
        try:
            mapping = {
                "last_seq": str(event["seq"]),
                "last_event": event["event_type"],
                "updated_at": str(time.time()),
            }
            if event.get("node_id"):
                mapping["current_node"] = event["node_id"]
            if event["event_type"] == "run_started":
                mapping["status"] = "running"
            elif event["event_type"] == "run_paused":
                mapping["status"] = "paused"
            elif event["event_type"] == "run_completed":
                mapping["status"] = "success"
            elif event["event_type"] == "run_failed":
                mapping["status"] = "failed"
            key = _exec_state_key(self.execution_id)
            await redis.hset(key, mapping=mapping)
            await redis.expire(key, EXEC_STATE_TTL_SECONDS)
        except Exception as e:
            logger.debug(f"[trace] Redis exec:state 更新失败（忽略）: {e}")

    @staticmethod
    async def mark_cancelled_state(execution_id: int) -> None:
        """取消路径更新 Redis 实时态"""
        try:
            if not RedisCache.is_enabled():
                return
            cache = await RedisCache.get_instance()
            redis = cache._client  # noqa: SLF001
            key = _exec_state_key(execution_id)
            await redis.hset(key, mapping={"status": "cancelled", "updated_at": str(time.time())})
            await redis.expire(key, EXEC_STATE_TTL_SECONDS)
        except Exception:
            pass


class TraceService:
    """Trace 写入/读取入口（M2→M10 契约：emit(event) -> buffered_write）"""

    _writers: Dict[int, TraceWriter] = {}

    @classmethod
    async def create_writer(cls, execution_id: int) -> TraceWriter:
        """创建执行实例写入器；恢复执行时以 DB max(seq) 播种，保证 seq 续接单调"""
        last = await TraceEvent.filter(execution_id=execution_id).order_by("-seq").first()
        writer = TraceWriter(execution_id, seed_seq=last.seq if last else 0)
        cls._writers[execution_id] = writer
        writer.start_periodic_flush()
        return writer

    @classmethod
    def get_writer(cls, execution_id: int) -> Optional[TraceWriter]:
        return cls._writers.get(execution_id)

    @classmethod
    async def close_writer(cls, execution_id: int) -> None:
        writer = cls._writers.pop(execution_id, None)
        if writer is not None:
            await writer.close()

    @classmethod
    async def close_all(cls) -> None:
        """进程退出兜底：全部 flush（finally 钩子调用）"""
        for execution_id in list(cls._writers.keys()):
            try:
                await cls.close_writer(execution_id)
            except Exception as e:
                logger.warning(f"[trace] 关闭写入器失败 execution_id={execution_id}: {e}")

    # ---------------- 读取（回放/补齐） ----------------
    @staticmethod
    async def list_events(execution_id: int, *, cursor: int = 0, limit: int = 200) -> List[TraceEvent]:
        """按 (execution_id, seq) 分页；cursor=last_seq 断线补齐（04-§5.1）"""
        limit = max(1, min(int(limit), 1000))
        return (
            await TraceEvent.filter(execution_id=execution_id, seq__gt=cursor)
            .order_by("seq")
            .limit(limit)
        )
