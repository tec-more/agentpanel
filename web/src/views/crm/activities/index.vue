<template>
  <div class="activity-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="类型">
          <el-select v-model="searchForm.type" placeholder="请选择" clearable style="width: 120px">
            <el-option label="电话" value="call" />
            <el-option label="会议" value="meeting" />
            <el-option label="邮件" value="email" />
            <el-option label="拜访" value="visit" />
            <el-option label="其他" value="other" />
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
          <span>活动列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建活动</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTagType(row.type)">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="subject" label="主题" min-width="160" />
        <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
        <el-table-column prop="activity_time" label="活动时间" width="160" />
        <el-table-column prop="lead_id" label="线索ID" width="90" align="center" />
        <el-table-column prop="opportunity_id" label="商机ID" width="90" align="center" />
        <el-table-column prop="contact_id" label="联系人ID" width="90" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
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

    <el-dialog v-model="dialogVisible" title="新建活动" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="类型" prop="type">
          <el-select v-model="form.type" placeholder="请选择" style="width: 100%">
            <el-option label="电话" value="call" />
            <el-option label="会议" value="meeting" />
            <el-option label="邮件" value="email" />
            <el-option label="拜访" value="visit" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="主题" prop="subject">
          <el-input v-model="form.subject" placeholder="请输入主题" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="请输入内容" />
        </el-form-item>
        <el-form-item label="活动时间" prop="activity_time">
          <el-date-picker v-model="form.activity_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="线索ID">
          <el-input-number v-model="form.lead_id" :min="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="商机ID">
          <el-input-number v-model="form.opportunity_id" :min="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="联系人ID">
          <el-input-number v-model="form.contact_id" :min="1" controls-position="right" style="width: 100%" />
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
import { getActivityList, createActivity, deleteActivity } from '@/api/crm'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const formRef = ref(null)

const searchForm = reactive({ type: null })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({
  type: '', subject: '', content: '', activity_time: '',
  lead_id: null, opportunity_id: null, contact_id: null
})

const rules = {
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  subject: [{ required: true, message: '请输入主题', trigger: 'blur' }],
  activity_time: [{ required: true, message: '请选择活动时间', trigger: 'change' }]
}

const typeLabel = (t) => ({ call: '电话', meeting: '会议', email: '邮件', visit: '拜访', other: '其他' }[t] || t)
const typeTagType = (t) => ({ call: 'primary', meeting: 'success', email: 'info', visit: 'warning', other: '' }[t] || '')

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getActivityList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取活动列表失败:', e) }
  finally { loading.value = false }
}

const resetForm = () => {
  form.type = ''; form.subject = ''; form.content = ''; form.activity_time = ''
  form.lead_id = null; form.opportunity_id = null; form.contact_id = null
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.type = null; handleSearch() }
const handleAdd = () => { resetForm(); dialogVisible.value = true }

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (!form.lead_id && !form.opportunity_id) {
      ElMessage.warning('线索ID和商机ID至少填写一个'); return
    }
    submitting.value = true
    const data = {
      type: form.type, subject: form.subject, content: form.content || null,
      activity_time: form.activity_time, lead_id: form.lead_id || null,
      opportunity_id: form.opportunity_id || null, contact_id: form.contact_id || null
    }
    await createActivity(data)
    ElMessage.success('创建成功'); dialogVisible.value = false; fetchData()
  } catch (e) { if (e !== false) ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除活动 "${row.subject}" 吗？`, '提示', { type: 'warning' })
    await deleteActivity(row.id); ElMessage.success('删除成功'); fetchData()
  } catch (e) {}
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.activity-list {
  .search-card { margin-bottom: 16px; }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>
