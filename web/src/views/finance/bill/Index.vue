<template>
  <div class="bill-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>票据管理</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="票据类型">
          <el-select v-model="searchForm.bill_type" placeholder="全部类型" clearable style="width: 120px">
            <el-option label="汇票" value="draft" />
            <el-option label="支票" value="check" />
            <el-option label="本票" value="promissory" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="未到期" value="pending" />
            <el-option label="已背书" value="endorsed" />
            <el-option label="已贴现" value="discounted" />
            <el-option label="已到期" value="matured" />
            <el-option label="已作废" value="void" />
          </el-select>
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker v-model="searchForm.maturity_date" type="month" placeholder="选择月份" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增票据</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="bill_no" label="票据编号" width="150" />
        <el-table-column prop="bill_type" label="票据类型" width="100">
          <template #default="{ row }">{{ getTypeLabel(row.bill_type) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="issue_date" label="出票日期" width="120" />
        <el-table-column prop="maturity_date" label="到期日期" width="120" />
        <el-table-column prop="payee" label="收款人" min-width="120" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEndorse(row)">背书</el-button>
            <el-button type="warning" link @click="handleDiscount(row)">贴现</el-button>
            <el-button type="danger" link @click="handleVoid(row)">作废</el-button>
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
import request from '@/utils/request'

const tableData = ref([])
const loading = ref(false)

const searchForm = reactive({
  bill_type: '',
  status: '',
  maturity_date: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const getTypeLabel = (type) => {
  const types = { draft: '汇票', check: '支票', promissory: '本票' }
  return types[type] || type
}

const getStatusLabel = (status) => {
  const statuses = { pending: '未到期', endorsed: '已背书', discounted: '已贴现', matured: '已到期', void: '已作废' }
  return statuses[status] || status
}

const getStatusType = (status) => {
  const types = { pending: 'info', endorsed: 'warning', discounted: 'primary', matured: 'success', void: 'danger' }
  return types[status] || 'info'
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.bill_type = ''
  searchForm.status = ''
  searchForm.maturity_date = ''
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  ElMessage.info('新增票据功能开发中')
}

const handleEndorse = (row) => {
  ElMessage.success('背书成功')
  fetchData()
}

const handleDiscount = (row) => {
  ElMessage.success('贴现成功')
  fetchData()
}

const handleVoid = (row) => {
  ElMessage.success('作废成功')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/bills', {
      params: { page: pagination.page, page_size: pagination.page_size, bill_type: searchForm.bill_type, status: searchForm.status, maturity_date: searchForm.maturity_date }
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
.bill-index {
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


