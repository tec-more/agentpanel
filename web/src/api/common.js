import request from '@/utils/request'

// 获取系统公共配置（前端名称、后台名称、版本等）
export function getSystemConfig() {
  return request.get('/v1/common/system-config')
}
