"""
M5 Qdrant 适配层（向量检索服务）

溯源：
- docs/arch/02 §4.4：collection 命名 kb_{knowledge_base_id}，一库一 collection；
  归属校验以 PG rag_knowledge_base.owner_* 为唯一事实源；先 PG 元数据后 Qdrant 写入，
  失败标记 pending 补偿
- docs/arch/05 §2.2：每次向量操作前查 PG 复核 kb 归属/授权，缓存 60s（Redis），
  缓存键含授权版本号；注销硬删
- docs/arch/06 R-13：向量操作必经 M5 且复核 PG 归属；禁止业务代码直连 Qdrant
- docs/arch/06 R-08：全部 async（AsyncQdrantClient）

归属复核决策（PG 事实源）：
  owner 匹配 → 允许；is_public=true → 允许（公共库，调用侧仍需 ResourceGrant 预发，
  由 M4 求交保证）；ResourceGrant(resource_type=kb) 存在 → 允许。
复核结果缓存 60s；缓存键含授权版本号 m5:kb_ver:{kb_id}（Redis 计数器，
授权/归属相关事实变化时经 invalidate_kb() 递增，旧键自然过期）。
"""
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from loguru import logger

from base.common.cache import RedisCache
from base.common.setting import settings

CACHE_TTL_SECONDS = 60
# payload 必带字段（02-§4.4）
PAYLOAD_FIELDS = ("chunk_id", "document_id", "kb_id")


class KBAccessDeniedError(Exception):
    """M5 复核拒绝（PG 事实源判定无归属/未授权）"""

    def __init__(self, kb_id: int, owner: Tuple[str, int]):
        self.kb_id = kb_id
        self.owner = owner
        super().__init__(f"知识库 {kb_id} 对主体 {owner[0]}:{owner[1]} 不可访问")


class QdrantUnavailableError(Exception):
    """Qdrant 超时/不可用（05-§1.1：上层按 1s/2s/4s 重试后走图策略）"""


def collection_name(kb_id: int) -> str:
    """collection 命名（02-§4.4：一库一 collection）"""
    return f"kb_{int(kb_id)}"


