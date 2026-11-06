<template>
  <div class="organization-management">
    <!-- 仅超级管理员可访问（与资源授权页权限口径一致） -->
    <el-result
      v-if="!userStore.isSuperuser"
      icon="error"
      title="无权限"
      sub-title="仅超级管理员可访问客户组织管理"
    />
    <template v-else>
      <!-- 搜索栏 -->
      <el-card shadow="never" class="search-card">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="关键词">
            <el-input v-model="searchForm.keyword" placeholder="组织名称" clearable />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
              <el-option label="启用" value="active" />
              <el-option label="停用" value="disabled" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
            <el-button :icon="Refresh" @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 组织列表 -->
      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="card-header">
            <span>客户组织</span>
            <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建组织</el-button>
          </div>
        </template>

        <el-table v-loading="loading" :data="tableData" border stripe>
          <el-table-column prop="id" label="ID" width="70" align="center" />
          <el-table-column prop="name" label="组织名称" min-width="180" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status === 'active' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="所有者" min-width="140">
            <template #default="{ row }">
              <span>{{ row.owner_username || '-' }}</span>
              <el-text v-if="row.owner_customer_id" size="small" type="info">
                #{{ row.owner_customer_id }}
              </el-text>
            </template>
          </el-table-column>
          <el-table-column prop="member_count" label="成员数" width="90" align="center" />
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" align="center" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link @click="openDetail(row)">详情</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无客户组织">
              <el-button type="primary" @click="openCreateDialog">新建组织</el-button>
            </el-empty>
          </template>
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

      <!-- 新建组织弹窗 -->
      <el-dialog v-model="createDialogVisible" title="新建组织" width="480px" @close="resetCreateForm">
        <el-form :model="createForm" label-width="90px">
          <el-form-item label="组织名称" required>
            <el-input v-model="createForm.name" placeholder="请输入组织名称" maxlength="100" show-word-limit />
          </el-form-item>
          <el-form-item label="所有者" required>
            <SubjectSelect
              v-model="createForm.owner_customer_id"
              subject-type="cus"
              :multiple="false"
            />
            <el-text size="small" type="info">所有者创建后自动成为组织 owner 成员</el-text>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="createLoading" @click="handleCreate">确定</el-button>
        </template>
      </el-dialog>

      <!-- 组织详情抽屉（成员 / 授权） -->
      <OrganizationDetailDrawer
        v-model="detailVisible"
        :org-id="currentOrgId"
        @refresh="fetchData"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getOrganizationList, createOrganization } from '@/api/organization'
import SubjectSelect from '@/views/grant/components/SubjectSelect.vue'
import OrganizationDetailDrawer from './components/OrganizationDetailDrawer.vue'

const userStore = useUserStore()

const loading = ref(false)
const tableData = ref([])
const detailVisible = ref(false)
const currentOrgId = ref(null)

const createDialogVisible = ref(false)
const createLoading = ref(false)

const searchForm = reactive({
  keyword: '',
  status: ''
})

const createForm = reactive({
  name: '',
  owner_customer_id: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.status) params.status = searchForm.status

    const res = await getOrganizationList(params)
    const d = res?.data ?? res
    tableData.value = d.items || []
    pagination.total = d.total || 0
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.keyword = ''
  searchForm.status = ''
  handleSearch()
}

const openDetail = (row) => {
  currentOrgId.value = row.id
  detailVisible.value = true
}

const openCreateDialog = () => {
  createDialogVisible.value = true
}

const resetCreateForm = () => {
  createForm.name = ''
  createForm.owner_customer_id = ''
}

const handleCreate = async () => {
  const name = createForm.name.trim()
  if (!name) {
    ElMessage.warning('请输入组织名称')
    return
  }
  if (!createForm.owner_customer_id) {
    ElMessage.warning('请选择组织所有者')
    return
  }

  createLoading.value = true
  try {
    await createOrganization({
      name,
      owner_customer_id: Number(createForm.owner_customer_id)
    })
    ElMessage.success('组织创建成功')
    createDialogVisible.value = false
    resetCreateForm()
    pagination.page = 1
    fetchData()
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    createLoading.value = false
  }
}

// 格式化日期时间为本地字符串
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
  if (userStore.isSuperuser) {
    fetchData()
  }
})
</script>

<style lang="scss" scoped>
.organization-management {
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
}
</style>
