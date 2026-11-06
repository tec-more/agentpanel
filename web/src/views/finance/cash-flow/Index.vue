<template>
  <div class="cash-flow-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>资金流水</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="账户">
          <el-select v-model="searchForm.account_id" placeholder="全部账户" clearable filterable style="width: 200px">
            <el-option v-for="a in accountList" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="searchForm.type" placeholder="收入/支出" clearable style="width: 120px">
            <el-option label="收入" value="income" />
            <el-option label="支出" value="expense" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="searchForm.date_range" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 240px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="account_name" label="账户名称" min-width="150" />
        <el-table-column prop="type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === 'income' ? 'success' : 'danger'" size="small">
              {{ row.type === 'income' ? '收入' : '支出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.type === 'income' ? '#67c23a' : '#f56c6c' }">
              {{ row.type === 'income' ? '+' : '-' }}{{ Number(row.amount).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="balance" label="余额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.balance).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="description" label="摘要" min-width="150" />
        <el-table-column prop="transaction_date" label="日期" width="120" />
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
const accountList = ref([])
const loading = ref(false)

const searchForm = reactive({
  account_id: null,
  type: '',
  date_range: null
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
  searchForm.account_id = null
  searchForm.type = ''
  searchForm.date_range = null
  pagination.page = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/cash-flow', { params: { page: pagination.page, page_size: pagination.page_size, account_id: searchForm.account_id, type: searchForm.type, start_date: searchForm.date_range?.[0], end_date: searchForm.date_range?.[1] } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const fetchAccounts = async () => {
  try {
    const data = await request.get('/v1/finance/bank-accounts/', { params: { page_size: 100 } })
    accountList.value = data.data?.data || []
  } catch (error) {
    accountList.value = []
  }
}

onMounted(() => {
  fetchAccounts()
  fetchData()
})
</script>

<style lang="scss" scoped>
.cash-flow-index {
  padding: 20px;
}
</style>


