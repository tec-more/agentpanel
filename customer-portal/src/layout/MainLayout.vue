<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <span class="logo-mark">C</span>
        <span>客户中心</span>
      </div>
      <el-menu :default-active="route.path" router class="menu"
        background-color="#10251c" text-color="#c8d6cf" active-text-color="#7fe0b0">
        <div class="menu-group">内容工作台</div>
        <el-menu-item index="/dashboard"><el-icon><DataBoard /></el-icon>工作台首页</el-menu-item>
        <el-menu-item index="/check"><el-icon><Search /></el-icon>内容合规检测</el-menu-item>
        <el-menu-item index="/rules"><el-icon><Document /></el-icon>合规规则</el-menu-item>
        <div class="menu-group">我的账户</div>
        <el-menu-item index="/profile"><el-icon><User /></el-icon>我的资料</el-menu-item>
        <el-menu-item index="/membership"><el-icon><Medal /></el-icon>我的会员</el-menu-item>
        <el-menu-item index="/orders"><el-icon><ShoppingBag /></el-icon>我的订单</el-menu-item>
        <el-menu-item index="/payments"><el-icon><Wallet /></el-icon>支付记录</el-menu-item>
        <el-menu-item index="/organizations"><el-icon><OfficeBuilding /></el-icon>我的组织</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="crumb">{{ currentTitle }}</div>
        <div class="user">
          <el-dropdown @command="onCommand">
            <span class="user-name">
              <el-icon><UserFilled /></el-icon> {{ auth.displayName }} <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">我的资料</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const currentTitle = computed(() => route.meta.title || '客户中心')

async function onCommand(cmd) {
  if (cmd === 'profile') router.push('/profile')
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout { height: 100%; }
.aside { background: #10251c; overflow: hidden; }
.logo {
  height: 60px; display: flex; align-items: center; gap: 10px;
  padding: 0 20px; color: #fff; font-size: 18px; font-weight: 600;
  border-bottom: 1px solid rgba(255,255,255,.08);
}
.logo-mark {
  width: 30px; height: 30px; border-radius: 8px;
  background: #2f9e6b; display: flex; align-items: center; justify-content: center;
}
.menu { border: none; }
.menu-group {
  color: #6f8a7c; font-size: 11px; letter-spacing: 1px;
  padding: 18px 20px 6px;
}
.header {
  background: #fff; border-bottom: 1px solid #e8ecea;
  display: flex; align-items: center; justify-content: space-between;
}
.crumb { font-size: 16px; font-weight: 600; }
.user-name { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 14px; }
.main { padding: 20px; overflow-y: auto; }
</style>
