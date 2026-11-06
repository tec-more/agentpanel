<template>
  <div v-if="visible" class="global-approval-bar">
    <div class="approval-inner">
      <!-- 左侧：流程信息 / 状态 -->
      <div class="approval-left">
        <el-icon class="approval-icon"><Stamp /></el-icon>
        <span class="approval-label">{{ flowLabel }}</span>
        <el-tag v-if="instance" :type="statusTagType" size="small" class="status-tag">
          {{ statusLabel }}
        </el-tag>
        <span v-if="mode === 'list'" class="approval-hint">此页面操作已配置审批流程</span>
      </div>

      <!-- 右侧：操作按钮 -->
      <div class="approval-right">
        <!-- 列表模式：仅提交创建审批 -->
        <template v-if="mode === 'list'">
          <el-button v-if="canCreate" type="warning" size="small" @click="onSubmit('create')">
            <el-icon><DocumentAdd /></el-icon> 提交审批
          </el-button>
        </template>

        <!-- 详情模式 -->
        <template v-else>
          <!-- 无实例：提交审批下拉 -->
          <el-dropdown
            v-if="!instance && canSubmit"
            trigger="click"
            @command="onSubmit"
            size="small"
          >
            <el-button type="warning" size="small">
              <el-icon><DocumentAdd /></el-icon> 提交审批
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="canCreate" command="create">
                  <el-icon><Plus /></el-icon> 提交创建审批
                </el-dropdown-item>
                <el-dropdown-item v-if="canUpdate" command="update">
                  <el-icon><Edit /></el-icon> 提交更新审批
                </el-dropdown-item>
                <el-dropdown-item v-if="canDelete" command="delete" divided>
                  <el-icon><Delete /></el-icon> 提交删除审批
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <!-- 有实例：审批人操作 -->
          <template v-if="instance && canApprove">
            <el-button
              v-for="task in pendingTasks"
              :key="'approve-' + task.id"
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

          <!-- 申请人撤销 -->
          <el-button v-if="instance && canCancel" type="info" size="small" @click="onCancel">
            <el-icon><CircleClose /></el-icon> 撤销
          </el-button>

          <!-- 查看审批详情 -->
          <el-button v-if="instance" size="small" @click="onViewDetail">
            <el-icon><View /></el-icon> 审批详情
          </el-button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Stamp, DocumentAdd, ArrowDown, Plus, Edit, Delete,
  Check, Close, Switch, CircleClose, View
} from '@element-plus/icons-vue'
import {
  getApprovalContextByRoute, submitForApproval,
  approveTask, cancelInstance, transferTask
} from '@/api/approval'
import { useSystemStore } from '@/stores/system'

const route = useRoute()
const router = useRouter()
const system = useSystemStore()

const loading = ref(false)
const contextData = ref(null)

const hasFlow = computed(() => contextData.value?.has_flow ?? false)
const model = computed(() => contextData.value?.model ?? null)
const mode = computed(() => contextData.value?.mode ?? 'list')
const flows = computed(() => contextData.value?.flows ?? [])
const instance = computed(() => contextData.value?.instance ?? null)
const pendingTasks = computed(() => contextData.value?.pending_tasks ?? [])

const canSubmit = computed(() => contextData.value?.can_submit ?? false)
const canApprove = computed(() => contextData.value?.can_approve ?? false)
const canCancel = computed(() => contextData.value?.can_cancel ?? false)
const canCreate = computed(() => contextData.value?.can_create ?? false)
const canUpdate = computed(() => contextData.value?.can_update ?? false)
const canDelete = computed(() => contextData.value?.can_delete ?? false)

// 加载中或无流程时不显示条；approval 插件未启用时整体禁用
const visible = computed(() => system.isPluginEnabled('approval') && !loading.value && hasFlow.value)

