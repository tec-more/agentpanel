<template>
  <div class="event-center-page">
    <!-- 顶部标题 + 统计 -->
    <el-card shadow="never" class="header-card">
      <div class="header-row">
        <div class="page-title">
          <el-icon><Bell /></el-icon>
          <span>事件中心</span>
        </div>
        <div class="stats-bar">
          <el-statistic title="订阅总数" :value="stats.subscriptions || 0" class="stat-item" />
          <el-statistic title="已启用" :value="stats.enabled_subscriptions || 0" class="stat-item" />
          <div class="stat-dist">
            <div class="dist-label">按来源分布</div>
            <div>
              <el-tag v-for="(count, source) in stats.by_source || {}" :key="source" size="small" class="dist-tag">
                {{ source }}: {{ count }}
              </el-tag>
              <span v-if="!hasEntries(stats.by_source)" class="muted">-</span>
            </div>
          </div>
          <div class="stat-dist">
            <div class="dist-label">记录状态分布</div>
            <div>
              <el-tag v-for="(count, status) in stats.records_by_status || {}" :key="status" size="small" class="dist-tag">
                {{ status }}: {{ count }}
              </el-tag>
              <span v-if="!hasEntries(stats.records_by_status)" class="muted">-</span>
            </div>
          </div>
          <el-button :icon="Refresh" circle size="small" title="刷新统计" @click="loadStats" />
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <!-- ==================== 订阅管理 ==================== -->
        <el-tab-pane label="订阅管理" name="subscriptions">
          <el-form :inline="true" :model="subFilters" class="filter-form" @submit.prevent="loadSubscriptions">
            <el-form-item label="事件名">
              <el-input v-model="subFilters.event_name" placeholder="如 sales.paid" clearable style="width: 180px" />
            </el-form-item>
            <el-form-item label="订阅方">
              <el-input v-model="subFilters.subscriber" placeholder="订阅方" clearable style="width: 150px" />
            </el-form-item>
            <el-form-item label="来源">
              <el-select v-model="subFilters.source" placeholder="全部" clearable style="width: 150px">
                <el-option label="declared（插件声明）" value="declared" />
                <el-option label="manual（后台新增）" value="manual" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Search" @click="loadSubscriptions">查询</el-button>
              <el-button @click="resetSubFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <div class="toolbar">
            <el-button :icon="Refresh" @click="loadSubscriptions">刷新</el-button>
            <el-button :icon="RefreshRight" :loading="syncing" @click="handleSync">同步插件声明</el-button>
            <el-button type="primary" :icon="Plus" @click="openCreate">新增订阅</el-button>
          </div>

          <el-table v-loading="subLoading" :data="subscriptions" border stripe size="small">
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="event_name" label="事件名" min-width="160" show-overflow-tooltip />
            <el-table-column prop="subscriber" label="订阅方" min-width="120" show-overflow-tooltip />
            <el-table-column label="来源" width="110" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="sourceTagType(row.source)">{{ row.source }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="系统" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_system ? 'warning' : 'info'">{{ row.is_system ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Handler" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.handler_ref || '-' }}</template>
            </el-table-column>
            <el-table-column label="描述" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.description || '-' }}</template>
            </el-table-column>
            <el-table-column label="创建时间" width="160">
              <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <div class="action-buttons">
                  <el-button link type="primary" :disabled="row.is_system" @click="handleToggle(row)">
                    {{ row.is_enabled ? '停用' : '启用' }}
                  </el-button>
                  <el-button link type="primary" :icon="Edit" :disabled="!canManage(row)" @click="openEdit(row)">编辑</el-button>
                  <el-button link type="danger" :icon="Delete" :disabled="!canManage(row)" @click="handleDelete(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ==================== 发布事件 ==================== -->
        <el-tab-pane label="发布事件" name="publish">
          <el-form :model="publishForm" label-width="130px" class="publish-form">
            <el-form-item label="事件名" required>
              <el-input v-model="publishForm.event_name" placeholder="小写点分格式，如 sales.paid" />
            </el-form-item>
            <el-form-item label="Payload (JSON)">
              <el-input v-model="publishForm.payload" type="textarea" :rows="8" spellcheck="false" />
              <div class="field-hint">必须是 JSON 对象，例如 { "order_id": 123 }；提交前会做 JSON.parse 校验。</div>
            </el-form-item>
            <el-form-item label="幂等键">
              <el-input v-model="publishForm.idempotency_key" placeholder="选填，同一幂等键重复投递不会产生重复副作用" clearable />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Promotion" :loading="publishLoading" @click="handlePublish">发布事件</el-button>
              <el-button @click="resetPublishForm">重置</el-button>
            </el-form-item>
          </el-form>

          <el-alert
            v-if="publishResult"
            :type="publishResult.duplicate ? 'warning' : 'success'"
            :title="publishResult.duplicate ? '重复投递（duplicate）：未产生新的副作用' : '发布成功'"
            :closable="false"
            class="publish-result"
          >
            <pre class="result-pre">{{ publishResultText }}</pre>
          </el-alert>
        </el-tab-pane>

        <!-- ==================== 发布记录 ==================== -->
        <el-tab-pane label="发布记录" name="records">
          <el-form :inline="true" :model="recordFilters" class="filter-form" @submit.prevent="searchRecords">
            <el-form-item label="事件名">
              <el-input v-model="recordFilters.event_name" placeholder="事件名" clearable style="width: 180px" />
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="recordFilters.status" placeholder="全部" clearable style="width: 170px">
                <el-option v-for="s in recordStatusOptions" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Search" @click="searchRecords">查询</el-button>
              <el-button @click="resetRecords">重置</el-button>
              <el-button :icon="Refresh" @click="loadRecords">刷新</el-button>
            </el-form-item>
          </el-form>

          <el-table v-loading="recordLoading" :data="records" border stripe size="small">
            <el-table-column prop="event_uuid" label="事件 UUID" min-width="220" show-overflow-tooltip />
            <el-table-column prop="event_name" label="事件名" min-width="150" show-overflow-tooltip />
            <el-table-column label="状态" width="150" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="retry_count" label="重试" width="80" align="center" />
            <el-table-column prop="replay_count" label="重放" width="80" align="center" />
            <el-table-column label="发布时间" width="160">
              <template #default="{ row }">{{ fmtTime(row.published_at) }}</template>
            </el-table-column>
            <el-table-column label="消费时间" width="160">
              <template #default="{ row }">{{ fmtTime(row.consumed_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right" align="center">
              <template #default="{ row }">
                <el-button v-if="canReplay(row)" link type="warning" :icon="VideoPlay" @click="handleReplay(row)">重放</el-button>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="recordPage"
              v-model:page-size="recordPageSize"
              :total="recordTotal"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @current-change="loadRecords"
              @size-change="searchRecords"
            />
          </div>
        </el-tab-pane>

        <!-- ==================== 规则说明 ==================== -->
        <el-tab-pane label="规则说明" name="rules">
          <div class="toolbar">
            <el-button :icon="Refresh" @click="loadRules">刷新规则</el-button>
          </div>
          <el-row v-if="ruleGroups.length" :gutter="12">
            <el-col v-for="group in ruleGroups" :key="group.key" :xs="24" :sm="12" class="rule-col">
              <el-card shadow="never">
                <template #header>
                  <span class="rule-title">{{ group.title }} <small>({{ group.key }})</small></span>
                </template>
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item v-for="[field, value] in group.fields" :key="field" :label="field">
                    <pre v-if="isComplex(value)" class="rule-pre">{{ formatRuleValue(value) }}</pre>
                    <span v-else>{{ formatRuleValue(value) }}</span>
                  </el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
          </el-row>
          <el-empty v-else description="暂无规则数据" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新增 / 编辑订阅 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑订阅' : '新增订阅'" width="620px">
      <el-form ref="formRef" :model="subForm" :rules="subRules" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="subForm.name" :disabled="isEdit" placeholder="订阅唯一名称" />
        </el-form-item>
        <el-form-item label="事件名" prop="event_name">
          <el-input v-model="subForm.event_name" :disabled="isEdit" placeholder="小写点分格式，如 sales.paid" />
        </el-form-item>
        <el-form-item label="订阅方" prop="subscriber">
          <el-input v-model="subForm.subscriber" :disabled="isEdit" placeholder="默认 custom" />
        </el-form-item>
        <el-form-item label="Handler" prop="handler_ref">
          <el-input v-model="subForm.handler_ref" placeholder="如 my_plugin.handlers:on_paid" />
          <div class="field-hint">格式 module:callable，即「模块路径:可调用对象名」；可留空。</div>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="subForm.description" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
        <el-form-item label="最大重试" prop="max_retries">
          <el-input-number v-model="subForm.max_retries" :min="0" :max="20" />
        </el-form-item>
        <el-form-item label="超时(ms)" prop="timeout_ms">
          <el-input-number v-model="subForm.timeout_ms" :min="100" :step="100" />
        </el-form-item>
        <el-form-item label="启用" prop="is_enabled">
          <el-switch v-model="subForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitSubscription">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Refresh, RefreshRight, Plus, Edit, Delete, Promotion, VideoPlay, Bell
} from '@element-plus/icons-vue'
import {
  getRules,
  getSubscriptions,
  createSubscription,
  updateSubscription,
  toggleSubscription,
  deleteSubscription,
  publishEvent,
  getRecords,
  replayEvent,
  getStats,
  syncDeclared
} from '@/api/eventCenter'

