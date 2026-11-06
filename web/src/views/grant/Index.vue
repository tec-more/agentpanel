<template>
  <div class="grant-management">
    <!-- FR-02：仅超级管理员可访问 -->
    <el-result
      v-if="!userStore.isSuperuser"
      icon="error"
      title="无权限"
      sub-title="仅超级管理员可访问资源授权管理"
    />
    <template v-else>
      <!-- 搜索栏 -->
      <el-card shadow="never" class="search-card">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="资源类型">
            <el-select v-model="searchForm.resource_type" placeholder="请选择" clearable style="width: 140px">
              <el-option
                v-for="(label, value) in RESOURCE_TYPE_MAP"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="主体类型">
            <el-select v-model="searchForm.owner_type" placeholder="请选择" clearable style="width: 140px">
              <el-option
                v-for="(label, value) in OWNER_TYPE_MAP"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="授权状态">
            <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
              <el-option label="生效中" value="valid" />
              <el-option label="已过期" value="expired" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词">
            <el-input v-model="searchForm.keyword" placeholder="资源名称/主体名称" clearable />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
            <el-button :icon="Refresh" @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 授权记录表格 -->
      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="card-header">
            <span>授权记录</span>
            <div class="header-actions">
              <el-tooltip content="变更记录保留 90 天" placement="top">
                <el-button :icon="Clock" @click="goChangeLog">变更记录</el-button>
              </el-tooltip>
              <el-button type="primary" :icon="Plus" @click="createDialogVisible = true">新建授权</el-button>
            </div>
          </div>
        </template>

        <el-table v-loading="loading" :data="tableData" border stripe>
          <el-table-column prop="id" label="ID" width="70" align="center" />
          <el-table-column label="主体" min-width="180">
            <template #default="{ row }">
              <el-tag :type="ownerTagType(row.owner_type)" size="small" class="type-tag">
                {{ row.owner_type_label || OWNER_TYPE_MAP[row.owner_type] || row.owner_type }}
              </el-tag>
              <span>{{ row.owner_label }}</span>
            </template>
          </el-table-column>
          <el-table-column label="资源" min-width="200">
            <template #default="{ row }">
              <el-tag size="small" class="type-tag">
                {{ row.resource_type_label || RESOURCE_TYPE_MAP[row.resource_type] || row.resource_type }}
              </el-tag>
              <span>{{ row.resource_label }}</span>
              <el-tag v-if="row.resource_deleted" type="danger" size="small" class="deleted-tag">已删除</el-tag>
              <el-tag v-else-if="row.resource_inactive" type="warning" size="small" class="deleted-tag">已停用</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="granted_by" label="授权来源" min-width="120" show-overflow-tooltip />
          <el-table-column label="授权时间" width="160">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="过期时间" width="160">
            <template #default="{ row }">
              <span v-if="!row.expires_at">长期有效</span>
              <span v-else>{{ formatDateTime(row.expires_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'valid'" type="success" size="small">生效中</el-tag>
              <el-tag v-else type="info" size="small">已过期</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button type="danger" link @click="handleRevoke(row)">撤销</el-button>
            </template>
          </el-table-column>
          <!-- FR-02：空态文案 + 新建授权引导按钮（测试节点1 Q2 裁定） -->
          <template #empty>
            <el-empty description="暂无授权记录">
              <el-button type="primary" @click="createDialogVisible = true">新建授权</el-button>
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

      <!-- 新建授权弹窗（FR-03） -->
      <GrantCreateDialog v-model="createDialogVisible" @success="fetchData" />
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Clock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getGrantList, revokeGrant } from '@/api/grant'
import GrantCreateDialog from './GrantCreateDialog.vue'

const userStore = useUserStore()
const router = useRouter()

// B1+：跳转数据变更审计，按 resource_grant 表预筛
const goChangeLog = () => {
  router.push({ path: '/panel/audit/data-changes', query: { table_name: 'resource_grant' } })
}

// 资源类型/主体类型中文映射
const RESOURCE_TYPE_MAP = {
  model: '模型',
  kb: '知识库',
  tool: '工具',
  agent: '智能体',
  node_type: '节点类型'
}
const OWNER_TYPE_MAP = {
  cus: '客户',
  usr: '后台用户',
  org: '客户组织'
}

const loading = ref(false)
const tableData = ref([])
const createDialogVisible = ref(false)

const searchForm = reactive({
  resource_type: '',
  owner_type: '',
  status: '',
  keyword: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

// 主体类型标签颜色
const ownerTagType = (ownerType) => {
  const map = { cus: 'success', usr: 'warning', org: 'primary' }
  return map[ownerType] || 'info'
}

// FR-07：拉取授权记录列表
const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.resource_type) params.resource_type = searchForm.resource_type
    if (searchForm.owner_type) params.owner_type = searchForm.owner_type
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.keyword) params.keyword = searchForm.keyword

    const res = await getGrantList(params)
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
  searchForm.resource_type = ''
  searchForm.owner_type = ''
  searchForm.status = ''
  searchForm.keyword = ''
  handleSearch()
}

// 撤销授权
const handleRevoke = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确认撤销「${row.owner_label}」对「${row.resource_label}」的授权？撤销后该主体立即失去访问权限。`,
      '撤销授权',
      {
        type: 'warning',
        confirmButtonText: '确认撤销',
        cancelButtonText: '取消'
      }
    )
    await revokeGrant({
      owner_type: row.owner_type,
      owner_id: row.owner_id,
      resource_type: row.resource_type,
      resource_id: row.resource_id
    })
    ElMessage.success('撤销成功')
    fetchData()
  } catch (e) {
    // 取消或错误（错误已由拦截器提示）
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
.grant-management {
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

      .header-actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }

    .type-tag {
      margin-right: 6px;
    }

    .deleted-tag {
      margin-left: 6px;
    }
  }

  .pagination-wrapper {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
