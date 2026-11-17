<template>
  <div class="contentops-contents">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>内容中心</span>
          <el-button type="primary" :icon="Plus" @click="handleCreate">新建内容</el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="search" class="search-form">
        <el-form-item label="关键词">
          <el-input v-model="search.keyword" placeholder="标题/摘要" clearable style="width: 200px"
                    @keyup.enter="fetchList" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="search.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="草稿" value="draft" />
            <el-option label="待确认" value="pending" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已发布" value="published" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchList">搜索</el-button>
          <el-button :icon="Refresh" @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="summary" label="摘要" min-width="180" show-overflow-tooltip />
        <el-table-column label="话题" width="180">
          <template #default="{ row }">
            <el-tag v-for="t in (row.topics || [])" :key="t" size="small" class="mr-1">{{ t }}</el-tag>
            <span v-if="!row.topics || !row.topics.length">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="320" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
            <el-button type="warning" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link @click="handleCheck(row)">合规检测</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]" :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchList" @current-change="fetchList" />
      </div>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑内容' : '新建内容'" width="700px"
               destroy-on-close>
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="请输入标题" maxlength="512" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" placeholder="可选摘要" />
        </el-form-item>
        <el-form-item label="话题">
          <el-select v-model="form.topics" multiple filterable allow-create default-first-option
                     placeholder="输入后回车添加话题" style="width: 100%" />
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input v-model="form.body" type="textarea" :rows="12" placeholder="支持富文本/纯文本" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="内容详情" size="60%">
      <div v-if="detail" class="detail-body">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
          <el-descriptions-item label="标题" :span="2">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="摘要" :span="2">{{ detail.summary || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">自适应生成</el-divider>
        <div class="adapt-bar">
          <el-select v-model="adaptPlatforms" multiple placeholder="选择目标平台" style="width: 320px">
            <el-option v-for="p in PLATFORMS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
          <el-switch v-model="adaptUseLlm" active-text="AI 改写" inactive-text="仅规则" />
          <el-button type="primary" :loading="adapting" @click="handleAdapt">生成成品</el-button>
        </div>

        <el-divider content-position="left">成品版本（{{ (detail.versions || []).length }}）</el-divider>
        <el-table :data="detail.versions || []" border size="small">
          <el-table-column prop="id" label="ID" width="65" align="center" />
          <el-table-column prop="platform" label="平台" width="110" />
          <el-table-column label="标题" min-width="160">
            <template #default="{ row }">{{ row.payload?.title || '-' }}</template>
          </el-table-column>
          <el-table-column label="自适应" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_adapted ? 'success' : 'info'" size="small">
                {{ row.is_adapted ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="确认" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.confirmed ? 'success' : 'warning'" size="small">
                {{ row.confirmed ? '已确认' : '未确认' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110" align="center">
            <template #default="{ row }">{{ row.status }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220" align="center">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="viewVersion(row)">查看</el-button>
              <el-button type="success" link size="small" @click="handleConfirm(row)">确认</el-button>
              <el-button v-if="row.parent_id" type="warning" link size="small"
                         @click="handleRollback(row)">回退</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <!-- 成品载荷查看弹窗 -->
    <el-dialog v-model="versionVisible" title="成品载荷" width="700px">
      <div v-if="currentVersion">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="平台">{{ currentVersion.platform }}</el-descriptions-item>
          <el-descriptions-item label="标题">{{ currentVersion.payload?.title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="正文">
            <div class="payload-body">{{ currentVersion.payload?.body || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="话题">{{ (currentVersion.payload?.topics || []).join(', ') || '-' }}</el-descriptions-item>
          <el-descriptions-item label="规则版本">{{ currentVersion.rule_version || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="currentVersion.diff && currentVersion.diff.length" class="diff-area">
          <h4>相对父版本改动</h4>
          <div v-for="(d, i) in currentVersion.diff" :key="i" class="diff-line">
            <span class="diff-old">- {{ typeof d === 'string' ? d : d.original }}</span>
            <span class="diff-new">+ {{ typeof d === 'string' ? d : d.revised }}</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Search, Refresh, View } from '@element-plus/icons-vue'
import {
  getContentList, getContentDetail, createContent, updateContent, deleteContent,
  generateAdapt, checkCompliance, confirmVersion, rollbackVersion, PLATFORMS
} from '@/api/contentops'

const loading = ref(false)
const list = ref([])
const search = reactive({ keyword: '', status: null })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const form = reactive({ title: '', summary: '', body: '', topics: [] })

const detailVisible = ref(false)
const detail = ref(null)
const adaptPlatforms = ref([])
const adaptUseLlm = ref(true)
const adapting = ref(false)
const versionVisible = ref(false)
const currentVersion = ref(null)

function statusLabel(s) {
  return ({ draft: '草稿', pending: '待确认', confirmed: '已确认', published: '已发布',
    review_passed: '审核通过', rejected: '已驳回' })[s] || s || '-'
}
function statusType(s) {
  return ({ draft: 'info', pending: 'warning', confirmed: 'success', published: 'success',
    review_passed: 'success', rejected: 'danger' })[s] || 'info'
}

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getContentList({
      page: pagination.page, page_size: pagination.pageSize,
      keyword: search.keyword || undefined, status: search.status || undefined
    })
    list.value = data.items || []
    pagination.total = data.total || 0
  } finally {
    loading.value = false
  }
}
function resetSearch() {
  search.keyword = ''
  search.status = null
  pagination.page = 1
  fetchList()
}

function handleCreate() {
  editingId.value = null
  Object.assign(form, { title: '', summary: '', body: '', topics: [] })
  dialogVisible.value = true
}
function handleEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    title: row.title, summary: row.summary || '', body: row.body, topics: row.topics || []
  })
  dialogVisible.value = true
}
async function submitForm() {
  if (!form.title || !form.body) {
    ElMessage.warning('标题和正文必填')
    return
  }
  submitting.value = true
  try {
    const payload = { title: form.title, summary: form.summary, body: form.body, topics: form.topics }
    if (editingId.value) await updateContent(editingId.value, payload)
    else await createContent(payload)
    ElMessage.success(editingId.value ? '已更新' : '已创建')
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}
async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除「${row.title}」？`, '提示', { type: 'warning' })
  await deleteContent(row.id)
  ElMessage.success('已删除')
  fetchList()
}

async function handleDetail(row) {
  detailVisible.value = true
  const { data } = await getContentDetail(row.id)
  detail.value = data
}
async function handleAdapt() {
  if (!detail.value || !adaptPlatforms.value.length) {
    ElMessage.warning('请选择目标平台')
    return
  }
  adapting.value = true
  try {
    const { data } = await generateAdapt({
      content_id: detail.value.id, platforms: adaptPlatforms.value, use_llm: adaptUseLlm.value
    })
    ElMessage.success(`已生成 ${data.items?.length || 0} 个成品`)
    const { data: fresh } = await getContentDetail(detail.value.id)
    detail.value = fresh
  } finally {
    adapting.value = false
  }
}
async function handleCheck(row) {
  const { data } = await checkCompliance({ content_id: row.id, channels: ['text'] })
  const hits = data.hits || data.hits_count || 0
  ElMessage.success(`检测完成，命中：${typeof hits === 'number' ? hits : (hits.length || 0)}`)
}
async function viewVersion(row) {
  currentVersion.value = row
  versionVisible.value = true
}
async function handleConfirm(row) {
  await ElMessageBox.confirm(`确认版本 #${row.id} 可用于导出？`, '人工确认', { type: 'info' })
  try {
    await confirmVersion(row.id, true)
    ElMessage.success('已确认')
    const { data } = await getContentDetail(detail.value.id)
    detail.value = data
  } catch (e) {
    ElMessage.error(e.message || '确认失败')
  }
}
async function handleRollback(row) {
  await ElMessageBox.confirm(`将版本 #${row.id} 回退到父版本？`, '提示', { type: 'warning' })
  await rollbackVersion(row.id)
  ElMessage.success('已回退')
  const { data } = await getContentDetail(detail.value.id)
  detail.value = data
}

onMounted(fetchList)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 16px; }
.pagination-wrapper { display: flex; justify-content: flex-end; margin-top: 16px; }
.mr-1 { margin-right: 4px; }
.detail-body { padding-right: 8px; }
.adapt-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.payload-body { white-space: pre-wrap; max-height: 300px; overflow: auto; }
.diff-area { margin-top: 16px; }
.diff-line { display: flex; flex-direction: column; margin-bottom: 8px; font-size: 13px; }
.diff-old { color: #c62828; }
.diff-new { color: #2e7d32; }
</style>