const activeTab = ref('subscriptions')

// 后端统一返回 SuccessResponse（{ code, data, msg }），取业务数据时兼容直接返回数据的场景
const pickData = (res) => res?.data || res
const showError = (e, fallback) => ElMessage.error(e?.response?.data?.msg || e?.message || fallback)
const hasEntries = (obj) => !!(obj && typeof obj === 'object' && Object.keys(obj).length)
const fmtTime = (value) => (value ? String(value).replace('T', ' ').slice(0, 19) : '-')
const sourceTagType = (source) => (source === 'manual' ? 'success' : 'warning')
const statusTagType = (status) => ({
  published: 'success',
  consuming: 'primary',
  consumed: 'success',
  failed: 'danger',
  dead_letter: 'danger',
  degraded_published: 'warning',
  degraded_consumed: 'warning'
}[status] || 'info')

// ==================== 统计 ==================== //

const stats = ref({})

const loadStats = async () => {
  try {
    const res = await getStats()
    stats.value = pickData(res) || {}
  } catch (e) {
    showError(e, '加载统计失败')
  }
}

// ==================== 订阅管理 ==================== //

const subLoading = ref(false)
const subscriptions = ref([])
const subFilters = reactive({ event_name: '', subscriber: '', source: '' })

const canManage = (row) => !row.is_system && row.source === 'manual'

