<template>
  <div class="harness-session">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="客户端">
          <el-input v-model="searchForm.client_id" placeholder="hcli_..." clearable />
        </el-form-item>
        <el-form-item label="用户 ID">
          <el-input v-model="searchForm.user_id" placeholder="本地用户 ID" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 130px">
            <el-option label="打开" value="open" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header><span>Harness 会话</span></template>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="session_no" label="会话号" width="210" show-overflow-tooltip />
        <el-table-column prop="client_id" label="客户端" width="190" show-overflow-tooltip />
        <el-table-column prop="user_id" label="用户" width="80" align="center">
          <template #default="{ row }">{{ row.user_id ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'open' ? 'success' : 'info'">
              {{ row.status === 'open' ? '打开' : '已关闭' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="format_version" label="日志版本" width="90" align="center">
          <template #default="{ row }">{{ row.format_version || '-' }}</template>
        </el-table-column>
        <el-table-column prop="gateway_key" label="网关 Key" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.gateway_key || '-' }}</template>
        </el-table-column>
        <el-table-column prop="run_count" label="运行数" width="80" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="175" />
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

    <el-dialog v-model="detailVisible" title="会话详情" width="900px">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="会话号">{{ detail.session.session_no }}</el-descriptions-item>
          <el-descriptions-item label="客户端">{{ detail.session.client_id }}</el-descriptions-item>
          <el-descriptions-item label="用户 ID">{{ detail.session.user_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.session.status }}</el-descriptions-item>
          <el-descriptions-item label="日志格式">{{ detail.session.format_version || '未识别' }}</el-descriptions-item>
          <el-descriptions-item label="网关 Key">{{ detail.session.gateway_key || '-' }}</el-descriptions-item>
          <el-descriptions-item label="工作目录">{{ detail.session.cwd || '-' }}</el-descriptions-item>
          <el-descriptions-item label="日志路径">{{ detail.session.session_log_path || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">用量汇总（来源不可混算）</el-divider>
        <el-row :gutter="12">
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>合计</span><b>{{ detail.usage.total.amount }}</b></div></el-card></el-col>
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>成本</span><b>{{ detail.usage.total.cost }}</b></div></el-card></el-col>
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>输入</span><b>{{ detail.usage.total.tokens_in }}</b></div></el-card></el-col>
          <el-col :span="6"><el-card shadow="never"><div class="metric"><span>输出</span><b>{{ detail.usage.total.tokens_out }}</b></div></el-card></el-col>
        </el-row>

        <el-divider content-position="left">运行记录</el-divider>
        <el-table :data="detail.runs" border stripe max-height="320">
          <el-table-column prop="run_no" label="运行号" width="190" show-overflow-tooltip />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="runTagType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="model" label="模型" width="130" />
          <el-table-column prop="reserved_tokens" label="预占" width="90" align="center" />
          <el-table-column prop="estimated_cost" label="预估成本" width="100" align="center" />
          <el-table-column label="失败原因" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.error_message || row.error_code || '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="175" />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import { getSessionList, getSessionDetail } from '@/api/harness'

const loading = ref(false)
const tableData = ref([])
const detailVisible = ref(false)
const detail = ref(null)
const searchForm = reactive({ client_id: '', user_id: '', status: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const runTagType = (status) => {
  if (status === 'succeeded') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed' || status === 'timeout') return 'danger'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchForm.client_id) params.client_id = searchForm.client_id
    if (searchForm.user_id) params.user_id = Number(searchForm.user_id)
    if (searchForm.status) params.status = searchForm.status
    const res = await getSessionList(params)
    tableData.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => {
  Object.assign(searchForm, { client_id: '', user_id: '', status: '' })
  pagination.page = 1
  fetchData()
}

const handleDetail = async (row) => {
  const res = await getSessionDetail(row.session_no)
  detail.value = res.data
  detailVisible.value = true
}

onMounted(fetchData)
</script>

<style scoped>
.harness-session { padding: 20px; }
.search-form { margin-bottom: 0; }
.pagination-wrapper { margin-top: 20px; display: flex; justify-content: flex-end; }
.metric { display: flex; justify-content: space-between; align-items: center; }
.metric b { font-size: 18px; }
</style>
