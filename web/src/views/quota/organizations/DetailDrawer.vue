<template>
  <el-drawer
    :model-value="modelValue"
    :title="detail?.organization?.name || '组织配额详情'"
    size="72%"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
    @open="load"
  >
    <div v-loading="loading" class="org-detail">
      <el-alert
        v-if="error"
        type="error"
        :closable="false"
        :title="error"
        class="mb-12"
      />

      <template v-else>
        <el-descriptions :column="3" border class="mb-16">
          <el-descriptions-item label="组织 ID">{{ detail?.organization?.org_id }}</el-descriptions-item>
          <el-descriptions-item label="组织状态">
            <el-tag :type="detail?.organization?.status === 'active' ? 'success' : 'info'" size="small">
              {{ detail?.organization?.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="活跃成员">{{ detail?.organization?.member_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="套餐">
            <span v-if="detail?.plan">{{ detail.plan.name }} <el-tag size="small" type="info">{{ detail.plan.code }}</el-tag></span>
            <span v-else class="muted">未绑定</span>
          </el-descriptions-item>
          <el-descriptions-item label="账户状态">
            <el-tag :type="detail?.account?.status === 'active' ? 'success' : 'danger'" size="small">
              {{ detail?.account?.status === 'active' ? '正常' : '停用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="统计窗口">
            <el-select v-model="days" size="small" style="width: 120px" @change="loadBoard">
              <el-option label="当前自然月" :value="0" />
              <el-option label="近 7 天" :value="7" />
              <el-option label="近 30 天" :value="30" />
            </el-select>
          </el-descriptions-item>
        </el-descriptions>

        <el-row :gutter="12" class="mb-16">
          <el-col :span="6"><div class="stat-card"><span>额度</span><strong>{{ fmt(detail?.account?.limit_total) }}</strong></div></el-col>
          <el-col :span="6"><div class="stat-card"><span>已用</span><strong>{{ fmt(detail?.account?.used_total) }}</strong></div></el-col>
          <el-col :span="6"><div class="stat-card"><span>预占</span><strong>{{ fmt(detail?.account?.held_total) }}</strong></div></el-col>
          <el-col :span="6"><div class="stat-card"><span>可用</span><strong>{{ fmt(detail?.account?.available_total) }}</strong></div></el-col>
        </el-row>

        <el-tabs v-model="tab">
          <el-tab-pane label="额度明细" name="quota">
            <el-table :data="quotaItems" size="small" border>
              <el-table-column prop="item" label="资源" width="140" />
              <el-table-column prop="limit" label="额度" width="110" />
              <el-table-column prop="used" label="已用" width="110" />
              <el-table-column prop="held" label="预占" width="110" />
              <el-table-column prop="available" label="可用" width="110" />
              <el-table-column label="使用率">
                <template #default="{ row }">
                  <el-progress
                    :percentage="ratio(row.used + row.held, row.limit)"
                    :status="ratio(row.used + row.held, row.limit) >= 80 ? 'warning' : ''"
                    :stroke-width="10"
                  />
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!quotaItems.length" description="暂无配额项" :image-size="80" />
          </el-tab-pane>

          <el-tab-pane label="成员排行" name="members">
            <el-table :data="board?.members || []" size="small" border>
              <el-table-column label="成员" min-width="150">
                <template #default="{ row }">
                  <span>{{ row.nickname || row.username || `#${row.member_id}` }}</span>
                  <span class="muted" v-if="row.username">（{{ row.username }}）</span>
                </template>
              </el-table-column>
              <el-table-column prop="role" label="角色" width="100" />
              <el-table-column prop="records" label="笔数" width="80" />
              <el-table-column label="用量" width="110">
                <template #default="{ row }">{{ fmt(row.used) }}</template>
              </el-table-column>
              <el-table-column label="预占" width="110">
                <template #default="{ row }">{{ fmt(row.held) }}</template>
              </el-table-column>
              <el-table-column label="Token 入/出" width="150">
                <template #default="{ row }">{{ row.tokens_in }} / {{ row.tokens_out }}</template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag v-if="!row.member_active" type="warning" size="small">成员失效</el-tag>
                  <el-tag v-else-if="!row.member_enabled" type="danger" size="small">账号停用</el-tag>
                  <el-tag v-else type="success" size="small">正常</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="用量拆分" name="breakdown">
            <div class="split-grid">
              <div v-for="group in splitGroups" :key="group.key" class="split-block">
                <div class="split-title">{{ group.title }}</div>
                <el-table :data="group.rows" size="small" border max-height="280">
                  <el-table-column :prop="group.key" :label="group.label" min-width="120" />
                  <el-table-column label="用量" width="110">
                    <template #default="{ row }">{{ fmt(row.used) }}</template>
                  </el-table-column>
                  <el-table-column prop="records" label="笔数" width="80" />
                  <el-table-column label="成本" width="110">
                    <template #default="{ row }">{{ fmtCost(row.cost) }}</template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane :label="`异常与预占 (${anomalies.length + (board?.reservations?.active_count || 0)})`" name="risk">
            <div class="split-title">异常项</div>
            <el-table :data="anomalies" size="small" border class="mb-16">
              <el-table-column label="类型" width="130">
                <template #default="{ row }">
                  <el-tag :type="anomalyType(row.type)" size="small">{{ anomalyLabel(row.type) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="说明" min-width="220">
                <template #default="{ row }">{{ anomalyDetail(row) }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!anomalies.length" description="无异常" :image-size="70" />

            <div class="split-title">活跃预占</div>
            <el-table :data="board?.reservations?.items || []" size="small" border max-height="320">
              <el-table-column prop="hold_id" label="预占 ID" min-width="140" />
              <el-table-column prop="member_id" label="成员" width="90" />
              <el-table-column label="资源" min-width="140">
                <template #default="{ row }">{{ itemsText(row.items) }}</template>
              </el-table-column>
              <el-table-column prop="source" label="来源" width="100" />
              <el-table-column prop="status" label="状态" width="90" />
              <el-table-column label="到期时间" width="180">
                <template #default="{ row }">
                  <span :class="{ 'text-danger': row.stale }">{{ fmtTime(row.expire_at) }}</span>
                  <el-tag v-if="row.stale" type="danger" size="small" class="ml-6">超期</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getOrgQuotaBoard, getOrgQuotaDetail } from '@/api/quota'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  orgId: { type: [Number, String], default: null }
})
defineEmits(['update:modelValue'])

const loading = ref(false)
const error = ref('')
const detail = ref(null)
const board = ref(null)
const tab = ref('quota')
const days = ref(0)

const quotaItems = computed(() =>
  (detail.value?.account?.items || []).filter((item) => item.item !== 'concurrency')
)

const anomalies = computed(() => board.value?.anomalies || [])

const splitGroups = computed(() => {
  const b = board.value?.breakdown || {}
  return [
    { key: 'source', label: '来源', title: '按来源', rows: b.by_source || [] },
    { key: 'usage_kind', label: '类型', title: '按 usage_kind', rows: b.by_usage_kind || [] },
    { key: 'resource_type', label: '资源类型', title: '按 resource_type', rows: b.by_resource || [] }
  ]
})

const ANOMALY_LABELS = {
  stale_hold: '超期预占',
  member_not_active: '成员失效',
  member_disabled: '成员账号停用',
  usage_member_missing: '成员维度缺失',
  plan_binding_missing: '套餐绑定丢失',
  account_frozen: '账户停用'
}

function anomalyLabel(type) {
  return ANOMALY_LABELS[type] || type
}

function anomalyType(type) {
  if (type === 'account_frozen' || type === 'plan_binding_missing') return 'danger'
  if (type === 'stale_hold' || type === 'member_not_active' || type === 'member_disabled') return 'warning'
  return 'info'
}

function anomalyDetail(row) {
  if (row.type === 'stale_hold') {
    return `预占 ${row.hold_id} 已于 ${fmtTime(row.expire_at)} 超期，成员 ${row.member_id ?? '-'}`
  }
  if (row.type === 'member_not_active') return `成员 ${row.member_id} 已不在组织成员中，历史用量 ${fmt(row.used)}`
  if (row.type === 'member_disabled') return `成员 ${row.member_id} 的客户账号已停用，历史用量 ${fmt(row.used)}`
  if (row.type === 'usage_member_missing') return `有 ${row.count} 笔流水缺少 member_id`
  return row.detail || '-'
}

function fmt(value) {
  const n = Number(value || 0)
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function fmtCost(value) {
  return Number(value || 0).toFixed(4)
}

function fmtTime(value) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

function ratio(used, limit) {
  const l = Number(limit || 0)
  if (!l) return 0
  return Math.min(Math.round((Number(used || 0) / l) * 100), 100)
}

function itemsText(items) {
  if (!items) return '-'
  return Object.entries(items).map(([key, val]) => `${key}: ${fmt(val)}`).join('，')
}

async function load() {
  if (!props.orgId) return
  loading.value = true
  error.value = ''
  detail.value = null
  board.value = null
  try {
    const [detailRes, boardRes] = await Promise.all([
      getOrgQuotaDetail(props.orgId),
      getOrgQuotaBoard(props.orgId, { days: days.value })
    ])
    detail.value = detailRes?.data ?? detailRes
    board.value = boardRes?.data ?? boardRes
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadBoard() {
  if (!props.orgId) return
  try {
    const res = await getOrgQuotaBoard(props.orgId, { days: days.value })
    board.value = res?.data ?? res
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '加载看板失败'
  }
}

defineExpose({ load })
</script>

<style scoped>
.org-detail {
  padding: 4px 8px 24px;
}
.mb-12 { margin-bottom: 12px; }
.mb-16 { margin-bottom: 16px; }
.ml-6 { margin-left: 6px; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; }
.text-danger { color: var(--el-color-danger); }
.stat-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--el-fill-color-blank);
}
.stat-card span { color: var(--el-text-color-secondary); font-size: 12px; }
.stat-card strong { font-size: 20px; font-weight: 600; }
.split-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.split-title {
  font-weight: 600;
  margin: 4px 0 8px;
}
</style>
