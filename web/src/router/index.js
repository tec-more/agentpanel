import { createRouter, createWebHistory } from 'vue-router'
import { useMenuStore } from '@/stores/menu'
import { useSystemStore } from '@/stores/system'
import { getInstallStatus } from '@/api/install'

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
    path: '/install',
    name: 'Install',
    component: () => import('@/install/Index.vue'),
    meta: { title: '系统安装向导', public: true }
  },
  {
    path: '/panel',
    name: 'panel',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/panel/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Index.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' }
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/user/Index.vue'),
        meta: { title: '用户管理', icon: 'User' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/user/Profile.vue'),
        meta: { title: '个人信息', hidden: true }
      },
      {
        path: 'departments',
        name: 'Departments',
        component: () => import('@/views/department/Index.vue'),
        meta: { title: '部门管理', icon: 'OfficeBuilding' }
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('@/views/role/Index.vue'),
        meta: { title: '角色管理', icon: 'UserFilled' }
      },
      {
        path: 'permissions',
        name: 'Permissions',
        component: () => import('@/views/permission/Index.vue'),
        meta: { title: '权限管理', icon: 'Key' }
      },
      {
        path: 'menus',
        name: 'Menus',
        component: () => import('@/views/menu/Index.vue'),
        meta: { title: '菜单管理', icon: 'Menu' }
      },
      {
        path: 'system-setting',
        name: 'SystemSetting',
        component: () => import('@/views/systemSetting/Index.vue'),
        meta: { title: '系统设置', icon: 'Setting' }
      },
      {
        path: 'plugins',
        name: 'Plugins',
        component: () => import('@/views/plugin/Index.vue'),
        meta: { title: '插件管理', icon: 'Connection' }
      },
      {
        path: 'customer',
        name: 'Customer',
        redirect: 'customer/list',
        meta: { title: '客户管理', icon: 'User' }
      },
      {
        path: 'customer/list',
        name: 'CustomerList',
        component: () => import('@/views/customer/Index.vue'),
        meta: { title: '客户列表' }
      },
      {
        path: 'customer/create',
        name: 'CustomerCreate',
        component: () => import('@/views/customer/Edit.vue'),
        meta: { title: '新增客户' }
      },
      {
        path: 'customer/edit/:id',
        name: 'CustomerEdit',
        component: () => import('@/views/customer/Edit.vue'),
        meta: { title: '编辑客户' }
      },
      {
        path: 'customer/detail/:id',
        name: 'CustomerDetail',
        component: () => import('@/views/customer/Detail.vue'),
        meta: { title: '客户详情' }
      },
      {
        path: 'customer/membership-levels',
        name: 'MembershipLevels',
        component: () => import('@/views/customer/membership-levels/index.vue'),
        meta: { title: '会员等级配置' }
      },
      {
        path: 'customer/orders',
        name: 'CustomerOrders',
        component: () => import('@/views/customer/orders/index.vue'),
        meta: { title: '订单管理' }
      },
      {
        path: 'customer/payments',
        name: 'CustomerPayments',
        component: () => import('@/views/customer/payments/index.vue'),
        meta: { title: '支付记录' }
      },
      {
        path: 'product',
        name: 'Product',
        component: () => import('@/views/product/Index.vue'),
        meta: { title: '产品管理', icon: 'Box' }
      },
      {
        path: 'product/category',
        name: 'ProductCategory',
        component: () => import('@/views/product/Category.vue'),
        meta: { title: '产品分类', icon: 'Folder' }
      },
      {
        path: 'product/attribute',
        name: 'ProductAttribute',
        component: () => import('@/views/product/Attribute.vue'),
        meta: { title: '产品属性', icon: 'Settings' }
      },
      {
        path: 'product/variant',
        name: 'ProductVariant',
        component: () => import('@/views/product/Variant.vue'),
        meta: { title: '产品变体', icon: 'Boxes' }
      },
      {
        path: 'product/:id',
        name: 'ProductDetail',
        component: () => import('@/views/product/Detail.vue'),
        meta: { title: '产品详情' }
      },
      {
        path: 'order',
        name: 'Order',
        component: () => import('@/views/order/Index.vue'),
        meta: { title: '订单管理', icon: 'Document' }
      },
      { path: 'order/:id', name: 'OrderDetail', component: () => import('@/views/order/Detail.vue'), meta: { title: '订单详情' } },
      // 第三方平台管理
      { path: 'thirdparty', name: 'ThirdParty', redirect: 'thirdparty/platforms', meta: { title: '第三方平台', icon: 'CloudServer' } },
      { path: 'thirdparty/platforms', name: 'ThirdPartyPlatforms', component: () => import('@/views/thirdparty/platforms/index.vue'), meta: { title: '平台管理', icon: 'Setting' } },
      { path: 'thirdparty/agents', name: 'ThirdPartyAgents', component: () => import('@/views/thirdparty/agents/index.vue'), meta: { title: '智能体管理', icon: 'Bot' } },
      // LLM大模型管理
      { path: 'llm/models', name: 'LLMModels', component: () => import('@/views/llm/models/index.vue'), meta: { title: '模型管理', icon: 'Management' } },
      { path: 'llm/api-keys', name: 'LLMApiKeys', component: () => import('@/views/llm/api-keys/index.vue'), meta: { title: 'API密钥', icon: 'Key' } },
      { path: 'llm/usage', name: 'LLMUsage', component: () => import('@/views/llm/usage/index.vue'), meta: { title: '使用记录', icon: 'DataAnalysis' } },
      // 智能体管理
      { path: 'agent/list', name: 'AgentList', component: () => import('@/views/agent/agents/index.vue'), meta: { title: '智能体' } },
      { path: 'agent/create', name: 'AgentCreate', component: () => import('@/views/agent/agents/edit.vue'), meta: { title: '创建智能体' } },
      { path: 'agent/edit/:id', name: 'AgentEdit', component: () => import('@/views/agent/agents/edit.vue'), meta: { title: '编辑智能体' } },
      { path: 'agent/skills', name: 'AgentSkills', component: () => import('@/views/agent/skills/index.vue'), meta: { title: '技能管理' } },
      { path: 'agent/skills/create', name: 'SkillCreate', component: () => import('@/views/agent/skills/edit.vue'), meta: { title: '创建技能' } },
      { path: 'agent/skills/edit/:id', name: 'SkillEdit', component: () => import('@/views/agent/skills/edit.vue'), meta: { title: '编辑技能' } },
      { path: 'agent/skills/category', name: 'SkillCategory', component: () => import('@/views/agent/skills/category.vue'), meta: { title: '技能分类管理' } },
      { path: 'agent/tools', name: 'AgentTools', component: () => import('@/views/agent/tools/index.vue'), meta: { title: '工具管理' } },
      { path: 'agent/tools/create', name: 'ToolCreate', component: () => import('@/views/agent/tools/edit.vue'), meta: { title: '创建工具' } },
      { path: 'agent/tools/edit/:id', name: 'ToolEdit', component: () => import('@/views/agent/tools/edit.vue'), meta: { title: '编辑工具' } },
      { path: 'agent/tool-tags', name: 'ToolTags', component: () => import('@/views/agent/tool_tags/index.vue'), meta: { title: '工具标签' } },
      { path: 'agent/workflows', name: 'AgentWorkflows', component: () => import('@/views/agent/workflows/index.vue'), meta: { title: '工作流' } },
      { path: 'agent/workflows/edit/:id', name: 'WorkflowEdit', component: () => import('@/views/agent/workflows/edit.vue'), meta: { title: '编辑工作流' } },
      { path: 'agent/executions', name: 'Executions', component: () => import('@/views/agent/executions.vue'), meta: { title: '执行记录' } },
      { path: 'agent/memory', name: 'AgentMemory', component: () => import('@/views/agent/memory/index.vue'), meta: { title: '记忆管理' } },
      { path: 'agent/dialog-flows', name: 'DialogFlows', component: () => import('@/views/agent/dialog-flows/index.vue'), meta: { title: '对话流' } },
      { path: 'agent/dialog-flows/edit/:id', name: 'DialogFlowEdit', component: () => import('@/views/agent/dialog-flows/edit.vue'), meta: { title: '编辑对话流' } },
      { path: 'agent/rag', name: 'RAG', component: () => import('@/views/agent/rag/index.vue'), meta: { title: 'RAG知识库' } },
      { path: 'joke/agent-debug', name: 'JokeAgentDebug', component: () => import('@/views/joke/agent-debug.vue'), meta: { title: '笑话智能体调试' } },
      // 财务管理模块
      {
        path: 'finance',
        name: 'Finance',
        component: () => import('@/views/finance/Index.vue'),
        redirect: 'finance/account',
        meta: { title: '财务管理', icon: 'Wallet' }
      },
      {
        path: 'finance/account',
        name: 'FinanceAccount',
        component: () => import('@/views/finance/account/Index.vue'),
        meta: { title: '会计科目' }
      },
      {
        path: 'finance/journal',
        name: 'FinanceJournal',
        component: () => import('@/views/finance/journal/Index.vue'),
        meta: { title: '凭证管理' }
      },
      {
        path: 'finance/report',
        name: 'FinanceReport',
        component: () => import('@/views/finance/report/Index.vue'),
        meta: { title: '财务报表' }
      },
      // 库存管理模块
      {
        path: 'inventory',
        name: 'Inventory',
        component: () => import('@/views/inventory/Index.vue'),
        meta: { title: '库存管理', icon: 'Box' }
      },
      {
        path: 'inventory/settings',
        name: 'InventorySettings',
        component: () => import('@/views/inventory/settings/Index.vue'),
        meta: { title: '基础设置' }
      },
      {
        path: 'inventory/settings/warehouse',
        name: 'Warehouse',
        component: () => import('@/views/inventory/settings/warehouse/Index.vue'),
        meta: { title: '仓库管理' }
      },
      {
        path: 'inventory/settings/location',
        name: 'Location',
        component: () => import('@/views/inventory/settings/location/Index.vue'),
        meta: { title: '库位管理' }
      },
      {
        path: 'inventory/settings/picking-type',
        name: 'PickingType',
        component: () => import('@/views/inventory/settings/picking-type/Index.vue'),
        meta: { title: '调拨类型' }
      },
      {
        path: 'inventory/settings/lot',
        name: 'Lot',
        component: () => import('@/views/inventory/settings/lot/Index.vue'),
        meta: { title: '批次管理' }
      },
      {
        path: 'inventory/settings/package',
        name: 'Package',
        component: () => import('@/views/inventory/settings/package/Index.vue'),
        meta: { title: '包裹管理' }
      },
      {
        path: 'inventory/picking',
        name: 'Picking',
        component: () => import('@/views/inventory/picking/Index.vue'),
        meta: { title: '调拨管理' }
      },
      {
        path: 'inventory/picking/incoming',
        name: 'PickingIncoming',
        component: () => import('@/views/inventory/picking/incoming/Index.vue'),
        meta: { title: '入库调拨' }
      },
      {
        path: 'inventory/picking/outgoing',
        name: 'PickingOutgoing',
        component: () => import('@/views/inventory/picking/outgoing/Index.vue'),
        meta: { title: '出库调拨' }
      },
      {
        path: 'inventory/picking/internal',
        name: 'PickingInternal',
        component: () => import('@/views/inventory/picking/internal/Index.vue'),
        meta: { title: '内部调拨' }
      },
      {
        path: 'inventory/quant',
        name: 'Quant',
        component: () => import('@/views/inventory/quant/Index.vue'),
        meta: { title: '库存查询' }
      },
      {
        path: 'inventory/quant/list',
        name: 'QuantList',
        component: () => import('@/views/inventory/quant/list/Index.vue'),
        meta: { title: '库存列表' }
      },
      {
        path: 'inventory/quant/summary',
        name: 'QuantSummary',
        component: () => import('@/views/inventory/quant/summary/Index.vue'),
        meta: { title: '库存汇总' }
      },
      {
        path: 'inventory/quant/reservation',
        name: 'QuantReservation',
        component: () => import('@/views/inventory/quant/reservation/Index.vue'),
        meta: { title: '预留查询' }
      },

    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404', public: true }
  }
]

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
  // /panel 和 /install 等后台路径用 backend_name，其他用 frontend_name
  const siteName = (to.path.startsWith('/panel') || to.path.startsWith('/install'))
    ? (systemStore.backend_name || systemStore.app_name)
    : (systemStore.frontend_name || systemStore.app_name)
  document.title = to.meta.title ? `${to.meta.title} - ${siteName}` : siteName

  // ---- 安装检查：未安装时强制进入安装向导（每次导航都向后端核实真实状态） ----
  const cacheInstalled = localStorage.getItem('system_installed') === 'true'
  if (!cacheInstalled || to.path === '/install') {
    let installed = cacheInstalled
    try {
      const resp = await fetch('/api/v1/install/status')
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
    if (!installed && to.path !== '/install') {
      next({ path: '/install' })
      return
    }
    if (installed && to.path === '/install') {
      next({ path: '/panel/login' })
      return
    }
  }

  const token = localStorage.getItem('token')
  const isLoggedIn = !!token

  if (to.path === '/panel/login' && isLoggedIn) {
    next({ path: '/panel/dashboard' })
    return
  }

  // ---- 动态路由加载（必须在 public 检查之前，因为 NotFound 也是 public） ----
  const menuStore = useMenuStore()
  const resolved = router.resolve(to)
  // 只有非公开路由才需要加载动态路由，但 NotFound 除外（它需要有机会匹配动态路由）
  const isNotFound = resolved.name === 'NotFound'
  
  if (isNotFound || !menuStore.routesReady) {
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
