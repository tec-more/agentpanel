<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="logo">
        <img src="@/assets/logo.svg" alt="logo" class="logo-img" />
        <span v-show="!isCollapse" class="logo-text">AI Panel</span>
      </div>

      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        :collapse-transition="false"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        :default-openeds="defaultOpenedMenus"
        @select="handleMenuSelect"
      >
        <!-- 动态菜单渲染 -->
        <template v-for="menu in menuStore.menuTree" :key="menu.id">
          <!-- 有子菜单的情况 -->
          <el-sub-menu v-if="menu.children && menu.children.length > 0" :index="getMenuIndexPath(menu.path, menu.id)">
            <template #title>
              <el-icon>
                <component :is="getIconComponent(menu.icon)" />
              </el-icon>
              <span>{{ menu.name }}</span>
            </template>
            <!-- 递归渲染子菜单 -->
            <template v-for="child in menu.children" :key="child.id">
              <el-sub-menu v-if="child.children && child.children.length > 0" :index="getMenuIndexPath(child.path, child.id)">
                <template #title>
                  <el-icon>
                    <component :is="getIconComponent(child.icon)" />
                  </el-icon>
                  <span>{{ child.name }}</span>
                </template>
                <el-menu-item v-for="subChild in child.children" :key="subChild.id" :index="getMenuIndexPath(subChild.path, subChild.id)" @click="handleMenuClick(subChild.path)">
                  <el-icon>
                    <component :is="getIconComponent(subChild.icon)" />
                  </el-icon>
                  <template #title>{{ subChild.name }}</template>
                </el-menu-item>
              </el-sub-menu>
              <el-menu-item v-else :index="getMenuIndexPath(child.path, child.id)" @click="handleMenuClick(child.path)">
                <el-icon>
                  <component :is="getIconComponent(child.icon)" />
                </el-icon>
                <template #title>{{ child.name }}</template>
              </el-menu-item>
            </template>
          </el-sub-menu>
          <!-- 没有子菜单的情况 -->
          <el-menu-item v-else :index="getMenuIndexPath(menu.path, menu.id)" @click="handleMenuClick(menu.path)">
            <el-icon>
              <component :is="getIconComponent(menu.icon)" />
            </el-icon>
            <template #title>{{ menu.name }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <!-- 顶部导航 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="toggleCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <el-button 
            type="link" 
            size="small" 
            @click="goBack" 
            class="back-btn"
            v-if="showBackButton"
          >
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/panel/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentMeta.title">
              {{ currentMeta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <MailBell v-if="system.isPluginEnabled('mail')" />
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="username">{{ userStore.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="main">
        <GlobalApproval />
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- 全局审批提示组件 -->
    <ApprovalPrompt />
  </el-container>

  <!-- 修改密码弹窗 -->
  <el-dialog v-model="passwordVisible" title="修改密码" width="400px">
    <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="80px">
      <el-form-item label="原密码" prop="old_password">
        <el-input v-model="passwordForm.old_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码" prop="new_password">
        <el-input v-model="passwordForm.new_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="确认密码" prop="confirm_password">
        <el-input v-model="passwordForm.confirm_password" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="passwordVisible = false">取消</el-button>
      <el-button type="primary" @click="submitPassword">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, markRaw } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UserFilled, ArrowLeft, ArrowDown, Fold, Expand
} from '@element-plus/icons-vue'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useMenuStore } from '@/stores/menu'
import { changePassword } from '@/api/auth'
import ApprovalPrompt from '@/views/approval/ApprovalPrompt.vue'
import GlobalApproval from '@/components/GlobalApproval.vue'
import MailBell from '@/components/MailBell.vue'
import { useSystemStore } from '@/stores/system'

// 全量注册 Element Plus 图标（293 个），菜单图标名可直接使用
const iconComponents = {}
for (const [name, comp] of Object.entries(ElementPlusIconsVue)) {
  iconComponents[name] = markRaw(comp)
}

// 根据图标名称获取组件：经 menuStore 的图标映射规范化（兼容 Lucide 等命名），再查官方图标，最后回退 Document
const getIconComponent = (iconName) => {
  const resolved = menuStore.getIconName(iconName)
  return iconComponents[resolved] || iconComponents.Document
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const menuStore = useMenuStore()
const system = useSystemStore()

const isCollapse = ref(false)
const passwordVisible = ref(false)
const passwordFormRef = ref(null)

const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const validateConfirm = (rule, value, callback) => {
  if (value !== passwordForm.value.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' }
  ]
}

const currentRoute = computed(() => route.path)
const currentMeta = computed(() => route.meta || {})

const showBackButton = computed(() => {
  // 在非首页的后台页面显示返回按钮
  return currentRoute.value !== '/panel/dashboard'
})

const goBack = () => {
  // 返回到上一个页面
  router.back()
}

// 添加 /panel 前缀到菜单路径
const getMenuIndexPath = (path, id) => {
  if (!path) return `menu-${id}`
  // 确保路径以 /panel 开头
  if (!path.startsWith('/panel')) {
    return `/panel${path}`
  }
  return path
}

// 处理菜单点击
const handleMenuClick = (path) => {
  if (path) {
    // 确保路径以 /panel 开头
    const targetPath = path.startsWith('/panel') ? path : `/panel${path}`
    router.push(targetPath)
  }
}

// 处理菜单选择事件（el-menu 的 @select 事件）
const handleMenuSelect = (index) => {
  // index 是菜单项的 index 属性值，这里不需要额外处理
  // 因为点击事件已经在 handleMenuClick 中处理了
  console.log('[菜单选择]', index)
}

// 计算默认展开的菜单
const defaultOpenedMenus = computed(() => {
  const currentPath = route.path
  const opened = []

  menuStore.menuTree.forEach(menu => {
    if (menu.children && menu.children.length > 0) {
      const hasActiveChild = menu.children.some(child => {
        const childPath = child.path.startsWith('/panel') ? child.path : `/panel${child.path}`
        return currentPath.startsWith(childPath)
      })
      if (hasActiveChild) {
        const parentPath = menu.path.startsWith('/panel') ? menu.path : `/panel${menu.path}`
        opened.push(parentPath)
      }
    }
  })

  return opened
})

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const handleCommand = async (command) => {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        type: 'warning'
      })
      await userStore.logout()
      menuStore.resetMenus()
      router.push('/panel')
    } catch {
      // 取消操作
    }
  } else if (command === 'password') {
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    passwordVisible.value = true
  } else if (command === 'profile') {
    router.push('/panel/profile')
  }
}

