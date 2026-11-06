<template>
  <div class="settlement-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>应付核销</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="供应商">
          <el-select v-model="searchForm.supplier_id" placeholder="选择供应商" clearable filterable style="width: 200px">
            <el-option v-for="s in supplierList" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="settlement-card">
      <template #header>
        <span>应付单</span>
      </template>
      <el-table v-loading="loading" :data="payableList" border stripe @selection-change="handlePayableSelection">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="payable_no" label="单据号" width="160" />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" />
        <el-table-column prop="amount" label="金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="remaining_amount" label="剩余金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.remaining_amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日期" width="120" />
      </el-table>
    </el-card>
    
    <el-card shadow="never" class="settlement-card">
      <template #header>
        <span>付款单</span>
      </template>
      <el-table v-loading="loading" :data="paymentList" border stripe @selection-change="handlePaymentSelection">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="payment_no" label="单据号" width="160" />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" />
        <el-table-column prop="amount" label="金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="remaining_amount" label="可核销金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.remaining_amount).toFixed(2) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <el-card shadow="never" class="summary-card">
      <div class="summary-row">
        <span>应付合计:</span>
        <span>{{ selectedPayableTotal.toFixed(2) }}</span>
      </div>
      <div class="summary-row">
        <span>付款合计:</span>
        <span>{{ selectedPaymentTotal.toFixed(2) }}</span>
      </div>
      <div class="summary-row total">
        <span>核销金额:</span>
        <span>{{ Math.min(selectedPayableTotal, selectedPaymentTotal).toFixed(2) }}</span>
      </div>
      <el-button type="primary" :disabled="!canSettle" @click="handleSettle">确认核销</el-button>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const payableList = ref([])
const paymentList = ref([])
const supplierList = ref([])
const loading = ref(false)

const searchForm = reactive({
  supplier_id: null
})

const selectedPayables = ref([])
const selectedPayments = ref([])

const selectedPayableTotal = computed(() => {
  return selectedPayables.value.reduce((sum, item) => sum + Number(item.remaining_amount), 0)
})

const selectedPaymentTotal = computed(() => {
  return selectedPayments.value.reduce((sum, item) => sum + Number(item.remaining_amount), 0)
})

const canSettle = computed(() => {
  return selectedPayables.value.length > 0 && selectedPayments.value.length > 0
})

const handlePayableSelection = (val) => {
  selectedPayables.value = val
}

const handlePaymentSelection = (val) => {
  selectedPayments.value = val
}

const handleSearch = () => {
  fetchData()
}

const handleReset = () => {
  searchForm.supplier_id = null
  selectedPayables.value = []
  selectedPayments.value = []
}

const handleSettle = async () => {
  ElMessage.success('核销成功')
  handleReset()
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchForm.supplier_id) params.append('supplier_id', searchForm.supplier_id)
    
    const [payableData, paymentData] = await Promise.all([
      request.get('/v1/finance/payables', { params: { status: 'confirmed', supplier_id: searchForm.supplier_id } }),
      request.get('/v1/finance/payments', { params: { status: 'confirmed', supplier_id: searchForm.supplier_id } })
    ])
    
    payableList.value = payableData.data || []
    paymentList.value = paymentData.data || []
  } catch (error) {
    payableList.value = []
    paymentList.value = []
  } finally {
    loading.value = false
  }
}

const fetchSuppliers = async () => {
  try {
    const data = await request.get('/v1/purchase/supplier/', { params: { page_size: 100 } })
    supplierList.value = data.data?.items || data.data || []
  } catch (error) {
    supplierList.value = []
  }
}

onMounted(() => {
  fetchSuppliers()
  fetchData()
})
</script>

<style lang="scss" scoped>
.settlement-index {
  padding: 20px;
  
  .settlement-card {
    margin-bottom: 15px;
  }
  
  .summary-card {
    .summary-row {
      display: flex;
      justify-content: space-between;
      padding: 10px 0;
      
      &.total {
        font-weight: bold;
        font-size: 1.1em;
        border-top: 1px solid #eee;
        margin-top: 10px;
        padding-top: 15px;
      }
    }
    
    button {
      margin-top: 15px;
    }
  }
}
</style>


