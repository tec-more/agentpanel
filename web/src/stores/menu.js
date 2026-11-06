import { defineStore } from 'pinia'
import { getUserMenus } from '@/api/rbac'

// 图标映射表
// 说明：值统一使用 @element-plus/icons-vue 的官方图标名（全量 293 个均可直接使用）
// 非官方命名（如 Lucide 风格）在此映射到官方图标，避免回退为默认 Document
const iconMap = {
  // 通用
  'Odometer': 'Odometer',
  'Setting': 'Setting',
  'Settings': 'Setting',
  'User': 'User',
  'UserFilled': 'UserFilled',
  'OfficeBuilding': 'OfficeBuilding',
  'Key': 'Key',
  'Menu': 'Menu',
  'Connection': 'Connection',
  'Document': 'Document',
  'DocumentChecked': 'DocumentChecked',
  'Folder': 'Folder',
  'Files': 'Files',
  'Grid': 'Grid',
  'List': 'List',
  'Search': 'Search',
  'Edit': 'Edit',
  'Delete': 'Delete',
  'Plus': 'Plus',
  'Minus': 'Minus',
  'Check': 'Check',
  'Close': 'Close',
  'Warning': 'Warning',
  'AlertTriangle': 'Warning',
  'Info': 'InfoFilled',
  'InfoFilled': 'InfoFilled',
  'Question': 'QuestionFilled',
  'QuestionFilled': 'QuestionFilled',
  'Star': 'Star',
  'Message': 'Message',
  'Bell': 'Bell',
  'BellFilled': 'BellFilled',
  'Notification': 'Notification',
  'Calendar': 'Calendar',
  'CalendarCheck': 'Calendar',
  'Clock': 'Clock',
  'Location': 'Location',
  'Phone': 'Phone',
  'Picture': 'Picture',
  'Video': 'VideoCamera',
  'VideoCamera': 'VideoCamera',
  'Upload': 'Upload',
  'Download': 'Download',
  'Link': 'Link',
  'Share': 'Share',
  'Lock': 'Lock',
  'Unlock': 'Unlock',
  'Tools': 'Tools',
  'Wrench': 'Tools',
  'Monitor': 'Monitor',
  'Cpu': 'Cpu',
  'Bot': 'Cpu',
  // 数据图表
  'DataLine': 'DataLine',
  'DataAnalysis': 'DataAnalysis',
  'PieChart': 'PieChart',
  'TrendCharts': 'TrendCharts',
  'Histogram': 'Histogram',
  'TrendingUp': 'TrendCharts',
  'TrendingDown': 'TrendCharts',
  'BarChart3': 'Histogram',
  'Activity': 'DataLine',
  'Rank': 'Rank',
  'DataBoard': 'DataBoard',
  // 业务：商品/销售/客户/CRM
  'Goods': 'Goods',
  'Box': 'Box',
  'Package': 'Box',
  'ShoppingCart': 'ShoppingCart',
  'ShoppingBag': 'ShoppingBag',
  'Sell': 'Sell',
  'Suitcase': 'Suitcase',
  'Briefcase': 'Briefcase',
  'Money': 'Money',
  'Wallet': 'Wallet',
  'Coin': 'Coin',
  'CreditCard': 'CreditCard',
  'Banknote': 'Money',
  'Calculator': 'Money',
  'Bank': 'OfficeBuilding',
  'Landmark': 'OfficeBuilding',
  'Building2': 'OfficeBuilding',
  'PriceTag': 'PriceTag',
  'Discount': 'Discount',
  'Present': 'Present',
  'Tickets': 'Tickets',
  'Stamp': 'Stamp',
  'Notebook': 'Notebook',
  'Reading': 'Reading',
  'BookOpen': 'Reading',
  'BookMark': 'Collection',
  'Collection': 'Collection',
  // 审计/安全
  'ShieldCheck': 'Lock',
  'FileCheck': 'DocumentChecked',
  'FileText': 'Document',
  'FileSpreadsheet': 'Document',
  'CheckCircle': 'CircleCheck',
  'CheckSquare': 'Select',
  'CircleCheck': 'CircleCheck',
  'Select': 'Select',
  // 消息/沟通
  'ChatDotRound': 'ChatDotRound',
  'ChatLineRound': 'ChatLineRound',
  'ChatRound': 'ChatRound',
  'Promotion': 'Promotion',
  'Headset': 'Headset',
  'Service': 'Service',
  // 其他
  'CloudServer': 'Monitor',
  'Platform': 'Platform',
  'Operation': 'Operation',
  'Management': 'Management',
  'Guide': 'Guide',
  'Compass': 'Compass',
  'Avatar': 'Avatar',
  'Columns': 'Grid',
  'Receipt': 'Tickets',
  'FileEdit': 'EditPen',
  'EditPen': 'EditPen',
  'Refresh': 'Refresh',
  'RefreshCw': 'Refresh',
  'Trash2': 'Delete',
  'ArrowRightLeft': 'Sort',
  'Sort': 'Sort',
  'Send': 'Promotion',
  'Inbox': 'Message',
  // Lucide 等第三方风格图标名 → Element Plus 官方图标
  'Trash': 'Delete',
  'Version': 'Clock',
  'Warehouse': 'House',
  'MapPin': 'Location',
  'Tags': 'PriceTag',
  'Layers': 'Grid',
  'Gift': 'Present',
  'LogIn': 'Download',
  'LogOut': 'Upload',
  'Repeat': 'Refresh',
  'ClipboardList': 'List',
  'Factory': 'OfficeBuilding',
  'Database': 'Grid',
  'ListChecks': 'List',
  'Boxes': 'Box',
  'Building': 'OfficeBuilding',
  'Van': 'ShoppingCart',
  'Table': 'Grid',
  'Layout': 'Operation',
  'Bookmark': 'Collection',
  'icon-agent': 'Cpu'
}