const submitPassword = async () => {
  await passwordFormRef.value.validate()
  await changePassword({
    old_password: passwordForm.value.old_password,
    new_password: passwordForm.value.new_password
  })
  ElMessage.success('密码修改成功')
  passwordVisible.value = false
}

// 组件挂载时加载菜单
onMounted(async () => {
  if (!menuStore.isLoaded) {
    await menuStore.fetchUserMenus()
  }
})
</script>

<style lang="scss" scoped>
.main-layout {
  height: 100vh;
}

.aside {
  background-color: #304156;
  transition: width 0.3s;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;

  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 16px;
    background-color: #263445;

    .logo-img {
      width: 32px;
      height: 32px;
    }

    .logo-text {
      margin-left: 10px;
      font-size: 18px;
      font-weight: bold;
      color: #fff;
      white-space: nowrap;
    }
  }

  .el-menu {
    border-right: none;
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
  }
  
  .el-menu::-webkit-scrollbar {
    width: 4px;
  }
  
  .el-menu::-webkit-scrollbar-track {
    background: #263445;
  }
  
  .el-menu::-webkit-scrollbar-thumb {
    background: #409eff;
    border-radius: 2px;
  }
  
  .el-menu::-webkit-scrollbar-thumb:hover {
    background: #66b1ff;
  }
}

.main-container {
  display: flex;
  flex-direction: column;
}

.header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);

  .header-left {
    display: flex;
    align-items: center;

    .collapse-btn {
      font-size: 20px;
      cursor: pointer;
      margin-right: 16px;

      &:hover {
        color: #409eff;
      }
    }

    .back-btn {
      margin-right: 16px;
      color: #606266;

      &:hover {
        color: #409eff;
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;

    .user-info {
      display: flex;
      align-items: center;
      cursor: pointer;

      .username {
        margin: 0 8px;
      }
    }
  }
}

.main {
  background-color: #f0f2f5;
  padding: 20px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>


