import { defineStore } from 'pinia'
import { CP_TOKEN_KEY, CP_CUSTOMER_KEY } from '@/utils/request'
import { apiLogin, apiLoginByCode, apiAuthMe } from '@/api'

export const useAuthStore = defineStore('cp-auth', {
  state: () => ({
    token: localStorage.getItem(CP_TOKEN_KEY) || '',
    customer: JSON.parse(localStorage.getItem(CP_CUSTOMER_KEY) || 'null')
  }),
  getters: {
    isLogged: (s) => !!s.token,
    displayName: (s) => s.customer?.nickname || s.customer?.username || s.customer?.email || '客户'
  },
  actions: {
    _persist(token, customer) {
      this.token = token
      this.customer = customer
      localStorage.setItem(CP_TOKEN_KEY, token)
      localStorage.setItem(CP_CUSTOMER_KEY, JSON.stringify(customer || {}))
    },
    async loginByPassword(email, password) {
      const res = await apiLogin({ email, password })
      this._persist(res.data.access_token, res.data.customer)
      return res
    },
    async loginByCode(email, code) {
      const res = await apiLoginByCode({ email, code })
      this._persist(res.data.access_token, res.data.customer)
      return res
    },
    async refreshMe() {
      const res = await apiAuthMe()
      if (res.data) {
        this.customer = res.data
        localStorage.setItem(CP_CUSTOMER_KEY, JSON.stringify(res.data))
      }
    },
    logout() {
      this.token = ''
      this.customer = null
      localStorage.removeItem(CP_TOKEN_KEY)
      localStorage.removeItem(CP_CUSTOMER_KEY)
    }
  }
})
