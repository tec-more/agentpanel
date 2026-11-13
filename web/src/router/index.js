import { createRouter, createWebHistory } from 'vue-router'
import { useMenuStore } from '@/stores/menu'
import { useSystemStore } from '@/stores/system'
import { getInstallStatus } from '@/api/install'
import { apiUrl } from '@/utils/apiBase'

// 纯动态路由：除平台框架级路由外，所有业务页面（含核心 users/dept/role/permission/
// menu/plugin/dashboard/系统设置 与全部插件页面）均由后端菜单接口下发，经
// menuStore.generateRoutes() 在 beforeEach 中动态注册。菜单记录在 migrations 种子
// SQL 与插件 manifest 中声明，不再在静态表中重复维护。
const routes = [
  {
    path: '/',
    name: 'LandingPage',
    component: () => import('@/views/LandingPage.vue'),
    meta: { title: 'AIPanelAdmin', public: true }
  },
  {
    path: '/panel/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '管理后台登录', public: true }
  },
  {
    path: '/panel',
    name: 'panel',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/panel/dashboard',
    // 仅保留非菜单驱动的核心隐藏页；其余页面全部走动态菜单路由
    children: [
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/user/Profile.vue'),
        meta: { title: '个人信息', hidden: true }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404', public: true }
  }
]

// 静态页面路由归属的插件（键为 /panel 下的第一段路径，值为 manifest 插件名）。
// 核心页面（users / dept / dashboard / plugins 等）不在表内，不做插件门控。
// 后端 /v1/common/system-config 下发的 enabled_plugins 为双真插件列表。
const PLUGIN_ROUTE_PREFIX = {
  customer: 'customer',
  product: 'product',
  order: 'sales',
  llm: 'llm',
  thirdparty: 'thirdparty',
  agent: 'agent',
  joke: 'agent',
  finance: 'finance',
  inventory: 'inventory'
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(async (to, from, next) => {
  // 初始化系统配置（确保每次路由都有 config.conf 中的名称可用）
  const systemStore = useSystemStore()
  if (!systemStore.loaded) {
    try {
      await systemStore.loadConfig()
    } catch (_) {}
  }
  // 动态拼接浏览器标题：页面标题 - 系统名称
  // /panel 等后台路径用 backend_name，其他用 frontend_name
  const siteName = to.path.startsWith('/panel')
    ? (systemStore.backend_name || systemStore.app_name)
    : (systemStore.frontend_name || systemStore.app_name)
  document.title = to.meta.title ? `${to.meta.title} - ${siteName}` : siteName

  // ---- 安装检查：未安装时强制进入安装向导（每次导航都向后端核实真实状态） ----
  // 注意：安装向导是独立页面（install.html），与主 SPA 分离，因此这里用整页
  // 跳转（window.location）切换到独立安装页，而不是 SPA 内部路由。
  // 安装检查：每次导航都向后端核实真实安装状态，不依赖 localStorage 缓存做短路。
  // 否则删除 .installed 标记后，浏览器仍会按旧的 system_installed=true 判定为「已安装」，
  // 既不进安装页、也不再向后端重新核实（旧逻辑里 `if (!cacheInstalled || ...)` 会在
  // 已缓存为 true 时直接跳过整个核实块）。
  let installed = localStorage.getItem('system_installed') === 'true'
  {
    try {
      const resp = await fetch(apiUrl('/v1/install/status'))
      const json = await resp.json()
      const data = json?.data || json
      installed = !!data.installed
      if (installed) {
        localStorage.setItem('system_installed', 'true')
      } else {
        localStorage.removeItem('system_installed')
      }
    } catch (_) {
      // 后端不可达时依赖本地缓存判断，避免把用户锁死在安装页
    }
  }
  if (!installed && to.path !== '/install') {
    window.location.href = '/install'
    return
  }
  if (installed && to.path === '/install') {
    window.location.href = '/panel/login'
    return
  }

  // 插件页面门控：仅已安装且已启用的插件页面可达（PLR-03 / PLR-09）。
  // 系统配置未成功加载时放行，避免后端不可达把全部插件页面锁死。
  const firstSegment = to.path.replace(/^\/panel\/?/, '').split('/')[0]
  const routePlugin = PLUGIN_ROUTE_PREFIX[firstSegment]
  if (systemStore.loaded && routePlugin && !systemStore.isPluginEnabled(routePlugin)) {
    next({ name: 'NotFound' })
    return
  }

  const token = localStorage.getItem('token')
  const isLoggedIn = !!token

  if (to.path === '/panel/login' && isLoggedIn) {
    next({ path: '/panel/dashboard' })
    return
  }

  // ---- 动态路由加载（必须在 public 检查之前，因为 NotFound 也是 public） ----
  // 未登录时不请求 /v1/menus/user-menus：该接口需要鉴权，登录页/落地页会在
  // 控制台刷出 401 并误触「登录已过期」跳转。菜单在登录成功后的首次导航再加载。
  const menuStore = useMenuStore()
  const resolved = router.resolve(to)
  // 只有非公开路由才需要加载动态路由，但 NotFound 除外（它需要有机会匹配动态路由）
  const isNotFound = resolved.name === 'NotFound'

  if (isLoggedIn && (isNotFound || !menuStore.routesReady)) {
    // 防止动态路由加载失败时的无限重定向循环
    if (menuStore.routeRetryCount >= 3) {
      console.warn('[路由守卫] 已达最大重试次数(3次)，停止重定向，放行到当前路由')
      menuStore.routesReady = true
      // 不调用 next()，继续往下走让后续逻辑处理
    } else {
      try {
        if (!menuStore.isLoaded) {
          await menuStore.fetchUserMenus()
        }

        const dynamicRoutes = menuStore.generateRoutes()

        if (dynamicRoutes.length > 0) {
          dynamicRoutes.forEach(route => {
            if (!router.hasRoute(route.name)) {
              router.addRoute('panel', route)
              menuStore.dynamicRouteNames.push(route.name)
            }
          })
        }

        menuStore.routesReady = true
        menuStore.routeRetryCount++

        // 重新导航：只传 path，不能展开 to（否则 name: 'NotFound' 会覆盖 path 指向 404）
        next({ path: to.path, query: to.query, hash: to.hash, replace: true })
        return
      } catch (error) {
        console.error('加载菜单失败:', error)
        menuStore.routesReady = true
        // 失败后继续往下走
      }
    }
  }

  menuStore.routeRetryCount = 0

  // ---- 公开页面直接放行 ----
  if (to.meta.public) {
    next()
    return
  }

  // ---- 需要登录的页面 ----
  if (!isLoggedIn) {
    next({ path: '/panel/login', query: { redirect: to.fullPath } })
    return
  }

  next()
})

export default router
