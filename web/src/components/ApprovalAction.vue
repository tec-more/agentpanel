<template>
  <div class="approval-action" v-if="ready">
    <!-- ====== 加载中 ====== -->
    <span v-if="loading" class="approval-loading">
      <el-icon class="is-loading"><Loading /></el-icon> 检测审批规则...
    </span>

    <!-- ====== 无审批流程 ====== -->
    <span v-else-if="!hasFlow" />

    <!-- ====== 列表模式：仅显示提交审批按钮 ====== -->
    <template v-else-if="mode === 'list'">
      <el-button v-if="canCreate" type="warning" @click="onSubmit('create')">
        <el-icon><DocumentAdd /></el-icon>
        提交审批
      </el-button>
    </template>

    <!-- ====== 详情模式 ====== -->
    <template v-else-if="mode === 'detail'">
      <!-- 无实例：显示提交审批按钮 -->
      <template v-if="!instance">
        <el-dropdown v-if="canSubmit" trigger="click" @command="onSubmit">
          <el-button type="warning">
            <el-icon><DocumentAdd /></el-icon>
            提交审批
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="canUpdate" command="update">
                <el-icon><Edit /></el-icon> 提交更新审批
              </el-dropdown-item>
              <el-dropdown-item v-if="canCreate" command="create">
                <el-icon><Plus /></el-icon> 重新提交创建审批
              </el-dropdown-item>
              <el-dropdown-item v-if="canDelete" command="delete" divided>
                <el-icon><Delete /></el-icon> 提交删除审批
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>

      <!-- 有实例：显示状态 + 操作 -->
      <template v-else>
        <div class="approval-instance-bar">
          <!-- 状态标签 -->
          <el-tag :type="statusTagType" class="approval-status-tag">
            {{ statusLabel }}
          </el-tag>

          <!-- 审批人操作：通过/拒绝 -->
          <template v-if="canApprove">
            <el-button
              v-for="task in pendingTasks"
              :key="task.id"
              type="success"
              size="small"
              @click="onApprove(task.id, true)"
            >
              <el-icon><Check /></el-icon> 通过
            </el-button>
            <el-button
              v-for="task in pendingTasks"
              :key="'reject-' + task.id"
              type="danger"
              size="small"
              @click="onApprove(task.id, false)"
            >
              <el-icon><Close /></el-icon> 拒绝
            </el-button>
            <el-button
              v-for="task in pendingTasks"
              :key="'transfer-' + task.id"
              size="small"
              @click="onTransfer(task.id)"
            >
              <el-icon><Switch /></el-icon> 转审
            </el-button>
          </template>

          <!-- 申请人操作：撤销 -->
          <el-button v-if="canCancel" type="info" size="small" @click="onCancel">
            <el-icon><CircleClose /></el-icon> 撤销
          </el-button>

          <!-- 查看详情 -->
          <el-button
            v-if="instance"
            size="small"
            @click="onViewDetail"
          >
            <el-icon><View /></el-icon> 审批详情
          </el-button>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Loading, DocumentAdd, ArrowDown, Edit, Plus, Delete,
  Check, Close, Switch, CircleClose, View
} from '@element-plus/icons-vue'
import { getApprovalContext, submitForApproval, approveTask, cancelInstance, transferTask } from '@/api/approval'

// =================== Props ===================
const props = defineProps({
  /** 业务模型标识，如 "purchase_order" */
  model: { type: String, required: true },
  /** 业务对象 ID（详情页传入，列表页不传） */
  businessId: { type: [Number, String], default: null },
  /** 模式：list（列表页默认按钮）/ detail（详情页含状态+多按钮） */
  mode: { type: String, default: 'list', validator: v => ['list', 'detail'].includes(v) },
})

// =================== Emits ===================
const emit = defineEmits([
  'submit',      // 提交审批: (action, flowInfo)
  'approve',     // 审批操作: (taskId, approved, comment)
  'cancel',      // 撤销: (instanceId)
  'transfer',    // 转审: (taskId, targetUserId)
  'viewDetail',  // 查看审批详情: (instanceId)
  'loaded',      // 加载完成: (context)
])

// =================== State ===================
const loading = ref(false)
const ready = ref(false)
const contextData = ref(null)

const hasFlow = computed(() => contextData.value?.has_flow ?? false)
const flows = computed(() => contextData.value?.flows ?? [])
const instance = computed(() => contextData.value?.instance ?? null)
const pendingTasks = computed(() => contextData.value?.pending_tasks ?? [])