class VectorStore:
    """Qdrant 适配层单例（collection 管理 / 向量读写 / payload 过滤 / 归属强校验）"""

    def __init__(self):
        self._client = None

    # ---------------- 客户端 ----------------
    async def _get_client(self):
        if self._client is not None:
            return self._client
        from qdrant_client import AsyncQdrantClient

        if not settings.QDRANT_ENABLED:
            raise QdrantUnavailableError("Qdrant 未启用")
        try:
            self._client = AsyncQdrantClient(
                url=settings.QDRANT_HOST,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=settings.QDRANT_TIMEOUT,
            )
            return self._client
        except Exception as e:
            raise QdrantUnavailableError(f"Qdrant 客户端初始化失败: {e}") from e

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    # ---------------- 归属复核（每次向量操作前，R-13） ----------------
    @staticmethod
    def _ver_key(kb_id: int) -> str:
        return f"m5:kb_ver:{int(kb_id)}"

    @staticmethod
    def _cache_key(kb_id: int, owner: Tuple[str, int], version: int) -> str:
        return f"m5:kb_authz:{int(kb_id)}:{owner[0]}:{owner[1]}:v{version}"

    async def _redis(self):
        try:
            if not RedisCache.is_enabled():
                return None
            cache = await RedisCache.get_instance()
            return cache._client  # noqa: SLF001（与 quota/authz 相同用法）
        except Exception:
            return None

    async def _authz_version(self, redis, kb_id: int) -> int:
        """授权版本号（Redis 计数器；无 Redis 时退化为时间分桶，保证 60s 内一致）"""
        if redis is None:
            return int(time.time()) // CACHE_TTL_SECONDS
        try:
            val = await redis.get(self._ver_key(kb_id))
            return int(val or 0)
        except Exception:
            return 0

    async def invalidate_kb(self, kb_id: int) -> None:
        """
        授权版本号递增（kb 归属/is_public 变化、ResourceGrant 授予/撤销后调用）。
        旧缓存键随 TTL 自然过期；新键立即触发 PG 复核。
        """
        redis = await self._redis()
        if redis is None:
            return
        try:
            await redis.incr(self._ver_key(kb_id))
        except Exception as e:
            logger.debug(f"[m5] 授权版本递增失败 kb_id={kb_id}: {e}")

    async def _pg_recheck(self, kb_id: int, owner: Tuple[str, int]) -> bool:
        """PG 事实源复核：归属 / 公共库 / ResourceGrant 授权（02-§4.4）"""
        from base.plugins.agent.models.rag import RAGKnowledgeBase
        from base.common.authz.service import ResourceGrantService

        kb = await RAGKnowledgeBase.get_or_none(id=kb_id)
        if kb is None or kb.status != "active":
            return False
        ot, oid = owner
        if kb.owner_type == ot and int(kb.owner_id or 0) == int(oid):
            return True
        if kb.is_public:
            return True
        return await ResourceGrantService.check_resource_access(owner, "kb", kb_id)

    async def verify_kb_access(self, kb_id: int, owner: Tuple[str, int]) -> None:
        """
        每次向量操作前复核 kb 归属/授权（R-13）。缓存 60s，缓存键含授权版本号。

        Raises:
            KBAccessDeniedError: PG 事实源判定不可访问
        """
        redis = await self._redis()
        version = await self._authz_version(redis, kb_id)
        if redis is not None:
            try:
                cached = await redis.get(self._cache_key(kb_id, owner, version))
                if cached is not None:
                    if cached == "1":
                        return
                    raise KBAccessDeniedError(kb_id, owner)
            except KBAccessDeniedError:
                raise
            except Exception as e:
                logger.debug(f"[m5] 归属缓存读取失败（回源 PG）: {e}")
        allowed = await self._pg_recheck(kb_id, owner)
        if redis is not None:
            try:
                await redis.set(
                    self._cache_key(kb_id, owner, version),
                    "1" if allowed else "0",
                    ex=CACHE_TTL_SECONDS,
                )
            except Exception as e:
                logger.debug(f"[m5] 归属缓存写入失败（忽略）: {e}")
        if not allowed:
            raise KBAccessDeniedError(kb_id, owner)

    # ---------------- collection 管理 ----------------
    async def ensure_collection(self, kb_id: int, dimension: int,
                                owner: Optional[Tuple[str, int]] = None) -> str:
        """创建知识库 collection（幂等）；owner 提供时先复核归属"""
        if owner is not None:
            await self.verify_kb_access(kb_id, owner)
        from qdrant_client.http.models import Distance, VectorParams

        client = await self._get_client()
        name = collection_name(kb_id)
        try:
            if not await client.collection_exists(name):
                await client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=int(dimension), distance=Distance.COSINE),
                )
        except QdrantUnavailableError:
            raise
        except Exception as e:
            raise QdrantUnavailableError(f"创建 collection 失败 {name}: {e}") from e
        return name

    async def drop_collection(self, kb_id: int, owner: Tuple[str, int]) -> None:
        """删除 collection（注销硬删，05-§2.2）"""
        await self.verify_kb_access(kb_id, owner)
        client = await self._get_client()
        try:
            await client.delete_collection(collection_name(kb_id))
        except Exception as e:
            raise QdrantUnavailableError(f"删除 collection 失败 kb_{kb_id}: {e}") from e

    # ---------------- 向量读写 ----------------
    async def upsert_chunks(
        self,
        kb_id: int,
        points: Sequence[Dict[str, Any]],
        owner: Tuple[str, int],
    ) -> int:
        """
        写入向量点（先 PG 元数据后 Qdrant；本方法只负责 Qdrant 段）

        Args:
            points: [{id, vector, payload:{chunk_id, document_id, kb_id, ...}}]

        Raises:
            KBAccessDeniedError / QdrantUnavailableError
        """
        await self.verify_kb_access(kb_id, owner)
        if not points:
            return 0
        from qdrant_client.http.models import PointStruct

        client = await self._get_client()
        structs = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload") or {})
            for p in points
        ]
        try:
            await client.upsert(collection_name=collection_name(kb_id), points=structs)
        except Exception as e:
            # 02-§4.4：失败标记 pending 补偿（由调用方记录 PG 向量状态）
            raise QdrantUnavailableError(f"向量写入失败 kb_{kb_id}: {e}") from e
        return len(structs)

    async def search(
        self,
        kb_id: int,
        vector: Sequence[float],
        owner: Tuple[str, int],
        *,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        payload_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        检索（payload 过滤 + 归属复核）

        Returns:
            [{chunk_id, document_id, kb_id, score, content, metadata}]
        """
        await self.verify_kb_access(kb_id, owner)
        client = await self._get_client()
        qfilter = None
        if payload_filter:
            from qdrant_client.http.models import FieldCondition, Filter, MatchValue

            qfilter = Filter(must=[
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in payload_filter.items()
            ])
        try:
            result = await client.query_points(
                collection_name=collection_name(kb_id),
                query=list(vector),
                limit=max(1, int(top_k)),
                score_threshold=score_threshold,
                query_filter=qfilter,
                with_payload=True,
            )
        except Exception as e:
            raise QdrantUnavailableError(f"向量检索失败 kb_{kb_id}: {e}") from e
        hits: List[Dict[str, Any]] = []
        for point in getattr(result, "points", []) or []:
            payload = dict(point.payload or {})
            hits.append({
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "kb_id": payload.get("kb_id", kb_id),
                "score": float(point.score or 0),
                "content": payload.get("content", ""),
                "metadata": {k: v for k, v in payload.items() if k not in PAYLOAD_FIELDS and k != "content"},
            })
        return hits

    async def delete_by_document(self, kb_id: int, document_id: int,
                                 owner: Tuple[str, int]) -> None:
        """按 document_id 过滤删除（03-§3.2：删文档=按 document_id 过滤删除）"""
        await self.verify_kb_access(kb_id, owner)
        from qdrant_client.http.models import FieldCondition, Filter, FilterSelector, MatchValue

        client = await self._get_client()
        try:
            await client.delete(
                collection_name=collection_name(kb_id),
                points_selector=FilterSelector(
                    filter=Filter(must=[
                        FieldCondition(key="document_id", match=MatchValue(value=int(document_id)))
                    ])
                ),
            )
        except Exception as e:
            raise QdrantUnavailableError(f"向量删除失败 kb_{kb_id} doc={document_id}: {e}") from e


vector_store = VectorStore()
