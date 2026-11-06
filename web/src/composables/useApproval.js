/**
 * 审批检测 Composable —— 业务页面引入，自动检测当前模型是否有审批规则。
 *
 * 两种用法：
 *
 * 1. 列表页（只需检测模型是否有审批规则）：
 *    const { hasApproval, canCreate, canUpdate, canDelete, checkModel } = useApproval()
 *    onMounted(() => checkModel('purchase_order'))
 *
 * 2. 详情页（需检测实例状态 + 当前用户审批任务）：
 *    const { context, hasFlow, instance, canSubmit, canApprove, canCancel, checkContext } = useApproval()
 *    onMounted(() => checkContext('purchase_order', 123))
 */
import { ref, computed } from 'vue'
import { checkApprovalForModel, getApprovalContext } from '@/api/approval'

export function useApproval() {
  const loading = ref(false)
  const approvalData = ref(null)   // check-for-model 结果
  const contextData = ref(null)     // /context 结果（含实例+任务）

  // ============ 列表页用 ============
  const hasApproval = computed(() => approvalData.value?.require_approval === true)
  const approvalFlows = computed(() => approvalData.value?.flows || [])

  const allActions = computed(() => {
    const actions = new Set()
    for (const flow of approvalFlows.value) {
      for (const a of flow.actions || []) actions.add(a)
    }
    return [...actions]
  })

  const canCreate = computed(() => allActions.value.includes('create'))
  const canUpdate = computed(() => allActions.value.includes('update'))
  const canDelete = computed(() => allActions.value.includes('delete'))
  const getFlowForAction = (action) => approvalFlows.value.find(f => (f.actions || []).includes(action)) || null

  async function checkModel(model) {
    if (!model) return
    loading.value = true
    try {
      const res = await checkApprovalForModel(model)
      if (res.code === 0 && res.data) approvalData.value = res.data
      else approvalData.value = null
    } catch { approvalData.value = null }
    finally { loading.value = false }
  }

  // ============ 详情页用（context = flows + instance + tasks） ============
  const context = computed(() => contextData.value)
  const hasFlow = computed(() => contextData.value?.has_flow ?? false)
  const instance = computed(() => contextData.value?.instance ?? null)
  const pendingTasks = computed(() => contextData.value?.pending_tasks ?? [])
  const canSubmit = computed(() => contextData.value?.can_submit ?? false)
  const canApprove = computed(() => contextData.value?.can_approve ?? false)
  const canCancel = computed(() => contextData.value?.can_cancel ?? false)

  async function checkContext(model, businessId) {
    if (!model) return
    loading.value = true
    try {
      const res = await getApprovalContext({ model, business_id: businessId })
      if (res.code === 0 && res.data) contextData.value = res.data
      else contextData.value = null
    } catch { contextData.value = null }
    finally { loading.value = false }
  }

  return {
    loading,
    // 列表页
    hasApproval, approvalFlows, allActions,
    canCreate, canUpdate, canDelete,
    checkModel, getFlowForAction,
    // 详情页
    context, hasFlow, instance, pendingTasks,
    canSubmit, canApprove, canCancel,
    checkContext,
  }
}
