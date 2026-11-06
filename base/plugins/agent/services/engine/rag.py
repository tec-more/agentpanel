"""
M4 RAG 检索入口（引擎侧）：kb_ids 与 M8 可访问集合求交（05-§2.2 五条）

规则实现：
1. 检索前置白名单：调用方传入 kb_ids；可访问集合 = 自有 ∪ 授权(ResourceGrant) ∪ 公共库；
   求交，空交集 → 拒绝（KBAccessDenied）
2. M5 强校验：每个 kb 的实际向量操作前由 vector_store 复核 PG 归属（本层不重复实现）
3. 公共库：is_public=true 计入可访问集合（公共库访问需管理员预发 ResourceGrant，
   由授权管理侧保证；M5 复核仍兜底）
4. 跨库检索：单节点最多 5 个 KB（防 fan-out 放大）
5. 注销清理：硬删由 M5/M4 管理路径处理（本层不涉及）

检索流程：求交 → 按 kb 的 embedding 模型向量化 query（M6）→ M5 search → 按 score 合并截断。
"""
import asyncio
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from loguru import logger

from base.common.authz.service import ResourceGrantService
from base.plugins.agent.services.engine.errors import KBAccessDenied, NodeExecutionError
from base.plugins.agent.services.vector_store import (
    QdrantUnavailableError,
    VectorStore,
    vector_store,
)

# 单节点最多 KB 数（05-§2.2 第四条）
MAX_KB_PER_NODE = 5


async def accessible_kb_ids(owner: Tuple[str, int], requested_ids: Sequence[int]) -> Set[int]:
    """
    计算请求 kb_ids 与主体可访问集合的交集

    可访问集合 = 自有（owner 匹配） ∪ 授权（ResourceGrant kb） ∪ 公共库（is_public）。
    全部过滤 status=active。
    """
    from base.plugins.agent.models.rag import RAGKnowledgeBase

    requested = {int(k) for k in (requested_ids or [])}
    if not requested:
        return set()

    own = await RAGKnowledgeBase.filter(
        id__in=requested, owner_type=owner[0], owner_id=owner[1], status="active"
    ).values_list("id", flat=True)
    public = await RAGKnowledgeBase.filter(
        id__in=requested, is_public=True, status="active"
    ).values_list("id", flat=True)
    granted_str = await ResourceGrantService.check_many(owner, "kb", list(requested))
    granted_ids = {int(k) for k in granted_str}
    # BUG-T15-009：granted 路径补 status="active" 过滤（own/public 已过滤，granted 此前未过滤导致 disabled KB 静默空召回）
    if granted_ids:
        active_granted = await RAGKnowledgeBase.filter(
            id__in=granted_ids, status="active"
        ).values_list("id", flat=True)
        granted = set(active_granted)
    else:
        granted = set()
    return set(own) | set(public) | granted


async def _embed_query(kb, query: str) -> List[float]:
    """经 M6 Embedding 服务向量化 query（按 kb 绑定模型）"""
    from base.plugins.agent.services.embedding_factory import EmbeddingFactory

    if not kb.embedding_model_id:
        raise NodeExecutionError(
            "EMBEDDING_UNAVAILABLE", f"知识库 {kb.id} 未配置 Embedding 模型", retryable=False
        )
    embed_model = await EmbeddingFactory.get_embedding_model(kb.embedding_model_id)
    if hasattr(embed_model, "aget_query_embedding"):
        return await embed_model.aget_query_embedding(query)
    return await asyncio.to_thread(embed_model.get_query_embedding, query)


async def retrieve(
    owner: Tuple[str, int],
    kb_ids: Sequence[int],
    query: str,
    *,
    top_k: int = 5,
    score_threshold: Optional[float] = None,
    payload_filter: Optional[Dict[str, Any]] = None,
    store: Optional[VectorStore] = None,
) -> List[Dict[str, Any]]:
    """
    RAG 检索入口（M2→M4 契约：rag_retrieve(kb_ids, query, top_k, owner) -> chunks[]）

    Raises:
        KBAccessDenied: 白名单求交为空 / 超 5 库
        NodeExecutionError: embedding 失败
        QdrantUnavailableError: 向量库不可用（引擎按 1s/2s/4s 重试，05-§1.1）
    """
    from base.plugins.agent.models.rag import RAGKnowledgeBase

    store = store or vector_store
    requested = [int(k) for k in (kb_ids or [])]
    if len(requested) > MAX_KB_PER_NODE:
        raise KBAccessDenied(f"单节点最多检索 {MAX_KB_PER_NODE} 个知识库，当前 {len(requested)}")
    allowed = await accessible_kb_ids(owner, requested)
    if not allowed:
        raise KBAccessDenied("请求的知识库不可访问或未授权（交集为空）")

    kbs = await RAGKnowledgeBase.filter(id__in=allowed, status="active").all()
    all_hits: List[Dict[str, Any]] = []
    for kb in kbs:
        vector = await _embed_query(kb, query)
        hits = await store.search(
            kb.id, vector, owner,
            top_k=top_k, score_threshold=score_threshold, payload_filter=payload_filter,
        )
        all_hits.extend(hits)
    # 按 score 合并（跨库在应用层合并，02-§3 取舍）
    all_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
    result = all_hits[: max(1, int(top_k))]
    if not result:
        logger.info(f"[rag] 召回为空 owner={owner[0]}:{owner[1]} kb_ids={sorted(allowed)}")
    return result
