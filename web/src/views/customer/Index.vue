<template>
  <div class="customer-management">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="客户名称">
          <el-input v-model="searchForm.username" placeholder="请输入客户名称" clearable />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="searchForm.email" placeholder="请输入邮箱" clearable />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="searchForm.phone" placeholder="请输入手机号" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="请选择" clearable style="width: 120px">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>客户列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增客户</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="nickname" label="昵称" width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="phone" label="手机号" width="120" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="handleToggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column label="认证" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_verified" type="success" size="small">已认证</el-tag>
            <el-tag v-else type="info" size="small">未认证</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录" width="160" />
        <el-table-column prop="login_count" label="登录次数" width="100" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
              <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
              <el-button type="success" link :icon="Money" @click="handleUpdatePoints(row)">充值</el-button>
              <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑客户' : '新增客户'"
      width="550px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="客户名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入客户名称" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="初始点卷">
          <el-input-number v-model="form.points" :min="0" :step="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="会员到期日期">
          <el-date-picker
            v-model="form.membership_expiry_date"
            type="datetime"
            placeholder="选择会员到期日期"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 充值点卷弹窗 -->
    <el-dialog v-model="pointsDialogVisible" title="充值点卷" width="400px">
      <div class="points-dialog-content">
        <p class="points-tip">当前客户: <strong>{{ currentCustomer?.name }}</strong></p>
        <p class="points-tip">当前点卷: <strong>{{ currentCustomer?.points }}</strong></p>
        <el-form ref="pointsFormRef" :model="pointsForm" :rules="pointsRules" label-width="80px">
          <el-form-item label="充值金额" prop="points">
            <el-input-number v-model="pointsForm.points" :min="100" :step="100" style="width: 100%" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="pointsDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="pointsLoading" @click="handlePointsSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete, Money, View } from '@element-plus/icons-vue'
import {
  getCustomerList,
  createCustomer,
  updateCustomer,
  deleteCustomer,
  toggleCustomerStatus,
  updateCustomerPoints
} from '@/api/customer'

const loading = ref(false)
const submitLoading = ref(false)
const pointsLoading = ref(false)
const dialogVisible = ref(false)
const pointsDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const pointsFormRef = ref(null)
const router = useRouter()

const tableData = ref([])
const currentCustomer = ref(null)

const searchForm = reactive({
  username: '',
  email: '',
  phone: '',
  is_active: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = ref({
  name: '',
  email: '',
  phone: '',
  points: 0,
  membership_expiry_date: null
})

const pointsForm = reactive({
  points: 100
})

const rules = {
  name: [
    { required: true, message: '请输入客户名称', trigger: 'blur' },
    { min: 2, max: 50, message: '客户名称长度在2-50个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}

const pointsRules = {
  points: [
    { required: true, message: '请输入充值金额', trigger: 'blur' },
    { type: 'number', min: 100, message: '充值金额不能少于100', trigger: 'blur' }
  ]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getCustomerList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items
    pagination.total = res.data.total
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.username = ''
  searchForm.email = ''
  searchForm.phone = ''
  searchForm.is_active = null
  handleSearch()
}

const handleAdd = () => {
  router.push('/panel/customer/create')
}

const handleDetail = (row) => {
  router.push(`/panel/customer/detail/${row.id}`)
}

const handleEdit = (row) => {
  router.push(`/panel/customer/edit/${row.id}`)
}

const handleSubmit = async () => {
  await formRef.value.validate()

  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateCustomer(form.value.id, {
        name: form.value.name,
        email: form.value.email,
        phone: form.value.phone,
        points: form.value.points,
        membership_expiry_date: form.value.membership_expiry_date
      })
      ElMessage.success('更新成功')
    } else {
      await createCustomer(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除客户 "${row.name}" 吗？`, '提示', {
      type: 'warning'
    })
    await deleteCustomer(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

const handleToggleStatus = async (row) => {
  try {
    await toggleCustomerStatus(row.id)
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch (e) {
    row.is_active = !row.is_active
  }
}

const handleUpdatePoints = (row) => {
  currentCustomer.value = row
  pointsForm.points = 100
  pointsDialogVisible.value = true
}

const handlePointsSubmit = async () => {
  await pointsFormRef.value.validate()

  pointsLoading.value = true
  try {
    await updateCustomerPoints(currentCustomer.value.id, {
      points: pointsForm.points
    })
    ElMessage.success('充值成功')
    pointsDialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    pointsLoading.value = false
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
  pointsFormRef.value?.resetFields()
}

// 格式化日期时间
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.customer-management {
  .search-card {
    margin-bottom: 16px;

    .search-form {
      display: flex;
      flex-wrap: wrap;

      .el-form-item {
        margin-bottom: 0;
        margin-right: 16px;
      }
    }
  }

  .table-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }

  .pagination-wrapper {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }

  .action-buttons {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 4px;
  }

  .points-dialog-content {
    .points-tip {
      margin-bottom: 16px;
      color: #666;
    }
  }
}
</style>

