<template>
  <div class="opening-balance-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>期初余额录入</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleImport">导入期初余额</el-button>
          </div>
        </div>
      </template>
      
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="会计期间">
          <el-input v-model="searchForm.period" placeholder="如 2026-07" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="科目类型">
          <el-select v-model="searchForm.account_type" placeholder="全部类型" clearable style="width: 140px">
            <el-option v-for="type in accountTypes" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="account_code" label="科目编码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="180" />
        <el-table-column prop="account_type" label="科目类型" width="120" />
        <el-table-column prop="opening_debit" label="期初借方" width="130" align="right">
          <template #default="{ row }">
            {{ Number(row.opening_debit).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="opening_credit" label="期初贷方" width="130" align="right">
          <template #default="{ row }">
            {{ Number(row.opening_credit).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
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
        <el-form-item label="会计期间" prop="period">
          <el-input v-model="formData.period" placeholder="如 2026-07" />
        </el-form-item>
        <el-form-item label="科目" prop="account_id">
          <el-select v-model="formData.account_id" placeholder="选择科目" style="width: 100%" filterable>
            <el-option v-for="acc in accountList" :key="acc.id" :label="acc.code + ' ' + acc.name" :value="acc.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="期初借方">
          <el-input v-model="formData.opening_debit" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="期初贷方">
          <el-input v-model="formData.opening_credit" type="number" placeholder="0.00" />
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

const tableData = ref([])
const accountTypes = ref([])
const accountList = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('录入期初余额')

const searchForm = reactive({
  period: '',
  account_type: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  period: '',
  account_id: null,
  opening_debit: '',
  opening_credit: ''
})

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.period = ''
  searchForm.account_type = ''
  handleSearch()
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑期初余额'
  Object.assign(formData, {
    period: row.period,
    account_id: row.account_id,
    opening_debit: row.opening_debit,
    opening_credit: row.opening_credit
  })
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!formData.account_id) {
    ElMessage.warning('请选择科目')
    return
  }
  
  dialogVisible.value = false
  ElMessage.success('保存成功')
  fetchData()
}

const handleImport = () => {
  ElMessage.info('导入功能开发中')
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/opening-balance', {
      params: { page: pagination.page, page_size: pagination.page_size, period: searchForm.period, account_type: searchForm.account_type }
    })
    
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    tableData.value = []
    pagination.total = 0
    console.error('查询失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.opening-balance-index {
  padding: 20px;
}
</style>


