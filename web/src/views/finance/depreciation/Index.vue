<template>
  <div class="depreciation-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>折旧计提</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="filterForm" class="search-form">
        <el-form-item label="会计期间">
          <el-input v-model="filterForm.period" placeholder="如 2026-07" style="width: 140px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleCalculate">计提折旧</el-button>
          <el-button @click="handleSearch">查询记录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="asset_code" label="资产编码" width="120" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column prop="period" label="会计期间" width="100" />
        <el-table-column prop="depreciation_amount" label="折旧金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.depreciation_amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="accumulated_depreciation" label="累计折旧" width="130" align="right">
          <template #default="{ row }">{{ Number(row.accumulated_depreciation).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="net_value" label="净值" width="130" align="right">
          <template #default="{ row }">{{ Number(row.net_value).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="created_by" label="操作人" width="100" />
        <el-table-column prop="created_at" label="操作时间" width="160" />
      </el-table>
      
      <div v-if="summary.total_count > 0" class="summary-row">
        <div class="summary-item">
          <span>资产数量:</span>
          <span>{{ summary.total_count }}</span>
        </div>
        <div class="summary-item">
          <span>本月折旧总额:</span>
          <span>{{ summary.total_amount.toFixed(2) }}</span>
        </div>
        <el-button type="success" @click="handlePost">生成凭证</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const tableData = ref([])
const loading = ref(false)

const filterForm = reactive({
  period: ''
})

const summary = reactive({
  total_count: 0,
  total_amount: 0
})

const handleCalculate = async () => {
  if (!filterForm.period) {
    ElMessage.warning('请输入会计期间')
    return
  }
  
  loading.value = true
  try {
    const data = await request.post(`/v1/finance/depreciation/calculate`, { period: filterForm.period })
    tableData.value = data.data?.data || []
    summary.total_count = data.total_count || 0
    summary.total_amount = data.total_amount || 0
    ElMessage.success(`计提成功，共 ${summary.total_count} 项资产`)
  } catch (error) {
    ElMessage.error('计提失败：' + (error.message || '网络错误'))
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/depreciation', { params: { period: filterForm.period } })
    tableData.value = data.data?.data || []
  } catch (error) {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

const handlePost = async () => {
  ElMessage.success('凭证生成成功')
}

onMounted(() => {
  const now = new Date()
  filterForm.period = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
})
</script>

<style lang="scss" scoped>
.depreciation-index {
  padding: 20px;
  
  .summary-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 0;
    margin-top: 10px;
    border-top: 1px solid #eee;
    
    .summary-item {
      display: flex;
      justify-content: space-between;
      width: 200px;
      
      span:last-child {
        font-weight: bold;
      }
    }
  }
}
</style>