const canSubmit = computed(() => contextData.value?.can_submit ?? false)
const canApprove = computed(() => contextData.value?.can_approve ?? false)
const canCancel = computed(() => contextData.value?.can_cancel ?? false)
const canCreate = computed(() => contextData.value?.can_create ?? false)
const canUpdate = computed(() => contextData.value?.can_update ?? false)
const canDelete = computed(() => contextData.value?.can_delete ?? false)

const statusLabel = computed(() => {
  const map = { pending: '审批中', approved: '已通过', rejected: '已拒绝', cancelled: '已撤销' }
  return map[instance.value?.status] || instance.value?.status || '未知'
})

const statusTagType = computed(() => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger', cancelled: 'info' }
  return map[instance.value?.status] || 'info'
})

// =================== Methods ===================

async function loadContext() {
  if (!props.model) return
  loading.value = true
  try {
    const params = { model: props.model }
    if (props.businessId != null && props.mode === 'detail') {
      params.business_id = props.businessId
    }
    const res = await getApprovalContext(params)
    if (res.code === 0 && res.data) {
      contextData.value = res.data
    }
    ready.value = true
    emit('loaded', contextData.value)
  } catch (e) {
    console.error('[ApprovalAction] 获取审批上下文失败:', e)
    ready.value = true
  } finally {
    loading.value = false
  }
}

/** 列表模式选择是否要提交审批 */
function getCreateFlow() {
  return flows.value.find(f => (f.actions || []).includes('create'))
}

/** 获取指定动作的首选流程 */
function getFlowForAction(action) {
  return flows.value.find(f => (f.actions || []).includes(action))
}

async function onSubmit(action) {
  const flow = getFlowForAction(action)
  if (!flow) {
    ElMessage.warning(`未找到支持「${action}」操作的审批流程`)
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定通过「${flow.flow_name}」提交${actionLabel(action)}审批吗？`,
      '提交审批',
      { type: 'warning' }
    )
    await submitForApproval({
      model: props.model,
      action,
      business_id: props.businessId,
      title: `${flow.flow_name} - ${actionLabel(action)}`,
    })
    // 40001 会被拦截器处理，正常返回表示已提交
    ElMessage.success('审批已提交')
    emit('submit', action, flow)
    await loadContext() // 刷新上下文
  } catch (e) {
    if (e === 'cancel' || e?.message === 'NEED_APPROVAL') return
    console.error('[ApprovalAction] 提交审批失败:', e)
  }
}

async function onApprove(taskId, approved) {
  try {
    const label = approved ? '通过' : '拒绝'
    const { value: comment } = await ElMessageBox.prompt(
      `请输入${label}意见（可选）`,
      `审批${label}`,
      { inputType: 'textarea' }
    ).catch(() => ({ value: null }))
    if (comment === null) return

    await approveTask(taskId, { approved, comment: comment || '' })
    ElMessage.success(`已${label}`)
    emit('approve', taskId, approved, comment)
    await loadContext()
  } catch (e) {
    console.error('[ApprovalAction] 审批操作失败:', e)
  }
}

async function onTransfer(taskId) {
  try {
    const { value: targetUserId } = await ElMessageBox.prompt(
      '请输入转审目标用户 ID',
      '转审',
      { inputType: 'number' }
    ).catch(() => ({ value: null }))
    if (targetUserId === null) return

    await transferTask(taskId, { transfer_to: Number(targetUserId), comment: '' })
    ElMessage.success('已转审')
    emit('transfer', taskId, Number(targetUserId))
    await loadContext()
  } catch (e) {
    console.error('[ApprovalAction] 转审失败:', e)
  }
}

async function onCancel() {
  try {
    await ElMessageBox.confirm('确定撤销此审批吗？', '撤销审批', { type: 'warning' })
    await cancelInstance(instance.value.id)
    ElMessage.success('审批已撤销')
    emit('cancel', instance.value.id)
    await loadContext()
  } catch (e) {
    if (e === 'cancel') return
    console.error('[ApprovalAction] 撤销失败:', e)
  }
}

function onViewDetail() {
  if (instance.value?.id) {
    emit('viewDetail', instance.value.id)
    ElMessage.info(`审批实例 #${instance.value.id}，请到审批中心查看`)
  }
}

function actionLabel(action) {
  const map = { create: '创建', update: '更新', delete: '删除' }
  return map[action] || action
}

// =================== Lifecycle ===================
onMounted(loadContext)
watch(() => [props.model, props.businessId, props.mode], loadContext)
</script>

<style lang="scss" scoped>
.approval-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;

  .approval-loading {
    font-size: 13px;
    color: #909399;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .approval-instance-bar {
    display: inline-flex;
    align-items: center;
    gap: 8px;

    .approval-status-tag {
      font-size: 13px;
    }
  }
}
</style>
