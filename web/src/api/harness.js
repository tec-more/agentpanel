import request from '@/utils/request'

// ==================== 会话 / 运行（管理端） ====================

export function getSessionList(params) {
  return request.get('/v1/harness/admin/sessions', { params })
}

export function getSessionDetail(sessionNo) {
  return request.get(`/v1/harness/admin/sessions/${sessionNo}`)
}

export function getRunList(params) {
  return request.get('/v1/harness/admin/runs', { params })
}

export function getRunDetail(runNo) {
  return request.get(`/v1/harness/admin/runs/${runNo}`)
}

export function getRunSteps(runNo, params) {
  return request.get(`/v1/harness/admin/runs/${runNo}/steps`, { params })
}

// ==================== 用量看板 ====================

export function getUsageOverview(params) {
  return request.get('/v1/harness/dashboard/usage', { params })
}

export function getRunUsage(runNo) {
  return request.get(`/v1/harness/dashboard/runs/${runNo}/usage`)
}

export function getSessionUsage(sessionNo) {
  return request.get(`/v1/harness/dashboard/sessions/${sessionNo}/usage`)
}

export function getAnomalies(params) {
  return request.get('/v1/harness/dashboard/anomalies', { params })
}

export function reconcileReservations(params) {
  return request.post('/v1/harness/dashboard/reconcile', null, { params })
}

// ==================== 网关记账 vs 客户端上报对账 ====================

export function runGatewayReconcile(params) {
  return request.post('/v1/harness/dashboard/reconcile/gateway', null, { params })
}

export function getReconcileDiffs(params) {
  return request.get('/v1/harness/dashboard/reconcile/diffs', { params })
}

export function getReconcileDiffDetail(diffId) {
  return request.get(`/v1/harness/dashboard/reconcile/diffs/${diffId}`)
}

export function resolveReconcileDiff(diffId, params) {
  return request.post(`/v1/harness/dashboard/reconcile/diffs/${diffId}/resolve`, null, { params })
}

export function getReconcileBatches(params) {
  return request.get('/v1/harness/dashboard/reconcile/batches', { params })
}

// ==================== 网关额度中断（预算/拒绝/截断/吊销） ====================

export function getGatewayQuota(params) {
  return request.get('/v1/harness/dashboard/gateway/quota', { params })
}

export function revokeGatewayLease(leaseId, params) {
  return request.post(`/v1/harness/dashboard/gateway/leases/${leaseId}/revoke`, null, { params })
}

// ==================== 审计事件 ====================

export function getAuditEvents(params) {
  return request.get('/v1/harness/audit-events', { params })
}

// ==================== 客户端凭据 ====================

export function getClientList(params) {
  return request.get('/v1/harness/clients', { params })
}

export function createClient(data) {
  return request.post('/v1/harness/clients', data)
}

export function revokeClient(clientId) {
  return request.post(`/v1/harness/clients/${clientId}/revoke`)
}

// ==================== 动作策略 ====================

export function getPolicyList(params) {
  return request.get('/v1/harness/policies', { params })
}

export function createPolicy(data) {
  return request.post('/v1/harness/policies', data)
}
