import request from '@/utils/request'

const BASE = '/v1/customer/admin/organizations'

// 组织列表（支持 keyword/status 筛选与分页）
export const getOrganizationList = (params) => {
  return request.get(BASE, { params })
}

// 组织详情（含成员与授权清单）
export const getOrganizationDetail = (id) => {
  return request.get(`${BASE}/${id}`)
}

// 新建组织
export const createOrganization = (data) => {
  return request.post(BASE, data)
}

// 添加组织成员
export const addOrganizationMember = (orgId, data) => {
  return request.post(`${BASE}/${orgId}/members`, data)
}

// 移除组织成员
export const removeOrganizationMember = (orgId, customerId) => {
  return request.delete(`${BASE}/${orgId}/members/${customerId}`)
}
