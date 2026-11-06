<template>
  <div class="expense-analysis-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>费用分析</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="部门">
          <el-select v-model="searchForm.department_id" placeholder="全部部门" clearable filterable style="width: 150px">
            <el-option v-for="d in departmentList" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="期间">
          <el-date-picker v-model="searchForm.period" type="month" placeholder="选择月份" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="department_name" label="部门" min-width="120" />
        <el-table-column prop="expense_type" label="费用类型" width="120" />
        <el-table-column prop="amount" label="费用金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="compare_amount" label="对比金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.compare_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="variance" label="差异" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: Number(row.variance) > 0 ? '#f56c6c' : '#67c23a' }">
              {{ Number(row.variance || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="variance_rate" label="差异率" width="100" align="right">
          <template #default="{ row }">{{ Number(row.variance_rate || 0).toFixed(2) }}%</template>
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
import request from '@/utils/request'

const tableData = ref([])
const departmentList = ref([])
const loading = ref(false)

const searchForm = reactive({
  department_id: null,
  period: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.department_id = null
  searchForm.period = ''
  pagination.page = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/expense-analysis', { params: { page: pagination.page, page_size: pagination.page_size, department_id: searchForm.department_id, period: searchForm.period } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const fetchDepartments = async () => {
  try {
    const data = await request.get('/v1/departments/list', { params: { page_size: 100 } })
    departmentList.value = data.data?.items || data.data || []
  } catch (error) {
    departmentList.value = []
  }
}

onMounted(() => {
  fetchDepartments()
  fetchData()
})
</script>

<style lang="scss" scoped>
.expense-analysis-index {
  padding: 20px;
}
</style>


