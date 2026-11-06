import request from '@/utils/request'

// 用户登录
export function login(data) {
  return request.post('/v1/auth/login', data)
}

// 用户注册（已禁用）
// export function register(data) {
//   return request.post('/v1/auth/register', data)
// }

// 获取当前用户信息
export function getCurrentUser() {
  return request.get('/v1/auth/me')
}

// 更新当前用户信息
export function updateProfile(data) {
  return request.put('/v1/auth/update-profile', data)
}

// 修改密码
export function changePassword(data) {
  return request.post('/v1/auth/change-password', data)
}

// 登出
export function logout() {
  return request.post('/v1/auth/logout')
}
