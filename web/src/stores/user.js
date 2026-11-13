import { defineStore } from 'pinia'
import { login as loginApi, getCurrentUser, logout as logoutApi } from '@/api/auth'
import { beginLogout } from '@/utils/request'

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
      // 1) 进入登出流程：抑制 401 拦截器弹提示 / 抢跳登录页（避免与本次跳转互相拉扯）
      beginLogout()
      // 2) 先让后台轮询、WebSocket 等组件停下来，避免退出后仍拿失效 token 发请求刷 401
      window.dispatchEvent(new CustomEvent('app:logout'))
      // 3) 登出审计请求须在清 token 前同步发出，但绝不阻塞跳转：
      //    后端 logout 只写审计日志，失败/超时都不影响本地登出（fire-and-forget）
      try {
        logoutApi().catch(() => {})
      } catch (_) {}
      // 4) 立即清理本地登录态，页面随即跳转，不再等待任何网络往返
      this.token = ''
      this.userInfo = {}
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
    }
  }
})
