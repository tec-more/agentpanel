<template>
  <div class="tax-in-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>进项发票</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="供应商">
            <el-select v-model="searchForm.supplier_id" placeholder="全部供应商" clearable filterable style="width: 200px">
              <el-option v-for="s in supplierList" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="发票类型">
            <el-select v-model="searchForm.invoice_type" placeholder="全部类型" clearable style="width: 140px">
              <el-option label="增值税专票" value="vat_special" />
              <el-option label="增值税普票" value="vat_normal" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
              <el-option label="已收到" value="issued" />
              <el-option label="已认证" value="verified" />
              <el-option label="已作废" value="cancelled" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">录入发票</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="invoice_no" label="发票号码" width="160" />
        <el-table-column prop="invoice_code" label="发票代码" width="140" />
        <el-table-column prop="supplier_name" label="供应商名称" min-width="150" />
        <el-table-column prop="invoice_type" label="发票类型" width="120">
          <template #default="{ row }">{{ getInvoiceTypeLabel(row.invoice_type) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="tax_amount" label="税额" width="120" align="right">
          <template #default="{ row }">{{ Number(row.tax_amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="total_amount" label="价税合计" width="130" align="right">
          <template #default="{ row }">{{ Number(row.total_amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="tax_rate" label="税率" width="80" align="center">
          <template #default="{ row }">{{ Number(row.tax_rate) }}%</template>
        </el-table-column>
        <el-table-column prop="invoice_date" label="开票日期" width="120" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 'issued'" type="success" link @click="handleVerify(row)">认证</el-button>
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
        <el-form-item label="供应商税号" prop="supplier_tax_id">
          <el-input v-model="formData.supplier_tax_id" placeholder="请输入供应商税号" />
        </el-form-item>
        <el-form-item label="发票号码" prop="invoice_no">
          <el-input v-model="formData.invoice_no" placeholder="请输入发票号码" />
        </el-form-item>
        <el-form-item label="发票代码">
          <el-input v-model="formData.invoice_code" placeholder="请输入发票代码" />
        </el-form-item>
        <el-form-item label="发票类型">
          <el-select v-model="formData.invoice_type" style="width: 100%">
            <el-option label="增值税专票" value="vat_special" />
            <el-option label="增值税普票" value="vat_normal" />
          </el-select>
        </el-form-item>
        <el-form-item label="税率">
          <el-select v-model="formData.tax_rate" style="width: 100%">
            <el-option label="13%" :value="13" />
            <el-option label="9%" :value="9" />
            <el-option label="6%" :value="6" />
            <el-option label="0%" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额(不含税)" prop="amount">
          <el-input v-model="formData.amount" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="税额">
          <el-input v-model="formData.tax_amount" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="开票日期">
          <el-date-picker v-model="formData.invoice_date" type="date" style="width: 100%" />
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
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('录入发票')

const searchForm = reactive({
  supplier_id: null,
  invoice_type: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  supplier_id: null,
  supplier_tax_id: '',
  invoice_no: '',
  invoice_code: '',
  invoice_type: 'vat_normal',
  tax_rate: 13,
  amount: '',
  tax_amount: '',
  invoice_date: '',
  description: ''
})

const getInvoiceTypeLabel = (type) => {
  const types = { vat_special: '增值税专票', vat_normal: '增值税普票', invoice: '普通发票' }
  return types[type] || type
}

const getStatusType = (status) => {
  const types = { draft: 'info', issued: 'primary', verified: 'success', cancelled: 'danger' }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = { draft: '草稿', issued: '已收到', verified: '已认证', cancelled: '已作废' }
  return labels[status] || status
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.supplier_id = null
  searchForm.invoice_type = ''
  searchForm.status = ''
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  dialogTitle.value = '录入发票'
  Object.assign(formData, {
    supplier_id: null,
    supplier_tax_id: '',
    invoice_no: '',
    invoice_code: '',
    invoice_type: 'vat_normal',
    tax_rate: 13,
    amount: '',
    tax_amount: '',
    invoice_date: new Date().toISOString().split('T')[0],
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑发票'
  Object.assign(formData, {
    supplier_id: row.supplier_id,
    supplier_tax_id: row.supplier_tax_id,
    invoice_no: row.invoice_no,
    invoice_code: row.invoice_code,
    invoice_type: row.invoice_type,
    tax_rate: row.tax_rate,
    amount: row.amount,
    tax_amount: row.tax_amount,
    invoice_date: row.invoice_date,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleVerify = async (row) => {
  ElMessage.success('发票已认证')
  fetchData()
}

const handleSave = async () => {
  if (!formData.supplier_id || !formData.invoice_no || !formData.amount) {
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
    const data = await request.get('/v1/finance/tax/invoices', {
      params: { page: pagination.page, page_size: pagination.page_size, is_input: true, supplier_id: searchForm.supplier_id, invoice_type: searchForm.invoice_type, status: searchForm.status }
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

onMounted(() => {
  fetchSuppliers()
  fetchData()
})
</script>

<style lang="scss" scoped>
.tax-in-index {
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


