<template>
  <el-dialog
    v-model="visible"
    title="需要审批"
    width="500px"
    :close-on-click-modal="false"
    :show-close="false"
    destroy-on-close
  >
    <div class="approval-prompt-content">
      <el-alert type="warning" :closable="false" class="prompt-alert">
        <template #title>
          该操作需要提交审批流程
        </template>
        {{ approvalData.flow_name || '审批流程' }}
      </el-alert>

      <div class="prompt-info">
        <p>当前操作被系统拦截，因为已配置对应的审批规则。您需要先提交审批，待审批通过后系统才会执行该操作。</p>
      </div>

      <el-form label-width="80px" class="prompt-form">
        <el-form-item label="审批标题">
          <el-input v-model="formData.title" placeholder="请输入审批标题" />
        </el-form-item>
        <el-form-item label="审批说明">
          <el-input v-model="formData.comment" type="textarea" :rows="3" placeholder="请输入审批说明（可选）" />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">提交审批</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createInstance } from '@/api/approval'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const visible = ref(false)
const submitting = ref(false)
const approvalData = ref({})
const pendingRequest = ref(null)

const formData = reactive({
  title: '',
  comment: ''
})

const handleApprovalRequired = (event) => {
  approvalData.value = event.detail || {}
  pendingRequest.value = approvalData.value

  // 自动生成标题
  const pathMap = {
    '/v1/purchase/order': '采购订单审批',
    '/v1/sales/order': '销售订单审批',
    '/v1/finance/expense': '费用报销审批'
  }
  formData.title = pathMap[approvalData.value.path] ||
    `${approvalData.value.business_type || '业务'}审批申请`
  formData.comment = ''
  visible.value = true
}

const handleCancel = () => {
  visible.value = false
  pendingRequest.value = null
  ElMessage.info('已取消操作，您可以选择稍后从审批中心提交')
}

const handleSubmit = async () => {
  if (!formData.title.trim()) {
    ElMessage.warning('请输入审批标题')
    return
  }

  submitting.value = true
  try {
    const res = await createInstance({
      flow_id: approvalData.value.flow_id,
      business_type: approvalData.value.business_type,
      title: formData.title,
      form_data: {
        title: formData.title,
        comment: formData.comment,
        path: approvalData.value.path,
        method: approvalData.value.method
      }
    })
    if (res.code === 0 || res.code === 200 || res.success) {
      ElMessage.success('审批已提交，请等待审批结果')
      visible.value = false
      pendingRequest.value = null
    }
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  window.addEventListener('approval-required', handleApprovalRequired)
})

onUnmounted(() => {
  window.removeEventListener('approval-required', handleApprovalRequired)
})
</script>

<style scoped lang="scss">
.approval-prompt-content {
  padding: 8px 0;
}

.prompt-alert {
  margin-bottom: 16px;
}

.prompt-info {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 16px;
}

.prompt-form {
  margin-top: 8px;
}
</style>
