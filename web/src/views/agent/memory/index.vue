<template>
  <div class="memory-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>记忆管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            新增记忆
          </el-button>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="mb-4">
        <el-form-item label="智能体">
          <el-select v-model="searchForm.agent_id" placeholder="请选择智能体" clearable filterable>
            <el-option v-for="agent in agents" :key="agent.id" :label="agent.name" :value="agent.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="记忆模式">
          <el-select v-model="searchForm.memory_mode" placeholder="请选择模式" clearable>
            <el-option label="公共记忆" value="public" />
            <el-option label="私有记忆" value="private" />
          </el-select>
        </el-form-item>
        <el-form-item label="记忆类型">
          <el-select v-model="searchForm.type" placeholder="请选择类型" clearable>
            <el-option label="短期记忆" value="short_term" />
            <el-option label="长期记忆" value="long_term" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容搜索">
          <el-input v-model="searchForm.keyword" placeholder="搜索记忆内容" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
      
      <el-table :data="memories" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="agent_name" label="所属智能体" width="120">
          <template #default="{ row }">
            {{ getAgentName(row.agent_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="content" label="记忆内容" min-width="250" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.type === 'long_term' ? 'success' : 'info'">
              {{ row.type === 'long_term' ? '长期记忆' : '短期记忆' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="memory_mode" label="记忆模式" width="100">
          <template #default="{ row }">
            <el-tag :type="row.memory_mode === 'public' ? 'success' : 'warning'">
              {{ row.memory_mode === 'public' ? '公共记忆' : '私有记忆' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="customer_id" label="客户ID" width="100" />
        <el-table-column prop="user_id" label="用户ID" width="100" />
        <el-table-column prop="importance" label="重要性" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.importance * 100" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column prop="recall_count" label="召回次数" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
          <div class="action-buttons">
            <el-button type="primary" size="small" @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(row.id)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="mt-4">
        <el-pagination
          v-model:current-page="pageInfo.currentPage"
          v-model:page-size="pageInfo.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pageInfo.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="所属智能体" prop="agent_id">
          <el-select v-model="formData.agent_id" placeholder="请选择智能体" style="width: 100%" filterable>
            <el-option v-for="agent in agents" :key="agent.id" :label="agent.name" :value="agent.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="记忆内容" prop="content">
          <el-input v-model="formData.content" type="textarea" :rows="4" placeholder="请输入记忆内容" />
        </el-form-item>
        <el-form-item label="记忆类型" prop="type">
          <el-select v-model="formData.type" placeholder="请选择类型">
            <el-option label="短期记忆" value="short_term" />
            <el-option label="长期记忆" value="long_term" />
          </el-select>
        </el-form-item>
        <el-form-item label="记忆模式" prop="memory_mode">
          <el-select v-model="formData.memory_mode" placeholder="请选择模式">
            <el-option label="公共记忆" value="public" />
            <el-option label="私有记忆" value="private" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户ID" v-if="formData.memory_mode === 'private'">
          <el-input-number v-model="formData.customer_id" :min="1" placeholder="请输入客户ID" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用户ID" v-if="formData.memory_mode === 'private'">
          <el-input-number v-model="formData.user_id" :min="1" placeholder="请输入用户ID" style="width: 100%" />
        </el-form-item>
        <el-form-item label="重要性">
          <el-slider v-model="formData.importance" :min="0" :max="1" :step="0.1" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, Search, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMemories, createMemory, updateMemory, deleteMemory } from '@/api/agent'
import { getAgents } from '@/api/agent'

const route = useRoute()
const loading = ref(false)
const memories = ref([])
const agents = ref([])

const searchForm = reactive({
  agent_id: route.query.agent_id ? parseInt(route.query.agent_id) : null,
  memory_mode: '',
  type: '',
  keyword: ''
})

const pageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const dialogVisible = ref(false)
const dialogTitle = ref('新增记忆')
const formRef = ref(null)
const formData = reactive({
  id: null,
  agent_id: null,
  content: '',
  type: 'short_term',
  memory_mode: 'public',
  customer_id: null,
  user_id: null,
  importance: 0.5
})

const rules = {
  agent_id: [{ required: true, message: '请选择智能体', trigger: 'change' }],
  content: [{ required: true, message: '请输入记忆内容', trigger: 'blur' }],
  type: [{ required: true, message: '请选择记忆类型', trigger: 'change' }]
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getAgentName = (agentId) => {
  const agent = agents.value.find(a => a.id === agentId)
  return agent ? agent.name : '-'
}

const fetchAgents = async () => {
  try {
    const res = await getAgents({ limit: 1000 })
    if (res.data) {
      agents.value = res.data.items || res.data
    }
  } catch (error) {
    console.error('获取智能体列表失败', error)
  }
}

const fetchMemories = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pageInfo.currentPage - 1) * pageInfo.pageSize,
      limit: pageInfo.pageSize,
      ...searchForm
    }
    if (params.agent_id) {
      params.agent_id = params.agent_id
    }
    const res = await getMemories(params)
    if (res.data) {
      memories.value = res.data.items || res.data
      pageInfo.total = res.data.total || memories.value.length
    }
  } catch (error) {
    ElMessage.error('获取记忆列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pageInfo.currentPage = 1
  fetchMemories()
}

const resetSearch = () => {
  searchForm.agent_id = null
  searchForm.memory_mode = ''
  searchForm.type = ''
  searchForm.keyword = ''
  handleSearch()
}

const handleSizeChange = (size) => {
  pageInfo.pageSize = size
  fetchMemories()
}

const handleCurrentChange = (current) => {
  pageInfo.currentPage = current
  fetchMemories()
}

const handleAdd = () => {
  dialogTitle.value = '新增记忆'
  Object.assign(formData, {
    id: null,
    agent_id: searchForm.agent_id || null,
    content: '',
    type: 'short_term',
    memory_mode: 'public',
    customer_id: null,
    user_id: null,
    importance: 0.5
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑记忆'
  Object.assign(formData, { ...row })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (formData.id) {
          await updateMemory(formData.id, formData)
          ElMessage.success('编辑成功')
        } else {
          await createMemory(formData)
          ElMessage.success('新增成功')
        }
        dialogVisible.value = false
        fetchMemories()
      } catch (error) {
        ElMessage.error('操作失败')
        console.error(error)
      }
    }
  })
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该记忆吗？', '提示', { type: 'warning' })
    await deleteMemory(id)
    ElMessage.success('删除成功')
    fetchMemories()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

onMounted(() => {
  fetchAgents()
  fetchMemories()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mb-4 {
  margin-bottom: 16px;
}
.mt-4 {
  margin-top: 16px;
}
.action-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  align-items: center;
  gap: 4px;
}
</style>


