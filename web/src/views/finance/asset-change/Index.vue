<template>
  <div class="app-container">
    <div class="search-form">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="资产编号">
          <el-input v-model="searchForm.asset_code" placeholder="请输入资产编号" style="width: 200px" />
        </el-form-item>
        <el-form-item label="资产名称">
          <el-input v-model="searchForm.asset_name" placeholder="请输入资产名称" style="width: 200px" />
        </el-form-item>
        <el-form-item label="变动类型">
          <el-select v-model="searchForm.change_type" placeholder="请选择变动类型" style="width: 200px">
            <el-option label="原值变动" value="value" />
            <el-option label="折旧变动" value="depreciation" />
            <el-option label="部门变动" value="department" />
            <el-option label="使用人变动" value="user" />
            <el-option label="使用状态变动" value="status" />
          </el-select>
        </el-form-item>
        <el-form-item label="变动日期">
          <el-date-picker v-model="searchForm.change_date" type="date" placeholder="请选择变动日期" style="width: 200px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
        <el-form-item style="float: right">
          <el-button type="primary" @click="handleAdd">新增变动</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="tableData" border style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="asset_code" label="资产编号" />
      <el-table-column prop="asset_name" label="资产名称" />
      <el-table-column prop="change_type" label="变动类型">
        <template #default="scope">
          <el-tag :type="getChangeTypeTag(scope.row.change_type)">{{ getChangeTypeLabel(scope.row.change_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="change_date" label="变动日期" />
      <el-table-column prop="before_value" label="变动前" />
      <el-table-column prop="after_value" label="变动后" />
      <el-table-column prop="change_reason" label="变动原因" />
      <el-table-column prop="operator" label="操作人" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="handleView(scope.row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
        :current-page="pagination.page"
        :page-sizes="[10, 20, 50, 100]"
        :page-size="pagination.page_size"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form ref="formRef" :model="formData" label-width="100px">
        <el-form-item label="资产编号" required>
          <el-select v-model="formData.asset_id" placeholder="请选择资产">
            <el-option v-for="asset in assets" :key="asset.id" :label="asset.code + ' - ' + asset.name" :value="asset.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="变动类型" required>
          <el-select v-model="formData.change_type" placeholder="请选择变动类型">
            <el-option label="原值变动" value="value" />
            <el-option label="折旧变动" value="depreciation" />
            <el-option label="部门变动" value="department" />
            <el-option label="使用人变动" value="user" />
            <el-option label="使用状态变动" value="status" />
          </el-select>
        </el-form-item>
        <el-form-item label="变动前值">
          <el-input v-model="formData.before_value" placeholder="请输入变动前值" />
        </el-form-item>
        <el-form-item label="变动后值">
          <el-input v-model="formData.after_value" placeholder="请输入变动后值" />
        </el-form-item>
        <el-form-item label="变动原因">
          <el-input v-model="formData.change_reason" type="textarea" :rows="3" placeholder="请输入变动原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const loading = ref(false)
const tableData = ref([])
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const searchForm = reactive({
  asset_code: '',
  asset_name: '',
  change_type: '',
  change_date: ''
})

const dialogVisible = ref(false)
const dialogTitle = ref('新增变动')
const formRef = ref(null)
const formData = reactive({
  id: null,
  asset_id: null,
  change_type: '',
  before_value: '',
  after_value: '',
  change_reason: ''
})

const assets = ref([])

const changeTypes = {
  value: '原值变动',
  depreciation: '折旧变动',
  department: '部门变动',
  user: '使用人变动',
  status: '使用状态变动'
}

const getChangeTypeLabel = (type) => changeTypes[type] || type

const getChangeTypeTag = (type) => {
  const tags = {
    value: 'warning',
    depreciation: 'danger',
    department: 'primary',
    user: 'info',
    status: 'success'
  }
  return tags[type] || 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/asset-change', { params: { page: pagination.page, page_size: pagination.page_size, ...searchForm } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    console.error('获取资产变动列表失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchAssets = async () => {
  try {
    const data = await request.get('/v1/finance/assets/', { params: { page_size: 100 } })
    assets.value = data.data?.data || []
  } catch (error) {
    console.error('获取资产列表失败:', error)
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.asset_code = ''
  searchForm.asset_name = ''
  searchForm.change_type = ''
  searchForm.change_date = ''
  pagination.page = 1
  fetchData()
}

const handleSizeChange = (size) => {
  pagination.page_size = size
  pagination.page = 1
  fetchData()
}

const handleCurrentChange = (page) => {
  pagination.page = page
  fetchData()
}

const handleAdd = () => {
  dialogTitle.value = '新增变动'
  formData.id = null
  formData.asset_id = null
  formData.change_type = ''
  formData.before_value = ''
  formData.after_value = ''
  formData.change_reason = ''
  dialogVisible.value = true
}

const handleView = (row) => {
  dialogTitle.value = '查看变动'
  formData.id = row.id
  formData.asset_id = row.asset_id
  formData.change_type = row.change_type
  formData.before_value = row.before_value
  formData.after_value = row.after_value
  formData.change_reason = row.change_reason
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    const data = await (formData.id ? request.put('/v1/finance/asset-change', formData) : request.post('/v1/finance/asset-change', formData))
    if (data.success) {
      dialogVisible.value = false
      fetchData()
    }
  } catch (error) {
    console.error('提交失败:', error)
  }
}

onMounted(() => {
  fetchData()
  fetchAssets()
})
</script>

<style scoped>
.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}
</style>
