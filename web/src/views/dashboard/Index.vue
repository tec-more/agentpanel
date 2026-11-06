<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20">
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon user-icon">
            <el-icon :size="28"><User /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.user_count }}</div>
            <div class="stat-label">用户总数</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon active-icon">
            <el-icon :size="28"><CircleCheck /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.active_user_count }}</div>
            <div class="stat-label">活跃用户</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon dept-icon">
            <el-icon :size="28"><OfficeBuilding /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.dept_count }}</div>
            <div class="stat-label">部门数量</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon role-icon">
            <el-icon :size="28"><UserFilled /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.role_count }}</div>
            <div class="stat-label">角色数量</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 第二行统计 -->
    <el-row :gutter="20" class="mt-20">
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon perm-icon">
            <el-icon :size="28"><Key /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.permission_count }}</div>
            <div class="stat-label">权限数量</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon menu-icon">
            <el-icon :size="28"><Menu /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.menu_count }}</div>
            <div class="stat-label">菜单数量</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-card shadow="hover" class="stat-card time-card">
          <div class="stat-icon time-icon">
            <el-icon :size="28"><Clock /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value time-value">{{ currentTime }}</div>
            <div class="stat-label">{{ currentDate }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 内容区 -->
    <el-row :gutter="20" class="mt-20">
      <!-- 欢迎卡片 -->
      <el-col :xs="24" :lg="16">
        <el-card shadow="hover" class="welcome-card">
          <template #header>
            <div class="card-header">
              <span>欢迎使用</span>
            </div>
          </template>
          <div class="welcome-content">
            <div class="welcome-text">
              <h2>AI Panel Admin</h2>
              <p class="subtitle">现代化后台管理系统</p>
              <p class="welcome-msg">
                欢迎回来，<span class="username">{{ userStore.username }}</span>！
                <span v-if="userInfo.last_login" class="last-login">
                  上次登录: {{ userInfo.last_login }}
                </span>
              </p>
            </div>
            <el-divider />
            <h4>快速入口</h4>
            <div class="quick-links">
              <el-button type="primary" @click="$router.push('/panel/users')">
                <el-icon><User /></el-icon>
                用户管理
              </el-button>
              <el-button type="success" @click="$router.push('/panel/departments')">
                <el-icon><OfficeBuilding /></el-icon>
                部门管理
              </el-button>
              <el-button type="warning" @click="$router.push('/panel/roles')">
                <el-icon><UserFilled /></el-icon>
                角色管理
              </el-button>
              <el-button type="info" @click="$router.push('/panel/menus')">
                <el-icon><Menu /></el-icon>
                菜单管理
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 用户信息卡片 -->
      <el-col :xs="24" :lg="8">
        <el-card shadow="hover" class="profile-card">
          <template #header>
            <div class="card-header">
              <span>个人信息</span>
            </div>
          </template>
          <div class="user-profile">
            <el-avatar :size="80" class="avatar">
              <el-icon :size="40"><UserFilled /></el-icon>
            </el-avatar>
            <div class="profile-info">
              <h3>{{ userInfo.username || userStore.username }}</h3>
              <p class="email">{{ userInfo.email || userStore.userInfo.email }}</p>
              <div class="tags">
                <el-tag
                  :type="userInfo.is_superuser || userStore.isSuperuser ? 'danger' : 'info'"
                  size="small"
                >
                  {{ userInfo.is_superuser || userStore.isSuperuser ? '超级管理员' : '普通用户' }}
                </el-tag>
                <el-tag
                  :type="userInfo.is_active !== false ? 'success' : 'warning'"
                  size="small"
                  class="ml-8"
                >
                  {{ userInfo.is_active !== false ? '正常' : '禁用' }}
                </el-tag>
              </div>
              <div v-if="userInfo.roles && userInfo.roles.length" class="roles">
                <span class="role-label">角色：</span>
                <el-tag
                  v-for="role in userInfo.roles"
                  :key="role"
                  size="small"
                  type="primary"
                  class="role-tag"
                >
                  {{ role }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近用户 -->
    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>最近注册用户</span>
              <el-button type="primary" link @click="$router.push('/panel/users')">
                查看全部
              </el-button>
            </div>
          </template>
          <el-table :data="stats.recent_users" stripe style="width: 100%">
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="email" label="邮箱" />
            <el-table-column prop="is_active" label="状态">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                  {{ row.is_active ? '正常' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="注册时间" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { UserFilled, CircleCheck } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getDashboardStats, getCurrentUserInfo } from '@/api/dashboard'

const userStore = useUserStore()

const stats = ref({
  user_count: 0,
  active_user_count: 0,
  dept_count: 0,
  role_count: 0,
  permission_count: 0,
  menu_count: 0,
  recent_users: []
})

const userInfo = ref({})

const currentTime = ref('')
const currentDate = ref('')
let timer = null

const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
  currentDate.value = now.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long'
  })
}

