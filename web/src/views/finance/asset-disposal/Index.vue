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
        <el-form-item label="处置方式">
          <el-select v-model="searchForm.disposal_type" placeholder="请选择处置方式" style="width: 200px">
            <el-option label="报废" value="scrap" />
            <el-option label="出售" value="sale" />
            <el-option label="捐赠" value="donation" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="处置日期">
          <el-date-picker v-model="searchForm.disposal_date" type="date" placeholder="请选择处置日期" style="width: 200px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
        <el-form-item style="float: right">
          <el-button type="primary" @click="handleAdd">新增处置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="tableData" border style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="asset_code" label="资产编号" />
      <el-table-column prop="asset_name" label="资产名称" />
      <el-table-column prop="disposal_type" label="处置方式">
        <template #default="scope">
          <el-tag :type="getDisposalTypeTag(scope.row.disposal_type)">{{ getDisposalTypeLabel(scope.row.disposal_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="disposal_date" label="处置日期" />
      <el-table-column prop="original_value" label="原值" />
      <el-table-column prop="accumulated_depreciation" label="累计折旧" />
      <el-table-column prop="net_value" label="净值" />
      <el-table-column prop="disposal_amount" label="处置收入" />
      <el-table-column prop="disposal_expense" label="处置费用" />
      <el-table-column prop="disposal_result" label="处置结果">
        <template #default="scope">
          <el-tag :type="scope.row.disposal_result === 'profit' ? 'success' : 'danger'">
            {{ scope.row.disposal_result === 'profit' ? '收益' : '损失' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="disposal_reason" label="处置原因" />
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
        <el-form-item label="处置方式" required>
          <el-select v-model="formData.disposal_type" placeholder="请选择处置方式">
            <el-option label="报废" value="scrap" />
            <el-option label="出售" value="sale" />
            <el-option label="捐赠" value="donation" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="处置日期">
          <el-date-picker v-model="formData.disposal_date" type="date" placeholder="请选择处置日期" />
        </el-form-item>
        <el-form-item label="原值">
          <el-input v-model="formData.original_value" type="number" placeholder="原值" />
        </el-form-item>
        <el-form-item label="累计折旧">
          <el-input v-model="formData.accumulated_depreciation" type="number" placeholder="累计折旧" />
        </el-form-item>
        <el-form-item label="处置收入">
          <el-input v-model="formData.disposal_amount" type="number" placeholder="处置收入" />
        </el-form-item>
        <el-form-item label="处置费用">
          <el-input v-model="formData.disposal_expense" type="number" placeholder="处置费用" />
        </el-form-item>
        <el-form-item label="处置原因">
          <el-input v-model="formData.disposal_reason" type="textarea" :rows="3" placeholder="请输入处置原因" />
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
  disposal_type: '',
  disposal_date: ''
})

const dialogVisible = ref(false)
const dialogTitle = ref('新增处置')
const formRef = ref(null)
const formData = reactive({
  id: null,
  asset_id: null,
  disposal_type: '',
  disposal_date: '',
  original_value: 0,
  accumulated_depreciation: 0,
  disposal_amount: 0,
  disposal_expense: 0,
  disposal_reason: ''
})

const assets = ref([])

const disposalTypes = {
  scrap: '报废',
  sale: '出售',
  donation: '捐赠',
  other: '其他'
}

const getDisposalTypeLabel = (type) => disposalTypes[type] || type

const getDisposalTypeTag = (type) => {
  const tags = {
    scrap: 'danger',
    sale: 'success',
    donation: 'warning',
    other: 'info'
  }
  return tags[type] || 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/asset-disposal', { params: { page: pagination.page, page_size: pagination.page_size, ...searchForm } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    console.error('获取资产清理列表失败:', error)
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
  searchForm.disposal_type = ''
  searchForm.disposal_date = ''
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
  dialogTitle.value = '新增处置'
  formData.id = null
  formData.asset_id = null
  formData.disposal_type = ''
  formData.disposal_date = ''
  formData.original_value = 0
  formData.accumulated_depreciation = 0
  formData.disposal_amount = 0
  formData.disposal_expense = 0
  formData.disposal_reason = ''
  dialogVisible.value = true
}

const handleView = (row) => {
  dialogTitle.value = '查看处置'
  formData.id = row.id
  formData.asset_id = row.asset_id
  formData.disposal_type = row.disposal_type
  formData.disposal_date = row.disposal_date
  formData.original_value = row.original_value
  formData.accumulated_depreciation = row.accumulated_depreciation
  formData.disposal_amount = row.disposal_amount
  formData.disposal_expense = row.disposal_expense
  formData.disposal_reason = row.disposal_reason
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    const data = await (formData.id ? request.put('/v1/finance/asset-disposal', formData) : request.post('/v1/finance/asset-disposal', formData))
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
