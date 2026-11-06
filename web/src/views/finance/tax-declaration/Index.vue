<template>
  <div class="tax-declaration-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>税务申报</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="期间">
          <el-date-picker v-model="searchForm.period" type="month" placeholder="选择月份" style="width: 160px" />
        </el-form-item>
        <el-form-item label="税种">
          <el-select v-model="searchForm.tax_type" placeholder="全部税种" clearable style="width: 120px">
            <el-option label="增值税" value="vat" />
            <el-option label="所得税" value="income_tax" />
            <el-option label="附加税" value="additional" />
            <el-option label="印花税" value="stamp" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="未申报" value="pending" />
            <el-option label="已申报" value="declared" />
            <el-option label="已缴税" value="paid" />
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
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="declared_at" label="申报日期" width="120" />
        <el-table-column prop="paid_at" label="缴税日期" width="120" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" type="primary" link @click="handleDeclare(row)">申报</el-button>
            <el-button v-if="row.status === 'declared'" type="success" link @click="handlePay(row)">缴税</el-button>
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
  period: '',
  tax_type: '',
  status: ''
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

const getStatusLabel = (status) => {
  const statuses = { pending: '未申报', declared: '已申报', paid: '已缴税' }
  return statuses[status] || status
}

const getStatusType = (status) => {
  const types = { pending: 'warning', declared: 'primary', paid: 'success' }
  return types[status] || 'info'
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.period = ''
  searchForm.tax_type = ''
  searchForm.status = ''
  pagination.page = 1
  fetchData()
}

const handleDeclare = (row) => {
  ElMessage.success('申报成功')
  fetchData()
}

const handlePay = (row) => {
  ElMessage.success('缴税成功')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/tax-declarations', {
      params: { page: pagination.page, page_size: pagination.page_size, period: searchForm.period, tax_type: searchForm.tax_type, status: searchForm.status }
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
.tax-declaration-index {
  padding: 20px;
}
</style>


