/**
 * 浏览器侧 API 前缀的唯一来源。
 *
 * 后端 base/app_wrapper.py 会把 /api 剥离后交给 FastAPI，
 * 因此前端只负责拼 /api，插件路由代码与 manifest 都不得再声明 /api。
 * 可通过 VITE_API_BASE_URL 覆盖（部署到子路径时）。
 */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

export function apiUrl(path = '') {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE}${normalized}`
}

export function wsUrl(path = '') {
  const url = apiUrl(path)
  if (/^https?:\/\//.test(url)) {
    return url.replace(/^http/, 'ws')
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${url}`
}
