import request from '@/utils/request'

// 获取仪表盘统计数据
export function getDashboardStats() {
  return request.get('/v1/dashboard/stats')
}

// 获取当前用户信息
export function getCurrentUserInfo() {
  return request.get('/v1/dashboard/user-info')
}
