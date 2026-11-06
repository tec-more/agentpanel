<template>
  <div class="cost-transfer-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>成本结转</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="期间">
          <el-date-picker v-model="searchForm.period" type="month" placeholder="选择月份" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleTransfer">执行结转</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column prop="transfer_date" label="结转日期" width="120" />
        <el-table-column prop="transfer_amount" label="结转金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.transfer_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="150" />
        <el-table-column prop="created_by" label="操作人" width="100" />
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

const handleTransfer = async () => {
  ElMessage.success('成本结转成功')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/cost-transfer', {
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
.cost-transfer-index {
  padding: 20px;
}
</style>


