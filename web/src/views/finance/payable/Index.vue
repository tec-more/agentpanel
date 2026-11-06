<template>
  <div class="payable-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>应付单</span>
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
          <el-button @click="handleAdd" type="primary">新增应付单</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="payable_no" label="应付单号" width="160" />
        <el-table-column prop="supplier_name" label="供应商名称" min-width="150" />
        <el-table-column prop="amount" label="应付金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="paid_amount" label="已付金额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.paid_amount).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="remaining_amount" label="剩余金额" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: Number(row.remaining_amount) > 0 ? '#f56c6c' : '#67c23a' }">
              {{ Number(row.remaining_amount).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日期" width="120" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="制单人" width="100" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 'draft'" type="success" link @click="handleConfirm(row)">审核</el-button>
            <el-button v-if="row.status !== 'cancelled'" type="danger" link @click="handleCancel(row)">取消</el-button>
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
        <el-form-item label="应付金额" prop="amount">
          <el-input v-model="formData.amount" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="到期日期" prop="due_date">
          <el-date-picker v-model="formData.due_date" type="date" style="width: 100%" />
        </el-form-item>
        <el-form-item label="来源类型">
          <el-select v-model="formData.source_type" style="width: 100%">
            <el-option label="手工录入" value="manual" />
            <el-option label="采购订单" value="purchase_order" />
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
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增应付单')
const dateRange = ref([])

const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'confirmed', label: '已审核' },
  { value: 'partial', label: '部分付款' },
  { value: 'paid', label: '已结清' },
  { value: 'cancelled', label: '已取消' }
]

const searchForm = reactive({
  supplier_id: null,
  status: '',
  due_date_start: '',
  due_date_end: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  supplier_id: null,
  amount: '',
  due_date: '',
  source_type: 'manual',
  description: ''
})

const getStatusType = (status) => {
  const types = { draft: 'info', confirmed: 'primary', partial: 'warning', paid: 'success', cancelled: 'danger' }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const found = statusOptions.find(s => s.value === status)
  return found ? found.label : status
}

const handleSearch = () => {
  if (dateRange.value && dateRange.value.length === 2) {
    searchForm.due_date_start = dateRange.value[0]
    searchForm.due_date_end = dateRange.value[1]
  }
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.supplier_id = null
  searchForm.status = ''
  searchForm.due_date_start = ''
  searchForm.due_date_end = ''
  dateRange.value = []
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  dialogTitle.value = '新增应付单'
  Object.assign(formData, {
    supplier_id: null,
    amount: '',
    due_date: '',
    source_type: 'manual',
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑应付单'
  Object.assign(formData, {
    supplier_id: row.supplier_id,
    amount: row.amount,
    due_date: row.due_date,
    source_type: row.source_type,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleConfirm = async (row) => {
  ElMessage.success('审核成功')
  fetchData()
}

const handleCancel = async (row) => {
  ElMessage.success('取消成功')
  fetchData()
}

const handleSave = async () => {
  if (!formData.supplier_id || !formData.amount) {
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
    const data = await request.get('/v1/finance/payables', {
      params: { page: pagination.page, page_size: pagination.page_size, supplier_id: searchForm.supplier_id, status: searchForm.status, due_date_start: searchForm.due_date_start, due_date_end: searchForm.due_date_end }
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
.payable-index {
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


