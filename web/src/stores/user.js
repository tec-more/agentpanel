import { defineStore } from 'pinia'
import { login as loginApi, getCurrentUser, logout as logoutApi } from '@/api/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    userInfo: JSON.parse(localStorage.getItem('userInfo') || '{}')
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    username: (state) => state.userInfo?.username || '',
    isSuperuser: (state) => state.userInfo?.is_superuser || false
  },

  actions: {
    async login(loginData) {
      const res = await loginApi(loginData)
      const { access_token, user } = res.data

      this.token = access_token
      this.userInfo = user

      localStorage.setItem('token', access_token)
      localStorage.setItem('userInfo', JSON.stringify(user))

      return res
    },

    async fetchUserInfo() {
      const res = await getCurrentUser()
      this.userInfo = res.data
      localStorage.setItem('userInfo', JSON.stringify(res.data))
      return res.data
    },

    async logout() {
      try {
        await logoutApi()
      } catch (e) {
        // 忽略登出错误
      }
      this.token = ''
      this.userInfo = {}
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
    }
  }
})