const loadStats = async () => {
  try {
    const res = await getDashboardStats()
    if (res.data) {
      stats.value = res.data
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

const loadUserInfo = async () => {
  try {
    const res = await getCurrentUserInfo()
    if (res.data) {
      userInfo.value = res.data
    }
  } catch (error) {
    console.error('加载用户信息失败:', error)
  }
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  loadStats()
  loadUserInfo()
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style lang="scss" scoped>
.dashboard {
  .mt-20 {
    margin-top: 20px;
  }

  .ml-8 {
    margin-left: 8px;
  }

  .stat-card {
    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      padding: 20px;
    }

    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      margin-right: 16px;
      flex-shrink: 0;
    }

    .user-icon {
      background: linear-gradient(135deg, #409EFF, #79bbff);
    }

    .active-icon {
      background: linear-gradient(135deg, #67C23A, #95d475);
    }

    .dept-icon {
      background: linear-gradient(135deg, #E6A23C, #eebe77);
    }

    .role-icon {
      background: linear-gradient(135deg, #F56C6C, #f89898);
    }

    .perm-icon {
      background: linear-gradient(135deg, #909399, #b1b3b8);
    }

    .menu-icon {
      background: linear-gradient(135deg, #9b59b6, #c39bd3);
    }

    .time-icon {
      background: linear-gradient(135deg, #1abc9c, #48c9b0);
    }

    .stat-content {
      flex: 1;
      min-width: 0;

      .stat-value {
        font-size: 28px;
        font-weight: 600;
        color: #303133;
        line-height: 1.2;
      }

      .time-value {
        font-size: 24px;
        font-family: 'Courier New', monospace;
      }

      .stat-label {
        font-size: 14px;
        color: #909399;
        margin-top: 4px;
      }
    }
  }

  .time-card {
    :deep(.el-card__body) {
      justify-content: flex-start;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .welcome-card {
    .welcome-content {
      .welcome-text {
        h2 {
          font-size: 24px;
          color: #303133;
          margin: 0 0 8px 0;
        }

        .subtitle {
          color: #909399;
          margin: 0 0 16px 0;
        }

        .welcome-msg {
          color: #606266;
          margin: 0;

          .username {
            color: #409EFF;
            font-weight: 500;
          }

          .last-login {
            color: #909399;
            font-size: 13px;
            margin-left: 16px;
          }
        }
      }

      h4 {
        color: #303133;
        font-size: 16px;
        margin: 0 0 16px 0;
      }

      .quick-links {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
      }
    }
  }

  .profile-card {
    .user-profile {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;

      .avatar {
        background: linear-gradient(135deg, #409EFF, #79bbff);
      }

      .profile-info {
        margin-top: 16px;
        width: 100%;

        h3 {
          font-size: 20px;
          color: #303133;
          margin: 0 0 8px 0;
        }

        .email {
          font-size: 14px;
          color: #909399;
          margin: 0 0 12px 0;
        }

        .tags {
          margin-bottom: 12px;
        }

        .roles {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid #EBEEF5;

          .role-label {
            color: #909399;
            font-size: 13px;
          }

          .role-tag {
            margin-left: 8px;
            margin-bottom: 4px;
          }
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .dashboard {
    .stat-card {
      margin-bottom: 12px;

      .stat-icon {
        width: 48px;
        height: 48px;
      }

      .stat-content {
        .stat-value {
          font-size: 22px;
        }
      }
    }

    .welcome-card .welcome-content {
      .quick-links {
        .el-button {
          width: 100%;
        }
      }
    }
  }
}
</style>


