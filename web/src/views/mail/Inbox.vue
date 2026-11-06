<template>
  <div class="mail-inbox">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="已读状态">
          <el-select v-model="searchForm.is_read" placeholder="全部" clearable style="width: 120px">
            <el-option label="未读" :value="false" />
            <el-option label="已读" :value="true" />
          </el-select>
        </el-form-item>
        <el-form-item label="标星">
          <el-select v-model="searchForm.is_starred" placeholder="全部" clearable style="width: 120px">
            <el-option label="已标星" :value="true" />
          </el-select>
        </el-form-item>
        <el-form-item label="消息类型">
          <el-select v-model="searchForm.message_type" placeholder="全部" clearable style="width: 140px">
            <el-option label="系统通知" value="notification" />
            <el-option label="评论" value="comment" />
            <el-option label="邮件" value="email" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务表名">
          <el-input v-model="searchForm.model" placeholder="如 purchase_order" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>收件箱</span>
          <div class="header-actions">
            <el-button size="small" :disabled="!selection.length" @click="batchMarkRead">批量已读</el-button>
            <el-button size="small" :disabled="!selection.length" @click="batchMarkUnread">批量未读</el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="tableData"
        border
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column label="" width="50" align="center">
          <template #default="{ row }">
            <span v-if="!row.is_read" class="unread-dot" />
          </template>
        </el-table-column>
        <el-table-column label="主题/正文" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="msg-cell">
              <div class="msg-subject">{{ row.message?.subject || row.message?.record_name || '(无主题)' }}</div>
              <div class="msg-body">{{ stripHtml(row.message?.body) }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTagType(row.message?.message_type)">
              {{ typeLabel(row.message?.message_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message.model" label="业务表" width="150" show-overflow-tooltip />
        <el-table-column prop="message.res_id" label="记录ID" width="90" align="center" />
        <el-table-column label="标星" width="70" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_starred" class="star-icon"><Star /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="接收时间" width="170" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
              <el-button v-if="!row.is_read" link @click="handleMarkRead(row)">标已读</el-button>
              <el-button v-else link @click="handleMarkUnread(row)">标未读</el-button>
              <el-button link @click="handleToggleStar(row)">
                {{ row.is_starred ? '取消标星' : '标星' }}
              </el-button>
            </div>
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="通知详情" width="720px">
      <el-descriptions v-if="currentNotification" :column="2" border>
        <el-descriptions-item label="主题" :span="2">
          {{ currentNotification.message?.subject || '(无主题)' }}
        </el-descriptions-item>
        <el-descriptions-item label="类型">
          <el-tag size="small" :type="typeTagType(currentNotification.message?.message_type)">
            {{ typeLabel(currentNotification.message?.message_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="子类型">
          {{ currentNotification.message?.subtype?.name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="业务表">{{ currentNotification.message?.model || '-' }}</el-descriptions-item>
        <el-descriptions-item label="记录ID">{{ currentNotification.message?.res_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发送者">
          {{ currentNotification.message?.author?.username || '系统' }}
        </el-descriptions-item>
        <el-descriptions-item label="接收时间">{{ currentNotification.created_at }}</el-descriptions-item>
        <el-descriptions-item label="正文" :span="2">
          <div class="msg-body-full" v-html="currentNotification.message?.body || '(无正文)'" />
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, View, Star } from '@element-plus/icons-vue'
import { getInbox, markRead, markUnread, toggleStar } from '@/api/mail'

const loading = ref(false)
const tableData = ref([])
const selection = ref([])
const detailDialogVisible = ref(false)
const currentNotification = ref(null)

const searchForm = reactive({
  is_read: null,
  is_starred: null,
  message_type: null,
  model: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const stripHtml = (html) => {
  if (!html) return ''
  return html.replace(/<[^>]+>/g, '').slice(0, 80)
}

const typeTagType = (t) => {
  if (t === 'comment') return 'success'
  if (t === 'email') return 'warning'
  return 'info'
}

const typeLabel = (t) => {
  if (t === 'comment') return '评论'
  if (t === 'email') return '邮件'
  if (t === 'notification') return '通知'
  return t || '-'
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.is_read !== null && searchForm.is_read !== '') {
      params.is_read = searchForm.is_read
    }
    if (searchForm.is_starred !== null && searchForm.is_starred !== '') {
      params.is_starred = searchForm.is_starred
    }
    if (searchForm.message_type) params.message_type = searchForm.message_type
    if (searchForm.model) params.model = searchForm.model

    const res = await getInbox(params)
    tableData.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } catch (e) {
    console.error('获取收件箱失败', e)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.is_read = null
  searchForm.is_starred = null
  searchForm.message_type = null
  searchForm.model = ''
  pagination.page = 1
  fetchData()
}

const handleSelectionChange = (val) => {
  selection.value = val
}

const notifyBellRefresh = () => {
  window.dispatchEvent(new CustomEvent('mail:refresh'))
}

const handleDetail = async (row) => {
  currentNotification.value = row
  detailDialogVisible.value = true
  if (!row.is_read) {
    try {
      await markRead([row.id])
      row.is_read = true
      notifyBellRefresh()
    } catch (e) {
      // 忽略
    }
  }
}

const handleMarkRead = async (row) => {
  try {
    await markRead([row.id])
    row.is_read = true
    ElMessage.success('已标记为已读')
    notifyBellRefresh()
  } catch (e) {
    ElMessage.error('标记失败')
  }
}

const handleMarkUnread = async (row) => {
  try {
    await markUnread([row.id])
    row.is_read = false
    ElMessage.success('已标记为未读')
    notifyBellRefresh()
  } catch (e) {
    ElMessage.error('标记失败')
  }
}

const handleToggleStar = async (row) => {
  try {
    const res = await toggleStar(row.id)
    row.is_starred = res.data?.is_starred
    ElMessage.success(row.is_starred ? '已标星' : '已取消标星')
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const batchMarkRead = async () => {
  const ids = selection.value.map(n => n.id)
  if (!ids.length) return
  try {
    const res = await markRead(ids)
    ElMessage.success(`已标记 ${res.data?.updated || 0} 条为已读`)
    fetchData()
    notifyBellRefresh()
  } catch (e) {
    ElMessage.error('批量操作失败')
  }
}

const batchMarkUnread = async () => {
  const ids = selection.value.map(n => n.id)
  if (!ids.length) return
  try {
    const res = await markUnread(ids)
    ElMessage.success(`已标记 ${res.data?.updated || 0} 条为未读`)
    fetchData()
    notifyBellRefresh()
  } catch (e) {
    ElMessage.error('批量操作失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.mail-inbox {
  padding: 16px;
}
.search-card {
  margin-bottom: 16px;
}
.table-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.unread-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f56c6c;
}
.msg-cell .msg-subject {
  font-weight: 500;
  color: #303133;
}
.msg-cell .msg-body {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.star-icon {
  color: #e6a23c;
}
.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.msg-body-full {
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}
</style>
