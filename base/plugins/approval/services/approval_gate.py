"""
审批门禁 + 执行器（审批模块独立，不依赖 BaseBusinessService）

职责：
1. 提供 ``NeedApprovalError`` —— 命中审批规则时抛出，由全局异常处理器
   转成 ``code=40001`` JSON，前端拦截器捕获。
2. 提供 ``gate_write(model, action, payload, business_id, applicant_id, title)`` ——
   按模型+动作查 approval_flow 表（流程本身即审批规则），命中则自动创建审批实例并抛
   NeedApprovalError；否则静默放行（判定异常默认放行）。
3. ``register_executor`` / ``APPROVAL_EXECUTORS`` —— 执行器注册表，存
   ``(model, action) -> (service_cls, method_name)``。可通过手动调用 register_executor
   登记，供审批通过后回调落库。
4. ``ApprovalExecutor.execute(instance)`` —— 审批实例通过完成时，按
   ``(business_type, action)`` 从注册表取 ``(cls, method)`` 回调落库。

设计要点：
- 门禁与执行分离：前端通过 /v1/approval/flow-rules/check-for-model 检测审批规则，
  确认后调用 /v1/approval/flow-rules/submit-for-approval 提交审批。
- 审批决策来源：``FlowService.check_approval_required_by_model`` 查询
  流程（approval_flow）表的 model/action/methods/priority 字段（后台配置）。
- 参数约定：
  create  -> method(payload)
  update  -> method(business_id, payload)
  delete  -> method(business_id)
- 所有跨模块导入均延迟到函数内，避免循环依赖。
"""
from typing import Any, Dict, Optional, Tuple, Type

from loguru import logger


# action -> HTTP method（审批规则 methods 存的是 HTTP 方法）
ACTION_TO_METHOD = {
    "create": "POST",
    "update": "PUT",
    "delete": "DELETE",
}


class NeedApprovalError(Exception):
    """命中审批规则时抛出，由异常处理器转成 40001 响应。"""

    def __init__(
        self,
        instance_id: int,
        flow_id: int,
        flow_name: str,
        model: str,
        action: str,
        business_type: Optional[str] = None,
    ):
        self.instance_id = instance_id
        self.flow_id = flow_id
        self.flow_name = flow_name
        self.model = model
        self.action = action
        self.business_type = business_type or model
        super().__init__(f"操作需要审批: {model}/{action} (instance={instance_id})")


# (model, action) -> (service_cls, method_name)
# 可通过手动调用 register_executor 登记，供审批通过后回调落库
APPROVAL_EXECUTORS: Dict[tuple, Tuple[Type, str]] = {}


def register_executor(model: str, action: str, service_cls: Type, method_name: str) -> None:
    """登记原始实现（不带门禁），供审批通过后回调。"""
    APPROVAL_EXECUTORS[(model, action)] = (service_cls, method_name)


def _to_dict(obj: Any) -> Any:
    """把可能为 Pydantic Model 的参数转成 dict，便于 JSON 存储与回放。"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return obj.dict()
        except Exception:
            pass
    return obj


async def gate_write(
    model: str,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    business_id: Optional[int] = None,
    applicant_id: Optional[int] = None,
    title: Optional[str] = None,
) -> None:
    """
    审批门禁核心。命中规则则自动建审批实例并抛 NeedApprovalError；否则静默放行。

    :param model: 业务模型标识，如 purchase_order
    :param action: create / update / delete
    :param payload: 业务数据快照（dict），存于 instance.business_data
    :param business_id: 业务对象 ID（update/delete 用）
    :param applicant_id: 申请人；缺省从 current_user_id 上下文取
    :param title: 审批标题；缺省自动生成
    """
    try:
        if applicant_id is None:
            from base.common.context import current_user_id
            applicant_id = current_user_id.get()

        # 没有申请人上下文无法建单，记录并放行（避免阻断正常业务）
        if applicant_id is None:
            logger.warning("审批门禁：缺少申请人上下文，跳过审批判定（放行）")
            return

        from base.plugins.approval.services.flow_service import FlowService
        from base.plugins.approval.services.instance_service import InstanceService
        from base.plugins.approval.schemas.instance_schema import InstanceCreate

        method = ACTION_TO_METHOD.get(action, "POST")
        check = await FlowService.check_approval_required_by_model(model, method)
        if not check.get("require_approval"):
            return

        # 命中规则：建审批实例（含 action + payload 快照）
        instance_payload = _to_dict(payload) if payload is not None else {}
        title = title or f"{model} {action} 审批"
        instance_data = InstanceCreate(
            business_type=model,
            business_id=business_id,
            title=title,
            business_data=instance_payload,
            form_data={},
            action=action,
        )
        instance = await InstanceService.create_instance(instance_data, applicant_id)

        logger.info(
            f"审批门禁拦截: model={model}, action={action}, "
            f"instance={instance.id}, flow={check.get('flow_name')}"
        )
        raise NeedApprovalError(
            instance_id=instance.id,
            flow_id=check["flow_id"],
            flow_name=check["flow_name"],
            model=model,
            action=action,
        )
    except NeedApprovalError:
        raise
    except Exception as e:
        # 判定异常不应阻断业务，记录日志后放行（与原中间件一致）
        logger.error(f"审批门禁判定异常，放行: {e}")
        return


class ApprovalExecutor:
    """审批通过后的业务执行器：按 (model, action) 回调原始实现真正落库。"""

    @staticmethod
    async def execute(instance) -> None:
        """
        审批实例通过完成时调用。

        从注册表取 ``(service_cls, method_name)``，通过 ``getattr`` 触发
        classmethod 描述符协议自动绑定 cls，确保回调正确。
        """
        model = getattr(instance, "business_type", None)
        action = getattr(instance, "action", None)
        if not model or not action:
            logger.warning("审批执行器：实例缺少 business_type/action，跳过")
            return

        entry = APPROVAL_EXECUTORS.get((model, action))
        if not entry:
            logger.warning(f"审批执行器：未找到执行器 {model}/{action}，跳过")
            return

        service_cls, method_name = entry
        method = getattr(service_cls, method_name, None)
        if method is None:
            logger.warning(f"审批执行器：{service_cls.__name__}.{method_name} 不存在，跳过")
            return

        payload = getattr(instance, "business_data", None) or {}
        business_id = getattr(instance, "business_id", None)

        try:
            if action == "create":
                await method(payload)
            elif action == "update":
                await method(business_id, payload)
            elif action == "delete":
                await method(business_id)
            else:
                logger.warning(f"审批执行器：未知 action={action}，跳过")
                return
            logger.info(
                f"审批通过自动执行成功: {model}/{action} instance={instance.id}"
            )
        except Exception as e:
            # 执行失败：审批状态已置为 approved，记录错误日志，不回滚状态
            logger.error(
                f"审批通过自动执行失败 instance={instance.id} ({model}/{action}): {e}"
            )
            # 失败信息回写到实例 result，便于排查
            try:
                instance.result = f"自动执行失败: {e}"
                await instance.save(update_fields=["result"])
            except Exception:
                pass
            raise
