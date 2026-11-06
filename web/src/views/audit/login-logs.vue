<template>
  <div class="login-logs">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="登录类型">
          <el-select v-model="searchForm.login_type" placeholder="请选择" clearable style="width: 140px">
            <el-option label="登录" value="login" />
            <el-option label="登出" value="logout" />
            <el-option label="登录失败" value="login_failed" />
            <el-option label="密码修改" value="password_change" />
            <el-option label="Token刷新" value="token_refresh" />
          </el-select>
        </el-form-item>
        <el-form-item label="登录方式">
          <el-select v-model="searchForm.login_method" placeholder="请选择" clearable style="width: 140px">
            <el-option label="密码" value="password" />
            <el-option label="短信" value="sms" />
            <el-option label="邮箱" value="email" />
            <el-option label="微信" value="wechat" />
            <el-option label="第三方" value="third_party" />
            <el-option label="Token" value="token" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否成功">
          <el-select v-model="searchForm.success" placeholder="请选择" clearable style="width: 100px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px"
          />
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
          <span>登录审计日志列表</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="trace_id" label="Trace ID" width="200" show-overflow-tooltip />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column label="登录类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getLoginTypeTagType(row.login_type)">
              {{ getLoginTypeLabel(row.login_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="login_method" label="登录方式" width="120" />
        <el-table-column label="是否成功" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.success ? 'success' : 'danger'">
              {{ row.success ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP地址" width="140" />
        <el-table-column prop="location" label="地理位置" width="150" show-overflow-tooltip />
        <el-table-column prop="session_id" label="会话ID" width="150" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="登录审计日志详情" width="900px">
      <el-descriptions v-if="currentLog" :column="1" border>
        <el-descriptions-item label="ID">{{ currentLog.id }}</el-descriptions-item>
        <el-descriptions-item label="Trace ID">{{ currentLog.trace_id }}</el-descriptions-item>
        <el-descriptions-item label="用户ID">{{ currentLog.user_id }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ currentLog.username }}</el-descriptions-item>
        <el-descriptions-item label="登录类型">
          <el-tag size="small" :type="getLoginTypeTagType(currentLog.login_type)">
            {{ getLoginTypeLabel(currentLog.login_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="登录方式">{{ currentLog.login_method }}</el-descriptions-item>
        <el-descriptions-item label="是否成功">
          <el-tag size="small" :type="currentLog.success ? 'success' : 'danger'">
            {{ currentLog.success ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="失败原因">{{ currentLog.fail_reason }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentLog.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="地理位置">{{ currentLog.location }}</el-descriptions-item>
        <el-descriptions-item label="User-Agent">{{ currentLog.user_agent }}</el-descriptions-item>
        <el-descriptions-item label="设备信息">
          <pre v-if="currentLog.device_info">{{ JSON.stringify(currentLog.device_info, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="会话ID">{{ currentLog.session_id }}</el-descriptions-item>
        <el-descriptions-item label="Token ID">{{ currentLog.token_id }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentLog.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentLog.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const detailDialogVisible = ref(false)
const currentLog = ref(null)

const tableData = ref([])
const dateRange = ref([])

const searchForm = reactive({
  username: '',
  login_type: null,
  login_method: null,
  success: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const getLoginTypeTagType = (loginType) => {
  const types = {
    login: 'success',
    logout: 'info',
    login_failed: 'danger',
    password_change: 'warning',
    token_refresh: 'primary'
  }
  return types[loginType] || ''
}

const getLoginTypeLabel = (loginType) => {
  const labels = {
    login: '登录',
    logout: '登出',
    login_failed: '登录失败',
    password_change: '密码修改',
    token_refresh: 'Token刷新'
  }
  return labels[loginType] || loginType
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_time = dateRange.value[0]
      params.end_time = dateRange.value[1]
    }
    const res = await request.get('/v1/audit/login-logs/list', { params })
    tableData.value = res.data.items || res.data || []
    pagination.total = res.data.total || tableData.value.length
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
  searchForm.login_type = null
  searchForm.login_method = null
  searchForm.success = null
  dateRange.value = []
  handleSearch()
}

const handleDetail = (row) => {
  currentLog.value = row
  detailDialogVisible.value = true
}

fetchData()
</script>

<style lang="scss" scoped>
.login-logs {
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
}
</style>


