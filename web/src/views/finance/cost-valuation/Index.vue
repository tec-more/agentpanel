<template>
  <div class="cost-valuation-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>成本计价</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="产品">
          <el-select v-model="searchForm.product_id" placeholder="全部产品" clearable filterable style="width: 200px">
            <el-option v-for="p in productList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="计价方法">
          <el-select v-model="searchForm.cost_method" placeholder="全部方法" clearable style="width: 140px">
            <el-option label="先进先出" value="fifo" />
            <el-option label="加权平均" value="average" />
            <el-option label="移动平均" value="moving_average" />
            <el-option label="标准成本" value="standard" />
          </el-select>
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
        <el-table-column prop="cost_method" label="计价方法" width="120">
          <template #default="{ row }">{{ getMethodLabel(row.cost_method) }}</template>
        </el-table-column>
        <el-table-column prop="unit_cost" label="单位成本" width="130" align="right">
          <template #default="{ row }">{{ Number(row.unit_cost).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="total_cost" label="总成本" width="130" align="right">
          <template #default="{ row }">{{ Number(row.total_cost).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="100" align="right" />
        <el-table-column prop="last_update" label="更新时间" width="150" />
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
  cost_method: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const getMethodLabel = (method) => {
  const methods = { fifo: '先进先出', average: '加权平均', moving_average: '移动平均', standard: '标准成本' }
  return methods[method] || method
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.product_id = null
  searchForm.cost_method = ''
  pagination.page = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/inventory-cost', {
      params: { page: pagination.page, page_size: pagination.page_size, product_id: searchForm.product_id, cost_method: searchForm.cost_method }
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
.cost-valuation-index {
  padding: 20px;
}
</style>


