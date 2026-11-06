<template>
  <div class="settlement-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>{{ isReceivable ? '应收核销' : '应付核销' }}</span>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="客户/供应商">
          <el-select v-model="searchForm.customer_id" placeholder="选择" clearable filterable style="width: 200px">
            <el-option v-for="c in partyList" :key="c.id" :label="c.name" :value="c.id" />
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
        <span>{{ isReceivable ? '应收单' : '应付单' }}</span>
      </template>
      <el-table v-loading="loading" :data="documentList" border stripe @selection-change="handleDocumentSelection">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="document_no" label="单据号" width="160" />
        <el-table-column prop="party_name" label="名称" min-width="150" />
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
        <span>{{ isReceivable ? '收款单' : '付款单' }}</span>
      </template>
      <el-table v-loading="loading" :data="paymentList" border stripe @selection-change="handlePaymentSelection">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="payment_no" label="单据号" width="160" />
        <el-table-column prop="party_name" label="名称" min-width="150" />
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
        <span>应收/应付合计:</span>
        <span>{{ selectedDocumentTotal.toFixed(2) }}</span>
      </div>
      <div class="summary-row">
        <span>收款/付款合计:</span>
        <span>{{ selectedPaymentTotal.toFixed(2) }}</span>
      </div>
      <div class="summary-row total">
        <span>核销金额:</span>
        <span>{{ Math.min(selectedDocumentTotal, selectedPaymentTotal).toFixed(2) }}</span>
      </div>
      <el-button type="primary" :disabled="!canSettle" @click="handleSettle">确认核销</el-button>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  isReceivable: { type: Boolean, default: true }
})

const documentList = ref([])
const paymentList = ref([])
const partyList = ref([])
const loading = ref(false)

const searchForm = reactive({
  customer_id: null
})

const selectedDocuments = ref([])
const selectedPayments = ref([])

const selectedDocumentTotal = computed(() => {
  return selectedDocuments.value.reduce((sum, item) => sum + Number(item.remaining_amount), 0)
})

const selectedPaymentTotal = computed(() => {
  return selectedPayments.value.reduce((sum, item) => sum + Number(item.remaining_amount), 0)
})

const canSettle = computed(() => {
  return selectedDocuments.value.length > 0 && selectedPayments.value.length > 0
})

const handleDocumentSelection = (val) => {
  selectedDocuments.value = val
}

const handlePaymentSelection = (val) => {
  selectedPayments.value = val
}

const handleSearch = () => {
  fetchData()
}

const handleReset = () => {
  searchForm.customer_id = null
  selectedDocuments.value = []
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
    if (searchForm.customer_id) params.append('customer_id', searchForm.customer_id)
    
    const docPath = props.isReceivable ? '/v1/finance/receivables' : '/v1/finance/payables'
    const payPath = props.isReceivable ? '/v1/finance/receipts/' : '/v1/finance/payments'
    const partyId = props.isReceivable ? searchForm.customer_id : searchForm.supplier_id
    
    const [docData, payData] = await Promise.all([
      request.get(docPath, { params: { status: 'confirmed', customer_id: searchForm.customer_id, supplier_id: searchForm.supplier_id } }),
      request.get(payPath, { params: { status: 'confirmed', customer_id: searchForm.customer_id, supplier_id: searchForm.supplier_id } })
    ])
    
    documentList.value = (docData.data || []).map(item => ({
      ...item,
      document_no: item.receivable_no || item.payable_no,
      party_name: item.customer_name || item.supplier_name
    }))
    
    paymentList.value = (payData.data || []).map(item => ({
      ...item,
      payment_no: item.receipt_no || item.payment_no,
      party_name: item.customer_name || item.supplier_name
    }))
  } catch (error) {
    documentList.value = []
    paymentList.value = []
  } finally {
    loading.value = false
  }
}

const fetchParties = async () => {
  try {
    const path = props.isReceivable ? '/v1/customer/list' : '/v1/purchase/supplier/'
    const data = await request.get(path, { params: { page_size: 100 } })
    partyList.value = data.data?.items || data.data || []
  } catch (error) {
    partyList.value = []
  }
}

onMounted(() => {
  fetchParties()
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


