<template>
  <div class="audit-trace">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="Trace ID">
          <el-input v-model="searchForm.trace_id" placeholder="请输入Trace ID" clearable />
        </el-form-item>
        <el-form-item label="用户ID">
          <el-input v-model="searchForm.user_id" placeholder="请输入用户ID" clearable />
        </el-form-item>
        <el-form-item label="模块">
          <el-input v-model="searchForm.module" placeholder="请输入模块" clearable />
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
          <span>全链路追踪</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe row-key="id" :tree-props="{ children: 'children', hasChildren: 'hasChildren' }">
        <el-table-column prop="trace_id" label="Trace ID" width="200" show-overflow-tooltip />
        <el-table-column prop="level" label="层级" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.level || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="phase" label="阶段" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="getPhaseTagType(row.phase)">
              {{ getPhaseLabel(row.phase) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="120" />
        <el-table-column prop="operation" label="操作" min-width="200" show-overflow-tooltip />
        <el-table-column prop="duration" label="耗时(ms)" width="100" align="center" sortable />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusTagType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
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

    <el-dialog v-model="detailDialogVisible" title="追踪详情" width="900px">
      <el-descriptions v-if="currentTrace" :column="2" border>
        <el-descriptions-item label="Trace ID" :span="2">{{ currentTrace.trace_id }}</el-descriptions-item>
        <el-descriptions-item label="层级">{{ currentTrace.level || 0 }}</el-descriptions-item>
        <el-descriptions-item label="阶段">
          <el-tag size="small" :type="getPhaseTagType(currentTrace.phase)">
            {{ getPhaseLabel(currentTrace.phase) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模块">{{ currentTrace.module }}</el-descriptions-item>
        <el-descriptions-item label="操作">{{ currentTrace.operation }}</el-descriptions-item>
        <el-descriptions-item label="用户ID">{{ currentTrace.user_id }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ currentTrace.duration }}ms</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag size="small" :type="getStatusTagType(currentTrace.status)">
            {{ currentTrace.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="输入数据" :span="2">
          <pre v-if="currentTrace.input_data">{{ JSON.stringify(currentTrace.input_data, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="输出数据" :span="2">
          <pre v-if="currentTrace.output_data">{{ JSON.stringify(currentTrace.output_data, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2">{{ currentTrace.error_message }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentTrace.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import { getTraceList, getTraceDetail } from '@/api/audit'

const loading = ref(false)
const detailDialogVisible = ref(false)
const currentTrace = ref(null)

const tableData = ref([])
const dateRange = ref([])

const searchForm = reactive({
  trace_id: '',
  user_id: '',
  module: '',
  start_time: null,
  end_time: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const getPhaseLabel = (phase) => {
  const labels = {
    input: '输入层',
    decision: '决策层',
    execution: '执行层',
    output: '输出层',
    system: '系统层'
  }
  return labels[phase] || phase
}

const getPhaseTagType = (phase) => {
  const types = {
    input: 'primary',
    decision: 'success',
    execution: 'warning',
    output: 'info',
    system: 'danger'
  }
  return types[phase] || ''
}

const getStatusTagType = (status) => {
  const types = {
    success: 'success',
    failed: 'danger',
    pending: 'warning'
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
    const res = await getTraceList(params)
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
  searchForm.trace_id = ''
  searchForm.user_id = ''
  searchForm.module = ''
  dateRange.value = []
  handleSearch()
}

const handleDetail = async (row) => {
  if (row.trace_id) {
    const res = await getTraceDetail(row.trace_id)
    currentTrace.value = res.data
  } else {
    currentTrace.value = row
  }
  detailDialogVisible.value = true
}

fetchData()
</script>

<style lang="scss" scoped>
.audit-trace {
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
}
</style>

