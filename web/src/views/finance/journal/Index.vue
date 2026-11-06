<template>
  <div class="journal-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>凭证管理</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="凭证类型">
            <el-select v-model="searchForm.journal_type" placeholder="全部类型" clearable style="width: 140px">
              <el-option v-for="type in journalTypes" :key="type.value" :label="type.label" :value="type.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
              <el-option v-for="status in journalStatuses" :key="status.value" :label="status.label" :value="status.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期范围">
            <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增凭证</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="journal_number" label="凭证号" />
        <el-table-column prop="journal_type" label="凭证类型">
          <template #default="{ row }">
            {{ getJournalTypeName(row.journal_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="journal_date" label="凭证日期" />
        <el-table-column prop="period" label="会计期间" />
        <el-table-column prop="description" label="摘要" />
        <el-table-column prop="total_debit" label="借方金额" />
        <el-table-column prop="total_credit" label="贷方金额" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="制单" />
        <el-table-column prop="confirmed_by" label="审核" />
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
              <el-button v-if="row.status === 'draft'" type="success" link @click="handleConfirm(row)">审核</el-button>
              <el-button v-if="row.status === 'confirmed'" type="primary" link @click="handlePost(row)">过账</el-button>
              <el-button v-if="row.status !== 'cancelled'" type="danger" link @click="handleCancel(row)">取消</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px">
      <el-form :model="formData" label-width="80px">
        <el-form-item label="凭证类型">
          <el-select v-model="formData.journal_type">
            <el-option v-for="type in journalTypes" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="凭证日期">
          <el-date-picker v-model="formData.journal_date" type="date" style="width: 100%" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="formData.description" placeholder="请输入摘要" />
        </el-form-item>
        <el-form-item label="凭证行">
          <div v-for="(line, index) in formData.lines" :key="index" class="journal-line">
            <el-select v-model="line.account_id" placeholder="选择科目" style="width: 180px">
              <el-option v-for="acc in accountList" :key="acc.id" :label="acc.code + ' ' + acc.name" :value="acc.id" />
            </el-select>
            <el-input v-model="line.debit" type="number" placeholder="借方" style="width: 120px" />
            <el-input v-model="line.credit" type="number" placeholder="贷方" style="width: 120px" />
            <el-input v-model="line.description" placeholder="明细摘要" style="width: 150px" />
            <el-button v-if="formData.lines.length > 1" type="danger" link @click="removeLine(index)">删除</el-button>
          </div>
          <el-button type="default" link @click="addLine">添加行</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const tableData = ref([])
const journalTypes = ref([])
const journalStatuses = ref([])
const accountList = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增凭证')
const isEdit = ref(false)
const currentId = ref(null)
const loading = ref(false)
const dateRange = ref([])

const searchForm = reactive({
  journal_type: '',
  status: '',
  journal_date_start: '',
  journal_date_end: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  journal_type: 'general',
  journal_date: new Date().toISOString().split('T')[0],
  description: '',
  lines: [{ account_id: null, debit: '', credit: '', description: '' }]
})

const getJournalTypeName = (type) => {
  const found = journalTypes.value.find(t => t.value === type)
  return found ? found.label : type
}

const getStatusName = (status) => {
  const found = journalStatuses.value.find(s => s.value === status)
  return found ? found.label : status
}

const getStatusType = (status) => {
  const types = {
    'draft': 'info',
    'confirmed': 'primary',
    'posted': 'success',
    'cancelled': 'danger'
  }
  return types[status] || 'info'
}

const handleSearch = async () => {
  if (dateRange.value && dateRange.value.length === 2) {
    searchForm.journal_date_start = dateRange.value[0].toISOString().split('T')[0]
    searchForm.journal_date_end = dateRange.value[1].toISOString().split('T')[0]
  }
  pagination.page = 1
  await fetchData()
}

const handleReset = () => {
  searchForm.journal_type = ''
  searchForm.status = ''
  searchForm.journal_date_start = ''
  searchForm.journal_date_end = ''
  dateRange.value = []
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增凭证'
  Object.assign(formData, {
    journal_type: 'general',
    journal_date: new Date().toISOString().split('T')[0],
    description: '',
    lines: [{ account_id: null, debit: '', credit: '', description: '' }]
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑凭证'
  Object.assign(formData, {
    journal_type: row.journal_type,
    journal_date: row.journal_date,
    description: row.description,
    lines: row.lines || [{ account_id: null, debit: '', credit: '', description: '' }]
  })
  dialogVisible.value = true
}

const addLine = () => {
  formData.lines.push({ account_id: null, debit: '', credit: '', description: '' })
}

const removeLine = (index) => {
  formData.lines.splice(index, 1)
}

const handleConfirm = async (row) => {
  await ElMessageBox.confirm('确定审核该凭证吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
  const data = await request.post(`/v1/finance/journals/${row.id}/confirm`)
  if (data.code === 0) {
    ElMessage.success(data.msg)
    fetchData()
  } else {
    ElMessage.error(data.msg || '审核失败')
  }
}

const handlePost = async (row) => {
  await ElMessageBox.confirm('确定过账该凭证吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
  const data = await request.post(`/v1/finance/journals/${row.id}/post`)
  if (data.code === 0) {
    ElMessage.success(data.msg)
    fetchData()
  } else {
    ElMessage.error(data.msg || '过账失败')
  }
}

const handleCancel = async (row) => {
  await ElMessageBox.confirm('确定取消该凭证吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
  const data = await request.post(`/v1/finance/journals/${row.id}/cancel`)
  if (data.code === 0) {
    ElMessage.success(data.msg)
    fetchData()
  } else {
    ElMessage.error(data.msg || '取消失败')
  }
}

const handleSave = async () => {
  if (!formData.journal_type || !formData.journal_date) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  if (isEdit.value) {
    const data = await request.put(`/v1/finance/journals/${currentId.value}`, formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  } else {
    const data = await request.post('/v1/finance/journals/', formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  }
}

const loadJournalTypes = async () => {
  const data = await request.get('/v1/finance/journals/types')
  if (data.code === 0) {
    journalTypes.value = data.data
  }
}

const loadJournalStatuses = async () => {
  const data = await request.get('/v1/finance/journals/statuses')
  if (data.code === 0) {
    journalStatuses.value = data.data
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/journals/', { params: { page: pagination.page, page_size: pagination.page_size, journal_type: searchForm.journal_type, status: searchForm.status, journal_date_start: searchForm.journal_date_start, journal_date_end: searchForm.journal_date_end } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
    pagination.page = data.data?.page || 1
    pagination.page_size = data.data?.page_size || 20
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  }
  loading.value = false
}

const fetchAccountList = async () => {
  const data = await request.get('/v1/finance/accounts/', { params: { page_size: 100 } })
  accountList.value = data.data?.data || []
}

onMounted(() => {
  loadJournalTypes()
  loadJournalStatuses()
  fetchData()
  fetchAccountList()
})
</script>

<style lang="scss" scoped>
.journal-index {
  padding: 20px;
  
  .search-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 10px;
    
    .search-form {
      flex: 1;
      margin: 0;
    }
    
    .search-actions {
      flex-shrink: 0;
    }
  }
  
  .journal-line {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
    align-items: center;
  }
}
</style>


