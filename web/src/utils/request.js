import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request = axios.create({
  baseURL: '/api',
  timeout: 15000
})

export function createRequestWithTimeout(timeout) {
  const instance = axios.create({
    baseURL: '/api',
    timeout
  })

  instance.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem('token')
      if (token) {
        config.headers['Authorization'] = `Bearer ${token}`
      }
      return config
    },
    (error) => {
      return Promise.reject(error)
    }
  )

  instance.interceptors.response.use(
    (response) => {
      const res = response.data
      if (res.code === 0 || res.code === 200 || res.success === true) {
        return res
      } else {
        ElMessage.error(res.msg || res.message || '请求失败')
        return Promise.reject(new Error(res.msg || res.message || '请求失败'))
      }
    },
    (error) => {
      console.error('[Request Error]', error)
      if (error.response) {
        const { status, data } = error.response
        if (status === 401) {
          localStorage.removeItem('token')
          localStorage.removeItem('userInfo')
          ElMessage.error('登录已过期，请重新登录')
          router.push('/panel/login')
        } else if (status === 503) {
          // 503 系统未安装 - 静默处理，清除缓存并跳转安装页
          localStorage.removeItem('system_installed')
          if (data?.redirect === '/install') {
            window.location.href = '/install'
          }
          return Promise.reject(new Error('SYSTEM_NOT_INSTALLED'))
        } else {
          ElMessage.error(data?.msg || data?.message || error.message || `请求失败 (${status})`)
        }
      } else if (error.request) {
        ElMessage.error('网络错误，请检查网络连接')
      } else {
        ElMessage.error(error.message || '请求失败')
      }
      return Promise.reject(error)
    }
  )

  return instance
}

// 请求拦截器 - 直接从 localStorage 读取 token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    // 如果是文件下载请求，直接返回原始响应
    if (response.config.responseType === 'blob') {
      return response
    }
    const res = response.data
    // 审批拦截响应：code=40001，需要引导用户提交审批
    if (res && res.code === 40001 && res.require_approval) {
      // 触发全局审批提示事件
      window.dispatchEvent(new CustomEvent('approval-required', { detail: res }))
      return Promise.reject(new Error('NEED_APPROVAL'))
    }
    // 后端成功响应码为 0 或 success 为 true
    // 兼容直接返回数据的格式（如分页响应 {items, total}）
    if (res.code === 0 || res.code === 200 || res.success === true || (res.items !== undefined)) {
      return res
    } else {
      ElMessage.error(res.msg || res.message || '请求失败')
      return Promise.reject(new Error(res.msg || res.message || '请求失败'))
    }
  },
  (error) => {
    console.error('[Request Error]', error)

    if (error.response) {
      const { status, data } = error.response

      // 打印详细错误信息
      console.error('[Response Error]', {
        status,
        data,
        message: data?.msg || data?.message || error.message
      })

      if (status === 401) {
        // 清除本地存储并跳转登录页
        localStorage.removeItem('token')
        localStorage.removeItem('userInfo')
        ElMessage.error('登录已过期，请重新登录')
        router.push('/panel/login')
      } else if (status === 403) {
        ElMessage.error('没有权限访问')
      } else if (status === 503) {
        // 503 系统未安装 - 静默处理，清除缓存并跳转安装页
        localStorage.removeItem('system_installed')
        if (data?.redirect === '/install') {
          router.push('/install')
        }
        // 静默拒绝，不弹错误提示
        return Promise.reject(new Error('SYSTEM_NOT_INSTALLED'))
      } else if (status === 400 && data?.code === 40001 && data?.require_approval) {
        // 审批拦截：触发全局审批提示事件，不显示错误提示
        window.dispatchEvent(new CustomEvent('approval-required', { detail: data }))
        return Promise.reject(new Error('NEED_APPROVAL'))
      } else if (status === 400) {
        // 400 Bad Request - 显示详细错误信息
        const errorMsg = data?.msg || data?.message || error.message || '请求参数错误'
        ElMessage.error(errorMsg)
        console.error('[400 Error Details]', data)
      } else {
        ElMessage.error(data?.msg || data?.message || error.message || `请求失败 (${status})`)
      }
    } else if (error.request) {
      ElMessage.error('网络错误，请检查网络连接')
    } else {
      ElMessage.error(error.message || '请求失败')
    }

    return Promise.reject(error)
  }
)

export default request
