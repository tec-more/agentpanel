import request from '@/utils/request'

// 获取用户列表
export function getUserList(params) {
  return request.get('/v1/users/list', { params })
}

// 获取用户详情
export function getUserDetail(userId) {
  return request.get(`/v1/users/${userId}`)
}

// 创建用户
export function createUser(data) {
  return request.post('/v1/users', data)
}

// 更新用户
export function updateUser(userId, data) {
  return request.put(`/v1/users/${userId}`, data)
}

// 删除用户
export function deleteUser(userId) {
  return request.delete(`/v1/users/${userId}`)
}

// 切换用户状态
export function toggleUserStatus(userId) {
  return request.patch(`/v1/users/${userId}/toggle-status`)
}