const loadSubscriptions = async () => {
  subLoading.value = true
  try {
    const params = {
      event_name: subFilters.event_name || undefined,
      subscriber: subFilters.subscriber || undefined,
      source: subFilters.source || undefined
    }
    const res = await getSubscriptions(params)
    const data = pickData(res)
    subscriptions.value = Array.isArray(data) ? data : (data?.items || [])
  } catch (e) {
    subscriptions.value = []
    showError(e, '加载订阅列表失败')
  } finally {
    subLoading.value = false
  }
}

const resetSubFilters = () => {
  subFilters.event_name = ''
  subFilters.subscriber = ''
  subFilters.source = ''
  loadSubscriptions()
}

const handleToggle = async (row) => {
  try {
    await toggleSubscription(row.id)
    ElMessage.success(row.is_enabled ? '已停用' : '已启用')
    loadSubscriptions()
    loadStats()
  } catch (e) {
    showError(e, '切换订阅状态失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除订阅「${row.name}」吗？`, '删除确认', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await deleteSubscription(row.id)
    ElMessage.success('订阅已删除')
    loadSubscriptions()
    loadStats()
  } catch (e) {
    showError(e, '删除订阅失败')
  }
}

const syncing = ref(false)
const handleSync = async () => {
  syncing.value = true
  try {
    const res = await syncDeclared()
    const data = pickData(res)
    ElMessage.success(`声明订阅已同步，共 ${data?.declared ?? 0} 条`)
    loadSubscriptions()
    loadStats()
  } catch (e) {
    showError(e, '同步插件声明失败')
  } finally {
    syncing.value = false
  }
}

// 新增 / 编辑表单
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const submitLoading = ref(false)
const formRef = ref(null)
const subForm = reactive({
  name: '',
  event_name: '',
  subscriber: '',
  handler_ref: '',
  description: '',
  max_retries: 3,
  timeout_ms: 30000,
  is_enabled: true
})
const subRules = {
  name: [{ required: true, message: '请输入订阅名称', trigger: 'blur' }],
  event_name: [{ required: true, message: '请输入事件名', trigger: 'blur' }]
}

const openCreate = () => {
  isEdit.value = false
  editingId.value = null
  Object.assign(subForm, {
    name: '', event_name: '', subscriber: '', handler_ref: '', description: '',
    max_retries: 3, timeout_ms: 30000, is_enabled: true
  })
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editingId.value = row.id
  Object.assign(subForm, {
    name: row.name || '',
    event_name: row.event_name || '',
    subscriber: row.subscriber || '',
    handler_ref: row.handler_ref || '',
    description: row.description || '',
    max_retries: row.max_retries ?? 3,
    timeout_ms: row.timeout_ms ?? 30000,
    is_enabled: !!row.is_enabled
  })
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const submitSubscription = async () => {
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }
  // 编辑时后端仅允许更新以下字段，name / event_name / subscriber 不可改
  const payload = {
    handler_ref: subForm.handler_ref,
    description: subForm.description,
    max_retries: subForm.max_retries,
    timeout_ms: subForm.timeout_ms,
    is_enabled: subForm.is_enabled
  }
  if (!isEdit.value) {
    Object.assign(payload, {
      name: subForm.name,
      event_name: subForm.event_name,
      subscriber: subForm.subscriber || 'custom'
    })
  }
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateSubscription(editingId.value, payload)
      ElMessage.success('订阅已更新')
    } else {
      await createSubscription(payload)
      ElMessage.success('订阅已创建')
    }
    dialogVisible.value = false
    loadSubscriptions()
    loadStats()
  } catch (e) {
    showError(e, '保存订阅失败')
  } finally {
    submitLoading.value = false
  }
}

