<template>
  <el-dialog
    :model-value="modelValue"
    title="新建授权"
    width="560px"
    @update:model-value="(val) => emit('update:modelValue', val)"
    @close="resetForm"
  >
    <el-form :model="form" label-width="90px">
      <el-form-item label="资源类型" required>
        <el-select v-model="form.resource_type" placeholder="请选择资源类型" style="width: 100%" @change="handleResourceTypeChange">
          <el-option
            v-for="(label, value) in RESOURCE_TYPE_MAP"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="选择资源" required>
        <ResourceSelect v-model="form.resource_id" :resource-type="form.resource_type" />
      </el-form-item>
      <el-form-item label="主体类型" required>
        <el-select v-model="form.owner_type" placeholder="请选择主体类型" style="width: 100%" @change="handleOwnerTypeChange">
          <el-option
            v-for="(label, value) in OWNER_TYPE_MAP"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="选择主体" required>
        <SubjectSelect v-model="form.subjects" :subject-type="form.owner_type" />
      </el-form-item>
      <el-form-item label="过期时间">
        <el-date-picker
          v-model="form.expires_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          placeholder="不填则长期有效"
          style="width: 100%"
        />
        <el-text size="small" type="info">不设置则长期有效；过期后主体自动失去权限</el-text>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, h } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createGrantBatch } from '@/api/grant'
import ResourceSelect from './components/ResourceSelect.vue'
import SubjectSelect from './components/SubjectSelect.vue'

// FR-03：新建授权弹窗
defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})
const emit = defineEmits(['update:modelValue', 'success'])

const RESOURCE_TYPE_MAP = {
  model: '模型',
  kb: '知识库',
  tool: '工具',
  agent: '智能体',
  node_type: '节点类型'
}
const OWNER_TYPE_MAP = {
  cus: '客户',
  usr: '后台用户',
  org: '客户组织'
}

const submitLoading = ref(false)

const form = reactive({
  resource_type: '',
  resource_id: '',
  owner_type: '',
  subjects: [],
  expires_at: null
})

// 切换资源类型后清空已选资源
const handleResourceTypeChange = () => {
  form.resource_id = ''
}

// 切换主体类型后清空已选主体
const handleOwnerTypeChange = () => {
  form.subjects = []
}

// 提交批量授权
const handleSubmit = async () => {
  if (!form.resource_type) {
    ElMessage.warning('请选择资源类型')
    return
  }
  if (!form.resource_id) {
    ElMessage.warning('请选择资源')
    return
  }
  if (!form.owner_type) {
    ElMessage.warning('请选择主体类型')
    return
  }
  if (!form.subjects.length) {
    ElMessage.warning('请选择主体')
    return
  }
  // OB-2：过期时间提交前阻断（FR-03 规则1，字段级校验）
  if (form.expires_at && new Date(form.expires_at) <= new Date()) {
    ElMessage.warning('过期时间必须晚于当前时间')
    return
  }

  submitLoading.value = true
  try {
    const payload = {
      resource_type: form.resource_type,
      resource_id: form.resource_id,
      subjects: form.subjects.map((id) => ({
        owner_type: form.owner_type,
        owner_id: id
      })),
      expires_at: form.expires_at || undefined
    }
    const res = await createGrantBatch(payload)
    const d = res?.data ?? res
    const succeeded = d.succeeded || []
    const failed = d.failed || []

    // §6.4：逐条独立明细反馈
    if (failed.length === 0) {
      // FR-03：区分新增/刷新（测试节点1 Q1 裁定）
      const createdCount = succeeded.filter((s) => s.created).length
      const refreshedCount = succeeded.length - createdCount
      const parts = []
      if (createdCount) parts.push(`新增 ${createdCount}`)
      if (refreshedCount) parts.push(`刷新 ${refreshedCount}`)
      ElMessage.success(`授权成功：${parts.join('，')}个主体`)
      emit('success')
      emit('update:modelValue', false)
      resetForm()
    } else {
      // 逐行展示失败主体与原因
      const message = h(
        'div',
        null,
        failed.map((f) => h('p', { key: `${f.owner_type}-${f.owner_id}` }, `主体 ${f.owner_type}:${f.owner_id}：${f.reason}`))
      )
      ElMessageBox.alert(message, `部分授权失败（成功 ${succeeded.length} / 失败 ${failed.length}）`, {
        confirmButtonText: '知道了',
        type: 'warning'
      })
      if (succeeded.length > 0) {
        emit('success')
      }
    }
  } catch (e) {
    // 接口级报错已由拦截器提示
  } finally {
    submitLoading.value = false
  }
}

const resetForm = () => {
  form.resource_type = ''
  form.resource_id = ''
  form.owner_type = ''
  form.subjects = []
  form.expires_at = null
}
</script>

<style scoped>
.el-select {
  width: 100%;
}
</style>
