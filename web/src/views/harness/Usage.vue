<template>
  <div class="harness-usage">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="filters" class="search-form">
        <el-form-item label="来源">
          <el-select v-model="filters.source" placeholder="全部" clearable style="width: 130px">
            <el-option label="provider" value="provider" />
            <el-option label="gateway" value="gateway" />
            <el-option label="estimated" value="estimated" />
          </el-select>
        </el-form-item>
        <el-form-item label="用量类型">
          <el-select v-model="filters.usage_kind" placeholder="全部" clearable style="width: 130px">
            <el-option label="普通回合" value="normal" />
            <el-option label="自动压缩" value="compaction" />
            <el-option label="子代理" value="subagent" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="filters.model" placeholder="deepseek-chat" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item label="客户端">
          <el-input v-model="filters.client_id" placeholder="hcli_..." clearable style="width: 170px" />
        </el-form-item>
        <el-form-item label="租户">
          <el-select v-model="filters.owner_type" placeholder="全部" clearable style="width: 100px">
            <el-option label="用户" value="usr" />
            <el-option label="客户" value="cus" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 340px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchData">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="12">
      <el-col :span="5"><el-card shadow="never"><div class="metric"><span>总用量</span><b>{{ data.total.amount }}</b></div></el-card></el-col>
      <el-col :span="5"><el-card shadow="never"><div class="metric"><span>总成本</span><b>{{ data.total.cost }}</b></div></el-card></el-col>
      <el-col :span="5"><el-card shadow="never"><div class="metric"><span>输入 token</span><b>{{ data.total.tokens_in }}</b></div></el-card></el-col>
      <el-col :span="5"><el-card shadow="never"><div class="metric"><span>输出 token</span><b>{{ data.total.tokens_out }}</b></div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="metric"><span>记录数</span><b>{{ data.total.records }}</b></div></el-card></el-col>
    </el-row>

    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>按来源（source，严禁混算）</span></template>
          <el-table :data="bucketRows(data.by_source)" size="small" border>
            <el-table-column prop="key" label="source" />
            <el-table-column prop="amount" label="用量" align="right" />
            <el-table-column prop="cost" label="成本" align="right" />
            <el-table-column prop="records" label="记录" align="right" width="70" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>按用量类型（usage_kind）</span></template>
          <el-table :data="bucketRows(data.by_kind)" size="small" border>
            <el-table-column prop="key" label="usage_kind" />
            <el-table-column prop="amount" label="用量" align="right" />
            <el-table-column prop="cost" label="成本" align="right" />
            <el-table-column prop="records" label="记录" align="right" width="70" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>按模型</span></template>
          <el-table :data="bucketRows(data.by_model)" size="small" border>
            <el-table-column prop="key" label="model" />
            <el-table-column prop="amount" label="用量" align="right" />
            <el-table-column prop="cost" label="成本" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>按租户（owner_type:owner_id）</span></template>
          <el-table :data="bucketRows(data.by_owner)" size="small" border>
            <el-table-column prop="key" label="租户" />
            <el-table-column prop="amount" label="用量" align="right" />
            <el-table-column prop="cost" label="成本" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>按客户端</span></template>
          <el-table :data="bucketRows(data.by_client)" size="small" border>
            <el-table-column prop="key" label="client_id" />
            <el-table-column prop="amount" label="用量" align="right" />
            <el-table-column prop="cost" label="成本" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>按网关虚拟 Key</span></template>
          <el-table :data="bucketRows(data.by_gateway)" size="small" border>
            <el-table-column prop="key" label="gateway_key" />
            <el-table-column prop="amount" label="用量" align="right" />
            <el-table-column prop="cost" label="成本" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        <div class="card-header">
          <span>异常明细</span>
          <div>
            <el-button size="small" :icon="Refresh" @click="fetchAnomalies">刷新</el-button>
            <el-button size="small" type="warning" :loading="reconciling" @click="handleReconcile">
              执行预占对账
            </el-button>
            <el-button size="small" type="primary" :loading="gatewayReconciling" @click="handleGatewayReconcile">
              执行网关对账
            </el-button>
          </div>
        </div>
      </template>
      <el-tabs>
        <el-tab-pane label="失败运行">
          <el-table :data="anomalies.failed_runs" size="small" border max-height="260">
            <el-table-column prop="run_no" label="运行号" width="200" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="error_code" label="错误码" width="120" />
            <el-table-column prop="error_message" label="错误信息" min-width="220" show-overflow-tooltip />
            <el-table-column prop="created_at" label="创建时间" width="175" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="超期预占">
          <el-table :data="anomalies.expired_reservations" size="small" border max-height="260">
            <el-table-column prop="hold_id" label="hold_id" width="220" />
            <el-table-column prop="ref_id" label="关联" width="200" />
            <el-table-column prop="expire_at" label="过期时间" width="175" />
            <el-table-column label="预占项" min-width="180">
              <template #default="{ row }">{{ JSON.stringify(row.items) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="缺价格用量">
          <el-table :data="anomalies.usage_missing_price" size="small" border max-height="260">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="run_ref" label="会话" width="200" />
            <el-table-column prop="model" label="模型" width="140" />
            <el-table-column prop="source" label="来源" width="100" />
            <el-table-column prop="amount" label="用量" width="100" align="right" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="高危拒绝">
          <el-table :data="anomalies.high_risk_denied" size="small" border max-height="260">
            <el-table-column prop="event_no" label="事件号" width="210" />
            <el-table-column prop="action" label="动作" width="150" />
            <el-table-column prop="run_no" label="运行号" width="200" />
            <el-table-column prop="call_id" label="callId" width="140" />
            <el-table-column prop="policy_code" label="策略" width="160" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="网关对账差异">
          <div class="reconcile-summary">
            <el-tag type="danger">高风险未处理 {{ reconcileSummary.high_open || 0 }}</el-tag>
            <el-tag>未处理 {{ reconcileSummary.open || 0 }}</el-tag>
            <span v-if="reconcileSummary.latest_batch" class="reconcile-batch">
              最近批次 {{ reconcileSummary.latest_batch.batch_no }}
              （{{ reconcileSummary.latest_batch.trigger }}，差异
              {{ reconcileSummary.latest_batch.stats?.diffs || 0 }}）
            </span>
          </div>

          <el-form :inline="true" :model="reconcileFilters" size="small" class="reconcile-form">
            <el-form-item label="级别">
              <el-select v-model="reconcileFilters.severity" placeholder="全部" clearable style="width: 100px">
                <el-option label="high" value="high" />
                <el-option label="low" value="low" />
              </el-select>
            </el-form-item>
            <el-form-item label="分类">
              <el-select v-model="reconcileFilters.category" placeholder="全部" clearable style="width: 190px">
                <el-option v-for="(label, key) in categoryLabels" :key="key" :label="label" :value="key" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="reconcileFilters.status" placeholder="全部" clearable style="width: 100px">
                <el-option label="未处理" value="open" />
                <el-option label="已处理" value="resolved" />
                <el-option label="已忽略" value="ignored" />
              </el-select>
            </el-form-item>
            <el-form-item label="运行号">
              <el-input v-model="reconcileFilters.run_no" placeholder="run_..." clearable style="width: 170px" />
            </el-form-item>
            <el-form-item label="会话">
              <el-input v-model="reconcileFilters.session_no" placeholder="session..." clearable style="width: 170px" />
            </el-form-item>
            <el-form-item label="客户端">
              <el-input v-model="reconcileFilters.client_id" placeholder="hcli_..." clearable style="width: 150px" />
            </el-form-item>
            <el-form-item label="租户">
              <el-select v-model="reconcileFilters.owner_type" placeholder="全部" clearable style="width: 90px">
                <el-option label="用户" value="usr" />
                <el-option label="客户" value="cus" />
                <el-option label="组织" value="org" />
              </el-select>
            </el-form-item>
            <el-form-item label="租户 ID">
              <el-input v-model="reconcileFilters.owner_id" placeholder="ID" clearable style="width: 90px" />
            </el-form-item>
            <el-form-item label="时间">
              <el-date-picker
                v-model="reconcileDateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始"
                end-placeholder="结束"
                value-format="YYYY-MM-DD HH:mm:ss"
                style="width: 320px"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="fetchReconcileDiffs(1)">查询</el-button>
              <el-button @click="resetReconcileFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <el-table v-loading="reconcileLoading" :data="reconcileDiffs" size="small" border max-height="300">
            <el-table-column prop="run_no" label="运行号" width="180" show-overflow-tooltip />
            <el-table-column prop="session_no" label="会话" width="170" show-overflow-tooltip />
            <el-table-column prop="client_id" label="客户端" width="120" show-overflow-tooltip />
            <el-table-column label="分类" width="170">
              <template #default="{ row }">{{ categoryLabels[row.category] || row.category }}</template>
            </el-table-column>
            <el-table-column label="级别" width="80">
              <template #default="{ row }">
                <el-tag :type="row.severity === 'high' ? 'danger' : 'info'" size="small">
                  {{ row.severity }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="gateway_amount" label="网关用量" width="100" align="right" />
            <el-table-column prop="client_amount" label="客户端用量" width="110" align="right" />
            <el-table-column prop="diff_amount" label="差额" width="90" align="right" />
            <el-table-column label="差额率" width="90" align="right">
              <template #default="{ row }">{{ formatRate(row.diff_rate) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_seen_at" label="最近命中" width="170" show-overflow-tooltip />
            <el-table-column prop="occurrence_count" label="命中" width="60" align="right" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDiff(row)">详情</el-button>
                <el-button v-if="row.status === 'open'" link type="success" @click="markDiff(row, 'resolved')">
                  标记已处理
                </el-button>
                <el-button v-if="row.status === 'open'" link type="info" @click="markDiff(row, 'ignored')">
                  忽略
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            class="reconcile-pagination"
            layout="total, prev, pager, next"
            :total="reconcileTotal"
            :page-size="reconcilePageSize"
            :current-page="reconcilePage"
            @current-change="fetchReconcileDiffs"
          />
        </el-tab-pane>
        <el-tab-pane label="网关额度中断">
          <div class="reconcile-summary">
            <el-tag type="danger">因额度拒绝 {{ quotaSummary.rejected_count || 0 }}</el-tag>
            <el-tag type="warning">估算截断 {{ quotaSummary.truncated_count || 0 }}</el-tag>
            <el-tag type="info">超预留 {{ quotaSummary.over_budget_count || 0 }}</el-tag>
            <el-tag>耗尽租约 {{ quotaSummary.exhausted_leases || 0 }}</el-tag>
            <el-tag type="success">在用租约 {{ quotaSummary.active_leases || 0 }}</el-tag>
            <el-button size="small" :icon="Refresh" @click="fetchGatewayQuota">刷新</el-button>
          </div>
          <el-table v-loading="quotaLoading" :data="quotaItems" size="small" border max-height="320">
            <el-table-column prop="lease_id" label="租约" width="180" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="85" />
            <el-table-column label="租户" width="120">
              <template #default="{ row }">
                {{ row.owner_type ? `${row.owner_type}:${row.owner_id}` : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="budget_tokens" label="预算" width="95" align="right" />
            <el-table-column prop="used_tokens" label="已用" width="95" align="right" />
            <el-table-column prop="reserved_tokens" label="在途" width="80" align="right" />
            <el-table-column prop="remaining_tokens" label="剩余" width="95" align="right" />
            <el-table-column prop="avg_tokens_per_request" label="均耗" width="80" align="right" />
            <el-table-column label="预计请求数" width="100" align="right">
              <template #default="{ row }">{{ row.estimated_requests ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="rejected_count" label="拒绝" width="70" align="right" />
            <el-table-column prop="truncated_count" label="截断" width="70" align="right" />
            <el-table-column label="操作" width="110" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'active'"
                  link
                  type="danger"
                  @click="handleRevokeLease(row)"
                >
                  吊销
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="diffDialogVisible" title="对账差异明细" width="820px">
      <template v-if="activeDiff">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="运行号">{{ activeDiff.run_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="会话">{{ activeDiff.session_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="客户端">{{ activeDiff.client_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="租户">
            {{ activeDiff.owner_type || '-' }}:{{ activeDiff.owner_id ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="分类">{{ categoryLabels[activeDiff.category] || activeDiff.category }}</el-descriptions-item>
          <el-descriptions-item label="级别">{{ activeDiff.severity }}</el-descriptions-item>
          <el-descriptions-item label="网关用量">{{ activeDiff.gateway_amount }}</el-descriptions-item>
          <el-descriptions-item label="客户端用量">{{ activeDiff.client_amount }}</el-descriptions-item>
          <el-descriptions-item label="差额">{{ activeDiff.diff_amount }}</el-descriptions-item>
          <el-descriptions-item label="差额率">{{ formatRate(activeDiff.diff_rate) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabels[activeDiff.status] || activeDiff.status }}</el-descriptions-item>
          <el-descriptions-item label="命中次数">{{ activeDiff.occurrence_count }}</el-descriptions-item>
          <el-descriptions-item label="网关租约">{{ activeDiff.gateway_key || '-' }}</el-descriptions-item>
          <el-descriptions-item label="指纹">{{ activeDiff.fingerprint }}</el-descriptions-item>
        </el-descriptions>
        <pre class="diff-json">{{ JSON.stringify(activeDiff.detail, null, 2) }}</pre>
      </template>
      <template #footer>
        <el-button v-if="activeDiff && activeDiff.status === 'open'" type="success" @click="markDiff(activeDiff, 'resolved')">
          标记已处理
        </el-button>
        <el-button v-if="activeDiff && activeDiff.status === 'open'" @click="markDiff(activeDiff, 'ignored')">
          忽略
        </el-button>
        <el-button @click="diffDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import {
  getUsageOverview, getAnomalies, reconcileReservations,
  runGatewayReconcile, getReconcileDiffs, getReconcileDiffDetail, resolveReconcileDiff,
  getGatewayQuota, revokeGatewayLease
} from '@/api/harness'

const dateRange = ref([])
const filtering = ref(false)
const reconciling = ref(false)
const filters = reactive({
  source: '', usage_kind: '', model: '', client_id: '', owner_type: ''
})
const data = reactive({
  total: { amount: 0, cost: 0, tokens_in: 0, tokens_out: 0, records: 0 },
  by_source: {}, by_kind: {}, by_model: {}, by_owner: {}, by_client: {}, by_gateway: {}
})
const anomalies = reactive({
  failed_runs: [], expired_reservations: [], usage_missing_price: [], high_risk_denied: [],
  gateway_reconcile: { open: 0, high_open: 0, latest_batch: null }
})

const categoryLabels = {
  only_gateway: '仅网关有（客户端漏报）',
  only_client: '仅客户端有（直连嫌疑）',
  value_mismatch: '数值不一致',
  duplicate_count: '同一请求重复计数',
  failure_timeout: '失败/超时请求',
  unmatched_gateway: '未匹配（网关侧）',
  unmatched_client: '未匹配（客户端侧）'
}
const statusLabels = { open: '未处理', resolved: '已处理', ignored: '已忽略' }
const statusType = (status) => ({ open: 'warning', resolved: 'success', ignored: 'info' }[status] || 'info')

const gatewayReconciling = ref(false)
const reconcileLoading = ref(false)
const reconcileDiffs = ref([])
const reconcileTotal = ref(0)
const reconcilePage = ref(1)
const reconcilePageSize = 20
const reconcileFilters = reactive({
  severity: '', category: '', status: '', run_no: '', session_no: '',
  client_id: '', owner_type: '', owner_id: ''
})
const reconcileDateRange = ref([])
const diffDialogVisible = ref(false)
const activeDiff = ref(null)
const reconcileSummary = reactive({ open: 0, high_open: 0, latest_batch: null })

const quotaLoading = ref(false)
const quotaItems = ref([])
const quotaSummary = reactive({
  rejected_count: 0, truncated_count: 0, over_budget_count: 0,
  exhausted_leases: 0, active_leases: 0
})

const formatRate = (value) => {
  const num = Number(value || 0)
  return `${(num * 100).toFixed(2)}%`
}

const bucketRows = (bucket) =>
  Object.entries(bucket || {}).map(([key, val]) => ({ key, ...val }))

const fetchData = async () => {
  filtering.value = true
  try {
    const params = {}
    Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v })
    if (dateRange.value?.length === 2) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    }
    const res = await getUsageOverview(params)
    const d = res.data || {}
    Object.assign(data, {
      total: d.total || data.total,
      by_source: d.by_source || {},
      by_kind: d.by_kind || {},
      by_model: d.by_model || {},
      by_owner: d.by_owner || {},
      by_client: d.by_client || {},
      by_gateway: d.by_gateway || {}
    })
  } finally {
    filtering.value = false
  }
}

const fetchAnomalies = async () => {
  const res = await getAnomalies({ limit: 20 })
  const summary = res.data?.gateway_reconcile || { open: 0, high_open: 0, latest_batch: null }
  Object.assign(anomalies, {
    failed_runs: res.data?.failed_runs || [],
    expired_reservations: res.data?.expired_reservations || [],
    usage_missing_price: res.data?.usage_missing_price || [],
    high_risk_denied: res.data?.high_risk_denied || [],
    gateway_reconcile: summary
  })
  Object.assign(reconcileSummary, {
    open: summary.open || 0,
    high_open: summary.high_open || 0,
    latest_batch: summary.latest_batch || null
  })
}

const handleReconcile = async () => {
  reconciling.value = true
  try {
    const res = await reconcileReservations({ release_expired: true, release_terminal_runs: true })
    ElMessage.success(`对账完成：释放 ${res.data?.released_count || 0}，失败 ${res.data?.failed_count || 0}`)
    fetchAnomalies()
  } finally {
    reconciling.value = false
  }
}

const handleReset = () => {
  Object.assign(filters, { source: '', usage_kind: '', model: '', client_id: '', owner_type: '' })
  dateRange.value = []
  fetchData()
}

const fetchReconcileDiffs = async (page = reconcilePage.value) => {
  reconcileLoading.value = true
  try {
    const params = { page, page_size: reconcilePageSize }
    Object.entries(reconcileFilters).forEach(([k, v]) => { if (v) params[k] = v })
    if (reconcileDateRange.value?.length === 2) {
      params.date_from = reconcileDateRange.value[0]
      params.date_to = reconcileDateRange.value[1]
    }
    const res = await getReconcileDiffs(params)
    reconcileDiffs.value = res.data?.items || []
    reconcileTotal.value = res.data?.total || 0
    reconcilePage.value = res.data?.page || page
  } finally {
    reconcileLoading.value = false
  }
}

const resetReconcileFilters = () => {
  Object.assign(reconcileFilters, {
    severity: '', category: '', status: '', run_no: '', session_no: '',
    client_id: '', owner_type: '', owner_id: ''
  })
  reconcileDateRange.value = []
  fetchReconcileDiffs(1)
}

const handleGatewayReconcile = async () => {
  gatewayReconciling.value = true
  try {
    const res = await runGatewayReconcile({ trigger: 'manual' })
    const stats = res.data?.stats || {}
    ElMessage.success(
      `网关对账完成：差异 ${stats.diffs || 0}，新增 ${stats.created || 0}，更新 ${stats.updated || 0}`
    )
    await fetchAnomalies()
    await fetchReconcileDiffs(1)
  } finally {
    gatewayReconciling.value = false
  }
}

const openDiff = async (row) => {
  const res = await getReconcileDiffDetail(row.id)
  activeDiff.value = res.data || row
  diffDialogVisible.value = true
}

const markDiff = async (row, status) => {
  const note = status === 'resolved'
    ? (await ElMessageBox.prompt('处理备注（可选）', '标记已处理', {
        inputPlaceholder: '例如：已核对客户端日志',
        confirmButtonText: '确定',
        cancelButtonText: '取消'
      }).then(({ value }) => value).catch(() => null))
    : '管理台忽略'
  if (note === null) return
  const res = await resolveReconcileDiff(row.id, { status, note })
  ElMessage.success('已更新差异状态')
  activeDiff.value = res.data || activeDiff.value
  diffDialogVisible.value = false
  await fetchAnomalies()
  await fetchReconcileDiffs(reconcilePage.value)
}

const fetchGatewayQuota = async () => {
  quotaLoading.value = true
  try {
    const res = await getGatewayQuota({ active_only: false, limit: 100 })
    quotaItems.value = res.data?.items || []
    Object.assign(quotaSummary, res.data?.summary || {})
  } finally {
    quotaLoading.value = false
  }
}

const handleRevokeLease = async (row) => {
  const reason = await ElMessageBox.prompt(
    `确认吊销租约 ${row.lease_id}？新请求将立即 401。`,
    '应急吊销',
    { inputPlaceholder: '吊销原因（写入审计）', confirmButtonText: '确定吊销', cancelButtonText: '取消' }
  ).then(({ value }) => value).catch(() => null)
  if (reason === null) return
  await revokeGatewayLease(row.lease_id, { reason: reason || 'manual_emergency' })
  ElMessage.success('租约已吊销')
  await fetchGatewayQuota()
  await fetchAnomalies()
}

onMounted(() => {
  fetchData()
  fetchAnomalies()
  fetchReconcileDiffs(1)
  fetchGatewayQuota()
})
</script>

<style scoped>
.harness-usage { padding: 20px; }
.search-form { margin-bottom: 0; }
.metric { display: flex; justify-content: space-between; align-items: center; }
.metric b { font-size: 18px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.reconcile-summary { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.reconcile-batch { color: #909399; font-size: 12px; }
.reconcile-form { margin-bottom: 4px; }
.reconcile-pagination { margin-top: 10px; justify-content: flex-end; }
.diff-json {
  margin-top: 12px;
  max-height: 360px;
  overflow: auto;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  padding: 12px;
  font-size: 12px;
}
</style>
