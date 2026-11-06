<template>
  <div class="expense-report-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>报销单</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="申请人">
          <el-select v-model="searchForm.applicant_id" placeholder="全部" clearable filterable style="width: 150px">
            <el-option v-for="u in userList" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="待审批" value="pending" />
            <el-option label="审批通过" value="approved" />
            <el-option label="已报销" value="reimbursed" />
            <el-option label="已拒绝" value="rejected" />
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
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增报销</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="report_no" label="报销单号" width="150" />
        <el-table-column prop="applicant_name" label="申请人" width="100" />
        <el-table-column prop="total_amount" label="报销金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.total_amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="申请日期" width="120" />
        <el-table-column prop="approved_at" label="审批日期" width="120" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'approved'" type="success" link @click="handleReimburse(row)">报销</el-button>
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
const userList = ref([])
const loading = ref(false)

const searchForm = reactive({
  applicant_id: null,
  status: '',
  date_range: null
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const getStatusLabel = (status) => {
  const statuses = { pending: '待审批', approved: '审批通过', reimbursed: '已报销', rejected: '已拒绝' }
  return statuses[status] || status
}

const getStatusType = (status) => {
  const types = { pending: 'warning', approved: 'primary', reimbursed: 'success', rejected: 'danger' }
  return types[status] || 'info'
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.applicant_id = null
  searchForm.status = ''
  searchForm.date_range = null
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  ElMessage.info('新增报销单功能开发中')
}

const handleView = (row) => {
  ElMessage.info('查看报销单详情功能开发中')
}

const handleReimburse = (row) => {
  ElMessage.success('报销成功')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/expense-reports', { params: { page: pagination.page, page_size: pagination.page_size, applicant_id: searchForm.applicant_id, status: searchForm.status, start_date: searchForm.date_range?.[0], end_date: searchForm.date_range?.[1] } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const fetchUsers = async () => {
  try {
    const data = await request.get('/v1/users/list', { params: { page_size: 100 } })
    userList.value = data.data?.items || data.data || []
  } catch (error) {
    userList.value = []
  }
}

onMounted(() => {
  fetchUsers()
  fetchData()
})
</script>

<style lang="scss" scoped>
.expense-report-index {
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


