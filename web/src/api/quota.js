import request from '@/utils/request'

// ==================== 组织配额 ====================
export function getOrgQuotaList(params) {
  return request.get('/v1/quota/organizations', { params })
}

export function getOrgQuotaAvailablePlans() {
  return request.get('/v1/quota/organizations/plans/available')
}

export function getOrgQuotaDetail(orgId) {
  return request.get(`/v1/quota/organizations/${orgId}`)
}

export function getOrgQuotaBoard(orgId, params) {
  return request.get(`/v1/quota/organizations/${orgId}/board`, { params })
}

export function assignOrgQuotaPlan(orgId, data) {
  return request.post(`/v1/quota/organizations/${orgId}/plan`, data)
}

export function unbindOrgQuotaPlan(orgId) {
  return request.delete(`/v1/quota/organizations/${orgId}/plan`)
}

export function setOrgQuotaStatus(orgId, status) {
  return request.post(`/v1/quota/organizations/${orgId}/status`, { status })
}

// ==================== 计量流水 ====================
export function getUsageRecords(params) {
  return request.get('/v1/usage-records', { params })
}
