"""
审批引擎核心逻辑
负责处理审批流程的状态机、节点流转、会签/或签判断等核心逻辑
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger


class ApprovalEngine:
    """审批引擎"""

    # 节点类型
    NODE_START = "start"          # 开始节点
    NODE_APPROVE = "approve"      # 审批节点
    NODE_CONDITION = "condition"  # 条件节点
    NODE_FORK = "fork"            # 分支节点
    NODE_JOIN = "join"            # 汇聚节点
    NODE_END = "end"              # 结束节点

    # 审批类型
    APPROVE_SINGLE = "single"     # 单签（一人通过即可）
    APPROVE_JOINT = "joint"       # 会签（所有人都通过）
    APPROVE_OR = "or"             # 或签（任一通过即可）

    # 审批状态
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    @staticmethod
    def get_node_config(flow_config: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
        """从流程配置中获取节点配置"""
        nodes = flow_config.get("nodes", [])
        for node in nodes:
            if node.get("id") == node_id:
                return node
        return None

    @staticmethod
    def get_start_node(flow_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取开始节点"""
        nodes = flow_config.get("nodes", [])
        for node in nodes:
            if node.get("type") == ApprovalEngine.NODE_START:
                return node
        # 如果没有明确的开始节点，取第一个审批节点
        for node in nodes:
            if node.get("type") == ApprovalEngine.NODE_APPROVE:
                return node
        return None

    @staticmethod
    async def create_approval_tasks(instance, node_config: Dict[str, Any], approver_ids: List[int]):
        """为审批节点创建审批任务"""
        from base.plugins.approval.models.approval_task import ApprovalTask

        tasks = []
        for approver_id in approver_ids:
            task = await ApprovalTask.create(
                instance_id=instance.id,
                node_id=node_config["id"],
                approver_id=approver_id,
                status=ApprovalEngine.STATUS_PENDING
            )
            tasks.append(task)
        return tasks

    @staticmethod
    async def check_node_complete(instance, node_config: Dict[str, Any]) -> tuple:
        """
        检查当前节点是否完成
        返回: (is_complete, is_approved, next_action)
        - is_complete: 节点是否完成
        - is_approved: 是否通过（用于决定下一步）
        - next_action: 下一步动作
        """
        from base.plugins.approval.models.approval_task import ApprovalTask

        node_type = node_config.get("type")
        approve_type = node_config.get("approve_type", ApprovalEngine.APPROVE_SINGLE)

        # 查询该节点的所有任务
        tasks = await ApprovalTask.filter(
            instance_id=instance.id,
            node_id=node_config["id"]
        ).all()

        if not tasks:
            return False, False, None

        # 统计任务状态
        approved_count = sum(1 for t in tasks if t.status == "approved")
        rejected_count = sum(1 for t in tasks if t.status == "rejected")
        pending_count = sum(1 for t in tasks if t.status == "pending")

        # 如果有人拒绝，整个节点拒绝
        if rejected_count > 0:
            return True, False, "reject"

        # 根据审批类型判断节点是否完成
        if approve_type == ApprovalEngine.APPROVE_OR:
            # 或签：任一通过即完成
            if approved_count > 0:
                return True, True, "approve"
            if pending_count == 0 and approved_count == 0:
                return True, False, "reject"
            return False, False, None

        elif approve_type == ApprovalEngine.APPROVE_JOINT:
            # 会签：所有待审批都通过才完成
            if pending_count == 0 and approved_count == len(tasks):
                return True, True, "approve"
            if pending_count > 0:
                return False, False, None
            return True, approved_count == len(tasks), "approve" if approved_count == len(tasks) else "reject"

        else:
            # 单签：一人通过即可
            if approved_count > 0:
                return True, True, "approve"
            if pending_count == 0 and approved_count == 0:
                return True, False, "reject"
            return False, False, None

    @staticmethod
    def evaluate_condition(condition_config: Dict[str, Any], form_data: Dict[str, Any]) -> bool:
        """
        评估条件节点
        condition_config: {
            "field": "amount",
            "operator": ">",  # >, <, >=, <=, ==, !=, in, not_in, contains
            "value": 10000
        }
        """
        field = condition_config.get("field")
        operator = condition_config.get("operator", "==")
        target_value = condition_config.get("value")

        if field not in form_data:
            return False

        actual_value = form_data.get(field)

        try:
            if operator == ">":
                return float(actual_value) > float(target_value)
            elif operator == "<":
                return float(actual_value) < float(target_value)
            elif operator == ">=":
                return float(actual_value) >= float(target_value)
            elif operator == "<=":
                return float(actual_value) <= float(target_value)
            elif operator == "==":
                return str(actual_value) == str(target_value)
            elif operator == "!=":
                return str(actual_value) != str(target_value)
            elif operator == "in":
                return actual_value in target_value
            elif operator == "not_in":
                return actual_value not in target_value
            elif operator == "contains":
                return target_value in str(actual_value)
            else:
                logger.warning(f"未知的条件操作符: {operator}")
                return False
        except (ValueError, TypeError) as e:
            logger.error(f"条件评估失败: {e}")
            return False

    @staticmethod
    def get_next_node(flow_config: Dict[str, Any], current_node: Dict[str, Any],
                      form_data: Dict[str, Any], action: str = "approve") -> Optional[Dict[str, Any]]:
        """
        获取下一节点
        根据当前节点配置和表单数据，计算下一节点
        """
        edges = flow_config.get("edges", [])
        current_node_id = current_node.get("id")

        # 找到从当前节点出发的边
        candidate_edges = [e for e in edges if e.get("source") == current_node_id]

        if not candidate_edges:
            return None

        # 如果是条件节点，根据条件选择分支
        if current_node.get("type") == ApprovalEngine.NODE_CONDITION:
            for edge in candidate_edges:
                condition = edge.get("condition")
                if condition is None:
                    # 默认分支（条件不满足时的分支）
                    return ApprovalEngine.get_node_config(flow_config, edge.get("target"))
                if ApprovalEngine.evaluate_condition(condition, form_data):
                    return ApprovalEngine.get_node_config(flow_config, edge.get("target"))
            # 如果没有匹配的条件，返回默认分支
            for edge in candidate_edges:
                if edge.get("condition") is None:
                    return ApprovalEngine.get_node_config(flow_config, edge.get("target"))
            return None

        # 对于其他类型节点，根据 action 选择分支
        if action == "reject":
            # 拒绝时走 reject 分支（如果有）
            for edge in candidate_edges:
                if edge.get("type") == "reject":
                    return ApprovalEngine.get_node_config(flow_config, edge.get("target"))
            # 没有拒绝分支，直接结束
            return None

        # 通过时走默认分支
        for edge in candidate_edges:
            if edge.get("type") != "reject":
                return ApprovalEngine.get_node_config(flow_config, edge.get("target"))

        return None

    @staticmethod
    async def get_approver_ids(node_config: Dict[str, Any], instance, current_user_id: int = None) -> List[int]:
        """
        获取节点审批人ID列表
        node_config.approver_config: {
            "type": "user"|"role"|"dept_head"|"dynamic",
            "user_ids": [1, 2, 3],
            "role_ids": [1, 2],
            "dept_id": 1,
            "expression": "applicant.dept_head"
        }
        """
        approver_config = node_config.get("approver_config", {})
        approver_type = approver_config.get("type", "user")
        approver_ids = []

        try:
            if approver_type == "user":
                approver_ids = approver_config.get("user_ids", [])

            elif approver_type == "role":
                # 查询拥有指定角色的用户
                from base.core.users.models.rbac import Role
                role_ids = approver_config.get("role_ids", [])
                for role_id in role_ids:
                    role = await Role.get_or_none(id=role_id)
                    if role:
                        users = await role.users.all()
                        approver_ids.extend([u.id for u in users])

            elif approver_type == "dept_head":
                # 部门负责人
                dept_id = approver_config.get("dept_id")
                if dept_id is None and instance:
                    # 获取申请人的部门
                    from base.core.users.models.users import User
                    applicant = await User.get_or_none(id=instance.applicant_id)
                    dept_id = applicant.dept_id if applicant else None

                if dept_id:
                    from base.core.dept.models.department import Department
                    dept = await Department.get_or_none(id=dept_id)
                    if dept and dept.manager_id:
                        approver_ids = [dept.manager_id]

            elif approver_type == "dynamic":
                # 动态表达式（简单实现：支持 applicant.dept_head）
                expression = approver_config.get("expression", "")
                if expression == "applicant.dept_head" and instance:
                    from base.core.users.models.users import User
                    from base.core.dept.models.department import Department
                    applicant = await User.get_or_none(id=instance.applicant_id)
                    if applicant and applicant.dept_id:
                        dept = await Department.get_or_none(id=applicant.dept_id)
                        if dept and dept.manager_id:
                            approver_ids = [dept.manager_id]

            # 去重
            approver_ids = list(set(approver_ids))

        except Exception as e:
            logger.error(f"获取审批人失败: {e}")
            approver_ids = []

        return approver_ids

    @staticmethod
    async def complete_instance(instance, status: str, result: str = None):
        """完成审批实例"""
        instance.status = status
        instance.result = result
        instance.complete_time = datetime.now()
        instance.current_node = None
        await instance.save()
        return instance
