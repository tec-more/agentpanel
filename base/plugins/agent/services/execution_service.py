"""
M2 执行编排服务（ExecutionService）

溯源：
- docs/arch/04 F2 试跑（draft + kind=dry_run，单用户试跑并发=1）/ F3 运行（绑定发布版本快照）
- docs/arch/04 F5 协作式取消（当前节点完成或下一个调度点终止）/ F6 HITL 暂停恢复（72h）
- docs/arch/04 F7 配额拦截：预估 → Redis 原子预占 → 执行 → 每节点结算 → 释放差额（R-09）
- docs/arch/03 §2.5：全局信号量 50 + 用户信号量（经 T4 acquire_concurrency），看门狗心跳
- docs/arch/05 §1.4：引擎崩溃 → 实例 interrupted + 预占释放 + 审计 critical
- docs/arch/06 R-02：归属判断在接入层完成，引擎只消费 ExecutionContext

事件流：backend emit → TraceWriter（批量缓冲 R-11）→ asyncio.Queue → SSE 生成器；
node_completed 事件携带 usage 时按 (execution_id,node_id,seq) 幂等结算（R-09）。
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from loguru import logger

from base.common.authz.context import OwnerContext
from base.common.quota.errors import QuotaError
from base.common.quota.metrics import inc_force_finalize, inc_settle_failure
from base.common.quota.services.estimator import estimate_tokens
from base.common.quota.services.quota_service import QuotaService
from base.plugins.agent.models.workflow import WorkflowExecution
from base.plugins.agent.services.engine import events as evt
from base.plugins.agent.services.engine.backend import InProcessBackend, RunControl
from base.plugins.agent.services.engine.context import (
    KIND_DRY_RUN,
    KIND_RUN,
    ExecutionContext,
)
from base.plugins.agent.services.trace_service import TraceService, TraceWriter

# 执行状态
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_INTERRUPTED = "interrupted"

# 心跳周期（conc: 看门狗 60s，03-§2.3）
HEARTBEAT_INTERVAL_S = 30
# SSE 心跳帧间隔（BUG-T15-014：静默期 comment 帧使断开写失败可被感知，触发自愈收尾）
SSE_PING_INTERVAL_S = 15
# cancel/resume 唤醒确认超时（BUG-T15-014：超时走保底强制收尾）
CANCEL_ACK_TIMEOUT_S = 5
# 试跑并发（F2：单用户试跑并发=1）
DRY_RUN_CONCURRENCY = 1
# 缺省用户并发（套餐未配置 concurrency 项时）
DEFAULT_RUN_CONCURRENCY = 5


def estimate_graph_items(graph: Dict[str, Any]) -> Dict[str, float]:
    """
    配额预估（F7/R-09：先于一切外部调用）
    字符启发式（03-§2.9）：llm 节点 prompt 模板 + max_tokens 预留；rag 节点 kb_search 计数
    """
    token_estimate = 0
    kb_search = 0
    for node in graph.get("nodes") or []:
        ntype = node.get("type")
        config = (node.get("data") or {}).get("config") or {}
        if ntype == "llm":
            template = (config.get("prompt_template") or config.get("prompt") or "")
            system = config.get("system_prompt") or ""
            token_estimate += estimate_tokens(
                system + template, reserve_output=int(config.get("max_tokens", 2000))
            )
        elif ntype == "rag_retrieval":
            kb_search += 1
        elif ntype == "sub_workflow" or ntype == "loop":
            body = config.get("body")
            if isinstance(body, dict):
                sub = estimate_graph_items(body)
                token_estimate += int(sub.get("token", 0))
                kb_search += int(sub.get("kb_search", 0))
    items: Dict[str, float] = {}
    if token_estimate:
        items["token"] = float(token_estimate)
    if kb_search:
        items["kb_search"] = float(kb_search)
    return items


def sse_format(event: Dict[str, Any]) -> str:
    """SSE 帧（04-§5.1：event/data 两段）"""
    payload = dict(event.get("payload") or {})
    payload.setdefault("seq", event.get("seq"))
    return f"event: {event['event_type']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ExecutionService:
    """执行实例生命周期编排"""

    # 运行控制注册表（协作式取消 / HITL 恢复；进程内单实例，P0）
    _controls: Dict[int, RunControl] = {}

    # ============================================================
    # 准备（建实例 → 预估预占 → 并发槽）
    # ============================================================
    @classmethod
    async def prepare(
        cls,
        owner: OwnerContext,
        *,
        workflow,
        graph: Dict[str, Any],
        inputs: Dict[str, Any],
        kind: str = KIND_RUN,
        version_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> ExecutionContext:
        """
        创建执行实例并完成前置拦截（配额预估 + 并发槽）。

        Raises:
            QuotaError: 42901（预估超 / 并发超，不进入引擎，零模型调用）
        """
        execution = await WorkflowExecution.create(
            workflow_id=workflow.id,
            status=STATUS_RUNNING,
            input_data=inputs or {},
            owner_type=owner.owner_type,
            owner_id=owner.owner_id,
            version_id=version_id,
            kind=kind,
        )
        ctx: Optional[ExecutionContext] = None
        try:
            # 1. 配额预估预占（R-09：先于一切外部调用）
            hold_id = await QuotaService.quota_estimate(
                owner, estimate_graph_items(graph), execution_id=execution.id
            )
            # 2. 并发槽（全局 50 + 用户套餐；F2：试跑并发=1）
            if kind == KIND_DRY_RUN:
                limit = DRY_RUN_CONCURRENCY
            else:
                limit = await cls._concurrency_limit(owner)
            await QuotaService.acquire_concurrency(owner, limit)
            ctx = ExecutionContext(
                owner_type=owner.owner_type,
                owner_id=owner.owner_id,
                execution_id=execution.id,
                domain=owner.owner_type,
                quota_hold_id=hold_id,
                kind=kind,
                workflow_id=workflow.id,
                version_id=version_id,
                session_id=session_id,
                settings=graph.get("settings") or {},
                check_resource=cls._build_resource_checker(owner),
            )
            return ctx
        except Exception:
            # 前置失败：实例标记失败并释放已占资源（05-§1.4）
            execution.status = STATUS_FAILED
            execution.error_message = "前置拦截失败"
            # BUG-T15-003 修复：统一使用 UTC（与 Tortoise auto_now_add / dialog_flow_service 对齐）
            execution.completed_at = datetime.utcnow()
            await execution.save()
            if ctx is not None and ctx.quota_hold_id:
                await QuotaService.quota_release(ctx.quota_hold_id)
            raise

    @staticmethod
    async def _concurrency_limit(owner: OwnerContext) -> int:
        from base.common.quota.services.plan_service import PlanService

        plan = await PlanService.resolve_plan(owner.owner_type, owner.owner_id)
        items = (plan.quota_items if plan else {}) or {}
        try:
            return max(1, int(items.get("concurrency", DEFAULT_RUN_CONCURRENCY)))
        except (TypeError, ValueError):
            return DEFAULT_RUN_CONCURRENCY

    @staticmethod
    def _build_resource_checker(owner: OwnerContext):
        """M8 资源复核回调注入（R-02：引擎不直接做归属判断）"""
        from base.common.authz.service import ResourceGrantService

        async def check(resource_type: str, resource_id: Any) -> bool:
            return await ResourceGrantService.check_resource_access(
                owner, resource_type, resource_id
            )

        return check

    # ============================================================
    # 事件流执行（SSE 生成器）
    # ============================================================
    @classmethod
    async def stream_events(
        cls,
        ctx: ExecutionContext,
        graph: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> AsyncIterator[str]:
        """
        执行并产出 SSE 帧。无论正常/异常结束，最终都完成：
        状态落库、配额结算/释放、并发槽释放、Trace flush（05-§1.4）。
        """
        execution_id = ctx.execution_id
        queue: asyncio.Queue = asyncio.Queue()
        control = RunControl()
        cls._controls[execution_id] = control
        writer = await TraceService.create_writer(execution_id)
        heartbeat = asyncio.create_task(cls._heartbeat(ctx, queue))
        # BUG-T15-014：保底自救所需引用挂到 control（cancel/resume API 经注册表可达）
        control.ctx = ctx
        control.writer = writer
        control.heartbeat_task = heartbeat

        async def emit(event_type: str, node_id: Optional[str], payload: Dict[str, Any]) -> None:
            event = await writer.emit(event_type, node_id, payload)
            await queue.put(event)
            if event_type == evt.EventType.NODE_COMPLETED:
                # BUG-T15-013：结算 DB 操作加超时保护，防 runner 卡死于间歇性 DB 挂起（race）
                try:
                    await asyncio.wait_for(cls._settle_node_usage(ctx, event), timeout=10.0)
                except (asyncio.TimeoutError, Exception) as e:
                    inc_settle_failure()  # M-7 监控埋点
                    logger.error(f"[engine] 节点结算超时/失败 execution_id={ctx.execution_id} "
                                 f"node={event.get('node_id')}: {type(e).__name__}: {e}")
            elif event_type == evt.EventType.RUN_PAUSED:
                # BUG-T15-013：paused 落库改后台 task（不阻塞 runner 推进至 resume 等待；
                # HITL 内存等待/恢复不依赖 DB paused 状态），后台 task 内带超时防泄漏
                asyncio.create_task(cls._update_status_guarded(execution_id, STATUS_PAUSED))

        async def runner() -> Dict[str, Any]:
            try:
                backend = InProcessBackend()
                result = await backend.execute(ctx, graph, inputs, emit, control)
                await queue.put({"__done__": True})
                return result
            except Exception as e:  # 引擎崩溃兜底（05-§1.4）
                logger.critical(
                    f"[engine] 执行器崩溃 execution_id={execution_id}: {e}"
                )
                await queue.put({"__done__": True})
                return {"status": STATUS_FAILED, "tokens": {"in": 0, "out": 0},
                        "error": {"code": "ENGINE_CRASH", "message": str(e)}}

        def _task_result(done_task: "asyncio.Task") -> Dict[str, Any]:
            if done_task.cancelled():
                return {"status": STATUS_CANCELLED}
            try:
                return done_task.result() or {"status": STATUS_FAILED}
            except Exception:
                return {"status": STATUS_FAILED}

        async def _finalize_once(final_result: Dict[str, Any]) -> None:
            """幂等收尾（BUG-T15-012）：正常路径由 generator finally 触发；SSE 客户端中断
            致 generator 未被关闭时，由 runner done_callback 兜底触发，确保状态落库/配额释放/
            并发槽释放/心跳停止，杜绝 status=running 僵尸与并发槽泄漏（单用户永久 429）。
            BUG-T15-014：互斥标记提升为 control 级共享（与 cancel/resume 保底路径同锁防双重释放）；
            v2：shield 保护收尾主体与置位原子绑定——即便调用方（generator finally）被
            aclose/重复 cancel 中断，内层 _finalize 已在独立 task 中继续运行，
            杜绝「finalized=True 但收尾未执行」的半置位缺陷（测试铁证3）。"""
            async with control.finalize_lock:
                if control.finalized:
                    return
                control.finalized = True
                heartbeat.cancel()
                await asyncio.shield(cls._finalize(ctx, final_result, writer))

        task = asyncio.create_task(runner())
        control.runner_task = task  # BUG-T15-014：保底路径强制取消用
        # BUG-T15-012 兜底：runner 完成即触发收尾，不依赖 generator finally 的及时执行
        task.add_done_callback(lambda t: asyncio.ensure_future(_finalize_once(_task_result(t))))
        final: Dict[str, Any] = {"status": STATUS_FAILED}
        try:
            while True:
                item = await queue.get()
                if item.get("__done__"):
                    final = _task_result(task)
                    break
                if item.get("__ping__"):
                    # SSE comment 心跳帧（BUG-T15-014）：断开时写失败使传输层感知并关闭 generator
                    yield ": ping\n\n"
                    continue
                yield sse_format(item)
        finally:
            if not task.done():
                control.request_cancel()
                # BUG-T15-014 v2：同时解除 HITL 等待——runner 立即醒走协作式取消
                # （ExecutionCancelled → ack 回执 + 「执行被取消」日志 + cancelled 返回），
                # 而非干等 5s 超时后强制 cancel（无回执无日志的非协作路径，测试铁证1）
                control.resume({"cancelled": True})
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                    pass
            await _finalize_once(_task_result(task) if task.done() else final)

    # ============================================================
    # 收尾（结算 / 释放 / 状态）
    # ============================================================
    @classmethod
    async def _finalize(cls, ctx: ExecutionContext, final: Dict[str, Any],
                        writer: TraceWriter) -> None:
        execution_id = ctx.execution_id
        status = final.get("status") or STATUS_FAILED
        if status == "success":
            status = STATUS_SUCCESS
        elif status not in (STATUS_CANCELLED, STATUS_INTERRUPTED):
            status = STATUS_FAILED
        try:
            # BUG-T15-014：收尾状态落库加超时保护（同 BUG-013 思路，防 DB 间歇挂起卡死收尾）
            await asyncio.wait_for(
                cls._update_status(
                    execution_id, status,
                    error=(final.get("error") or {}).get("message") or None,
                    output=final.get("outputs") or None,
                ),
                timeout=10.0,
            )
        except Exception as e:
            logger.error(f"[engine] 执行状态落库失败 execution_id={execution_id}: {e}")
        # 释放剩余预占（已节点结算部分由 settle 转正式）
        try:
            if ctx.quota_hold_id:
                await QuotaService.quota_release(ctx.quota_hold_id)
        except Exception as e:
            logger.error(f"[engine] 配额预占释放失败 execution_id={execution_id}: {e}")
        # 并发槽释放
        try:
            await QuotaService.release_concurrency(ctx.owner)
        except Exception as e:
            logger.error(f"[engine] 并发槽释放失败 execution_id={execution_id}: {e}")
        cls._controls.pop(execution_id, None)
        await TraceService.close_writer(execution_id)
        logger.info(
            f"[engine] 执行结束 execution_id={execution_id} status={status} "
            f"tokens={final.get('tokens')}"
        )

    @staticmethod
    async def _update_status(execution_id: int, status: str, *,
                             error: Optional[str] = None,
                             output: Optional[Dict[str, Any]] = None) -> None:
        execution = await WorkflowExecution.get_or_none(id=execution_id)
        if execution is None:
            return
        execution.status = status
        if error is not None:
            execution.error_message = error[:2000]
        if output is not None:
            execution.output_data = output
        if status in (STATUS_SUCCESS, STATUS_FAILED, STATUS_CANCELLED, STATUS_INTERRUPTED):
            # BUG-T15-003 修复：统一使用 UTC（与 Tortoise auto_now_add / dialog_flow_service 对齐）
            execution.completed_at = datetime.utcnow()
        await execution.save()

    @classmethod
    async def _update_status_guarded(cls, execution_id: int, status: str, **kw) -> None:
        """带超时保护的状态落库（BUG-T15-013：供后台 task 调用，防 DB 间歇挂起致 task 泄漏卡死）"""
        try:
            await asyncio.wait_for(cls._update_status(execution_id, status, **kw), timeout=10.0)
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"[engine] 状态落库超时/失败 execution_id={execution_id} status={status}: "
                         f"{type(e).__name__}: {e}")

    @classmethod
    async def _settle_node_usage(cls, ctx: ExecutionContext, event: Dict[str, Any]) -> None:
        """每节点结算（R-09：幂等键 execution_id+node_id+seq）"""
        usage = (event.get("payload") or {}).get("usage") or {}
        tokens_in = int(usage.get("tokens_in") or 0)
        tokens_out = int(usage.get("tokens_out") or 0)
        resource_type = usage.get("resource_type")
        amount = usage.get("amount")
        entries: List[Dict[str, Any]] = []
        if tokens_in or tokens_out:
            entries.append({
                "execution_id": ctx.execution_id,
                "node_id": event.get("node_id"),
                "seq": event.get("seq") or 0,
                "resource_type": "token",
                "amount": tokens_in + tokens_out,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "model": usage.get("model"),
            })
        elif resource_type and amount:
            entries.append({
                "execution_id": ctx.execution_id,
                "node_id": event.get("node_id"),
                "seq": event.get("seq") or 0,
                "resource_type": resource_type,
                "amount": amount,
            })
        if not entries:
            return
        try:
            await QuotaService.quota_settle(ctx.quota_hold_id or None, entries, owner=ctx.owner)
        except Exception as e:
            logger.error(f"[engine] 节点结算失败 execution_id={ctx.execution_id}: {e}")

    @staticmethod
    async def _heartbeat(ctx: ExecutionContext, queue: Optional[asyncio.Queue] = None) -> None:
        """并发槽看门狗心跳（03-§2.3：60s 兜底，30s 周期续期）
        + SSE 心跳帧（BUG-T15-014：15s 注入 comment 帧，静默期断开写失败可被传输层感知）"""
        tick = 0
        try:
            while True:
                await asyncio.sleep(SSE_PING_INTERVAL_S)
                tick += 1
                if tick * SSE_PING_INTERVAL_S >= HEARTBEAT_INTERVAL_S:
                    tick = 0
                    await QuotaService.heartbeat_concurrency(ctx.owner)
                if queue is not None:
                    await queue.put({"__ping__": True})
        except asyncio.CancelledError:
            pass

    # ============================================================
    # 取消（F5 协作式）
    # ============================================================
    @classmethod
    async def cancel(cls, execution_id: int) -> str:
        """
        请求取消：置位取消标记；HITL 等待中的同步解除等待由引擎检测取消标志处理。
        返回当前状态（重复取消幂等）。

        BUG-T15-014：置位后等待引擎 ack 回执（CANCEL_ACK_TIMEOUT_S）；超时说明 runner
        卡死/传输层异常（如 SSE 断开后唤醒失效），走保底强制收尾，杜绝并发槽永久泄漏。
        """
        execution = await WorkflowExecution.get_or_none(id=execution_id)
        if execution is None:
            return "not_found"
        if execution.status not in (STATUS_RUNNING, STATUS_PAUSED):
            return execution.status
        control = cls._controls.get(execution_id)
        if control is not None:
            control.ack_event.clear()  # 清历史回执，防误判（紧邻置位，窗口安全）
            control.request_cancel()
            control.resume({"cancelled": True})  # 解除 HITL 等待，引擎下一个检查点抛 ExecutionCancelled
            # v2：runner 已终结则无需等 ack（收尾由 done_callback 兜底完成，直接返回）
            if control.runner_task is not None and control.runner_task.done():
                return STATUS_CANCELLED
            try:
                await asyncio.wait_for(control.ack_event.wait(), timeout=CANCEL_ACK_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.critical(
                    f"[engine] cancel 唤醒无回执 execution_id={execution_id}，"
                    f"{CANCEL_ACK_TIMEOUT_S}s 超时，强制收尾（保底自救）"
                )
                await cls._force_finalize(
                    control, execution_id,
                    owner=(execution.owner_type, execution.owner_id),
                    status=STATUS_CANCELLED, error="已被用户取消（唤醒无响应，强制收尾）",
                )
            return STATUS_CANCELLED
        # 无活动控制面（消费端已断开等）：直接标记取消
        await cls._update_status(execution_id, STATUS_CANCELLED,
                                 error="已被用户取消")
        await TraceWriter.mark_cancelled_state(execution_id)
        return STATUS_CANCELLED

    @classmethod
    async def _force_finalize(cls, control, execution_id: int, *,
                              owner: Tuple[str, int], status: str, error: str) -> None:
        """BUG-T15-014 保底自救：cancel/resume 唤醒失效时强制收尾（落库终态 + 释放并发槽 +
        停心跳 + 清注册表 + Trace flush）。与 runner done_callback 的 _finalize_once 经
        control.finalize_lock/finalized 互斥，防双重释放并发槽。"""
        inc_force_finalize(status=status)  # M-4 监控埋点：保底触发即协作路径失效信号
        logger.warning(
            f"[engine] 保底强制收尾 execution_id={execution_id} status={status} "
            f"runner_done={control.runner_task.done() if control.runner_task else None} "
            f"finalized={control.finalized}"
        )
        if control.runner_task is not None and not control.runner_task.done():
            control.runner_task.cancel()
        async with control.finalize_lock:
            if control.finalized:
                return
            control.finalized = True
        if control.heartbeat_task is not None:
            control.heartbeat_task.cancel()
        if control.ctx is not None and control.writer is not None:
            # shield 保护：即便调用方（HTTP handler）被取消，收尾主体在独立 task 中必达
            await asyncio.shield(cls._finalize(
                control.ctx,
                {"status": status, "error": {"code": "FORCE_FINALIZE", "message": error}},
                control.writer,
            ))
            return
        # 引用缺失的极端兜底（generator 未正常启动）：至少落库终态 + 释放并发槽 + 清注册表
        await cls._update_status_guarded(execution_id, status, error=error)
        try:
            await QuotaService.release_concurrency(owner)
        except Exception as e:
            logger.error(f"[engine] 保底释放并发槽失败 execution_id={execution_id}: {e}")
        cls._controls.pop(execution_id, None)
        try:
            await TraceService.close_writer(execution_id)
        except Exception:
            pass

    # ============================================================
    # HITL 恢复（F6：paused → running 状态机，幂等）
    # ============================================================
    @classmethod
    async def resume(cls, execution_id: int, *, approved: bool,
                     comment: str = "") -> Tuple[bool, str]:
        """
        注入审批结果并恢复执行。

        Returns:
            (accepted, status)：仅 paused → running 合法；重复提交返回当前状态（幂等）
        """
        execution = await WorkflowExecution.get_or_none(id=execution_id)
        if execution is None:
            return False, "not_found"
        if execution.status != STATUS_PAUSED:
            return False, execution.status
        control = cls._controls.get(execution_id)
        if control is None:
            return False, "no_active_control"
        control.ack_event.clear()  # BUG-T15-014：清历史回执，紧邻置位窗口安全
        await cls._update_status(execution_id, STATUS_RUNNING)
        control.resume({"approved": approved, "comment": comment})
        # BUG-T15-014：唤醒确认——hitl 唤醒后引擎回执 ack；超时说明 runner 已死/传输层异常，
        # 恢复无从谈起，状态收敛 interrupted 并强制收尾（防 running 僵尸 + 槽永久泄漏）
        if control.runner_task is not None and control.runner_task.done():
            # v2：runner 已终结，恢复无从谈起（边缘窗口：_finalize 落库前 resume 到达）
            logger.critical(
                f"[engine] resume 时 runner 已终结 execution_id={execution_id}，"
                f"强制收尾 interrupted（保底自救）"
            )
            await cls._force_finalize(
                control, execution_id,
                owner=(execution.owner_type, execution.owner_id),
                status=STATUS_INTERRUPTED, error="runner 已终结，执行无法恢复（保底收尾）",
            )
            return False, STATUS_INTERRUPTED
        try:
            await asyncio.wait_for(control.ack_event.wait(), timeout=CANCEL_ACK_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.critical(
                f"[engine] resume 唤醒无回执 execution_id={execution_id}，"
                f"{CANCEL_ACK_TIMEOUT_S}s 超时，强制收尾（保底自救）"
            )
            await cls._force_finalize(
                control, execution_id,
                owner=(execution.owner_type, execution.owner_id),
                status=STATUS_INTERRUPTED, error="恢复唤醒无响应，执行已中断（保底收尾）",
            )
            return False, STATUS_INTERRUPTED
        return True, STATUS_RUNNING

    # ============================================================
    # 断点标记（F5：进程重启后运行中实例标记 interrupted，P0 不自动恢复）
    # ============================================================
    @classmethod
    async def mark_interrupted_on_startup(cls) -> int:
        """启动任务：running/paused → interrupted；悬挂预占由 M9 清理任务兜底（AR-08）"""
        count = await WorkflowExecution.filter(
            status__in=[STATUS_RUNNING, STATUS_PAUSED]
        ).update(
            status=STATUS_INTERRUPTED,
            error_message="进程重启，执行实例标记中断（P0 不自动恢复）",
            # BUG-T15-003 修复：统一使用 UTC（与 Tortoise auto_now_add / dialog_flow_service 对齐）
            completed_at=datetime.utcnow(),
        )
        if count:
            logger.critical(
                f"[engine] 启动断点标记：{count} 个运行中实例标记 interrupted"
            )
        return count

    # ============================================================
    # 查询（用户侧列表/详情）
    # ============================================================
    @staticmethod
    async def list_executions(owner: OwnerContext, *, workflow_id: Optional[int] = None,
                              kind: Optional[str] = None, skip: int = 0,
                              limit: int = 50) -> List[WorkflowExecution]:
        query = WorkflowExecution.filter(
            owner_type=owner.owner_type, owner_id=owner.owner_id
        )
        if workflow_id:
            query = query.filter(workflow_id=workflow_id)
        if kind:
            query = query.filter(kind=kind)
        return await query.order_by("-created_at").offset(skip).limit(min(limit, 200))

    @staticmethod
    async def get_execution(owner: OwnerContext, execution_id: int) -> Optional[WorkflowExecution]:
        return await WorkflowExecution.get_or_none(
            id=execution_id, owner_type=owner.owner_type, owner_id=owner.owner_id
        )
