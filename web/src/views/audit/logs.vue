<template>
  <div class="audit-logs">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="searchForm.module" placeholder="请输入模块" clearable />
        </el-form-item>
        <el-form-item label="操作">
          <el-input v-model="searchForm.operation" placeholder="请输入操作" clearable />
        </el-form-item>
        <el-form-item label="审计级别">
          <el-select v-model="searchForm.level" placeholder="请选择" clearable style="width: 120px">
            <el-option label="INFO" value="info" />
            <el-option label="WARNING" value="warning" />
            <el-option label="ERROR" value="error" />
            <el-option label="CRITICAL" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="审计状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="待审核" value="pending" />
            <el-option label="已审核" value="reviewed" />
            <el-option label="已归档" value="archived" />
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
          <span>审计日志列表</span>
          <div>
            <el-button :icon="TrendCharts" @click="handleStatistics">统计概览</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="trace_id" label="Trace ID" width="200" show-overflow-tooltip />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="module" label="模块" width="120" />
        <el-table-column prop="operation" label="操作" min-width="200" show-overflow-tooltip />
        <el-table-column prop="method" label="请求方法" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getMethodTagType(row.method)">
              {{ row.method }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="请求路径" min-width="200" show-overflow-tooltip />
        <el-table-column label="审计级别" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getLevelTagType(row.level)">
              {{ row.level?.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP地址" width="140" />
        <el-table-column prop="duration" label="执行时长(ms)" width="120" align="center" />
        <el-table-column prop="status_code" label="状态码" width="100" align="center" />
        <el-table-column label="审计状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusTagType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
              <el-button type="primary" link :icon="Edit" @click="handleReview(row)">审核</el-button>
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
    <el-dialog v-model="detailDialogVisible" title="审计日志详情" width="800px">
      <el-descriptions v-if="currentLog" :column="1" border>
        <el-descriptions-item label="ID">{{ currentLog.id }}</el-descriptions-item>
        <el-descriptions-item label="Trace ID">{{ currentLog.trace_id }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ currentLog.username }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ currentLog.module }}</el-descriptions-item>
        <el-descriptions-item label="操作">{{ currentLog.operation }}</el-descriptions-item>
        <el-descriptions-item label="请求方法">
          <el-tag size="small" :type="getMethodTagType(currentLog.method)">
            {{ currentLog.method }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="请求路径">{{ currentLog.path }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentLog.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="User-Agent">{{ currentLog.user_agent }}</el-descriptions-item>
        <el-descriptions-item label="请求参数">
          <pre v-if="currentLog.request_params">{{ JSON.stringify(currentLog.request_params, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="响应数据">{{ currentLog.response_data }}</el-descriptions-item>
        <el-descriptions-item label="状态码">{{ currentLog.status_code }}</el-descriptions-item>
        <el-descriptions-item label="错误信息">{{ currentLog.error_message }}</el-descriptions-item>
        <el-descriptions-item label="执行时长">{{ currentLog.duration }}ms</el-descriptions-item>
        <el-descriptions-item label="审计级别">
          <el-tag size="small" :type="getLevelTagType(currentLog.level)">
            {{ currentLog.level?.toUpperCase() }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="业务流水号">{{ currentLog.business_no }}</el-descriptions-item>
        <el-descriptions-item label="关联记录ID">{{ currentLog.related_record_id }}</el-descriptions-item>
        <el-descriptions-item label="审计状态">
          <el-tag size="small" :type="getStatusTagType(currentLog.status)">
            {{ getStatusLabel(currentLog.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="审核人ID">{{ currentLog.review_user_id }}</el-descriptions-item>
        <el-descriptions-item label="审核时间">{{ currentLog.review_time }}</el-descriptions-item>
        <el-descriptions-item label="审核备注">{{ currentLog.review_comment }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentLog.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentLog.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 审核弹窗 -->
    <el-dialog v-model="reviewDialogVisible" title="审核审计日志" width="500px">
      <el-form ref="reviewFormRef" :model="reviewForm" label-width="80px">
        <el-form-item label="审计状态">
          <el-radio-group v-model="reviewForm.status">
            <el-radio value="reviewed">已审核</el-radio>
            <el-radio value="archived">已归档</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="审核备注">
          <el-input v-model="reviewForm.review_comment" type="textarea" :rows="4" placeholder="请输入审核备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleReviewSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 统计概览弹窗 -->
    <el-dialog v-model="statisticsDialogVisible" title="审计统计概览" width="800px">
      <div v-if="statistics" class="statistics-content">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value">{{ statistics.total }}</div>
                <div class="stat-label">总记录数</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value info">{{ statistics.info }}</div>
                <div class="stat-label">INFO级别</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value warning">{{ statistics.warning }}</div>
                <div class="stat-label">WARNING级别</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value danger">{{ statistics.error }}</div>
                <div class="stat-label">ERROR级别</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value critical">{{ statistics.critical }}</div>
                <div class="stat-label">CRITICAL级别</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, View, Edit, TrendCharts } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitLoading = ref(false)
const detailDialogVisible = ref(false)
const reviewDialogVisible = ref(false)
const statisticsDialogVisible = ref(false)
const currentLog = ref(null)
const reviewFormRef = ref(null)

const tableData = ref([])
const statistics = ref(null)
const dateRange = ref([])

const searchForm = reactive({
  username: '',
  module: '',
  operation: '',
  level: null,
  status: null,
  ip_address: null,
  start_time: null,
  end_time: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const reviewForm = ref({
  status: '',
  review_comment: ''
})

const getAuditLogList = async (params) => {
  return request.get('/v1/audit/audit-logs/list', { params })
}

const updateAuditLog = async (id, data) => {
  return request.put(`/v1/audit/audit-logs/${id}`, data)
}

const getAuditStatistics = async (params) => {
  return request.get('/v1/audit/audit-logs/statistics/overview', { params })
}

const getMethodTagType = (method) => {
  const types = {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger',
    PATCH: 'info'
  }
  return types[method?.toUpperCase()] || ''
}

const getLevelTagType = (level) => {
  const types = {
    info: 'info',
    warning: 'warning',
    error: 'danger',
    critical: 'danger'
  }
  return types[level] || 'info'
}

const getStatusTagType = (status) => {
  const types = {
    pending: 'warning',
    reviewed: 'success',
    archived: 'info'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    pending: '待审核',
    reviewed: '已审核',
    archived: '已归档'
  }
  return labels[status] || status
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
    const res = await getAuditLogList(params)
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
  searchForm.module = ''
  searchForm.operation = ''
  searchForm.level = null
  searchForm.status = null
  dateRange.value = []
  handleSearch()
}

const handleDetail = (row) => {
  currentLog.value = row
  detailDialogVisible.value = true
}

const handleReview = (row) => {
  reviewForm.value = {
    status: row.status,
    review_comment: row.review_comment || ''
  }
  currentLog.value = row
  reviewDialogVisible.value = true
}

const handleReviewSubmit = async () => {
  submitLoading.value = true
  try {
    await updateAuditLog(currentLog.value.id, reviewForm.value)
    ElMessage.success('审核成功')
    reviewDialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    submitLoading.value = false
  }
}

const handleStatistics = async () => {
  statisticsDialogVisible.value = true
  const params = {}
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_time = dateRange.value[0]
    params.end_time = dateRange.value[1]
  }
  try {
    const res = await getAuditStatistics(params)
    statistics.value = res.data
  } catch (e) {
    statistics.value = null
  }
}

fetchData()
</script>

<style lang="scss" scoped>
.audit-logs {
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

  .statistics-content {
    .stat-item {
      text-align: center;
      padding: 12px 0;

      .stat-value {
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 8px;
      }

      .stat-label {
        color: #666;
        font-size: 14px;
      }

      &.info {
        color: #409eff;
      }

      &.warning {
        color: #e6a23c;
      }

      &.danger {
        color: #f56c6c;
      }

      &.critical {
        color: #c00;
      }
    }
  }
}
</style>


