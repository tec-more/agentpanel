<template>
  <div class="customer-edit">
    <el-card shadow="never" class="edit-card">
      <template #header>
        <div class="card-header">
          <el-button type="primary" :icon="Back" @click="handleBack">返回列表</el-button>
          <span class="edit-title">{{ isEdit ? '编辑客户' : '新增客户' }}</span>
        </div>
      </template>

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="10" animated />
      </div>

      <div v-else class="edit-content">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="120px"
          class="customer-form"
        >
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="用户名" prop="username">
                <el-input
                  v-model="form.username"
                  placeholder="请输入用户名"
                  :disabled="isEdit"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="昵称" prop="nickname">
                <el-input
                  v-model="form.nickname"
                  placeholder="请输入昵称"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="邮箱" prop="email">
                <el-input
                  v-model="form.email"
                  placeholder="请输入邮箱"
                  type="email"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="手机号" prop="phone">
                <el-input
                  v-model="form.phone"
                  placeholder="请输入手机号"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20" v-if="!isEdit">
            <el-col :span="12">
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="form.password"
                  type="password"
                  placeholder="请输入密码"
                  show-password
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="确认密码" prop="confirmPassword">
                <el-input
                  v-model="form.confirmPassword"
                  type="password"
                  placeholder="请再次输入密码"
                  show-password
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="状态">
                <el-switch
                  v-model="form.is_active"
                  active-text="启用"
                  inactive-text="禁用"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item>
            <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
              {{ isEdit ? '保存' : '创建' }}
            </el-button>
            <el-button @click="handleBack">取消</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import {
  getCustomerDetail,
  createCustomer,
  updateCustomer
} from '@/api/customer'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitLoading = ref(false)
const formRef = ref(null)

const isEdit = computed(() => !!route.params.id)
const customerId = computed(() => route.params.id)

const form = reactive({
  username: '',
  nickname: '',
  email: '',
  phone: '',
  password: '',
  confirmPassword: '',
  is_active: true
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在2-50个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度在6-128个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 如果是编辑模式，获取客户详情
const fetchCustomerDetail = async () => {
  if (!isEdit.value) return

  loading.value = true
  try {
    const res = await getCustomerDetail(customerId.value)
    const customer = res.data

    // 填充表单
    form.username = customer.username || ''
    form.nickname = customer.nickname || ''
    form.email = customer.email || ''
    form.phone = customer.phone || ''
    form.is_active = customer.is_active ?? true
  } catch (e) {
    ElMessage.error('获取客户信息失败')
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()

    submitLoading.value = true

    const submitData = {
      username: form.username,
      nickname: form.nickname,
      email: form.email,
      phone: form.phone || null,
      is_active: form.is_active
    }

    // 新增时需要密码
    if (!isEdit.value) {
      submitData.password = form.password
    }

    if (isEdit.value) {
      await updateCustomer(customerId.value, submitData)
      ElMessage.success('更新成功')
    } else {
      await createCustomer(submitData)
      ElMessage.success('创建成功')
    }

    // 延迟跳转，让用户看到成功提示
    setTimeout(() => {
      handleBack()
    }, 500)
  } catch (e) {
    // 表单验证失败或API错误
    if (submitLoading.value) {
      ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
    }
  } finally {
    submitLoading.value = false
  }
}

const handleBack = () => {
  router.push('/panel/customer/list')
}

onMounted(() => {
  fetchCustomerDetail()
})
</script>

<style lang="scss" scoped>
.customer-edit {
  .edit-card {
    .card-header {
      display: flex;
      align-items: center;
      gap: 16px;

      .edit-title {
        font-size: 18px;
        font-weight: bold;
      }
    }
  }

  .loading-container {
    padding: 20px 0;
  }

  .edit-content {
    .customer-form {
      max-width: 800px;
    }
  }
}
</style>


