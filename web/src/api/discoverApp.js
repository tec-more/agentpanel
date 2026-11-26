import request from '@/utils/request'

// 运营后台：dsh「发现应用」面板的应用目录（harness 插件，USR 超管）
// 2026-11-26 从 /v1/customer/admin 迁入 /v1/harness/admin。
export const getDiscoverApps = () => request.get('/v1/harness/admin/discover-apps')
export const createDiscoverApp = (data) => request.post('/v1/harness/admin/discover-apps', data)
export const updateDiscoverApp = (id, data) => request.put(`/v1/harness/admin/discover-apps/${id}`, data)
export const deleteDiscoverApp = (id) => request.delete(`/v1/harness/admin/discover-apps/${id}`)
export const toggleDiscoverApp = (id, isActive) =>
  request.patch(`/v1/harness/admin/discover-apps/${id}/status`, { is_active: isActive })
