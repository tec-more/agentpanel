<template>
  <div class="contentops-reviews">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>合规审核</span>
          <el-radio-group v-model="status" @change="fetchList">
            <el-radio-button value="pending">待处理</el-radio-button>
            <el-radio-button value="approved">已放行</el-radio-button>
            <el-radio-button value="rejected">已驳回</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="任务ID" width="90" align="center" />
        <el-table-column prop="content_version_id" label="成品版本ID" width="120" align="center" />
        <el-table-column label="P1命中数" width="110" align="center">
          <template #default="{ row }">
            <el-tag type="warning" size="small">{{ row.hit_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="decision" label="判定" width="100" align="center">
          <template #default="{ row }">{{ row.decision || '-' }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="理由" min-width="180" show-overflow-tooltip />
        <el-table-column prop="reviewer_id" label="审核人ID" width="100" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column v-if="status === 'pending'" label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="success" link :icon="CircleCheck" @click="handleDecide(row, 'approve')">放行</el-button>
            <el-button type="danger" link :icon="CircleClose" @click="handleDecide(row, 'reject')">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { getReviewQueue, decideReview } from '@/api/contentops'

const loading = ref(false)
const list = ref([])
const status = ref('pending')

function taskStatusLabel(s) {
  return ({ pending: '待处理', approved: '已放行', rejected: '已驳回' })[s] || s || '-'
}
function taskStatusType(s) {
  return ({ pending: 'warning', approved: 'success', rejected: 'danger' })[s] || 'info'
}

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getReviewQueue(status.value)
    list.value = data.items || []
  } finally {
    loading.value = false
  }
}

async function handleDecide(row, decision) {
  let reason = null
  if (decision === 'reject') {
    try {
      const { value } = await ElMessageBox.prompt('请输入驳回理由（必填）', '驳回审核', {
        confirmButtonText: '确认驳回', cancelButtonText: '取消',
        inputValidator: (v) => (v && v.trim() ? true : '驳回理由不能为空')
      })
      reason = value
    } catch (_) {
      return
    }
  } else {
    await ElMessageBox.confirm(`放行成品版本 #${row.content_version_id}？`, '审核放行', { type: 'info' })
  }
  try {
    await decideReview(row.id, { decision, reason })
    ElMessage.success(decision === 'approve' ? '已放行' : '已驳回')
    fetchList()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

onMounted(fetchList)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
