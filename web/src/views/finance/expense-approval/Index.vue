<template>
  <div class="expense-approval-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>费用审批</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="申请人">
          <el-input v-model="searchForm.applicant_name" placeholder="搜索申请人" clearable />
        </el-form-item>
        <el-form-item label="费用类型">
          <el-select v-model="searchForm.expense_type" placeholder="全部类型" clearable style="width: 140px">
            <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
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
        <el-table-column prop="description" label="申请事由" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="success" link @click="handleApprove(row)">批准</el-button>
            <el-button type="danger" link @click="handleReject(row)">拒绝</el-button>
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)

const typeOptions = [
  { value: 'travel', label: '差旅费' },
  { value: 'entertainment', label: '招待费' },
  { value: 'office', label: '办公费' },
  { value: 'communication', label: '通讯费' },
  { value: 'transportation', label: '交通费' },
  { value: 'other', label: '其他' }
]

const searchForm = reactive({
  applicant_name: '',
  expense_type: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const getTypeLabel = (type) => {
  const found = typeOptions.find(t => t.value === type)
  return found ? found.label : type
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.applicant_name = ''
  searchForm.expense_type = ''
  pagination.page = 1
  fetchData()
}

const handleApprove = async (row) => {
  ElMessage.success(`已批准 ${row.apply_no}`)
  fetchData()
}

const handleReject = async (row) => {
  ElMessage.success(`已拒绝 ${row.apply_no}`)
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/expense-applies', {
      params: { page: pagination.page, page_size: pagination.page_size, status: 'pending', applicant_name: searchForm.applicant_name, expense_type: searchForm.expense_type }
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
.expense-approval-index {
  padding: 20px;
}
</style>


