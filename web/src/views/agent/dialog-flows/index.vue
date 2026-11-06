<template>
  <div class="dialog-flow-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>对话流</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              新建对话流
            </el-button>
          </div>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="mb-4">
        <el-form-item label="对话流名称">
          <el-input v-model="searchForm.name" placeholder="请输入对话流名称" clearable />
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
      
      <el-table :data="dialogFlows" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="对话流名称" min-width="150" />
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
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="handleEdit(row)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button 
                v-if="row.status === 'active'" 
                type="warning" 
                size="small" 
                @click="handleToggleStatus(row)"
              >
                <el-icon><SwitchButton /></el-icon>
                禁用
              </el-button>
              <el-button 
                v-if="row.status === 'inactive'" 
                type="success" 
                size="small" 
                @click="handleToggleStatus(row)"
              >
                <el-icon><SwitchButton /></el-icon>
                启用
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

    <el-dialog v-model="createDialogVisible" title="新建对话流" width="500px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="100px">
        <el-form-item label="对话流名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入对话流名称" />
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

    <el-dialog v-model="executeDialogVisible" title="执行对话流" width="600px">
      <el-form label-width="100px">
        <el-form-item label="对话流名称">
          <el-input :value="currentDialogFlow?.name" disabled />
        </el-form-item>
        <el-form-item label="输入数据">
          <el-input v-model="executeInput" type="textarea" :rows="4" placeholder="JSON格式输入数据" />
        </el-form-item>
        <el-form-item label="执行结果">
          <el-input v-model="executeResult" type="textarea" :rows="4" readonly placeholder="执行结果" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="executeDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="doExecute" :loading="executing">执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search, Refresh, Edit, Delete, VideoPlay, Upload, Download, SwitchButton } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDialogFlows, createDialogFlow, deleteDialogFlow, executeDialogFlow, updateDialogFlow } from '@/api/agent'

const router = useRouter()
const loading = ref(false)
const dialogFlows = ref([])

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
  name: [{ required: true, message: '请输入对话流名称', trigger: 'blur' }]
}

const executeDialogVisible = ref(false)
const executing = ref(false)
const currentDialogFlow = ref(null)
const executeInput = ref('{}')
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



const fetchDialogFlows = async () => {
  loading.value = true
  try {
    const res = await getDialogFlows({
      skip: (pageInfo.currentPage - 1) * pageInfo.pageSize,
      limit: pageInfo.pageSize,
      ...searchForm
    })
    if (res.data) {
      dialogFlows.value = res.data.items || res.data
      pageInfo.total = res.data.total || dialogFlows.value.length
    }
  } catch (error) {
    ElMessage.error('获取对话流列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pageInfo.currentPage = 1
  fetchDialogFlows()
}

const resetSearch = () => {
  searchForm.name = ''
  searchForm.status = ''
  handleSearch()
}

const handleSizeChange = (size) => {
  pageInfo.pageSize = size
  fetchDialogFlows()
}

const handleCurrentChange = (current) => {
  pageInfo.currentPage = current
  fetchDialogFlows()
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
        const res = await createDialogFlow({
          ...createForm,
          status: 'draft',
          flow_data: { nodes: [], edges: [] }
        })
        ElMessage.success('创建成功')
        createDialogVisible.value = false
        router.push(`/panel/agent/dialog-flows/edit/${res.data.id}`)
      } catch (error) {
        ElMessage.error('创建失败')
        console.error(error)
      }
    }
  })
}

const handleEdit = (row) => {
  router.push(`/panel/agent/dialog-flows/edit/${row.id}`)
}

const handleToggleStatus = async (row) => {
  const newStatus = row.status === 'active' ? 'inactive' : 'active'
  const action = newStatus === 'active' ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定要${action}该对话流吗？`, '提示', { type: 'warning' })
    await updateDialogFlow(row.id, { status: newStatus })
    ElMessage.success(`${action}成功`)
    fetchDialogFlows()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(`${action}失败`)
      console.error(error)
    }
  }
}

const handleExecute = (row) => {
  currentDialogFlow.value = row
  executeInput.value = '{}'
  executeResult.value = ''
  executeDialogVisible.value = true
}

const doExecute = async () => {
  executing.value = true
  try {
    let input = {}
    try {
      input = JSON.parse(executeInput.value)
    } catch (e) {
      ElMessage.error('输入数据格式错误')
      return
    }
    const res = await executeDialogFlow(currentDialogFlow.value.id, input)
    executeResult.value = JSON.stringify(res.data, null, 2)
    ElMessage.success('执行成功')
  } catch (error) {
    executeResult.value = error.message || '执行失败'
    ElMessage.error('执行失败')
  } finally {
    executing.value = false
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该对话流吗？', '提示', { type: 'warning' })
    await deleteDialogFlow(id)
    ElMessage.success('删除成功')
    fetchDialogFlows()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

onMounted(() => {
  fetchDialogFlows()
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


