﻿<template>
  <div class="workflow-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工作流</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              新建工作流
            </el-button>
          </div>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="mb-4">
        <el-form-item label="工作流名称">
          <el-input v-model="searchForm.name" placeholder="请输入工作流名称" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="草稿" value="draft" />
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
      
      <el-table :data="workflows" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="工作流名称" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusName(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="380" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="handleEdit(row)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button type="info" size="small" @click="handleCopy(row)">
                <el-icon><CopyDocument /></el-icon>
                复制
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

    <el-dialog v-model="createDialogVisible" title="新建工作流" width="500px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="100px">
        <el-form-item label="工作流名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建并编辑</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="executeDialogVisible" title="执行工作流" width="600px">
      <el-form :model="executeForm" label-width="100px">
        <el-form-item label="工作流名称">
          <el-input :value="currentWorkflow?.name" disabled />
        </el-form-item>
        <el-form-item label="输入数据">
          <el-input v-model="executeForm.input_data" type="textarea" :rows="4" placeholder="JSON格式输入数据" />
        </el-form-item>
        <el-form-item label="执行结果">
          <el-input v-model="executeResult" type="textarea" :rows="4" readonly placeholder="执行结果" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="executeDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="doExecute" :loading="executeLoading">执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search, Refresh, Edit, Delete, VideoPlay, CopyDocument, Upload, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getWorkflows, createWorkflow, deleteWorkflow, executeWorkflow } from '@/api/agent'

const router = useRouter()
const loading = ref(false)
const workflows = ref([])

const searchForm = reactive({
  name: '',
  status: ''
})

const pageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const createDialogVisible = ref(false)
const createFormRef = ref(null)
const createForm = reactive({
  name: '',
  description: ''
})

const createRules = {
  name: [{ required: true, message: '请输入工作流名称', trigger: 'blur' }]
}

const executeDialogVisible = ref(false)
const executeLoading = ref(false)
const currentWorkflow = ref(null)
const executeForm = reactive({ input_data: '' })
const executeResult = ref('')

const statusMap = {
  draft: '草稿',
  active: '启用',
  inactive: '禁用'
}

const getStatusName = (status) => statusMap[status] || status
const getStatusType = (status) => {
  const map = { draft: 'info', active: 'success', inactive: 'danger' }
  return map[status] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchWorkflows = async () => {
  loading.value = true
  try {
    const res = await getWorkflows({
      skip: (pageInfo.currentPage - 1) * pageInfo.pageSize,
      limit: pageInfo.pageSize,
      ...searchForm
    })
    if (res.data) {
      workflows.value = res.data.items || res.data
      pageInfo.total = res.data.total || workflows.value.length
    }
  } catch (error) {
    ElMessage.error('获取工作流列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pageInfo.currentPage = 1
  fetchWorkflows()
}

const resetSearch = () => {
  searchForm.name = ''
  searchForm.status = ''
  handleSearch()
}

const handleSizeChange = (size) => {
  pageInfo.pageSize = size
  fetchWorkflows()
}

const handleCurrentChange = (current) => {
  pageInfo.currentPage = current
  fetchWorkflows()
}

const handleCreate = () => {
  Object.assign(createForm, { name: '', description: '' })
  createDialogVisible.value = true
}

const submitCreate = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const res = await createWorkflow({
          ...createForm,
          status: 'draft',
          definition: { nodes: [], edges: [] }
        })
        ElMessage.success('创建成功')
        createDialogVisible.value = false
        router.push(`/panel/agent/workflows/edit/${res.data.id}`)
      } catch (error) {
        ElMessage.error('创建失败')
        console.error(error)
      }
    }
  })
}

const handleEdit = (row) => {
  router.push(`/panel/agent/workflows/edit/${row.id}`)
}

const handleExecute = (row) => {
  currentWorkflow.value = row
  executeForm.input_data = ''
  executeResult.value = ''
  executeDialogVisible.value = true
}

const doExecute = async () => {
  executeLoading.value = true
  try {
    let input = {}
    try {
      input = JSON.parse(executeForm.input_data)
    } catch (e) {
      ElMessage.error('输入数据格式错误')
      return
    }
    const res = await executeWorkflow(currentWorkflow.value.id, input)
    executeResult.value = JSON.stringify(res.data, null, 2)
    ElMessage.success('执行成功')
  } catch (error) {
    executeResult.value = error.message || '执行失败'
    ElMessage.error('执行失败')
  } finally {
    executeLoading.value = false
  }
}

const handleCopy = async (row) => {
  try {
    await createWorkflow({
      name: `${row.name} (副本)`,
      description: row.description,
      status: 'draft',
      definition: row.definition
    })
    ElMessage.success('复制成功')
    fetchWorkflows()
  } catch (error) {
    ElMessage.error('复制失败')
    console.error(error)
  }
}
const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该工作流吗？', '提示', { type: 'warning' })
    await deleteWorkflow(id)
    ElMessage.success('删除成功')
    fetchWorkflows()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

onMounted(() => {
  fetchWorkflows()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 10px;
}
.mb-4 {
  margin-bottom: 16px;
}
.mt-4 {
  margin-top: 16px;
}
.action-buttons {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 4px;
}
</style>


