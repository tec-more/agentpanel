<template>
  <div class="lead-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="姓名/公司" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="新线索" value="new" />
            <el-option label="跟进中" value="following" />
            <el-option label="已转化" value="converted" />
            <el-option label="无效" value="invalid" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="searchForm.source" placeholder="请选择" clearable style="width: 120px">
            <el-option v-for="s in sourceOptions" :key="s.code" :label="s.name" :value="s.code" />
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
          <span>线索列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建线索</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="name" label="姓名" min-width="120" />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="email" label="邮箱" min-width="160" />
        <el-table-column prop="company" label="公司" min-width="140" />
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_follow_up_time" label="最后跟进" width="160" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link :icon="Check" @click="handleConvert(row)" :disabled="row.status === 'converted'">转化</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑线索' : '新建线索'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="公司">
          <el-input v-model="form.company" placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="form.source" placeholder="请选择" clearable style="width: 100%">
            <el-option v-for="s in sourceOptions" :key="s.code" :label="s.name" :value="s.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
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
import { Search, Refresh, Plus, Edit, Delete, Check } from '@element-plus/icons-vue'
import { getLeadList, createLead, updateLead, deleteLead, convertLead, getLeadSources } from '@/api/crm'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const sourceOptions = ref([])

const searchForm = reactive({
  keyword: '',
  status: null,
  source: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  id: null,
  name: '',
  phone: '',
  email: '',
  company: '',
  source: null,
  description: ''
})

const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [{ validator: (r, v, cb) => { if (!v && !form.email) { cb(new Error('手机号和邮箱至少填写一个')) } else { cb() } }, trigger: 'blur' }],
  email: [{ validator: (r, v, cb) => { if (!v && !form.phone) { cb(new Error('手机号和邮箱至少填写一个')) } else { cb() } }, trigger: 'blur' }]
}

const statusLabel = (s) => ({ new: '新线索', following: '跟进中', converted: '已转化', invalid: '无效' }[s] || s)
const statusTagType = (s) => ({ new: 'info', following: 'warning', converted: 'success', invalid: 'danger' }[s] || '')

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getLeadList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    console.error('获取线索列表失败:', e)
  } finally {
    loading.value = false
  }
}

const fetchSources = async () => {
  try {
    const res = await getLeadSources()
    sourceOptions.value = res.data || []
  } catch (e) {
    console.error('获取线索来源失败:', e)
  }
}

const resetForm = () => {
  form.id = null
  form.name = ''
  form.phone = ''
  form.email = ''
  form.company = ''
  form.source = null
  form.description = ''
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.keyword = ''; searchForm.status = null; searchForm.source = null; handleSearch() }

const handleAdd = () => {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    const data = { name: form.name, phone: form.phone || null, email: form.email || null, company: form.company || null, source: form.source || null, description: form.description || null }
    if (isEdit.value) {
      await updateLead(form.id, data)
      ElMessage.success('更新成功')
    } else {
      await createLead(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    if (e !== false) ElMessage.error(e.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

const handleConvert = async (row) => {
  try {
    await ElMessageBox.confirm(`确定将线索 "${row.name}" 转化为客户吗？`, '提示', { type: 'warning' })
    await convertLead(row.id)
    ElMessage.success('转化成功')
    fetchData()
  } catch (e) {}
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除线索 "${row.name}" 吗？`, '提示', { type: 'warning' })
    await deleteLead(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {}
}

onMounted(() => { fetchSources(); fetchData() })
</script>

<style lang="scss" scoped>
.lead-list {
  .search-card { margin-bottom: 16px; }
  .table-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; }
  }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>
