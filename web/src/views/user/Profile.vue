<template>
  <div class="profile-container">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span>个人信息</span>
        </div>
      </template>
      
      <el-form 
        ref="profileFormRef"
        :model="profileForm" 
        :rules="profileRules" 
        label-width="100px"
        class="profile-form"
      >
        <el-descriptions :column="2" border class="user-info">
          <el-descriptions-item label="用户ID">{{ userStore.userInfo?.id }}</el-descriptions-item>
          <el-descriptions-item label="用户名">{{ userStore.userInfo?.username }}</el-descriptions-item>
          <el-descriptions-item label="是否激活">
            <el-tag :type="userStore.userInfo?.is_active ? 'success' : 'danger'">
              {{ userStore.userInfo?.is_active ? '是' : '否' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="是否管理员">
            <el-tag :type="userStore.userInfo?.is_superuser ? 'primary' : 'info'">
              {{ userStore.userInfo?.is_superuser ? '是' : '否' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最后登录">
            {{ userStore.userInfo?.last_login ? formatDateTime(userStore.userInfo.last_login) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ userStore.userInfo?.created_at ? formatDateTime(userStore.userInfo.created_at) : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        
        <el-divider content-position="left">编辑信息</el-divider>
        
        <el-form-item label="姓名" prop="alias">
          <el-input v-model="profileForm.alias" placeholder="请输入姓名" />
        </el-form-item>
        
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        
        <el-form-item label="电话" prop="phone">
          <el-input v-model="profileForm.phone" placeholder="请输入电话" />
        </el-form-item>
        
        <el-form-item label="部门" prop="dept_id">
          <span class="dept-name">{{ userStore.userInfo?.dept_name || '-' }}</span>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="submitProfile" :loading="loading">保存修改</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { updateProfile, getCurrentUser } from '@/api/auth'

const userStore = useUserStore()
const profileFormRef = ref(null)
const loading = ref(false)

const profileForm = ref({
  alias: '',
  email: '',
  phone: ''
})

const profileRules = {
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const initForm = () => {
  const userInfo = userStore.userInfo
  if (userInfo) {
    profileForm.value = {
      alias: userInfo.alias || '',
      email: userInfo.email || '',
      phone: userInfo.phone || ''
    }
  }
}

const resetForm = () => {
  initForm()
  profileFormRef.value?.resetFields()
}

const submitProfile = async () => {
  await profileFormRef.value.validate()
  loading.value = true
  try {
    const res = await updateProfile(profileForm.value)
    ElMessage.success(res.msg || '更新成功')
    // 重新获取用户信息并更新 store
    await userStore.fetchUserInfo()
  } catch (error) {
    console.error('更新失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  initForm()
})
</script>

<style lang="scss" scoped>
.profile-container {
  padding: 0;
}

.profile-card {
  .card-header {
    font-size: 18px;
    font-weight: 500;
  }
  
  .profile-form {
    max-width: 800px;
    margin: 0 auto;
  }
  
  .user-info {
    margin-bottom: 20px;
  }
  
  .dept-name {
    color: #606266;
  }
}
</style>


