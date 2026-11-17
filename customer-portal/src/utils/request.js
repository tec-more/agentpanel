import axios from 'axios'
import { ElMessage } from 'element-plus'

// 客户门户专用 token key，与管理后台（token/userInfo）物理隔离，
// 避免同一浏览器里后台账号与客户身份互相串号。
export const CP_TOKEN_KEY = 'cp_token'
export const CP_CUSTOMER_KEY = 'cp_customer'

const request = axios.create({
  baseURL: __API_BASE__,
  timeout: 20000
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem(CP_TOKEN_KEY)
  if (token && !config.headers?.['Authorization']) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const res = response.data
    // 后端 success_response: code=0 或 success=true；fail_response: code!=0
    if (res.success === true || res.code === 0 || res.code === 200) {
      return res
    }
    ElMessage.error(res.msg || res.message || '请求失败')
    return Promise.reject(new Error(res.msg || res.message || '请求失败'))
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem(CP_TOKEN_KEY)
        localStorage.removeItem(CP_CUSTOMER_KEY)
        ElMessage.error('登录已过期，请重新登录')
        const redirect = encodeURIComponent(window.location.pathname)
        window.location.href = `/portal/login?redirect=${redirect}`
        return Promise.reject(error)
      }
      ElMessage.error(data?.msg || data?.message || `请求失败 (${status})`)
    } else if (error.request) {
      ElMessage.error('网络错误，请检查网络连接')
    } else {
      ElMessage.error(error.message || '请求失败')
    }
    return Promise.reject(error)
  }
)

export default request
