<template>
  <div class="cost-variance-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>成本差异分析</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="产品">
          <el-select v-model="searchForm.product_id" placeholder="全部产品" clearable filterable style="width: 200px">
            <el-option v-for="p in productList" :key="p.id" :label="p.name" :value="p.id" />
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
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column prop="standard_cost" label="标准成本" width="130" align="right">
          <template #default="{ row }">{{ Number(row.standard_cost || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="actual_cost" label="实际成本" width="130" align="right">
          <template #default="{ row }">{{ Number(row.actual_cost || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="variance_amount" label="差异金额" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: Number(row.variance_amount) > 0 ? '#f56c6c' : '#67c23a' }">
              {{ Number(row.variance_amount || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="variance_rate" label="差异率" width="100" align="right">
          <template #default="{ row }">{{ Number(row.variance_rate || 0).toFixed(2) }}%</template>
        </el-table-column>
        <el-table-column prop="variance_type" label="差异类型" width="100">
          <template #default="{ row }">{{ row.variance_type === 'positive' ? '有利差异' : '不利差异' }}</template>
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
const productList = ref([])
const loading = ref(false)

const searchForm = reactive({
  product_id: null,
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
  searchForm.product_id = null
  searchForm.period = ''
  pagination.page = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/cost-variance', {
      params: { page: pagination.page, page_size: pagination.page_size, product_id: searchForm.product_id, period: searchForm.period }
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

const fetchProducts = async () => {
  try {
    const data = await request.get('/v1/product/list', { params: { page_size: 100 } })
    productList.value = data.data?.items || data.data || []
  } catch (error) {
    productList.value = []
  }
}

onMounted(() => {
  fetchProducts()
  fetchData()
})
</script>

<style lang="scss" scoped>
.cost-variance-index {
  padding: 20px;
}
</style>


