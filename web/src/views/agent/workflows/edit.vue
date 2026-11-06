<template>
  <div class="workflow-edit">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ isEdit ? '编辑工作流' : '创建工作流' }}</span>
          <div class="header-right">
            <el-button type="primary" @click="handleSubmit" :loading="saving">
              <el-icon><Check /></el-icon>
              保存
            </el-button>
            <el-button 
              type="warning" 
              @click="publishWorkflow" 
              v-if="isEdit && formData.status !== 'active'"
            >
              <el-icon><Check /></el-icon>
              发布
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px" style="max-width: 800px;">
        <el-form-item label="工作流名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="草稿" value="draft" />
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getWorkflow, createWorkflow, updateWorkflow } from '@/api/agent'

const route = useRoute()
const router = useRouter()
const formRef = ref(null)
const saving = ref(false)

const workflowId = route.params.id
const isEdit = computed(() => !!workflowId)

const formData = reactive({
  name: '',
  description: '',
  status: 'draft'
})

const rules = {
  name: [{ required: true, message: '请输入工作流名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const goBack = () => {
  router.push('/panel/agent/workflows')
}

const fetchWorkflow = async () => {
  if (!workflowId) return
  try {
    const res = await getWorkflow(workflowId)
    Object.assign(formData, res.data)
  } catch (error) {
    ElMessage.error('获取工作流信息失败')
    console.error(error)
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        if (isEdit.value) {
          await updateWorkflow(workflowId, formData)
          ElMessage.success('更新成功')
        } else {
          const res = await createWorkflow({ ...formData, definition: { nodes: [], edges: [] } })
          ElMessage.success('创建成功')
          router.push(`/panel/agent/workflows/edit/${res.data.id}`)
        }
      } catch (error) {
        ElMessage.error('操作失败')
        console.error(error)
      } finally {
        saving.value = false
      }
    }
  })
}

const publishWorkflow = async () => {
  saving.value = true
  try {
    await updateWorkflow(workflowId, { status: 'active' })
    formData.status = 'active'
    ElMessage.success('发布成功')
  } catch (error) {
    ElMessage.error('发布失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchWorkflow()
})
</script>

<style scoped>
.workflow-edit {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-right {
  display: flex;
  gap: 10px;
}
</style>

