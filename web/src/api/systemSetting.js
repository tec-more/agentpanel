import request from '@/utils/request'

// 获取系统设置列表
export function getSystemSettingList(params) {
  return request.get('/v1/system-settings/list', { params })
}

// 获取公开设置（无需登录）
export function getPublicSettings() {
  return request.get('/v1/system-settings/public')
}

// 获取设置详情
export function getSystemSettingDetail(settingId) {
  return request.get(`/v1/system-settings/${settingId}`)
}

// 创建设置
export function createSystemSetting(data) {
  return request.post('/v1/system-settings', data)
}

// 更新设置
export function updateSystemSetting(settingId, data) {
  return request.put(`/v1/system-settings/${settingId}`, data)
}

// 批量更新设置
export function batchUpdateSystemSettings(data) {
  return request.put('/v1/system-settings/batch', data)
}

// 删除设置
export function deleteSystemSetting(settingId) {
  return request.delete(`/v1/system-settings/${settingId}`)
}

// 初始化默认设置
export function initDefaultSettings() {
  return request.post('/v1/system-settings/init')
}
