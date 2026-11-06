<template>
  <div class="cash-plan-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>资金计划</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="期间">
          <el-date-picker v-model="searchForm.period" type="month" placeholder="选择月份" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增计划</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column prop="plan_income" label="计划收入" width="130" align="right">
          <template #default="{ row }">{{ Number(row.plan_income || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="plan_expense" label="计划支出" width="130" align="right">
          <template #default="{ row }">{{ Number(row.plan_expense || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="actual_income" label="实际收入" width="130" align="right">
          <template #default="{ row }">{{ Number(row.actual_income || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="actual_expense" label="实际支出" width="130" align="right">
          <template #default="{ row }">{{ Number(row.actual_expense || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="income_variance" label="收入差异" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: Number(row.income_variance) > 0 ? '#67c23a' : '#f56c6c' }">
              {{ Number(row.income_variance || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="expense_variance" label="支出差异" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: Number(row.expense_variance) > 0 ? '#f56c6c' : '#67c23a' }">
              {{ Number(row.expense_variance || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
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

const searchForm = reactive({
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
  searchForm.period = ''
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  ElMessage.info('新增资金计划功能开发中')
}

const handleEdit = (row) => {
  ElMessage.info('编辑资金计划功能开发中')
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/cash-plan', {
      params: { page: pagination.page, page_size: pagination.page_size, period: searchForm.period }
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
.cash-plan-index {
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


