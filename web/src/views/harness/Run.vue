<template>
  <div class="harness-run">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="会话号">
          <el-input v-model="searchForm.session_no" placeholder="hs_..." clearable />
        </el-form-item>
        <el-form-item label="客户端">
          <el-input v-model="searchForm.client_id" placeholder="hcli_..." clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 130px">
            <el-option label="待开始" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="成功" value="succeeded" />
            <el-option label="失败" value="failed" />
            <el-option label="超时" value="timeout" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header><span>Harness 运行记录</span></template>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="run_no" label="运行号" width="200" show-overflow-tooltip />
        <el-table-column prop="session_no" label="会话号" width="190" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="runTagType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="130" />
        <el-table-column prop="reserved_tokens" label="预占 token" width="110" align="center" />
        <el-table-column prop="estimated_cost" label="预估成本" width="100" align="center" />
        <el-table-column label="失败原因" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.error_message || row.error_code || '-' }}</template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="175" />
        <el-table-column prop="finished_at" label="结束时间" width="175" />
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

    <el-drawer v-model="drawerVisible" title="运行详情" size="760px">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="运行号">{{ detail.run.run_no }}</el-descriptions-item>
          <el-descriptions-item label="会话号">{{ detail.run.session_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="runTagType(detail.run.status)">{{ detail.run.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="模型">{{ detail.run.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预占 token">{{ detail.run.reserved_tokens }}</el-descriptions-item>
          <el-descriptions-item label="预估成本">{{ detail.run.estimated_cost }}</el-descriptions-item>
          <el-descriptions-item label="预占 hold">{{ detail.run.hold_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="失败原因">
            {{ detail.run.error_message || detail.run.error_code || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ detail.run.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ detail.run.finished_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">用量（按来源分组，不混算）</el-divider>
        <el-row :gutter="10">
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>合计</span><b>{{ detail.usage.total.amount }}</b></div></el-card></el-col>
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>成本</span><b>{{ detail.usage.total.cost }}</b></div></el-card></el-col>
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>输入</span><b>{{ detail.usage.total.tokens_in }}</b></div></el-card></el-col>
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>输出</span><b>{{ detail.usage.total.tokens_out }}</b></div></el-card></el-col>
        </el-row>
        <el-row :gutter="10" style="margin-top: 10px">
          <el-col :span="8">
            <el-table :data="bucketRows(detail.usage.by_source)" size="small" border>
              <el-table-column prop="key" label="source" />
              <el-table-column prop="amount" label="用量" align="right" />
            </el-table>
          </el-col>
          <el-col :span="8">
            <el-table :data="bucketRows(detail.usage.by_kind)" size="small" border>
              <el-table-column prop="key" label="usage_kind" />
              <el-table-column prop="amount" label="用量" align="right" />
            </el-table>
          </el-col>
          <el-col :span="8">
            <el-table :data="bucketRows(detail.usage.by_model)" size="small" border>
              <el-table-column prop="key" label="model" />
              <el-table-column prop="amount" label="用量" align="right" />
            </el-table>
          </el-col>
        </el-row>

        <el-divider content-position="left">预占对账</el-divider>
        <el-descriptions v-if="detail.reservation" :column="2" border>
          <el-descriptions-item label="hold_id">{{ detail.reservation.hold_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.reservation.status }}</el-descriptions-item>
          <el-descriptions-item label="计数模式">{{ detail.reservation.counter_mode }}</el-descriptions-item>
          <el-descriptions-item label="过期时间">{{ detail.reservation.expire_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预占项">{{ JSON.stringify(detail.reservation.items) }}</el-descriptions-item>
          <el-descriptions-item label="已用量">{{ JSON.stringify(detail.reservation.used_items) }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="无预占记录（未绑定套餐或已清理）" :image-size="60" />

        <el-divider content-position="left">步骤事件</el-divider>
        <el-table v-loading="stepsLoading" :data="steps" size="small" border stripe max-height="360">
          <el-table-column prop="seq" label="序号" width="70" align="center" />
          <el-table-column prop="node_id" label="节点" min-width="150" show-overflow-tooltip />
          <el-table-column prop="step_type" label="类型" width="110" />
          <el-table-column prop="name" label="名称" width="120" show-overflow-tooltip />
          <el-table-column prop="model" label="模型" width="120" />
          <el-table-column prop="tokens_in" label="输入" width="70" align="right" />
          <el-table-column prop="tokens_out" label="输出" width="70" align="right" />
          <el-table-column prop="source" label="来源" width="90" />
          <el-table-column prop="call_id" label="callId" width="140" show-overflow-tooltip />
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import { getRunList, getRunDetail, getRunSteps } from '@/api/harness'

const loading = ref(false)
const stepsLoading = ref(false)
const tableData = ref([])
const steps = ref([])
const drawerVisible = ref(false)
const detail = ref(null)
const searchForm = reactive({ session_no: '', client_id: '', status: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const runTagType = (status) => {
  if (status === 'succeeded') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed' || status === 'timeout') return 'danger'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const bucketRows = (bucket) =>
  Object.entries(bucket || {}).map(([key, val]) => ({
    key,
    amount: val.amount,
    cost: val.cost,
    records: val.records
  }))

const fetchData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchForm.session_no) params.session_no = searchForm.session_no
    if (searchForm.client_id) params.client_id = searchForm.client_id
    if (searchForm.status) params.status = searchForm.status
    const res = await getRunList(params)
    tableData.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => {
  Object.assign(searchForm, { session_no: '', client_id: '', status: '' })
  pagination.page = 1
  fetchData()
}

const handleDetail = async (row) => {
  const res = await getRunDetail(row.run_no)
  detail.value = res.data
  drawerVisible.value = true
  steps.value = []
  stepsLoading.value = true
  try {
    const stepRes = await getRunSteps(row.run_no, { page: 1, page_size: 200 })
    steps.value = stepRes.data?.items || []
  } finally {
    stepsLoading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.harness-run { padding: 20px; }
.search-form { margin-bottom: 0; }
.pagination-wrapper { margin-top: 20px; display: flex; justify-content: flex-end; }
.metric { display: flex; justify-content: space-between; align-items: center; }
.metric b { font-size: 18px; }
</style>
