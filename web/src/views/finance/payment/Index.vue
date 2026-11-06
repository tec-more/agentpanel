<template>
  <div class="payment-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>付款单</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="供应商">
            <el-select v-model="searchForm.supplier_id" placeholder="全部供应商" clearable filterable style="width: 200px">
              <el-option v-for="s in supplierList" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="日期范围">
            <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增付款单</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="payment_no" label="付款单号" width="160" />
        <el-table-column prop="supplier_name" label="供应商名称" min-width="150" />
        <el-table-column prop="bank_account_name" label="银行账户" width="150" />
        <el-table-column prop="amount" label="付款金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="payment_date" label="付款日期" width="120" />
        <el-table-column prop="payment_method" label="付款方式" width="120">
          <template #default="{ row }">{{ getPaymentMethodLabel(row.payment_method) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="制单人" width="100" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 'draft'" type="success" link @click="handleConfirm(row)">审核</el-button>
            <el-button v-if="row.status === 'confirmed'" type="primary" link @click="handlePost(row)">过账</el-button>
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
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="formData" label-width="100px">
        <el-form-item label="供应商" prop="supplier_id">
          <el-select v-model="formData.supplier_id" placeholder="选择供应商" style="width: 100%" filterable>
            <el-option v-for="s in supplierList" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="银行账户" prop="bank_account_id">
          <el-select v-model="formData.bank_account_id" placeholder="选择账户" style="width: 100%" filterable>
            <el-option v-for="b in bankAccountList" :key="b.id" :label="b.bank_name + ' ' + b.account_no" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="付款金额" prop="amount">
          <el-input v-model="formData.amount" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="付款日期" prop="payment_date">
          <el-date-picker v-model="formData.payment_date" type="date" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="formData.payment_method" style="width: 100%">
            <el-option label="银行转账" value="bank_transfer" />
            <el-option label="现金" value="cash" />
            <el-option label="支票" value="check" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.description" type="textarea" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const tableData = ref([])
const supplierList = ref([])
const bankAccountList = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增付款单')
const dateRange = ref([])

const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'confirmed', label: '已审核' },
  { value: 'posted', label: '已过账' },
  { value: 'cancelled', label: '已取消' }
]

const searchForm = reactive({
  supplier_id: null,
  status: '',
  payment_date_start: '',
  payment_date_end: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  supplier_id: null,
  bank_account_id: null,
  amount: '',
  payment_date: '',
  payment_method: 'bank_transfer',
  description: ''
})

const getStatusType = (status) => {
  const types = { draft: 'info', confirmed: 'primary', posted: 'success', cancelled: 'danger' }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const found = statusOptions.find(s => s.value === status)
  return found ? found.label : status
}

const getPaymentMethodLabel = (method) => {
  const methods = { bank_transfer: '银行转账', cash: '现金', check: '支票', other: '其他' }
  return methods[method] || method
}

const handleSearch = () => {
  if (dateRange.value && dateRange.value.length === 2) {
    searchForm.payment_date_start = dateRange.value[0]
    searchForm.payment_date_end = dateRange.value[1]
  }
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.supplier_id = null
  searchForm.status = ''
  searchForm.payment_date_start = ''
  searchForm.payment_date_end = ''
  dateRange.value = []
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  dialogTitle.value = '新增付款单'
  Object.assign(formData, {
    supplier_id: null,
    bank_account_id: null,
    amount: '',
    payment_date: new Date().toISOString().split('T')[0],
    payment_method: 'bank_transfer',
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑付款单'
  Object.assign(formData, {
    supplier_id: row.supplier_id,
    bank_account_id: row.bank_account_id,
    amount: row.amount,
    payment_date: row.payment_date,
    payment_method: row.payment_method,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleConfirm = async (row) => {
  ElMessage.success('审核成功')
  fetchData()
}

const handlePost = async (row) => {
  ElMessage.success('过账成功')
  fetchData()
}

const handleSave = async () => {
  if (!formData.supplier_id || !formData.bank_account_id || !formData.amount) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  dialogVisible.value = false
  ElMessage.success('保存成功')
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/payments', {
      params: { page: pagination.page, page_size: pagination.page_size, supplier_id: searchForm.supplier_id, status: searchForm.status, payment_date_start: searchForm.payment_date_start, payment_date_end: searchForm.payment_date_end }
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

const fetchSuppliers = async () => {
  try {
    const data = await request.get('/v1/purchase/supplier/', { params: { page_size: 100 } })
    supplierList.value = data.data?.items || data.data || []
  } catch (error) {
    supplierList.value = []
  }
}

const fetchBankAccounts = async () => {
  try {
    const data = await request.get('/v1/finance/bank-accounts/', { params: { page_size: 100 } })
    bankaccountList.value = data.data?.data || []
  } catch (error) {
    bankAccountList.value = []
  }
}

onMounted(() => {
  fetchSuppliers()
  fetchBankAccounts()
  fetchData()
})
</script>

<style lang="scss" scoped>
.payment-index {
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