const flowLabel = computed(() => {
  if (!hasFlow.value) return ''
  if (instance.value) {
    return instance.value.title || `${model.value || ''} 审批`
  }
  const names = flows.value.map(f => f.flow_name).filter(Boolean)
  return names[0] || '审批流程'
})

const statusLabel = computed(() => {
  const map = { pending: '审批中', approved: '已通过', rejected: '已拒绝', cancelled: '已撤销' }
  return map[instance.value?.status] || instance.value?.status || '未知'
})

const statusTagType = computed(() => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger', cancelled: 'info' }
  return map[instance.value?.status] || 'info'
})

function getBusinessId() {
  // 从路由参数提取业务对象 ID（支持 :id 参数）
  const id = route.params?.id
  if (id == null || id === '') return null
  const num = Number(id)
  return Number.isNaN(num) ? null : num
}

async function loadContext() {
  // approval 插件未启用时不发请求，避免 404
  if (!system.isPluginEnabled('approval')) {
    contextData.value = null
    return
  }
  const currentRoute = route.path
  if (!currentRoute) return
  loading.value = true
  try {
    const params = { route: currentRoute }
    const bid = getBusinessId()
    if (bid != null) params.business_id = bid
    const res = await getApprovalContextByRoute(params)
    if (res.code === 0 && res.data) {
      contextData.value = res.data
    } else {
      contextData.value = null
    }
  } catch (e) {
    console.error('[GlobalApproval] 获取审批上下文失败:', e)
    contextData.value = null
  } finally {
    loading.value = false
  }
}

function getFlowForAction(action) {
  return flows.value.find(f => (f.actions || []).includes(action))
}

function actionLabel(action) {
  const map = { create: '创建', update: '更新', delete: '删除' }
  return map[action] || action
}

async function onSubmit(action) {
  const flow = getFlowForAction(action)
  if (!flow) {
    ElMessage.warning(`未找到支持「${actionLabel(action)}」操作的审批流程`)
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定通过「${flow.flow_name}」提交${actionLabel(action)}审批吗？`,
      '提交审批',
      { type: 'warning' }
    )
    await submitForApproval({
      model: model.value,
      action,
      business_id: getBusinessId(),
      title: `${flow.flow_name} - ${actionLabel(action)}`,
    })
    ElMessage.success('审批已提交')
    await loadContext()
  } catch (e) {
    if (e === 'cancel') return
    // 40001 由响应拦截器统一处理，这里吞掉避免重复报错
    if (e?.message === 'NEED_APPROVAL') return
    console.error('[GlobalApproval] 提交审批失败:', e)
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
    await loadContext()
  } catch (e) {
    console.error('[GlobalApproval] 审批操作失败:', e)
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
    await loadContext()
  } catch (e) {
    console.error('[GlobalApproval] 转审失败:', e)
  }
}

async function onCancel() {
  try {
    await ElMessageBox.confirm('确定撤销此审批吗？', '撤销审批', { type: 'warning' })
    await cancelInstance(instance.value.id)
    ElMessage.success('审批已撤销')
    await loadContext()
  } catch (e) {
    if (e === 'cancel') return
    console.error('[GlobalApproval] 撤销失败:', e)
  }
}

function onViewDetail() {
  router.push('/panel/approval/center')
}

onMounted(loadContext)
watch(() => route.path, loadContext)
watch(() => route.params?.id, loadContext)
</script>

<style lang="scss" scoped>
.global-approval-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  margin-bottom: 12px;
  background-color: var(--el-color-warning-light-9);
  border: 1px solid var(--el-color-warning-light-7);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.approval-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  gap: 12px;
  flex-wrap: wrap;
}

.approval-left {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #5a4a1a;
  flex-wrap: wrap;

  .approval-icon {
    color: var(--el-color-warning);
    font-size: 16px;
  }

  .approval-label {
    font-weight: 600;
  }

  .status-tag {
    margin-left: 4px;
  }

  .approval-hint {
    color: #909399;
    font-size: 12px;
  }
}

.approval-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