// ==================== 发布事件 ==================== //

const publishForm = reactive({ event_name: '', payload: '{}', idempotency_key: '' })
const publishLoading = ref(false)
const publishResult = ref(null)
const publishResultText = computed(() => JSON.stringify(publishResult.value || {}, null, 2))

const resetPublishForm = () => {
  publishForm.event_name = ''
  publishForm.payload = '{}'
  publishForm.idempotency_key = ''
  publishResult.value = null
}

const handlePublish = async () => {
  let payload
  try {
    payload = JSON.parse(publishForm.payload || '{}')
  } catch (e) {
    ElMessage.error(`payload 不是合法的 JSON：${e.message}`)
    return
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    ElMessage.error('payload 必须是 JSON 对象')
    return
  }
  if (!publishForm.event_name.trim()) {
    ElMessage.error('请输入事件名')
    return
  }
  publishLoading.value = true
  try {
    const res = await publishEvent({
      event_name: publishForm.event_name.trim(),
      payload,
      idempotency_key: publishForm.idempotency_key.trim() || undefined
    })
    publishResult.value = pickData(res) || {}
    if (publishResult.value.duplicate) {
      ElMessage.warning('重复投递：该幂等键已存在，未产生新的副作用')
    } else {
      ElMessage.success('事件已发布')
    }
  } catch (e) {
    showError(e, '发布事件失败')
  } finally {
    publishLoading.value = false
  }
}