// 视图组件映射 - 根据后端返回的 component 路径映射到实际组件
const viewModules = import.meta.glob('@/views/**/*.vue', { eager: false })

// 根据 component 路径获取组件
function loadComponent(component) {
  if (!component) return null

  const normalizedComponent = component.replace(/^\//, '')

  const possiblePatterns = [
    `${normalizedComponent}.vue`,
    `${normalizedComponent}/index.vue`,
    normalizedComponent,
    `${normalizedComponent}/index`
  ]

  for (const pattern of possiblePatterns) {
    const searchKey = `@/views/${pattern}`
    if (viewModules[searchKey]) {
      return viewModules[searchKey]
    }

    for (const [key, value] of Object.entries(viewModules)) {
      if (key.endsWith(`/${pattern}`) || key === searchKey) {
        return value
      }
    }
  }

  console.warn(`[菜单Store] 找不到组件: ${component}，返回 NotFound`)
  return () => import('@/views/NotFound.vue')
}

export const useMenuStore = defineStore('menu', {
  state: () => ({
    // 原始菜单数据（从后端获取）
    menus: [],
    // 是否已加载菜单
    isLoaded: false,
    // 加载中状态
    loading: false,
    // 动态路由是否已注入
    routesReady: false,
    // 动态路由名称列表（用于追踪已添加的路由）
    dynamicRouteNames: [],
    // 路由重试计数器（防止无限重定向循环）
    routeRetryCount: 0
  }),

  getters: {
    // 获取菜单树
    menuTree: (state) => state.menus,

    // 获取图标名称
    getIconName: () => (iconName) => {
      return iconMap[iconName] || iconName || 'Document'
    }
  },

  actions: {
    // 从后端加载用户菜单
    async fetchUserMenus() {
      if (this.loading) return

      this.loading = true
      try {
        const res = await getUserMenus()
        console.log('[菜单Store] 获取到的菜单数据:', res)
        // 后端返回 code=0 表示成功 (RET.OK)
        if ((res.code === 0 || res.code === 200 || res.success) && res.data) {
          this.menus = res.data
          this.isLoaded = true
          console.log('[菜单Store] 菜单数据已保存:', this.menus)
        }
      } catch (error) {
        console.error('加载菜单失败:', error)
        this.menus = []
      } finally {
        this.loading = false
      }
    },

    // 生成动态路由
    generateRoutes() {
      const routes = []
      console.log('[菜单Store] generateRoutes 开始处理菜单:', this.menus)

      const flattenMenu = (menu) => {
        console.log('[菜单Store] 处理菜单:', menu)
        if (menu.menu_type === 'button') return []

        const result = []

        let routePath = menu.path || ''
        
        if (routePath.startsWith('/panel')) {
          routePath = routePath.replace(/^\/panel/, '')
        }
        if (routePath.startsWith('/')) {
          routePath = routePath.substring(1)
        }
        
        routePath = routePath.replace(/\/+/g, '/').replace(/\/$/, '')
        
        console.log('[菜单Store] 菜单路径:', menu.path, '转换后:', routePath)

        if (menu.component) {
          const route = {
            path: routePath,
            name: menu.name,
            meta: {
              title: menu.name,
              icon: menu.icon,
              permission: menu.permission,
              cached: menu.is_cached
            }
          }

          const component = loadComponent(menu.component)
          console.log('[菜单Store] 加载组件:', menu.component, '结果:', component)
          if (component) {
            route.component = component
          } else {
            route.component = () => import('@/views/NotFound.vue')
          }

          result.push(route)
        }

        if (menu.children && menu.children.length > 0) {
          menu.children.forEach(child => {
            result.push(...flattenMenu(child))
          })
        }

        return result
      }

      this.menus.forEach(menu => {
        if (menu.menu_type !== 'button') {
          routes.push(...flattenMenu(menu))
        }
      })

      routes.sort((a, b) => {
        return b.path.split('/').length - a.path.split('/').length
      })

      console.log('[菜单Store] generateRoutes 完成，生成的路由:', routes)
      return routes
    },

    // 重置菜单状态
    resetMenus() {
      this.menus = []
      this.isLoaded = false
      this.loading = false
      this.routesReady = false
      this.dynamicRouteNames = []
      this.routeRetryCount = 0
    }
  }
})