<template>
  <div class="instance-detail" v-loading="loading">
    <template v-if="detail">
      <!-- 基本信息 -->
      <el-descriptions title="审批信息" :column="2" border>
        <el-descriptions-item label="审批标题">{{ detail.instance.title }}</el-descriptions-item>
        <el-descriptions-item label="业务类型">{{ detail.instance.business_type || '通用' }}</el-descriptions-item>
        <el-descriptions-item label="申请人">
          {{ detail.instance.applicant?.alias || detail.instance.applicant?.username || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(detail.instance.status)" size="small">
            {{ getStatusLabel(detail.instance.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detail.instance.created_at }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ detail.instance.complete_time || '-' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 表单数据 -->
      <el-card shadow="never" class="section-card" v-if="detail.instance.form_data">
        <template #header><span>表单数据</span></template>
        <pre class="form-data">{{ JSON.stringify(detail.instance.form_data, null, 2) }}</pre>
      </el-card>

      <!-- 审批进度 -->
      <el-card shadow="never" class="section-card">
        <template #header><span>审批进度</span></template>
        <div class="progress-container">
          <div
            v-for="(task, index) in detail.tasks"
            :key="task.id"
            class="progress-node"
            :class="getTaskStatusClass(task.status)"
          >
            <div class="node-header">
              <span class="node-name">{{ task.node_id }}</span>
              <el-tag :type="getTaskStatusType(task.status)" size="small">
                {{ getTaskStatusLabel(task.status) }}
              </el-tag>
            </div>
            <div class="node-approver">
              审批人：{{ task.approver_name || '-' }}
            </div>
            <div class="node-comment" v-if="task.comment">
              意见：{{ task.comment }}
            </div>
            <div class="node-time" v-if="task.approve_time">
              {{ task.approve_time }}
            </div>
          </div>
        </div>
      </el-card>

      <!-- 审批记录 -->
      <el-card shadow="never" class="section-card">
        <template #header><span>审批记录</span></template>
        <el-timeline>
          <el-timeline-item
            v-for="record in detail.records"
            :key="record.id"
            :timestamp="record.created_at"
            :type="getRecordType(record.action)"
          >
            <div class="record-item">
              <span class="record-operator">{{ record.operator_name || '-' }}</span>
              <span class="record-action">{{ getActionLabel(record.action) }}</span>
              <span class="record-comment" v-if="record.comment">：{{ record.comment }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getInstanceDetail } from '@/api/approval'

const props = defineProps({
  instanceId: { type: Number, required: true }
})

const loading = ref(false)
const detail = ref(null)

const statusMap = {
  pending: { label: '审批中', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },
  cancelled: { label: '已撤销', type: 'info' }
}

const taskStatusMap = {
  pending: { label: '待审批', type: 'warning', class: 'pending' },
  approved: { label: '已通过', type: 'success', class: 'approved' },
  rejected: { label: '已拒绝', type: 'danger', class: 'rejected' },
  transferred: { label: '已转审', type: 'info', class: 'transferred' },
  skipped: { label: '已跳过', type: 'info', class: 'skipped' }
}

const actionMap = {
  submit: '发起审批',
  approve: '通过',
  reject: '拒绝',
  transfer: '转审',
  cancel: '撤销'
}

const getStatusLabel = (s) => statusMap[s]?.label || s
const getStatusType = (s) => statusMap[s]?.type || 'info'
const getTaskStatusLabel = (s) => taskStatusMap[s]?.label || s
const getTaskStatusType = (s) => taskStatusMap[s]?.type || 'info'
const getTaskStatusClass = (s) => taskStatusMap[s]?.class || ''
const getActionLabel = (a) => actionMap[a] || a

const getRecordType = (action) => {
  const map = { submit: 'primary', approve: 'success', reject: 'danger', transfer: 'warning', cancel: 'info' }
  return map[action] || 'primary'
}

const fetchDetail = async () => {
  loading.value = true
  try {
    const res = await getInstanceDetail(props.instanceId)
    if (res.code === 0 || res.code === 200 || res.success) {
      detail.value = res.data
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchDetail)
</script>

<style scoped lang="scss">
.instance-detail {
  padding: 8px;
}

.section-card {
  margin-top: 16px;
}

.form-data {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}

.progress-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-node {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  background: #fff;

  &.approved { border-color: #67c23a; background: #f0f9eb; }
  &.rejected { border-color: #f56c6c; background: #fef0f0; }
  &.pending { border-color: #e6a23c; background: #fdf6ec; }
  &.transferred, &.skipped { border-color: #909399; background: #f4f4f5; }
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.node-name {
  font-weight: 600;
  color: #303133;
}

.node-approver, .node-comment, .node-time {
  font-size: 13px;
  color: #606266;
  margin-top: 4px;
}

.record-item {
  font-size: 14px;
}

.record-operator {
  font-weight: 600;
  color: #303133;
}

.record-action {
  color: #409eff;
  margin: 0 4px;
}

.record-comment {
  color: #606266;
}
</style>
