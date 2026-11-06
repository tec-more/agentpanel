<template>
  <div class="tax-summary-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>税额汇总</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
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
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column prop="tax_type" label="税种" width="100">
          <template #default="{ row }">{{ getTypeLabel(row.tax_type) }}</template>
        </el-table-column>
        <el-table-column prop="taxable_amount" label="计税金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.taxable_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="tax_amount" label="应缴税额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.tax_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="paid_amount" label="已缴税额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.paid_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="outstanding_amount" label="欠缴税额" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: Number(row.outstanding_amount) > 0 ? '#f56c6c' : '#67c23a' }">
              {{ Number(row.outstanding_amount || 0).toFixed(2) }}
            </span>
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

const getTypeLabel = (type) => {
  const types = { vat: '增值税', income_tax: '所得税', additional: '附加税', stamp: '印花税' }
  return types[type] || type
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.period = ''
  pagination.page = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/tax-summary', {
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
.tax-summary-index {
  padding: 20px;
}
</style>


