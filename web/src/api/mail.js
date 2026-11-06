import request from '@/utils/request'

// ==================== 通知（收件箱） ====================

export const getInbox = (params) => {
  return request.get('/v1/mail/notifications/inbox', { params })
}

export const getUnreadCount = () => {
  return request.get('/v1/mail/notifications/unread-count')
}

export const markRead = (notification_ids) => {
  return request.post('/v1/mail/notifications/mark-read', { notification_ids })
}

export const markUnread = (notification_ids) => {
  return request.post('/v1/mail/notifications/mark-unread', { notification_ids })
}

export const toggleStar = (notification_id, starred) => {
  const data = starred === undefined || starred === null ? {} : { starred }
  return request.post(`/v1/mail/notifications/${notification_id}/star`, data)
}

// ==================== 消息（记录消息/Chatter） ====================

export const getMessageThread = (model, res_id, params) => {
  return request.get('/v1/mail/messages/thread', { params: { model, res_id, ...params } })
}

export const postMessage = (data) => {
  return request.post('/v1/mail/messages', data)
}

export const getMessage = (id) => {
  return request.get(`/v1/mail/messages/${id}`)
}

export const updateMessage = (id, data) => {
  return request.put(`/v1/mail/messages/${id}`, data)
}

export const deleteMessage = (id) => {
  return request.delete(`/v1/mail/messages/${id}`)
}

// ==================== 关注者 ====================

export const followRecord = (data) => {
  return request.post('/v1/mail/followers/follow', data)
}

export const unfollowRecord = (data) => {
  return request.post('/v1/mail/followers/unfollow', data)
}

export const listFollowers = (model, res_id) => {
  return request.get('/v1/mail/followers/list', { params: { model, res_id } })
}

export const checkFollowing = (model, res_id) => {
  return request.get('/v1/mail/followers/check', { params: { model, res_id } })
}

export const myFollowing = (model) => {
  return request.get('/v1/mail/followers/my-following', { params: { model } })
}

// ==================== 消息子类型 ====================

export const listSubtypes = (params) => {
  return request.get('/v1/mail/subtypes', { params })
}

export const getSubtype = (id) => {
  return request.get(`/v1/mail/subtypes/${id}`)
}

export const createSubtype = (data) => {
  return request.post('/v1/mail/subtypes', data)
}

export const updateSubtype = (id, data) => {
  return request.put(`/v1/mail/subtypes/${id}`, data)
}

export const deleteSubtype = (id) => {
  return request.delete(`/v1/mail/subtypes/${id}`)
}

// ==================== 事件→消息映射 ====================

export const listMappings = (params) => {
  return request.get('/v1/mail/mappings', { params })
}

export const getMapping = (id) => {
  return request.get(`/v1/mail/mappings/${id}`)
}

export const createMapping = (data) => {
  return request.post('/v1/mail/mappings', data)
}

export const updateMapping = (id, data) => {
  return request.put(`/v1/mail/mappings/${id}`, data)
}

export const deleteMapping = (id) => {
  return request.delete(`/v1/mail/mappings/${id}`)
}
