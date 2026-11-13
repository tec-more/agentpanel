/**
 * 安装向导专用 API（独立入口，不依赖主 SPA 的 request/router）。
 * 全部基于 fetch 直连，避免引入主应用的 axios 拦截器与路由模块，
 * 保证安装页是一个真正独立、可单独加载的页面。
 */
import { apiUrl } from '@/utils/apiBase'

async function postJson(path, body, timeout) {
  const controller = timeout ? new AbortController() : null
  let timer = null
  if (controller) {
    timer = setTimeout(() => controller.abort(), timeout)
  }
  try {
    const resp = await fetch(apiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
      signal: controller ? controller.signal : undefined
    })
    const data = await resp.json().catch(() => ({}))
    return data?.data ?? data
  } finally {
    if (timer) clearTimeout(timer)
  }
}

async function getJson(path) {
  const resp = await fetch(apiUrl(path), { method: 'GET' })
  const data = await resp.json().catch(() => ({}))
  return data?.data ?? data
}

// 环境检测
export function envCheck() {
  return getJson('/v1/install/env-check')
}

// 安装状态
export function getInstallStatus() {
  return getJson('/v1/install/status')
}

// 测试数据库连接（长超时）
export function testDatabaseConnection(data) {
  return postJson('/v1/install/test-database', data, 120000)
}

// 执行安装（超长超时）
export function executeInstallation(data) {
  return postJson('/v1/install/execute', data, 600000)
}

// 获取系统公共配置（用于安装页标题回显，未配置时为空）
export function fetchSystemConfig() {
  return getJson('/v1/common/system-config')
}
