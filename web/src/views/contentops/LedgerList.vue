<template>
  <div class="contentops-ledger">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>发布台账</span>
          <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 150px"
                     @change="fetchList">
            <el-option label="待发布" value="pending" />
            <el-option label="已发布" value="published" />
            <el-option label="已放弃" value="abandoned" />
          </el-select>
        </div>
      </template>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="version_id" label="版本ID" width="90" align="center" />
        <el-table-column label="平台" width="130">
          <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="ledgerStatusType(row.status)" size="small">{{ ledgerStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="planned_at" label="计划发布" width="170" />
        <el-table-column prop="published_at" label="实际发布" width="170" />
        <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleStatus(row)">状态</el-button>
            <el-button type="success" link size="small" @click="handleEffect(row)">效果数据</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 状态更新弹窗 -->
    <el-dialog v-model="statusVisible" title="更新发布状态" width="480px">
      <el-form :model="statusForm" label-width="90px">
        <el-form-item label="状态">
          <el-select v-model="statusForm.status" style="width: 100%">
            <el-option label="待发布" value="pending" />
            <el-option label="已发布" value="published" />
            <el-option label="已放弃" value="abandoned" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布时间">
          <el-date-picker v-model="statusForm.published_at" type="datetime" placeholder="选择时间"
                          value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="statusForm.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusVisible = false">取消</el-button>
        <el-button type="primary" @click="submitStatus">保存</el-button>
      </template>
    </el-dialog>

    <!-- 效果数据抽屉 -->
    <el-drawer v-model="effectVisible" title="效果数据" size="55%">
      <div v-if="currentLedger">
        <el-descriptions :column="2" border class="mb-4">
          <el-descriptions-item label="台账ID">{{ currentLedger.id }}</el-descriptions-item>
          <el-descriptions-item label="平台">{{ platformLabel(currentLedger.platform) }}</el-descriptions-item>
          <el-descriptions-item label="版本ID">{{ currentLedger.version_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ ledgerStatusLabel(currentLedger.status) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">历史数据</el-divider>
        <el-table :data="effects" border size="small">
          <el-table-column prop="stat_date" label="日期" width="120" />
          <el-table-column prop="views" label="阅读/播放" width="100" align="right" />
          <el-table-column prop="likes" label="点赞" width="90" align="right" />
          <el-table-column prop="comments" label="评论" width="90" align="right" />
          <el-table-column prop="favorites" label="收藏" width="90" align="right" />
          <el-table-column label="来源" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.source === 'csv' ? 'warning' : 'info'" size="small">{{ row.source }}</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <el-divider content-position="left">手工回填</el-divider>
        <el-form :model="effectForm" label-width="90px">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="阅读/播放"><el-input-number v-model="effectForm.views" :min="0" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="点赞"><el-input-number v-model="effectForm.likes" :min="0" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="评论"><el-input-number v-model="effectForm.comments" :min="0" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="收藏"><el-input-number v-model="effectForm.favorites" :min="0" style="width:100%" /></el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="统计日期">
            <el-date-picker v-model="effectForm.stat_date" type="date" value-format="YYYY-MM-DD"
                            placeholder="选择日期" style="width: 100%" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="submitEffect">提交回填</el-button>
          </el-form-item>
        </el-form>

        <el-divider content-position="left">CSV 导入</el-divider>
        <el-form label-width="90px">
          <el-form-item label="CSV 内容">
            <el-input v-model="csvContent" type="textarea" :rows="5"
                      placeholder="第一行表头，如：date,views,likes,comments,favorites" />
          </el-form-item>
          <el-form-item label="列映射">
            <el-input v-model="csvMapping" placeholder='JSON，如 {"date":"stat_date","播放量":"views"}' />
          </el-form-item>
          <el-form-item>
            <el-button @click="submitCsv">导入 CSV</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getLedgerList, updateLedger, addEffect, importEffect, getEffect, PLATFORMS
} from '@/api/contentops'

const loading = ref(false)
const list = ref([])
const filterStatus = ref(null)

const statusVisible = ref(false)
const statusForm = reactive({ status: 'pending', published_at: null, note: '' })
const currentStatusId = ref(null)

const effectVisible = ref(false)
const currentLedger = ref(null)
const effects = ref([])
const effectForm = reactive({ views: 0, likes: 0, comments: 0, favorites: 0, stat_date: null })
const csvContent = ref('')
const csvMapping = ref('')

function platformLabel(v) { return PLATFORMS.find((p) => p.value === v)?.label || v }
function ledgerStatusLabel(s) { return ({ pending: '待发布', published: '已发布', abandoned: '已放弃' })[s] || s || '-' }
function ledgerStatusType(s) { return ({ pending: 'warning', published: 'success', abandoned: 'info' })[s] || 'info' }

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getLedgerList(filterStatus.value ? { status: filterStatus.value } : {})
    list.value = data.items || []
  } finally {
    loading.value = false
  }
}

function handleStatus(row) {
  currentStatusId.value = row.id
  Object.assign(statusForm, {
    status: row.status, published_at: row.published_at || null, note: row.note || ''
  })
  statusVisible.value = true
}
async function submitStatus() {
  await updateLedger(currentStatusId.value, {
    status: statusForm.status,
    published_at: statusForm.published_at || undefined,
    note: statusForm.note
  })
  ElMessage.success('已更新')
  statusVisible.value = false
  fetchList()
}

async function handleEffect(row) {
  currentLedger.value = row
  effectVisible.value = true
  Object.assign(effectForm, { views: 0, likes: 0, comments: 0, favorites: 0, stat_date: null })
  csvContent.value = ''
  csvMapping.value = ''
  await loadEffects(row.id)
}
async function loadEffects(ledgerId) {
  const { data } = await getEffect(ledgerId)
  effects.value = data.items || []
}
async function submitEffect() {
  try {
    await addEffect(currentLedger.value.id, { ...effectForm })
    ElMessage.success('已回填')
    await loadEffects(currentLedger.value.id)
  } catch (e) {
    ElMessage.error(e.message || '回填失败')
  }
}
async function submitCsv() {
  if (!csvContent.value.trim()) { ElMessage.warning('请填写 CSV 内容'); return }
  let mapping = {}
  if (csvMapping.value.trim()) {
    try { mapping = JSON.parse(csvMapping.value) }
    catch (_) { ElMessage.error('列映射不是合法 JSON'); return }
  }
  try {
    const { data } = await importEffect(currentLedger.value.id, {
      csv_content: csvContent.value, column_mapping: mapping
    })
    ElMessage.success(`已导入 ${data.imported || 0} 条`)
    await loadEffects(currentLedger.value.id)
  } catch (e) {
    ElMessage.error(e.message || '导入失败')
  }
}

onMounted(fetchList)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.mb-4 { margin-bottom: 16px; }
</style>
