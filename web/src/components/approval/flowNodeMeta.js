// 审批流程节点 / 配置 元数据与中文映射
// 与后端 ApprovalEngine 的语义对齐：
//   approve_type: single(单人) / or(或签) / joint(会签)
//   approver_config.type: user(指定用户) / role(按角色) / dept_head(部门主管) / dynamic
//   节点 type: start / approve / condition / end
//   边 action: approve(通过) / reject(拒绝)

export const NODE_TYPES = {
  start: { key: 'start', label: '开始', color: '#10B981', icon: 'VideoPlay', desc: '流程发起入口' },
  approve: { key: 'approve', label: '审批', color: '#2563EB', icon: 'Stamp', desc: '需要审批人处理的节点' },
  condition: { key: 'condition', label: '条件', color: '#F59E0B', icon: 'Share', desc: '按字段条件分流' },
  end: { key: 'end', label: '结束', color: '#6B7280', icon: 'CircleCheck', desc: '流程终点' }
}

export const NODE_TYPE_LIST = Object.values(NODE_TYPES)

export const APPROVE_MODES = [
  { value: 'single', label: '单人', desc: '一人通过即可，其余自动跳过' },
  { value: 'or', label: '或签', desc: '任一审批人通过即算通过' },
  { value: 'joint', label: '会签', desc: '所有审批人都通过才算通过' }
]

export const APPROVER_SOURCES = [
  { value: 'user', label: '指定用户', desc: '从用户列表中选择，支持单/多人' },
  { value: 'role', label: '按角色', desc: '角色下所有成员均为审批人' },
  { value: 'dept_head', label: '部门主管', desc: '取申请人（或指定）部门负责人' }
]

export const CONDITION_OPERATORS = [
  { value: '>', label: '大于' },
  { value: '<', label: '小于' },
  { value: '>=', label: '大于等于' },
  { value: '<=', label: '小于等于' },
  { value: '==', label: '等于' },
  { value: '!=', label: '不等于' },
  { value: 'in', label: '属于' },
  { value: 'not_in', label: '不属于' },
  { value: 'contains', label: '包含' }
]

export const EDGE_ACTIONS = [
  { value: 'approve', label: '通过', color: '#10B981' },
  { value: 'reject', label: '拒绝', color: '#EF4444' }
]

// 生成唯一节点 id
export function genNodeId(type = 'node') {
  return `${type}_${Date.now().toString(36)}_${Math.floor(Math.random() * 1e4).toString(36)}`
}

// 创建默认节点 data（与引擎 schema 对齐）
export function createNodeData(type, position) {
  const base = {
    nodeType: type,
    name: NODE_TYPES[type]?.label || type
  }
  if (type === 'approve') {
    return {
      ...base,
      approve_type: 'single',
      approver_config: { type: 'user', user_ids: [] }
    }
  }
  if (type === 'condition') {
    return { ...base, field: '', operator: '>', value: '' }
  }
  return base
}
