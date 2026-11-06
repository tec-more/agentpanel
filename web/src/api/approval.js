import request from '@/utils/request'

// ==================== 流程规则 ====================

export const getFlowList = (params) => {
  return request.get('/v1/approval/flow-rules', { params })
}

export const getFlowDetail = (id) => {
  return request.get(`/v1/approval/flow-rules/${id}`)
}

export const createFlow = (data) => {
  return request.post('/v1/approval/flow-rules', data)
}

export const updateFlow = (id, data) => {
  return request.put(`/v1/approval/flow-rules/${id}`, data)
}

export const deleteFlow = (id) => {
  return request.delete(`/v1/approval/flow-rules/${id}`)
}

export const toggleFlowStatus = (id, isActive) => {
  return request.post(`/v1/approval/flow-rules/${id}/toggle`, { is_active: isActive })
}

export const getFlowByBusinessType = (businessType) => {
  return request.get(`/v1/approval/flow-rules/business-type/${businessType}`)
}

// ==================== 审批实例 ====================

export const createInstance = (data) => {
  return request.post('/v1/approval/instances', data)
}

export const getInstanceList = (params) => {
  return request.get('/v1/approval/instances', { params })
}

export const getInstanceDetail = (id) => {
  return request.get(`/v1/approval/instances/${id}`)
}

export const cancelInstance = (id) => {
  return request.post(`/v1/approval/instances/${id}/cancel`)
}

export const getInstanceByBusiness = (businessType, businessId) => {
  return request.get(`/v1/approval/instances/business/${businessType}/${businessId}`)
}

// ==================== 审批任务 ====================

export const getMyTasks = (params) => {
  return request.get('/v1/approval/tasks/my', { params })
}

export const getTaskDetail = (id) => {
  return request.get(`/v1/approval/tasks/${id}`)
}

export const approveTask = (id, data) => {
  return request.post(`/v1/approval/tasks/${id}/approve`, data)
}

export const transferTask = (id, data) => {
  return request.post(`/v1/approval/tasks/${id}/transfer`, data)
}

// ==================== 流程规则的模型/动作元信息 ====================

// 获取所有可用的业务模型（用于流程规则配置），返回模型列表
export const getAvailableModels = () => {
  return request.get('/v1/approval/flow-rules/models')
}

// 获取指定业务模型对应的 service 执行动作列表（create/update/delete）
export const getModelActions = (model) => {
  return request.get('/v1/approval/flow-rules/actions', { params: { model } })
}

// 校验流程配置结构（不落库）
export const validateFlow = (data) => {
  return request.post('/v1/approval/flow-rules/validate', data)
}

// ==================== 前端审批检测与提交（无需权限） ====================

/**
 * 检测指定模型+动作是否需要审批（前端页面级调用）
 * @param {string} model - 业务模型标识，如 "purchase_order"
 * @param {string} action - 动作 create/update/delete，不传返回该模型所有匹配流程
 * @returns {require_approval, flows: [{flow_id, flow_name, flow_code, actions, methods, ...}]}
 */
export const checkApprovalForModel = (model, action = null) => {
  return request.get('/v1/approval/flow-rules/check-for-model', {
    params: { model, action }
  })
}

/**
 * 获取审批上下文：合并流程规则 + 实例状态 + 当前用户审批任务
 * @param {object} params - { model, business_id }
 * @returns { has_flow, flows, instance, pending_tasks, can_submit, can_approve, can_cancel, can_create, can_update, can_delete }
 */
export const getApprovalContext = (params) => {
  return request.get('/v1/approval/flow-rules/context', { params })
}

/**
 * 按当前前端路由反查审批上下文（全局审批组件用）
 * @param {object} params - { route, business_id }
 * @returns { has_flow, model, mode, flows, instance, pending_tasks, can_* }
 */
export const getApprovalContextByRoute = (params) => {
  return request.get('/v1/approval/flow-rules/context-by-route', { params })
}

/**
 * 提交审批（前端用户确认后调用）
 * @param {object} data - { model, action, data: payload, business_id, title }
 */
export const submitForApproval = (data) => {
  return request.post('/v1/approval/flow-rules/submit-for-approval', data)
}
