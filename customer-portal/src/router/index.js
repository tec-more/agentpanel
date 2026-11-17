import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('@/layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '工作台' } },
      { path: 'check', name: 'check', component: () => import('@/views/ComplianceCheck.vue'), meta: { title: '内容合规检测' } },
      { path: 'rules', name: 'rules', component: () => import('@/views/Rules.vue'), meta: { title: '合规规则' } },
      { path: 'profile', name: 'profile', component: () => import('@/views/Profile.vue'), meta: { title: '我的资料' } },
      { path: 'membership', name: 'membership', component: () => import('@/views/Membership.vue'), meta: { title: '我的会员' } },
      { path: 'orders', name: 'orders', component: () => import('@/views/Orders.vue'), meta: { title: '我的订单' } },
      { path: 'payments', name: 'payments', component: () => import('@/views/Payments.vue'), meta: { title: '支付记录' } },
      { path: 'organizations', name: 'organizations', component: () => import('@/views/Organizations.vue'), meta: { title: '我的组织' } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory('/portal/'),
  routes
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLogged) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  if (to.path === '/login' && auth.isLogged) {
    next('/dashboard')
    return
  }
  next()
})

export default router
