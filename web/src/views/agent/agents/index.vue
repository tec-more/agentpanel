﻿<template>
  <div class="agent-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>智能体</span>
          <div style="display: flex; gap: 8px;">
            <el-button @click="handleImport">
              <el-icon><Upload /></el-icon>
              导入
            </el-button>
            <el-button type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              新增智能体
            </el-button>
          </div>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="mb-4">
        <el-form-item label="智能体名称">
          <el-input v-model="searchForm.name" placeholder="请输入智能体名称" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
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
      
      <el-table :data="agents" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="智能体名称" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="memory_count" label="记忆数量" width="100" />
        <el-table-column prop="memory_capacity" label="记忆容量" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="320" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="handleEdit(row)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button type="warning" size="small" @click="handleMemory(row)">
                <el-icon><Memo /></el-icon>
                记忆
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
        <el-form-item label="智能体名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入智能体名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="记忆容量" prop="memory_capacity">
          <el-input-number v-model="formData.memory_capacity" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item label="配置">
          <el-input v-model="configJson" type="textarea" :rows="4" placeholder="JSON格式配置" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <input
      type="file"
      ref="fileInput"
      accept=".json"
      style="display: none"
      @change="handleFileChange"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search, Refresh, Edit, Delete, Memo, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAgents, createAgent, updateAgent, deleteAgent, importAgent } from '@/api/agent'

const router = useRouter()
const loading = ref(false)
const agents = ref([])
const fileInput = ref(null)

const searchForm = reactive({
  name: '',
  status: ''
})

const pageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const dialogVisible = ref(false)
const dialogTitle = ref('新增智能体')
const formRef = ref(null)
const formData = reactive({
  id: null,
  name: '',
  description: '',
  status: 'active',
  memory_capacity: 100,
  config: {}
})

const configJson = computed({
  get: () => JSON.stringify(formData.config, null, 2),
  set: (val) => {
    try {
      formData.config = JSON.parse(val)
    } catch (e) {
      // ignore parse error
    }
  }
})

const rules = {
  name: [{ required: true, message: '请输入智能体名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchAgents = async () => {
  loading.value = true
  try {
    const res = await getAgents({
      skip: (pageInfo.currentPage - 1) * pageInfo.pageSize,
      limit: pageInfo.pageSize,
      ...searchForm
    })
    if (res.data) {
      agents.value = res.data.items || res.data
      pageInfo.total = res.data.total || agents.value.length
    }
  } catch (error) {
    ElMessage.error('获取智能体列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pageInfo.currentPage = 1
  fetchAgents()
}

const resetSearch = () => {
  searchForm.name = ''
  searchForm.status = ''
  handleSearch()
}

const handleSizeChange = (size) => {
  pageInfo.pageSize = size
  fetchAgents()
}

const handleCurrentChange = (current) => {
  pageInfo.currentPage = current
  fetchAgents()
}

const handleAdd = () => {
  router.push('/panel/agent/create')
}

const handleEdit = (row) => {
  router.push(`/panel/agent/edit/${row.id}`)
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (formData.id) {
          await updateAgent(formData.id, formData)
          ElMessage.success('编辑成功')
        } else {
          await createAgent(formData)
          ElMessage.success('新增成功')
        }
        dialogVisible.value = false
        fetchAgents()
      } catch (error) {
        ElMessage.error('操作失败')
        console.error(error)
      }
    }
  })
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该智能体吗？', '提示', { type: 'warning' })
    await deleteAgent(id)
    ElMessage.success('删除成功')
    fetchAgents()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const handleMemory = (row) => {
  window.location.href = `/panel/agent/memory?agent_id=${row.id}`
}

const handleImport = () => {
  fileInput.value?.click()
}

const handleFileChange = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  try {
    const reader = new FileReader()
    reader.onload = async (e) => {
      try {
        const data = JSON.parse(e.target.result)
        
        await ElMessageBox.confirm(
          '确定要导入该智能体配置吗？',
          '导入确认',
          { type: 'warning' }
        )
        
        const res = await importAgent(data)
        if (res) {
          ElMessage.success('导入成功！')
          fetchAgents()
        }
      } catch (parseError) {
        ElMessage.error('JSON格式错误，请检查文件')
        console.error(parseError)
      }
    }
    reader.readAsText(file)
  } catch (error) {
    ElMessage.error('文件读取失败')
    console.error(error)
  } finally {
    // clear input value to allow select same file again
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

onMounted(() => {
  fetchAgents()
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

