
import request from '@/utils/request'

// ==================== 全链路追踪 ====================

export function getTraceList(params) {
  return request.get('/v1/audit/trace/list', { params })
}

export function getTraceDetail(traceId) {
  return request.get(`/v1/audit/trace/${traceId}`)
}

// ==================== 审计日志 ====================

export function getAuditLogList(params) {
  return request.get('/v1/audit/audit-logs/list', { params })
}

export function getAuditLogDetail(id) {
  return request.get(`/v1/audit/audit-logs/${id}`)
}

export function updateAuditLog(id, data) {
  return request.put(`/v1/audit/audit-logs/${id}`, data)
}

export function getAuditStatistics(params) {
  return request.get('/v1/audit/audit-logs/statistics/overview', { params })
}

// ==================== 数据变更记录 ====================

export function getDataChangeList(params) {
  return request.get('/v1/audit/data-changes/list', { params })
}

export function getDataChangeDetail(id) {
  return request.get(`/v1/audit/data-changes/${id}`)
}

// ==================== 登录审计 ====================

export function getLoginLogList(params) {
  return request.get('/v1/audit/login-logs/list', { params })
}

export function getLoginLogDetail(id) {
  return request.get(`/v1/audit/login-logs/${id}`)
}

// ==================== 风险审计 ====================

export function getRiskList(params) {
  return request.get('/v1/audit/risks/list', { params })
}

export function getRiskDetail(id) {
  return request.get(`/v1/audit/risks/${id}`)
}

export function updateRisk(id, data) {
  return request.put(`/v1/audit/risks/${id}`, data)
}

export function updateRiskStatus(id, status, comment) {
  return request.put(`/v1/audit/risks/${id}/status`, null, { params: { status, comment } })
}

export function getRiskStatistics(params) {
  return request.get('/v1/audit/risks/statistics', { params })
}

// ==================== 审计报告 ====================

export function getReportList(params) {
  return request.get('/v1/audit/reports/list', { params })
}

export function getReportDetail(id) {
  return request.get(`/v1/audit/reports/${id}`)
}

export function createReport(data) {
  return request.post('/v1/audit/reports', null, { params: data })
}

export function updateReport(id, data) {
  return request.put(`/v1/audit/reports/${id}`, null, { params: data })
}

export function downloadReport(id) {
  return request.get(`/v1/audit/reports/${id}/download`, { responseType: 'blob' })
}

export function generateComplianceReport(params) {
  return request.post('/v1/audit/reports/generate/compliance', null, { params })
}

export function generateRiskReport(params) {
  return request.post('/v1/audit/reports/generate/risk', null, { params })
}

// ==================== 审计配置 ====================

export function getConfigList(params) {
  return request.get('/v1/audit/audit-configs/list', { params })
}

export function createConfig(data) {
  return request.post('/v1/audit/audit-configs/', data)
}

export function updateConfig(id, data) {
  return request.put(`/v1/audit/audit-configs/${id}`, data)
}

export function deleteConfig(id) {
  return request.delete(`/v1/audit/audit-configs/${id}`)
}

export function getConfigDetail(id) {
  return request.get(`/v1/audit/audit-configs/${id}`)
}

// ==================== 菜单同步 ====================

export function syncAuditMenu() {
  return request.post('/v1/menus/sync-audit-menu')
}

export function debugGetAllMenus() {
  return request.get('/v1/menus/debug/all-menus')
}

