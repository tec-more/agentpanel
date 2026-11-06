<template>
  <div class="daily-journal-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>日记账</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="日期范围">
          <el-date-picker 
            v-model="dateRange" 
            type="daterange" 
            range-separator="至" 
            start-placeholder="开始日期" 
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item label="会计期间">
          <el-input v-model="searchForm.period" placeholder="如 2026-07" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="科目">
          <el-select 
            v-model="searchForm.account_id" 
            placeholder="全部科目" 
            clearable 
            filterable
            style="width: 220px"
          >
            <el-option 
              v-for="acc in accountList" 
              :key="acc.id" 
              :label="acc.code + ' ' + acc.name" 
              :value="acc.id" 
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>日记账记录</span>
          <div class="header-info">
            <el-tag type="info" size="small">共 {{ total }} 条</el-tag>
          </div>
        </div>
      </template>
      
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="journal_date" label="日期" width="120" />
        <el-table-column prop="period" label="会计期间" width="100" />
        <el-table-column prop="account_code" label="科目编码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="150" />
        <el-table-column prop="description" label="摘要" min-width="180" show-overflow-tooltip />
        <el-table-column prop="reference" label="凭证号" width="150" />
        <el-table-column prop="debit" label="借方金额" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.debit && Number(row.debit) > 0">
              {{ Number(row.debit).toFixed(2) }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="credit" label="贷方金额" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.credit && Number(row.credit) > 0">
              {{ Number(row.credit).toFixed(2) }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="余额" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.balance_type === 'credit' ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
              {{ row.balance ? Number(row.balance).toFixed(2) : '0.00' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="方向" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.balance_type === 'credit' ? 'danger' : 'success'" size="small">
              {{ row.balance_type === 'credit' ? '贷' : '借' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[20, 50, 100, 200]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
      
      <div v-if="!loading && tableData.length === 0" class="empty-tip">
        <el-empty description="暂无日记账数据，日记账在凭证过账后自动生成" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const tableData = ref([])
const accountList = ref([])
const loading = ref(false)
const total = ref(0)
const dateRange = ref([])

const searchForm = reactive({
  period: '',
  account_id: null
})

const pagination = reactive({
  page: 1,
  page_size: 20
})

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.period = ''
  searchForm.account_id = null
  dateRange.value = []
  pagination.page = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const queryParams = {
      page: pagination.page,
      page_size: pagination.page_size,
      period: searchForm.period,
      account_id: searchForm.account_id
    }
    
    if (dateRange.value && dateRange.value.length === 2) {
      queryParams.journal_date_start = dateRange.value[0]
      queryParams.journal_date_end = dateRange.value[1]
    }
    
    const data = await request.get('/v1/finance/reports/daily', { params: queryParams })
    tableData.value = data.data?.data || []
    total.value = data.total || 0
  } catch (error) {
    console.error('查询日记账出错:', error)
    ElMessage.error('查询失败：' + (error.message || '网络错误'))
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const fetchAccountList = async () => {
  try {
    const data = await request.get('/v1/finance/accounts/', { params: { page_size: 100 } })
    accountList.value = data.data?.data || []
  } catch (error) {
    console.error('获取科目列表失败:', error)
    accountList.value = []
  }
}

onMounted(() => {
  fetchAccountList()
  fetchData()
})
</script>

<style lang="scss" scoped>
.daily-journal-index {
  padding: 20px;
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .empty-tip {
    padding: 20px 0;
  }
}
</style>



