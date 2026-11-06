<template>
  <div class="user-management">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="searchForm.email" placeholder="请输入邮箱" clearable />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="searchForm.dept_id"
            :data="deptTree"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="请选择部门"
            clearable
            check-strictly
            style="width: 180px"
          />
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
          <span>用户列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增用户</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="alias" label="姓名" min-width="100" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="dept_name" label="部门" min-width="120" />
        <el-table-column label="角色" min-width="150">
          <template #default="{ row }">
            <template v-if="row.is_superuser">
              <el-tag type="danger" size="small">超级管理员</el-tag>
            </template>
            <template v-else-if="row.roles && row.roles.length > 0">
              <el-tag
                v-for="role in row.roles"
                :key="role.id"
                size="small"
                style="margin-right: 4px"
              >
                {{ role.name }}
              </el-tag>
            </template>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              :disabled="row.is_superuser"
              @change="handleToggleStatus(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="Key" @click="handleAssignRole(row)">角色</el-button>
              <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
              <el-button
                type="danger"
                link
                :icon="Delete"
                :disabled="row.is_superuser"
                @click="handleDelete(row)"
              >
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
      :title="isEdit ? '编辑用户' : '新增用户'"
      width="550px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="姓名" prop="alias">
          <el-input v-model="form.alias" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="部门" prop="dept_id">
          <el-tree-select
            v-model="form.dept_id"
            :data="deptTree"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="请选择部门"
            clearable
            check-strictly
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配角色弹窗 -->
    <el-dialog v-model="roleDialogVisible" title="分配角色" width="500px">
      <div class="role-dialog-content">
        <p class="role-tip">当前用户: <strong>{{ currentUser?.username }}</strong></p>
        <el-checkbox-group v-model="checkedRoles" class="role-list">
          <div v-for="role in allRoles" :key="role.id" class="role-item">
            <el-checkbox :value="role.id" :label="role.id">
              <span class="role-name">{{ role.name }}</span>
              <span class="role-code">({{ role.code }})</span>
            </el-checkbox>
          </div>
        </el-checkbox-group>
        <el-empty v-if="allRoles.length === 0" description="暂无角色数据" />
      </div>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleLoading" @click="handleRoleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete, Key } from '@element-plus/icons-vue'
import {
  getUserList,
  createUser,
  updateUser,
  deleteUser,
  toggleUserStatus
} from '@/api/user'
import { getDepartmentTree } from '@/api/department'
import { getRoleList, getUserRoles, setUserRoles } from '@/api/rbac'

const loading = ref(false)
const submitLoading = ref(false)
const roleLoading = ref(false)
const dialogVisible = ref(false)
const roleDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const tableData = ref([])
const deptTree = ref([])
const allRoles = ref([])
const currentUser = ref(null)
const checkedRoles = ref([])

const searchForm = reactive({
  username: '',
  email: '',
  dept_id: null,
  is_active: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = ref({
  username: '',
  alias: '',
  email: '',
  password: '',
  phone: '',
  dept_id: null
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在3-20个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getUserList({
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

const fetchDeptTree = async () => {
  try {
    const res = await getDepartmentTree()
    deptTree.value = res.data || []
  } catch (e) {
    deptTree.value = []
  }
}

const fetchAllRoles = async () => {
  try {
    const res = await getRoleList({ page: 1, page_size: 100, is_active: true })
    allRoles.value = res.data.items || res.data || []
  } catch (e) {
    allRoles.value = []
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.username = ''
  searchForm.email = ''
  searchForm.dept_id = null
  searchForm.is_active = null
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  form.value = {
    username: '',
    alias: '',
    email: '',
    password: '',
    phone: '',
    dept_id: null
  }
  fetchDeptTree()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  form.value = {
    id: row.id,
    username: row.username,
    alias: row.alias || '',
    email: row.email,
    phone: row.phone || '',
    dept_id: row.dept_id
  }
  fetchDeptTree()
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()

  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateUser(form.value.id, {
        alias: form.value.alias,
        email: form.value.email,
        phone: form.value.phone,
        dept_id: form.value.dept_id
      })
      ElMessage.success('更新成功')
    } else {
      await createUser(form.value)
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
    await ElMessageBox.confirm(`确定要删除用户 "${row.username}" 吗？`, '提示', {
      type: 'warning'
    })
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

const handleToggleStatus = async (row) => {
  try {
    await toggleUserStatus(row.id)
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch (e) {
    row.is_active = !row.is_active
  }
}

const handleAssignRole = async (row) => {
  currentUser.value = row
  await fetchAllRoles()

  try {
    const res = await getUserRoles(row.id)
    checkedRoles.value = (res.data || []).map(r => r.id)
  } catch (e) {
    checkedRoles.value = []
  }

  roleDialogVisible.value = true
}

const handleRoleSubmit = async () => {
  roleLoading.value = true
  try {
    await setUserRoles(currentUser.value.id, checkedRoles.value)
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    roleLoading.value = false
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
}

onMounted(() => {
  fetchData()
  fetchDeptTree()
})
</script>

<style lang="scss" scoped>
.user-management {
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
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .action-buttons {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 4px;
  }

  .role-dialog-content {
    .role-tip {
      margin-bottom: 16px;
      color: #666;
    }

    .role-list {
      display: flex;
      flex-wrap: wrap;

      .role-item {
        width: 50%;
        margin-bottom: 12px;

        .role-name {
          font-weight: 500;
        }

        .role-code {
          color: #999;
          font-size: 12px;
          margin-left: 4px;
        }
      }
    }
  }
}
</style>


