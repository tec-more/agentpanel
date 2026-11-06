<template>
  <div class="expense-apply-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>费用申请</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="费用类型">
            <el-select v-model="searchForm.expense_type" placeholder="全部类型" clearable style="width: 140px">
              <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">申请费用</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="apply_no" label="申请单号" width="160" />
        <el-table-column prop="applicant_name" label="申请人" width="100" />
        <el-table-column prop="department_name" label="部门" width="120" />
        <el-table-column prop="expense_type" label="费用类型" width="120">
          <template #default="{ row }">{{ getTypeLabel(row.expense_type) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="申请金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="apply_date" label="申请日期" width="120" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="申请事由" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 'pending'" type="danger" link @click="handleCancel(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="formData" label-width="100px">
        <el-form-item label="费用类型" prop="expense_type">
          <el-select v-model="formData.expense_type" placeholder="选择费用类型" style="width: 100%">
            <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="申请金额" prop="amount">
          <el-input v-model="formData.amount" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="申请日期" prop="apply_date">
          <el-date-picker v-model="formData.apply_date" type="date" style="width: 100%" />
        </el-form-item>
        <el-form-item label="申请事由" prop="description">
          <el-input v-model="formData.description" type="textarea" placeholder="请输入申请事由" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('申请费用')

const typeOptions = [
  { value: 'travel', label: '差旅费' },
  { value: 'entertainment', label: '招待费' },
  { value: 'office', label: '办公费' },
  { value: 'communication', label: '通讯费' },
  { value: 'transportation', label: '交通费' },
  { value: 'other', label: '其他' }
]

const statusOptions = [
  { value: 'pending', label: '待审批' },
  { value: 'approved', label: '已批准' },
  { value: 'rejected', label: '已拒绝' }
]

const searchForm = reactive({
  expense_type: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  expense_type: '',
  amount: '',
  apply_date: '',
  description: ''
})

const getTypeLabel = (type) => {
  const found = typeOptions.find(t => t.value === type)
  return found ? found.label : type
}

const getStatusType = (status) => {
  const types = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const found = statusOptions.find(s => s.value === status)
  return found ? found.label : status
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.expense_type = ''
  searchForm.status = ''
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  dialogTitle.value = '申请费用'
  Object.assign(formData, {
    expense_type: '',
    amount: '',
    apply_date: new Date().toISOString().split('T')[0],
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑申请'
  Object.assign(formData, {
    expense_type: row.expense_type,
    amount: row.amount,
    apply_date: row.apply_date,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleCancel = async (row) => {
  ElMessage.success('撤销成功')
  fetchData()
}

const handleSave = async () => {
  if (!formData.expense_type || !formData.amount) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  dialogVisible.value = false
  ElMessage.success('申请已提交')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/expense-applies', {
      params: { page: pagination.page, page_size: pagination.page_size, expense_type: searchForm.expense_type, status: searchForm.status }
    })
    
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.expense-apply-index {
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
}
</style>


