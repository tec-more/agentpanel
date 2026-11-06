import request from '@/utils/request'

// 获取授权记录列表
export const getGrantList = (params) => {
  return request.get('/v1/agent/admin/grants/list', { params })
}

// 创建单条授权（备用）
export const createGrant = (data) => {
  return request.post('/v1/agent/admin/grants', data)
}

// 批量创建授权
export const createGrantBatch = (data) => {
  return request.post('/v1/agent/admin/grants/batch', data)
}

// 撤销授权（DELETE 携带请求体）
export const revokeGrant = (data) => {
  return request.delete('/v1/agent/admin/grants', { data })
}

// 按主体查询授权（备用）
export const getGrantsBySubject = (params) => {
  return request.get('/v1/agent/admin/grants/by-subject', { params })
}

// 搜索可授权主体（客户/后台用户/组织）
export const getGrantSubjects = (params) => {
  return request.get('/v1/agent/admin/grants/subjects', { params })
}

// 搜索可授权资源选项
export const getResourceOptions = (params) => {
  return request.get('/v1/agent/admin/grants/resource-options', { params })
}
