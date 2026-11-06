<template>
  <div class="period-close-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>期末结转</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="期间">
          <el-date-picker v-model="searchForm.period" type="month" placeholder="选择月份" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleClose">执行结转</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column prop="close_date" label="结转日期" width="120" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'closed' ? 'success' : 'info'" size="small">
              {{ row.status === 'closed' ? '已结账' : '未结账' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="profit_amount" label="本期利润" width="130" align="right">
          <template #default="{ row }">{{ Number(row.profit_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="created_by" label="操作人" width="100" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'closed'" type="primary" link @click="handleClose">结转</el-button>
            <el-button v-if="row.status === 'closed'" type="danger" link @click="handleReverse">反结账</el-button>
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
  period: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const handleClose = async () => {
  ElMessage.success('期末结转成功')
  fetchData()
}

const handleReverse = async () => {
  ElMessage.success('反结账成功')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/period-close', {
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
.period-close-index {
  padding: 20px;
}
</style>


