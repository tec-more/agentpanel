<template>
  <div class="general-ledger-query-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>总账查询</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="科目">
          <el-select v-model="searchForm.account_id" placeholder="全部科目" clearable filterable style="width: 200px">
            <el-option v-for="a in accountList" :key="a.id" :label="a.name" :value="a.id" />
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
        <el-table-column prop="account_code" label="科目编码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="150" />
        <el-table-column prop="begin_debit" label="期初借方" width="130" align="right">
          <template #default="{ row }">{{ Number(row.begin_debit).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="begin_credit" label="期初贷方" width="130" align="right">
          <template #default="{ row }">{{ Number(row.begin_credit).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="period_debit" label="本期借方" width="130" align="right">
          <template #default="{ row }">{{ Number(row.period_debit).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="period_credit" label="本期贷方" width="130" align="right">
          <template #default="{ row }">{{ Number(row.period_credit).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="end_debit" label="期末借方" width="130" align="right">
          <template #default="{ row }">{{ Number(row.end_debit).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="end_credit" label="期末贷方" width="130" align="right">
          <template #default="{ row }">{{ Number(row.end_credit).toFixed(2) }}</template>
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
const accountList = ref([])
const loading = ref(false)

const searchForm = reactive({
  account_id: null,
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
  searchForm.account_id = null
  searchForm.period = ''
  pagination.page = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/general-ledger', {
      params: { page: pagination.page, page_size: pagination.page_size, account_id: searchForm.account_id, period: searchForm.period }
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

const fetchAccounts = async () => {
  try {
    const data = await request.get('/v1/finance/accounts/', { params: { page_size: 100 } })
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
.general-ledger-query-index {
  padding: 20px;
}
</style>


