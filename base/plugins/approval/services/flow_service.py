"""
流程定义 Service（同时承载审批规则的匹配能力）
"""
import ast
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from tortoise.expressions import Q
from loguru import logger

from base.plugins.approval.models.approval_flow import ApprovalFlow
from base.plugins.approval.schemas.flow_schema import FlowCreate, FlowUpdate, FlowListQuery


# ---------------------------------------------------------------------------
# 插件扫描：业务模型（service）与 ORM 模型（中文名）元数据
# ---------------------------------------------------------------------------
_PLUGIN_SCAN_CACHE = None


def _snake(name: str) -> str:
    """CamelCase -> snake_case。"""
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def _is_tortoise_model(node) -> bool:
    """粗略判断 AST 节点是否为 Tortoise 模型类。"""
    if not isinstance(node, ast.ClassDef):
        return False
    for stmt in node.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
            return True
    for base in node.bases:
        bname = base.id if isinstance(base, ast.Name) else (base.attr if isinstance(base, ast.Attribute) else "")
        if bname in ("Model", "BaseModel", "TimestampMixin"):
            return True
    return False


def _scan_plugins():
    """扫描所有插件，返回 (services, model_meta)。

    扫描所有 service 类中定义了 ``model`` 类变量的类（不再依赖 BaseBusinessService 继承）。
    services: [{"model", "plugin", "methods"}]
    model_meta: {plugin: [{"table","classname","verbose_name","table_description"}]}
    """
    global _PLUGIN_SCAN_CACHE
    if _PLUGIN_SCAN_CACHE is not None:
        return _PLUGIN_SCAN_CACHE

    plugins_dir = Path(__file__).resolve().parent.parent.parent
    services: List[Dict[str, Any]] = []
    model_meta: Dict[str, List[Dict[str, Any]]] = {}

    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue
        plugin = plugin_dir.name
        services_dir = plugin_dir / "services"
        models_dir = plugin_dir / "models"

        if services_dir.is_dir():
            for service_file in services_dir.rglob("*.py"):
                if service_file.name == "__init__.py":
                    continue
                try:
                    tree = ast.parse(service_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    # 扫描所有定义了 model 类变量的 Service 类（不再依赖 BaseBusinessService 继承）
                    model_val = None
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for t in stmt.targets:
                                if isinstance(t, ast.Name) and t.id == "model":
                                    if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                                        model_val = stmt.value.value
                                    break
                    if not model_val:
                        continue
                    methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                    services.append({"model": model_val, "plugin": plugin, "methods": methods})

        if models_dir.is_dir():
            for model_file in models_dir.rglob("*.py"):
                if model_file.name in ("__init__.py", "base.py"):
                    continue
                try:
                    tree = ast.parse(model_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for node in ast.walk(tree):
                    if not _is_tortoise_model(node):
                        continue
                    table = None
                    verbose_name = None
                    table_description = None
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for t in stmt.targets:
                                if isinstance(t, ast.Name) and t.id == "verbose_name":
                                    if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                                        verbose_name = stmt.value.value
                        elif isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
                            for mstmt in stmt.body:
                                if isinstance(mstmt, ast.Assign):
                                    for mt in mstmt.targets:
                                        if isinstance(mt, ast.Name) and mt.id == "table":
                                            if isinstance(mstmt.value, ast.Constant) and isinstance(mstmt.value.value, str):
                                                table = mstmt.value.value
                                        if isinstance(mt, ast.Name) and mt.id == "table_description":
                                            if isinstance(mstmt.value, ast.Constant) and isinstance(mstmt.value.value, str):
                                                table_description = mstmt.value.value
                    model_meta.setdefault(plugin, []).append({
                        "table": table,
                        "classname": node.name,
                        "verbose_name": verbose_name,
                        "table_description": table_description,
                    })

    _PLUGIN_SCAN_CACHE = (services, model_meta)
    return _PLUGIN_SCAN_CACHE


class FlowService:
    """审批流程定义服务"""

    # 合法的审批方式（对应 ApprovalEngine.APPROVE_*）
    VALID_APPROVE_TYPES = {"single", "or", "joint"}
    # 合法的审批人来源（对应 ApprovalEngine.get_approver_ids）
    VALID_APPROVER_TYPES = {"user", "role", "dept_head", "dynamic"}
    # 合法的节点类型
    VALID_NODE_TYPES = {"start", "approve", "condition", "fork", "join", "end"}

    @staticmethod
    def validate_flow_config(config: Dict[str, Any]) -> List[str]:
        """校验 flow_config 结构合法性，返回错误信息列表（空列表表示校验通过）。

        仅做结构校验，不触碰引擎与实例流转逻辑；plugin 启用后 engine 已能解析该结构。
        """
        if not config or not isinstance(config, dict):
            return ["流程配置不能为空"]

        nodes = config.get("nodes")
        edges = config.get("edges")
        if not isinstance(nodes, list) or not nodes:
            return ["流程配置必须包含至少一个节点"]
        if not isinstance(edges, list):
            return ["流程配置 edges 必须为数组"]

        node_ids: set = set()
        start_count = 0
        end_count = 0

        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                return [f"第 {idx + 1} 个节点格式非法"]
            node_id = node.get("id")
            if not node_id:
                return [f"第 {idx + 1} 个节点缺少 id"]
            if node_id in node_ids:
                return [f"节点 id 重复: {node_id}"]
            node_ids.add(node_id)

            node_type = node.get("type")
            if node_type == "start":
                start_count += 1
            elif node_type == "end":
                end_count += 1
            elif node_type == "approve":
                approve_type = node.get("approve_type")
                if approve_type not in FlowService.VALID_APPROVE_TYPES:
                    return [f"审批节点 {node_id} 的审批方式(approve_type)非法: {approve_type}（应为 single/or/joint）"]
                approver_config = node.get("approver_config") or {}
                approver_type = approver_config.get("type")
                if approver_type not in FlowService.VALID_APPROVER_TYPES:
                    return [f"审批节点 {node_id} 的审批人来源(approver_config.type)非法: {approver_type}（应为 user/role/dept_head/dynamic）"]
                if approver_type == "user" and not approver_config.get("user_ids"):
                    return [f"审批节点 {node_id} 选择了「指定用户」但未选择任何用户"]
                if approver_type == "role" and not approver_config.get("role_ids"):
                    return [f"审批节点 {node_id} 选择了「按角色」但未选择任何角色"]
                # dept_head / dynamic 允许不指定部门（取申请人部门）
            elif node_type == "condition":
                if not node.get("field"):
                    return [f"条件节点 {node_id} 缺少字段(field)"]
                if not node.get("operator"):
                    return [f"条件节点 {node_id} 缺少运算符(operator)"]
                if "value" not in node:
                    return [f"条件节点 {node_id} 缺少值(value)"]
            elif node_type not in FlowService.VALID_NODE_TYPES:
                return [f"未知节点类型: {node_type}（节点 {node_id}）"]

        if start_count != 1:
            return [f"必须且只能有 1 个开始节点（当前 {start_count} 个）"]
        if end_count < 1:
            return ["至少需要 1 个结束节点"]

        for idx, edge in enumerate(edges):
            if not isinstance(edge, dict):
                return [f"第 {idx + 1} 条边格式非法"]
            source = edge.get("source")
            target = edge.get("target")
            if source not in node_ids:
                return [f"第 {idx + 1} 条边的起点(source)不存在: {source}"]
            if target not in node_ids:
                return [f"第 {idx + 1} 条边的终点(target)不存在: {target}"]

        return []

    @staticmethod
    async def create_flow(data: FlowCreate) -> ApprovalFlow:
        """创建流程"""
        # 校验流程配置结构
        errors = FlowService.validate_flow_config(data.flow_config)
        if errors:
            raise ValueError("；".join(errors))

        # 检查编码是否已存在
        existing = await ApprovalFlow.get_or_none(code=data.code)
        if existing:
            raise ValueError(f"流程编码 {data.code} 已存在")

        flow = await ApprovalFlow.create(
            name=data.name,
            code=data.code,
            description=data.description,
            form_config=data.form_config,
            flow_config=data.flow_config,
            business_type=data.business_type,
            model=data.model or data.business_type,
            action=data.action,
            methods=data.methods,
            priority=data.priority,
            is_active=data.is_active,
            route_patterns=data.route_patterns or [],
        )
        return flow

    @staticmethod
    async def update_flow(flow_id: int, data: FlowUpdate) -> Optional[ApprovalFlow]:
        """更新流程"""
        flow = await ApprovalFlow.get_or_none(id=flow_id)
        if not flow:
            return None

        # 若本次更新包含 flow_config，先校验结构
        if data.flow_config is not None:
            errors = FlowService.validate_flow_config(data.flow_config)
            if errors:
                raise ValueError("；".join(errors))

        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(flow, key, value)

        await flow.save()
        return flow

    @staticmethod
    async def delete_flow(flow_id: int) -> bool:
        """删除流程"""
        flow = await ApprovalFlow.get_or_none(id=flow_id)
        if not flow:
            return False

        if flow.is_system:
            raise ValueError("系统预设流程不可删除")

        await flow.delete()
        return True

    @staticmethod
    async def get_flow(flow_id: int) -> Optional[ApprovalFlow]:
        """获取流程"""
        return await ApprovalFlow.get_or_none(id=flow_id)

    @staticmethod
    async def get_flow_by_code(code: str) -> Optional[ApprovalFlow]:
        """根据编码获取流程"""
        return await ApprovalFlow.get_or_none(code=code)

    @staticmethod
    async def get_flow_by_business_type(business_type: str) -> Optional[ApprovalFlow]:
        """根据业务类型获取启用的流程"""
        return await ApprovalFlow.get_or_none(
            business_type=business_type,
            is_active=True
        )

    @staticmethod
    async def get_flow_list(query: FlowListQuery) -> Dict[str, Any]:
        """获取流程列表"""
        q = Q()
        if query.name:
            q &= Q(name__icontains=query.name)
        if query.business_type:
            q &= Q(business_type=query.business_type)
        if query.model:
            q &= Q(model=query.model)
        if query.action:
            q &= Q(action=query.action)
        if query.is_active is not None:
            q &= Q(is_active=query.is_active)

        total = await ApprovalFlow.filter(q).count()
        flows = await ApprovalFlow.filter(q).offset(
            (query.page - 1) * query.page_size
        ).limit(query.page_size)

        return {
            "total": total,
            "items": [await flow.to_dict() for flow in flows],
            "page": query.page,
            "page_size": query.page_size
        }

    @staticmethod
    async def toggle_flow_status(flow_id: int, is_active: bool) -> Optional[ApprovalFlow]:
        """切换流程启用状态"""
        flow = await ApprovalFlow.get_or_none(id=flow_id)
        if not flow:
            return None
        flow.is_active = is_active
        await flow.save()
        return flow

    @staticmethod
    def get_available_models() -> List[Dict[str, str]]:
        """获取所有可用的业务模型（用于流程规则配置）。

        标识（model）取自各插件的 ``BaseBusinessService`` 子类（审批门禁实际使用的标识），
        中文名优先读取 ORM 模型类的 ``verbose_name``，其次 ``Meta.table_description``，
        再回退到 model 本身。展示格式：``中文(model)``。
        """
        services, model_meta = _scan_plugins()
        result: List[Dict[str, str]] = []
        for s in services:
            model = s["model"]
            plugin = s["plugin"]
            cn = None
            for m in model_meta.get(plugin, []):
                tbl = m["table"] or ""
                stripped = tbl[len(plugin) + 1:] if tbl.startswith(plugin + "_") else tbl
                match = (
                    tbl == model
                    or tbl == f"{plugin}_{model}"
                    or _snake(m["classname"]) == model
                    or stripped == model
                )
                if match:
                    cn = m["verbose_name"] or m["table_description"]
                    break
            label = f"{cn}({model})" if cn else model
            result.append({"model": model, "label": label})
        result.sort(key=lambda x: x["model"])
        return result

    @staticmethod
    def get_model_actions(model: str) -> List[Dict[str, str]]:
        """返回指定模型可配置的审批动作（create/update/delete）。

        仅检查 _scan_plugins 中是否存在该 model，存在即返回标准三动作。
        """
        services, _ = _scan_plugins()
        for s in services:
            if s["model"] != model:
                continue
            return [
                {"value": "create", "label": "创建(create)"},
                {"value": "update", "label": "更新(update)"},
                {"value": "delete", "label": "删除(delete)"},
            ]
        return []

    @staticmethod
    async def get_matched_flow_by_model(model: str, method: str) -> Optional[ApprovalFlow]:
        """
        根据业务模型和方法获取匹配的流程（按 model + methods + action 匹配，取代原规则表）。

        - 仅匹配启用且 model 命中的流程；
        - HTTP 方法必须在流程 ``methods`` 列表中；
        - 流程指定了 action 时，仅匹配该动作；未指定则匹配全部动作（向后兼容）；
        - 同一 model+action 命中多条流程时按优先级（priority）取最高。
        """
        action = {"POST": "create", "PUT": "update", "DELETE": "delete"}.get(method)
        flows = await ApprovalFlow.filter(is_active=True, model=model).order_by("-priority").all()
        for flow in flows:
            if method not in (flow.methods or []):
                continue
            # 流程指定了 action 时，仅匹配该动作；未指定则匹配全部动作（向后兼容）
            if flow.action and action and flow.action != action:
                continue
            return flow
        return None

    @staticmethod
    async def check_approval_required_by_model(model: str, method: str) -> Dict[str, Any]:
        """
        根据业务模型和方法检查是否需要审批（基于模型匹配的核心入口）。
        返回: {
            "require_approval": bool,
            "flow_id": int,
            "flow_name": str,
            "model": str
        }
        """
        flow = await FlowService.get_matched_flow_by_model(model, method)
        if not flow:
            return {
                "require_approval": False,
                "flow_id": None,
                "flow_name": None,
                "model": model
            }

        return {
            "require_approval": True,
            "flow_id": flow.id,
            "flow_name": flow.name,
            "model": model
        }

    # ------------------------------------------------------------------
    # 路由匹配：全局审批组件按当前前端路由反查命中的流程
    # ------------------------------------------------------------------

    @staticmethod
    def _route_pattern_to_regex(pattern: str) -> "re.Pattern":
        """把 vue-router 风格路由模式转正则。

        ``/panel/purchase/order/:id`` -> ``^/panel/purchase/order/([^/]+)$``
        其余字符按字面转义。
        """
        # 先按 / 分段，逐段处理：:param 段替换为 [^/]+，其余段转义
        segments = pattern.split("/")
        regex_parts = []
        for seg in segments:
            if seg.startswith(":"):
                regex_parts.append(r"([^/]+)")
            else:
                regex_parts.append(re.escape(seg))
        return re.compile("^" + "/".join(regex_parts) + "$")

    @staticmethod
    async def match_route_to_flows(route: str) -> List[ApprovalFlow]:
        """加载所有启用且 route_patterns 非空的流程，返回命中的流程列表（按 priority 降序）。"""
        if not route:
            return []
        flows = await ApprovalFlow.filter(is_active=True).order_by("-priority").all()
        matched = []
        for flow in flows:
            patterns = flow.route_patterns or []
            if not patterns:
                continue
            for pat in patterns:
                if not isinstance(pat, str) or not pat:
                    continue
                if FlowService._route_pattern_to_regex(pat).match(route):
                    matched.append(flow)
                    break
        return matched

    @staticmethod
    async def build_approval_context(
        model: str,
        business_id: Optional[int],
        user_id: int,
    ) -> Dict[str, Any]:
        """构建审批上下文：合并流程规则、实例状态、当前用户的审批任务。

        供 /context 与 /context-by-route 复用，返回前端可直接用于渲染审批按钮的数据。
        """
        from base.plugins.approval.models.approval_instance import ApprovalInstance
        from base.plugins.approval.models.approval_task import ApprovalTask

        flows = await ApprovalFlow.filter(is_active=True, model=model).order_by("-priority").all()
        flow_list = []
        all_actions = set()

        for flow in flows:
            actions = []
            if flow.action:
                actions.append(flow.action)
            else:
                m_to_a = {"POST": "create", "PUT": "update", "DELETE": "delete"}
                actions = [m_to_a[m] for m in (flow.methods or []) if m in m_to_a]
            all_actions.update(actions)
            flow_list.append({
                "flow_id": flow.id,
                "flow_name": flow.name,
                "flow_code": flow.code,
                "actions": actions,
                "methods": flow.methods,
                "priority": flow.priority,
                "business_type": flow.business_type,
            })

        has_flow = len(flow_list) > 0

        instance_data = None
        pending_tasks_data: List[Dict[str, Any]] = []
        can_approve = False
        can_cancel = False

        if business_id is not None:
            instance = await ApprovalInstance.get_or_none(
                business_type=model, business_id=business_id
            )
            if instance:
                instance_data = await instance.to_dict(include_flow=True) if hasattr(instance, "to_dict") else None
                if instance_data is None and hasattr(instance, "to_dict"):
                    instance_data = await instance.to_dict()

                if instance.status == "pending":
                    tasks = await ApprovalTask.filter(
                        instance_id=instance.id, status="pending", approver_id=user_id
                    ).all()
                    pending_tasks_data = [await t.to_dict() for t in tasks]
                    can_approve = len(pending_tasks_data) > 0

                if instance.applicant_id == user_id and instance.status == "pending":
                    can_cancel = True

        has_pending_instance = bool(instance_data and instance_data.get("status") == "pending")
        can_submit = has_flow and not has_pending_instance

        return {
            "model": model,
            "business_id": business_id,
            "has_flow": has_flow,
            "flows": flow_list,
            "instance": instance_data,
            "pending_tasks": pending_tasks_data,
            "can_submit": can_submit,
            "can_approve": can_approve,
            "can_cancel": can_cancel,
            "can_create": "create" in all_actions,
            "can_update": "update" in all_actions,
            "can_delete": "delete" in all_actions,
        }

    @staticmethod
    async def get_context_by_route(
        route: str,
        business_id: Optional[int],
        user_id: int,
    ) -> Dict[str, Any]:
        """按当前前端路由反查命中的流程，返回审批上下文。

        - 命中流程取首个的 model 作为业务模型标识
        - mode: business_id 存在 -> detail，否则 list
        - 未命中任何流程 -> has_flow=False，全局组件据此隐藏
        """
        matched = await FlowService.match_route_to_flows(route)
        if not matched:
            return {
                "route": route,
                "model": None,
                "mode": "list" if business_id is None else "detail",
                "business_id": business_id,
                "has_flow": False,
                "flows": [],
                "instance": None,
                "pending_tasks": [],
                "can_submit": False,
                "can_approve": False,
                "can_cancel": False,
                "can_create": False,
                "can_update": False,
                "can_delete": False,
            }

        model = matched[0].model or matched[0].business_type
        mode = "detail" if business_id is not None else "list"
        ctx = await FlowService.build_approval_context(model, business_id, user_id)
        ctx["route"] = route
        ctx["mode"] = mode
        return ctx

    @staticmethod
    async def initialize_default_data():
        """初始化默认数据"""
        # 检查是否已存在默认流程
        existing = await ApprovalFlow.get_or_none(code="default_purchase_approval")
        if existing:
            return

        # 创建采购审批默认流程
        default_flow_config = {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "name": "开始",
                    "approver_config": {},
                    "approve_type": "single"
                },
                {
                    "id": "manager_approve",
                    "type": "approve",
                    "name": "部门经理审批",
                    "approver_config": {
                        "type": "dynamic",
                        "expression": "applicant.dept_head"
                    },
                    "approve_type": "single"
                },
                {
                    "id": "director_approve",
                    "type": "approve",
                    "name": "总监审批",
                    "approver_config": {
                        "type": "role",
                        "role_ids": [1]
                    },
                    "approve_type": "single"
                },
                {
                    "id": "end",
                    "type": "end",
                    "name": "结束",
                    "approver_config": {},
                    "approve_type": "single"
                }
            ],
            "edges": [
                {"source": "start", "target": "manager_approve", "type": "approve"},
                {"source": "manager_approve", "target": "director_approve", "type": "approve"},
                {"source": "director_approve", "target": "end", "type": "approve"},
                {"source": "manager_approve", "target": "end", "type": "reject"},
                {"source": "director_approve", "target": "end", "type": "reject"}
            ]
        }

        await ApprovalFlow.create(
            name="采购审批流程",
            code="default_purchase_approval",
            description="采购订单审批默认流程",
            form_config=[
                {"field": "title", "label": "标题", "type": "text", "required": True},
                {"field": "amount", "label": "金额", "type": "number", "required": True},
                {"field": "reason", "label": "事由", "type": "textarea", "required": False}
            ],
            flow_config=default_flow_config,
            business_type="purchase_order",
            model="purchase_order",
            action=None,
            methods=["POST", "PUT", "DELETE"],
            priority=100,
            is_active=True,
            is_system=True,
            route_patterns=["/panel/purchase/order", "/panel/purchase/order/:id"],
        )
        logger.info("创建默认采购审批流程")
