<template>
  <div class="harness-audit">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="运行号">
          <el-input v-model="searchForm.run_no" placeholder="hr_..." clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="工具名">
          <el-input v-model="searchForm.target_id" placeholder="如 shell / git.push" clearable style="width: 170px" />
        </el-form-item>
        <el-form-item label="事件动作">
          <el-select v-model="searchForm.action" placeholder="全部" clearable filterable style="width: 180px">
            <el-option v-for="a in actions" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险">
          <el-select v-model="searchForm.risk_level" placeholder="全部" clearable style="width: 110px">
            <el-option label="low" value="low" />
            <el-option label="medium" value="medium" />
            <el-option label="high" value="high" />
            <el-option label="critical" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="审批结果">
          <el-select v-model="searchForm.decision" placeholder="全部" clearable style="width: 120px">
            <el-option label="allow" value="allow" />
            <el-option label="deny" value="deny" />
            <el-option label="ask" value="ask" />
            <el-option label="approved" value="approved" />
            <el-option label="denied" value="denied" />
          </el-select>
        </el-form-item>
        <el-form-item label="callId">
          <el-input v-model="searchForm.call_id" placeholder="callId" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header><span>审计事件</span></template>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="occurred_at" label="发生时间" width="175" />
        <el-table-column prop="action" label="动作" width="150" />
        <el-table-column label="目标" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.target_id">{{ row.target_type }} / {{ row.target_id }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="riskTagType(row.risk_level)">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="决策" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.decision" size="small" :type="decisionTagType(row.decision)">
              {{ row.decision }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="policy_code" label="策略" width="150" show-overflow-tooltip />
        <el-table-column prop="call_id" label="callId" width="140" show-overflow-tooltip />
        <el-table-column prop="run_no" label="运行号" width="190" show-overflow-tooltip />
        <el-table-column prop="raw_type" label="原始类型" width="140" show-overflow-tooltip />
        <el-table-column label="操作" width="90" fixed="right">
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

    <el-dialog v-model="detailVisible" title="审计事件详情" width="760px">
      <el-descriptions v-if="current" :column="1" border>
        <el-descriptions-item label="事件号">{{ current.event_no }}</el-descriptions-item>
        <el-descriptions-item label="动作">{{ current.action }}</el-descriptions-item>
        <el-descriptions-item label="目标">{{ current.target_type }} / {{ current.target_id }}</el-descriptions-item>
        <el-descriptions-item label="风险">{{ current.risk_level }}</el-descriptions-item>
        <el-descriptions-item label="决策">{{ current.decision || '-' }}</el-descriptions-item>
        <el-descriptions-item label="策略">{{ current.policy_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="callId">{{ current.call_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ current.event_source }} / {{ current.raw_type }}</el-descriptions-item>
        <el-descriptions-item label="原始序号">{{ current.raw_seq }}</el-descriptions-item>
        <el-descriptions-item label="发生时间">{{ current.occurred_at }}</el-descriptions-item>
        <el-descriptions-item label="明细">
          <pre>{{ JSON.stringify(current.detail, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import { getAuditEvents } from '@/api/harness'

const actions = [
  'tool.call', 'tool.result', 'approval.asked', 'approval.decided',
  'approval.requested', 'action.evaluated', 'permission.preset',
  'sandbox.mode', 'approval.policy', 'event.unknown', 'event.collection_gap'
]

const loading = ref(false)
const tableData = ref([])
const detailVisible = ref(false)
const current = ref(null)
const searchForm = reactive({
  run_no: '', target_id: '', action: '', risk_level: '', decision: '', call_id: ''
})
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const riskTagType = (level) => {
  if (level === 'critical') return 'danger'
  if (level === 'high') return 'warning'
  if (level === 'medium') return 'primary'
  return 'info'
}

const decisionTagType = (decision) => {
  if (decision === 'allow' || decision === 'approved') return 'success'
  if (decision === 'deny' || decision === 'denied') return 'danger'
  if (decision === 'ask') return 'warning'
  return 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    Object.entries(searchForm).forEach(([k, v]) => { if (v) params[k] = v })
    const res = await getAuditEvents(params)
    tableData.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => {
  Object.assign(searchForm, {
    run_no: '', target_id: '', action: '', risk_level: '', decision: '', call_id: ''
  })
  pagination.page = 1
  fetchData()
}
const handleDetail = (row) => {
  current.value = row
  detailVisible.value = true
}

onMounted(fetchData)
</script>

<style scoped>
.harness-audit { padding: 20px; }
.search-form { margin-bottom: 0; }
.pagination-wrapper { margin-top: 20px; display: flex; justify-content: flex-end; }
pre { max-height: 320px; overflow: auto; margin: 0; }
</style>