// ==================== 发布记录 ==================== //

const recordLoading = ref(false)
const records = ref([])
const recordFilters = reactive({ event_name: '', status: '' })
const recordPage = ref(1)
const recordPageSize = ref(20)
const recordTotal = ref(0)
const recordStatusOptions = [
  'published', 'consuming', 'consumed', 'failed', 'dead_letter',
  'degraded_published', 'degraded_consumed'
]

const canReplay = (row) => row.status === 'failed' || row.status === 'dead_letter'

const loadRecords = async () => {
  recordLoading.value = true
  try {
    const params = {
      event_name: recordFilters.event_name || undefined,
      status: recordFilters.status || undefined,
      page: recordPage.value,
      page_size: recordPageSize.value
    }
    const res = await getRecords(params)
    const data = pickData(res)
    records.value = data?.items || []
    recordTotal.value = data?.total || 0
  } catch (e) {
    records.value = []
    recordTotal.value = 0
    showError(e, '加载发布记录失败')
  } finally {
    recordLoading.value = false
  }
}

const searchRecords = () => {
  recordPage.value = 1
  loadRecords()
}

const resetRecords = () => {
  recordFilters.event_name = ''
  recordFilters.status = ''
  recordPage.value = 1
  loadRecords()
}

const handleReplay = async (row) => {
  try {
    const res = await replayEvent(row.event_uuid, { reason: '管理页手动重放' })
    const data = pickData(res)
    ElMessage.success(data?.replayed ? '事件已重放' : '重放请求已提交')
    loadRecords()
    loadStats()
  } catch (e) {
    showError(e, '重放事件失败')
  }
}

// ==================== 规则说明 ==================== //

const rulesData = ref({})
const ruleTitles = {
  event_name: '事件名规范',
  payload: '载荷规范',
  idempotency: '幂等性',
  delivery: '投递语义',
  isolation: '隔离性',
  subscription: '订阅规则',
  publish: '发布入口'
}

const isComplex = (value) => value !== null && typeof value === 'object'
const formatRuleValue = (value) => {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

const ruleGroups = computed(() => {
  const data = rulesData.value || {}
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return [{ key: 'rules', title: '规则', fields: [['值', data]] }]
  }
  return Object.entries(data).map(([key, value]) => ({
    key,
    title: ruleTitles[key] || key,
    fields: isComplex(value) && !Array.isArray(value)
      ? Object.entries(value)
      : [['值', value]]
  }))
})

const loadRules = async () => {
  try {
    const res = await getRules()
    rulesData.value = pickData(res) || {}
  } catch (e) {
    rulesData.value = {}
    showError(e, '加载规则说明失败')
  }
}

onMounted(() => {
  loadSubscriptions()
  loadRecords()
  loadRules()
  loadStats()
})
</script>

<style scoped>
.event-center-page { padding: 16px; }
.header-card { margin-bottom: 12px; }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.page-title { display: flex; align-items: center; gap: 6px; font-size: 18px; font-weight: 600; }
.stats-bar { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.stat-item { min-width: 88px; }
.stat-dist { font-size: 12px; }
.dist-label { color: var(--el-text-color-secondary); margin-bottom: 4px; }
.dist-tag { margin: 0 4px 4px 0; }
.muted { color: var(--el-text-color-secondary); }
.filter-form :deep(.el-form-item) { margin-bottom: 8px; }
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.publish-form { max-width: 680px; }
.field-hint { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; margin-top: 2px; }
.publish-result { margin-top: 16px; max-width: 680px; }
.result-pre, .rule-pre { margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 12px; line-height: 1.5; }
.rule-col { margin-bottom: 12px; }
.rule-title { font-weight: 600; }
.rule-title small { color: var(--el-text-color-secondary); font-weight: 400; }
.rule-pre { max-height: 220px; overflow-y: auto; }
.action-buttons { display: flex; flex-wrap: wrap; gap: 2px; }
</style>
