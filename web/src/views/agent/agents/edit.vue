<template>
  <div class="agent-edit">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ isEdit ? '编辑智能体' : '创建智能体' }}</span>
          <div class="header-right">
            <el-button type="primary" @click="handleSubmit" :loading="saving">
              <el-icon><Check /></el-icon>
              保存
            </el-button>
            <el-button 
              type="warning" 
              @click="publishAgent" 
              v-if="isEdit && formData.status !== 'active'"
            >
              <el-icon><Check /></el-icon>
              发布
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px" style="max-width: 800px;">
        <el-form-item label="智能体名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入智能体名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="记忆容量" prop="memory_capacity">
          <el-input-number v-model="formData.memory_capacity" :min="1" :max="10000" />
          <span style="margin-left: 10px; color: #909399;">条</span>
        </el-form-item>
        <el-form-item label="默认记忆模式">
          <el-select v-model="formData.default_memory_mode" placeholder="请选择记忆模式" style="width: 100%">
            <el-option label="公共记忆（所有用户共享）" value="public" />
            <el-option label="私有记忆（每个用户独立）" value="private" />
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
import { getAgent, createAgent, updateAgent } from '@/api/agent'

const route = useRoute()
const router = useRouter()
const formRef = ref(null)
const saving = ref(false)

const agentId = route.params.id
const isEdit = computed(() => !!agentId)

const formData = reactive({
  name: '',
  description: '',
  status: 'active',
  memory_capacity: 100,
  default_memory_mode: 'public'
})

const rules = {
  name: [{ required: true, message: '请输入智能体名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const goBack = () => {
  router.push('/panel/agent/list')
}

const fetchAgent = async () => {
  if (!agentId) return
  try {
    const res = await getAgent(agentId)
    Object.assign(formData, res.data)
  } catch (error) {
    ElMessage.error('获取智能体信息失败')
    console.error(error)
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        const submitData = {
          name: formData.name,
          description: formData.description,
          status: formData.status,
          memory_capacity: formData.memory_capacity,
          default_memory_mode: formData.default_memory_mode,
          config: formData.config
        }
        
        if (isEdit.value) {
          await updateAgent(agentId, submitData)
          ElMessage.success('更新成功')
        } else {
          const res = await createAgent(submitData)
          ElMessage.success('创建成功')
          router.push(`/panel/agent/edit/${res.data.id}`)
        }
      } catch (error) {
        ElMessage.error('保存失败')
        console.error(error)
      } finally {
        saving.value = false
      }
    }
  })
}

const publishAgent = async () => {
  try {
    await updateAgent(agentId, {
      status: 'active'
    })
    formData.status = 'active'
    ElMessage.success('智能体发布成功')
  } catch (error) {
    ElMessage.error('智能体发布失败')
    console.error(error)
  }
}

onMounted(() => {
  if (isEdit.value) {
    fetchAgent()
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 16px;
}
.header-right {
  margin-left: auto;
}
</style>


