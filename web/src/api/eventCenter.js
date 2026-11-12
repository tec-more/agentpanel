import request from '@/utils/request'

// ==================== 规则说明 ==================== //

// 获取事件订阅与发布规则
export function getRules() {
  return request.get('/v1/event-center/rules')
}

// ==================== 订阅管理 ==================== //

// 查询订阅关系（支持 event_name / subscriber / source 筛选）
export function getSubscriptions(params) {
  return request.get('/v1/event-center/subscriptions', { params })
}

// 新增自定义订阅
export function createSubscription(data) {
  return request.post('/v1/event-center/subscriptions', data)
}

// 修改订阅
export function updateSubscription(id, data) {
  return request.put(`/v1/event-center/subscriptions/${id}`, data)
}

// 启用 / 停用订阅
export function toggleSubscription(id) {
  return request.post(`/v1/event-center/subscriptions/${id}/toggle`)
}

// 删除自定义订阅
export function deleteSubscription(id) {
  return request.delete(`/v1/event-center/subscriptions/${id}`)
}

// ==================== 事件发布 ==================== //

// 手动发布事件
export function publishEvent(data) {
  return request.post('/v1/event-center/publish', data)
}

// ==================== 发布记录 ==================== //

// 查询事件发布记录（支持 event_name / status / page / page_size）
export function getRecords(params) {
  return request.get('/v1/event-center/records', { params })
}

// 重放 failed / dead_letter 事件
export function replayEvent(uuid, data) {
  return request.post(`/v1/event-center/records/${uuid}/replay`, data)
}

// ==================== 统计与同步 ==================== //

// 事件中心统计
export function getStats() {
  return request.get('/v1/event-center/stats')
}

// 重新同步插件声明订阅
export function syncDeclared() {
  return request.post('/v1/event-center/sync')
}
