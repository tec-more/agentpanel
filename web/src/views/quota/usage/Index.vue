<template>
  <div class="usage-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" @submit.prevent="search">
        <el-form-item label="组织">
          <el-select
            v-model="filters.owner_id"
            placeholder="全部组织"
            clearable
            filterable
            style="width: 220px"
          >
            <el-option
              v-for="org in orgOptions"
              :key="org.org_id"
              :label="`${org.name}（#${org.org_id}）`"
              :value="org.org_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="成员 ID">
          <el-input-number v-model="filters.member_id" :min="1" :controls="false" placeholder="成员 customer_id" style="width: 160px" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.timeRange"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.source" placeholder="全部" clearable style="width: 140px">
            <el-option label="provider" value="provider" />
            <el-option label="gateway" value="gateway" />
            <el-option label="estimated" value="estimated" />
            <el-option label="legacy" value="legacy" />
          </el-select>
        </el-form-item>
        <el-form-item label="用量类型">
          <el-select v-model="filters.usage_kind" placeholder="全部" clearable style="width: 140px">
            <el-option label="普通" value="normal" />
            <el-option label="自动压缩" value="compaction" />
            <el-option label="子代理" value="subagent" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
          <el-button :disabled="!rows.length" @click="exportCsv">导出当前页</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <div class="toolbar">
        <div class="toolbar-title">计量流水</div>
        <span class="muted">共 {{ total }} 条</span>
      </div>

      <el-alert v-if="error" type="error" :closable="false" :title="error" class="mb-12" />

      <el-table v-loading="loading" :data="rows" border stripe>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="组织 / 成员" min-width="150">
          <template #default="{ row }">
            <div>#{{ row.owner_id }}</div>
            <div class="muted">成员 {{ row.member_id ?? '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            <el-tag :type="sourceType(row.source)" size="small">{{ row.source }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="用量类型" width="110">
          <template #default="{ row }">
            <span>{{ kindLabel(row.usage_kind) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="120" />
        <el-table-column label="模型" min-width="130">
          <template #default="{ row }">
            <span>{{ row.model || '-' }}</span>
            <div class="muted">{{ row.provider || '' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="用量" width="100" align="right">
          <template #default="{ row }">{{ fmt(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="Token 入/出" width="130">
          <template #default="{ row }">{{ row.tokens_in }} / {{ row.tokens_out }}</template>
        </el-table-column>
        <el-table-column label="缓存 读/写" width="120">
          <template #default="{ row }">{{ row.cache_read_tokens }} / {{ row.cache_write_tokens }}</template>
        </el-table-column>
        <el-table-column label="成本" width="110" align="right">
          <template #default="{ row }">{{ Number(row.cost || 0).toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="追溯" min-width="150">
          <template #default="{ row }">
            <div v-if="row.execution_id">执行 #{{ row.execution_id }}</div>
            <div class="muted" v-if="row.session_ref">会话 {{ row.session_ref }}</div>
            <div class="muted" v-if="row.gateway_key">Key {{ row.gateway_key }}</div>
            <span v-if="!row.execution_id && !row.session_ref && !row.gateway_key" class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="load"
          @size-change="search"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrgQuotaList, getUsageRecords } from '@/api/quota'

const loading = ref(false)
const error = ref('')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const orgOptions = ref([])

const filters = reactive({
  owner_id: undefined,
  member_id: undefined,
  timeRange: [],
  source: undefined,
  usage_kind: undefined
})

function fmt(value) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function fmtTime(value) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

function sourceType(source) {
  if (source === 'provider') return 'success'
  if (source === 'gateway') return 'warning'
  if (source === 'estimated') return 'info'
  return ''
}

function kindLabel(kind) {
  return { normal: '普通', compaction: '自动压缩', subagent: '子代理' }[kind] || kind || '-'
}

async function loadOrgs() {
  try {
    const res = await getOrgQuotaList({ page: 1, page_size: 100 })
    const data = res?.data ?? res
    orgOptions.value = data?.items || []
  } catch (e) {
    orgOptions.value = []
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [start, end] = filters.timeRange || []
    const params = {
      page: page.value,
      page_size: pageSize.value,
      owner_type: filters.owner_id ? 'org' : undefined,
      owner_id: filters.owner_id || undefined,
      member_id: filters.member_id || undefined,
      source: filters.source || undefined,
      usage_kind: filters.usage_kind || undefined,
      start_time: start || undefined,
      end_time: end || undefined
    }
    const res = await getUsageRecords(params)
    const data = res?.data ?? res
    rows.value = data?.items || []
    total.value = data?.total || 0
  } catch (e) {
    rows.value = []
    total.value = 0
    error.value = e?.response?.data?.detail || e?.message || '加载计量流水失败'
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.owner_id = undefined
  filters.member_id = undefined
  filters.timeRange = []
  filters.source = undefined
  filters.usage_kind = undefined
  search()
}

function exportCsv() {
  if (!rows.value.length) return
  const headers = [
    '时间', '组织ID', '成员ID', '来源', '用量类型', '资源类型',
    '模型', '提供商', '用量', 'Token入', 'Token出', '缓存读', '缓存写', '成本'
  ]
  const lines = rows.value.map((r) => [
    fmtTime(r.created_at),
    r.owner_id,
    r.member_id ?? '',
    r.source,
    r.usage_kind,
    r.resource_type,
    r.model || '',
    r.provider || '',
    r.amount,
    r.tokens_in,
    r.tokens_out,
    r.cache_read_tokens,
    r.cache_write_tokens,
    Number(r.cost || 0).toFixed(6)
  ])
  const csv = [headers, ...lines]
    .map((line) => line.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `usage-records-page-${page.value}.csv`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已导出当前页 CSV')
}

onMounted(async () => {
  await loadOrgs()
  load()
})
</script>

<style scoped>
.usage-page {
  padding: 16px;
}
.filter-card {
  margin-bottom: 12px;
}
.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.toolbar-title {
  font-size: 16px;
  font-weight: 600;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.mb-12 { margin-bottom: 12px; }
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
