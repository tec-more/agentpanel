<template>
  <div class="task-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="待处理" value="pending" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>跟进任务列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建任务</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="title" label="任务标题" min-width="160" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="lead_id" label="线索ID" width="90" align="center" />
        <el-table-column prop="opportunity_id" label="商机ID" width="90" align="center" />
        <el-table-column prop="assigned_to" label="执行人" width="90" align="center" />
        <el-table-column prop="due_date" label="截止时间" width="160" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="completed_at" label="完成时间" width="160" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending' || row.status === 'in_progress'" type="success" link @click="handleComplete(row)">完成</el-button>
            <el-button v-if="row.status === 'pending' || row.status === 'in_progress'" type="warning" link @click="handleCancel(row)">取消</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建任务" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="线索ID">
          <el-input-number v-model="form.lead_id" :min="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="商机ID">
          <el-input-number v-model="form.opportunity_id" :min="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="执行人ID" prop="assigned_to">
          <el-input-number v-model="form.assigned_to" :min="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="截止时间" prop="due_date">
          <el-date-picker v-model="form.due_date" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="完成时创建活动">
          <el-switch v-model="form.create_activity_on_complete" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Delete } from '@element-plus/icons-vue'
import { getTaskList, createTask, completeTask, cancelTask } from '@/api/crm'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const formRef = ref(null)

const searchForm = reactive({ status: null })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({
  title: '', description: '', lead_id: null, opportunity_id: null,
  assigned_to: null, due_date: '', create_activity_on_complete: false
})

const rules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  assigned_to: [{ required: true, message: '请输入执行人ID', trigger: 'blur' }],
  due_date: [{ required: true, message: '请选择截止时间', trigger: 'change' }]
}

const statusLabel = (s) => ({ pending: '待处理', in_progress: '进行中', completed: '已完成', cancelled: '已取消' }[s] || s)
const statusTagType = (s) => ({ pending: 'warning', in_progress: 'primary', completed: 'success', cancelled: 'info' }[s] || '')

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getTaskList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取任务列表失败:', e) }
  finally { loading.value = false }
}

const resetForm = () => {
  form.title = ''; form.description = ''; form.lead_id = null; form.opportunity_id = null
  form.assigned_to = null; form.due_date = ''; form.create_activity_on_complete = false
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.status = null; handleSearch() }
const handleAdd = () => { resetForm(); dialogVisible.value = true }

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (!form.lead_id && !form.opportunity_id) {
      ElMessage.warning('线索ID和商机ID至少填写一个'); return
    }
    submitting.value = true
    const data = {
      title: form.title, description: form.description || null, lead_id: form.lead_id || null,
      opportunity_id: form.opportunity_id || null, assigned_to: form.assigned_to,
      due_date: form.due_date, create_activity_on_complete: form.create_activity_on_complete
    }
    await createTask(data)
    ElMessage.success('创建成功'); dialogVisible.value = false; fetchData()
  } catch (e) { if (e !== false) ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const handleComplete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定完成任务 "${row.title}" 吗？`, '提示', { type: 'warning' })
    await completeTask(row.id, { create_activity: false })
    ElMessage.success('完成成功'); fetchData()
  } catch (e) {}
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm(`确定取消任务 "${row.title}" 吗？`, '提示', { type: 'warning' })
    await cancelTask(row.id); ElMessage.success('取消成功'); fetchData()
  } catch (e) {}
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除任务 "${row.title}" 吗？`, '提示', { type: 'warning' })
    ElMessage.info('后端暂无删除接口'); fetchData()
  } catch (e) {}
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.task-list {
  .search-card { margin-bottom: 16px; }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>
