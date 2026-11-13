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

// 登出（fire-and-forget，不阻塞页面跳转）
// 注意：axios 的请求拦截器是通过 Promise 链异步调度的，即使拦截器函数同步返回
// config，真正注入 header 也发生在微任务里。而调用方 logout() 返回后会立即同步
// 清掉 localStorage 里的 token，届时才执行拦截器就只能读到空值，导致后端返回
// 401 "Not authenticated"。因此这里在发起请求的同一时刻把 token 固化到 header。
// silent: 审计请求失败/超时都不打控制台错误、不弹提示、不触发 401 自动跳转。
export function logout() {
  const token = localStorage.getItem('token')
  return request.post('/v1/auth/logout', undefined, {
    silent: true,
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
}
