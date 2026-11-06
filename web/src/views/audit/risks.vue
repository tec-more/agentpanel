<template>
  <div class="audit-risks">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="风险级别">
          <el-select v-model="searchForm.risk_level" placeholder="请选择" clearable style="width: 150px;">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="严重" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 150px;">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已处理" value="resolved" />
            <el-option label="已忽略" value="ignored" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险类型">
          <el-input v-model="searchForm.risk_type" placeholder="请输入风险类型" clearable />
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

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>风险审计列表</span>
          <el-button type="primary" :icon="TrendCharts" @click="handleStatistics">统计概览</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="risk_type" label="风险类型" width="150" />
        <el-table-column prop="risk_level" label="风险级别" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getRiskLevelTagType(row.risk_level)">
              {{ getRiskLevelLabel(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="风险描述" min-width="250" show-overflow-tooltip />
        <el-table-column prop="module" label="模块" width="120" />
        <el-table-column prop="related_record_id" label="关联记录" width="150" />
        <el-table-column prop="status" label="处理状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusTagType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
              <el-button type="primary" link :icon="Edit" @click="handleHandle(row)">处理</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

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

    <el-dialog v-model="detailDialogVisible" title="风险详情" width="800px">
      <el-descriptions v-if="currentRisk" :column="2" border>
        <el-descriptions-item label="ID">{{ currentRisk.id }}</el-descriptions-item>
        <el-descriptions-item label="风险类型">{{ currentRisk.risk_type }}</el-descriptions-item>
        <el-descriptions-item label="风险级别">
          <el-tag size="small" :type="getRiskLevelTagType(currentRisk.risk_level)">
            {{ getRiskLevelLabel(currentRisk.risk_level) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="处理状态">
          <el-tag size="small" :type="getStatusTagType(currentRisk.status)">
            {{ getStatusLabel(currentRisk.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模块">{{ currentRisk.module }}</el-descriptions-item>
        <el-descriptions-item label="关联记录">{{ currentRisk.related_record_id }}</el-descriptions-item>
        <el-descriptions-item label="风险描述" :span="2">{{ currentRisk.description }}</el-descriptions-item>
        <el-descriptions-item label="风险详情" :span="2">
          <pre v-if="currentRisk.details">{{ JSON.stringify(currentRisk.details, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="处理记录" :span="2">
          <pre v-if="currentRisk.handling_records">{{ JSON.stringify(currentRisk.handling_records, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="处理人">{{ currentRisk.handled_by }}</el-descriptions-item>
        <el-descriptions-item label="处理时间">{{ currentRisk.handled_at }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentRisk.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentRisk.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="handleDialogVisible" title="处理风险" width="600px">
      <el-form ref="handleFormRef" :model="handleForm" label-width="100px">
        <el-form-item label="处理状态" prop="status">
          <el-radio-group v-model="handleForm.status">
            <el-radio value="processing">处理中</el-radio>
            <el-radio value="resolved">已处理</el-radio>
            <el-radio value="ignored">已忽略</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="处理意见" prop="comment">
          <el-input v-model="handleForm.comment" type="textarea" :rows="4" placeholder="请输入处理意见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleHandleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="statisticsDialogVisible" title="风险统计概览" width="800px">
      <div v-if="statistics" class="statistics-content">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value">{{ statistics.total }}</div>
                <div class="stat-label">总风险数</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value critical">{{ statistics.critical }}</div>
                <div class="stat-label">严重风险</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value danger">{{ statistics.high }}</div>
                <div class="stat-label">高风险</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value warning">{{ statistics.medium }}</div>
                <div class="stat-label">中风险</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value info">{{ statistics.low }}</div>
                <div class="stat-label">低风险</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value">{{ statistics.pending }}</div>
                <div class="stat-label">待处理</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover">
              <div class="stat-item">
                <div class="stat-value success">{{ statistics.resolved }}</div>
                <div class="stat-label">已处理</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, View, Edit, TrendCharts } from '@element-plus/icons-vue'
import { getRiskList, getRiskDetail, updateRiskStatus as apiUpdateRiskStatus, getRiskStatistics } from '@/api/audit'

const loading = ref(false)
const submitLoading = ref(false)
const detailDialogVisible = ref(false)
const handleDialogVisible = ref(false)
const statisticsDialogVisible = ref(false)
const currentRisk = ref(null)
const handleFormRef = ref(null)

const tableData = ref([])
const statistics = ref(null)
const dateRange = ref([])

const searchForm = reactive({
  risk_level: '',
  status: '',
  risk_type: '',
  start_time: null,
  end_time: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const handleForm = ref({
  status: 'resolved',
  comment: ''
})

const getRiskLevelLabel = (level) => {
  const labels = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '严重'
  }
  return labels[level] || level
}

const getRiskLevelTagType = (level) => {
  const types = {
    low: 'info',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return types[level] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    pending: '待处理',
    processing: '处理中',
    resolved: '已处理',
    ignored: '已忽略'
  }
  return labels[status] || status
}

const getStatusTagType = (status) => {
  const types = {
    pending: 'warning',
    processing: 'primary',
    resolved: 'success',
    ignored: 'info'
  }
  return types[status] || 'info'
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
    const res = await getRiskList(params)
    tableData.value = res.data.items || res.data || []
    pagination.total = res.data.total || tableData.value.length
  } catch (e) {
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.risk_level = ''
  searchForm.status = ''
  searchForm.risk_type = ''
  dateRange.value = []
  handleSearch()
}

const handleDetail = async (row) => {
  const res = await getRiskDetail(row.id)
  currentRisk.value = res.data
  detailDialogVisible.value = true
}

const handleHandle = (row) => {
  currentRisk.value = row
  handleForm.value = {
    status: row.status === 'pending' ? 'processing' : 'resolved',
    comment: ''
  }
  handleDialogVisible.value = true
}

const handleHandleSubmit = async () => {
  submitLoading.value = true
  try {
    await apiUpdateRiskStatus(currentRisk.value.id, handleForm.value.status, handleForm.value.comment)
    ElMessage.success('处理成功')
    handleDialogVisible.value = false
    fetchData()
  } catch (e) {
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
    const res = await getRiskStatistics(params)
    statistics.value = res.data
  } catch (e) {
    statistics.value = null
  }
}

fetchData()
</script>

<style lang="scss" scoped>
.audit-risks {
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

      &.success {
        color: #67c23a;
      }
    }
  }
}
</style>



