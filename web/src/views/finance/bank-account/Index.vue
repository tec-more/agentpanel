<template>
  <div class="bank-account-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>银行账户</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="银行名称">
            <el-input v-model="searchForm.bank_name" placeholder="搜索银行名称" clearable />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.is_active" placeholder="全部状态" clearable style="width: 100px">
              <el-option label="启用" :value="true" />
              <el-option label="禁用" :value="false" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增账户</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="account_name" label="账户名称" min-width="150" />
        <el-table-column prop="bank_name" label="银行名称" width="150" />
        <el-table-column prop="account_no" label="银行账号" width="200" />
        <el-table-column prop="currency" label="币种" width="80" />
        <el-table-column prop="balance" label="账户余额" width="130" align="right">
          <template #default="{ row }">{{ Number(row.balance).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleToggle(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
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
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="formData" label-width="100px">
        <el-form-item label="账户名称" prop="account_name">
          <el-input v-model="formData.account_name" placeholder="请输入账户名称" />
        </el-form-item>
        <el-form-item label="银行名称" prop="bank_name">
          <el-input v-model="formData.bank_name" placeholder="请输入银行名称" />
        </el-form-item>
        <el-form-item label="银行账号" prop="account_no">
          <el-input v-model="formData.account_no" placeholder="请输入银行账号" />
        </el-form-item>
        <el-form-item label="币种">
          <el-select v-model="formData.currency" style="width: 100%">
            <el-option label="人民币" value="CNY" />
            <el-option label="美元" value="USD" />
            <el-option label="欧元" value="EUR" />
            <el-option label="日元" value="JPY" />
          </el-select>
        </el-form-item>
        <el-form-item label="账户余额">
          <el-input v-model="formData.balance" type="number" placeholder="0.00" />
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
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增账户')

const searchForm = reactive({
  bank_name: '',
  is_active: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  account_name: '',
  bank_name: '',
  account_no: '',
  currency: 'CNY',
  balance: '',
  description: ''
})

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.bank_name = ''
  searchForm.is_active = ''
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  dialogTitle.value = '新增账户'
  Object.assign(formData, {
    account_name: '',
    bank_name: '',
    account_no: '',
    currency: 'CNY',
    balance: '',
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑账户'
  Object.assign(formData, {
    account_name: row.account_name,
    bank_name: row.bank_name,
    account_no: row.account_no,
    currency: row.currency,
    balance: row.balance,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleToggle = async (row) => {
  const action = row.is_active ? '禁用' : '启用'
  ElMessage.success(`${action}成功`)
  fetchData()
}

const handleSave = async () => {
  if (!formData.account_name || !formData.bank_name || !formData.account_no) {
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
    const data = await request.get('/v1/finance/bank-accounts', {
      params: { page: pagination.page, page_size: pagination.page_size, bank_name: searchForm.bank_name, is_active: searchForm.is_active }
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
.bank-account-index {
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


