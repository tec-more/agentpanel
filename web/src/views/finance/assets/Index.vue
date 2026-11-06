<template>
  <div class="app-container">
    <div class="search-form">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="资产编号">
          <el-input v-model="searchForm.keyword" placeholder="请输入资产编号或名称" style="width: 200px" />
        </el-form-item>
        <el-form-item label="资产类型">
          <el-select v-model="searchForm.asset_type" placeholder="请选择资产类型" style="width: 200px">
            <el-option label="房屋建筑物" value="building" />
            <el-option label="机器设备" value="machinery" />
            <el-option label="运输工具" value="vehicle" />
            <el-option label="电子设备" value="electronic" />
            <el-option label="办公设备" value="office" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="使用状态">
          <el-select v-model="searchForm.status" placeholder="请选择使用状态" style="width: 200px">
            <el-option label="在用" value="in_use" />
            <el-option label="闲置" value="idle" />
            <el-option label="维修中" value="repair" />
            <el-option label="已报废" value="scrapped" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
        <el-form-item style="float: right">
          <el-button type="primary" @click="handleAdd">新增资产</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="tableData" border style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="code" label="资产编号" />
      <el-table-column prop="name" label="资产名称" />
      <el-table-column prop="asset_type" label="资产类型">
        <template #default="scope">
          <el-tag>{{ getAssetTypeLabel(scope.row.asset_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="specification" label="规格型号" />
      <el-table-column prop="brand" label="品牌" />
      <el-table-column prop="quantity" label="数量" width="100" />
      <el-table-column prop="unit" label="计量单位" width="100" />
      <el-table-column prop="original_value" label="原值" width="120">
        <template #default="scope">
          {{ formatMoney(scope.row.original_value) }}
        </template>
      </el-table-column>
      <el-table-column prop="accumulated_depreciation" label="累计折旧" width="120">
        <template #default="scope">
          {{ formatMoney(scope.row.accumulated_depreciation) }}
        </template>
      </el-table-column>
      <el-table-column prop="net_value" label="净值" width="120">
        <template #default="scope">
          {{ formatMoney(scope.row.net_value) }}
        </template>
      </el-table-column>
      <el-table-column prop="department_name" label="使用部门" />
      <el-table-column prop="user_name" label="使用人" />
      <el-table-column prop="purchase_date" label="购入日期" />
      <el-table-column prop="status" label="使用状态">
        <template #default="scope">
          <el-tag :type="getStatusTag(scope.row.status)">{{ getStatusLabel(scope.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="handleView(scope.row)">查看</el-button>
          <el-button size="small" type="warning" @click="handleEdit(scope.row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDepreciate(scope.row)">计提折旧</el-button>
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

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
      <el-form ref="formRef" :model="formData" label-width="120px">
        <el-form-item label="资产编号" required>
          <el-input v-model="formData.code" placeholder="请输入资产编号" />
        </el-form-item>
        <el-form-item label="资产名称" required>
          <el-input v-model="formData.name" placeholder="请输入资产名称" />
        </el-form-item>
        <el-form-item label="资产类型" required>
          <el-select v-model="formData.asset_type" placeholder="请选择资产类型">
            <el-option label="房屋建筑物" value="building" />
            <el-option label="机器设备" value="machinery" />
            <el-option label="运输工具" value="vehicle" />
            <el-option label="电子设备" value="electronic" />
            <el-option label="办公设备" value="office" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格型号">
          <el-input v-model="formData.specification" placeholder="请输入规格型号" />
        </el-form-item>
        <el-form-item label="品牌">
          <el-input v-model="formData.brand" placeholder="请输入品牌" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input v-model="formData.quantity" type="number" placeholder="数量" />
        </el-form-item>
        <el-form-item label="计量单位">
          <el-input v-model="formData.unit" placeholder="计量单位" />
        </el-form-item>
        <el-form-item label="原值" required>
          <el-input v-model="formData.original_value" type="number" placeholder="原值" />
        </el-form-item>
        <el-form-item label="预计使用年限">
          <el-input v-model="formData.useful_life" type="number" placeholder="预计使用年限（年）" />
        </el-form-item>
        <el-form-item label="残值率">
          <el-input v-model="formData.residual_rate" type="number" placeholder="残值率（%）" />
        </el-form-item>
        <el-form-item label="使用部门">
          <el-select v-model="formData.department_id" placeholder="请选择部门">
            <el-option v-for="dept in departments" :key="dept.id" :label="dept.name" :value="dept.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="使用人">
          <el-select v-model="formData.user_id" placeholder="请选择使用人">
            <el-option v-for="user in users" :key="user.id" :label="user.name" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="购入日期">
          <el-date-picker v-model="formData.purchase_date" type="date" placeholder="请选择购入日期" />
        </el-form-item>
        <el-form-item label="使用状态">
          <el-select v-model="formData.status" placeholder="请选择使用状态">
            <el-option label="在用" value="in_use" />
            <el-option label="闲置" value="idle" />
            <el-option label="维修中" value="repair" />
            <el-option label="已报废" value="scrapped" />
          </el-select>
        </el-form-item>
        <el-form-item label="存放地点">
          <el-input v-model="formData.location" placeholder="请输入存放地点" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="3" placeholder="请输入备注" />
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
  keyword: '',
  asset_type: '',
  status: ''
})

const dialogVisible = ref(false)
const dialogTitle = ref('新增资产')
const formRef = ref(null)
const formData = reactive({
  id: null,
  code: '',
  name: '',
  asset_type: '',
  specification: '',
  brand: '',
  quantity: 1,
  unit: '',
  original_value: 0,
  useful_life: 5,
  residual_rate: 5,
  department_id: null,
  user_id: null,
  purchase_date: '',
  status: 'in_use',
  location: '',
  remark: ''
})

const departments = ref([])
const users = ref([])

const assetTypes = {
  building: '房屋建筑物',
  machinery: '机器设备',
  vehicle: '运输工具',
  electronic: '电子设备',
  office: '办公设备',
  other: '其他'
}

const statuses = {
  in_use: '在用',
  idle: '闲置',
  repair: '维修中',
  scrapped: '已报废'
}

const getAssetTypeLabel = (type) => assetTypes[type] || type

const getStatusLabel = (status) => statuses[status] || status

const getStatusTag = (status) => {
  const tags = {
    in_use: 'success',
    idle: 'warning',
    repair: 'info',
    scrapped: 'danger'
  }
  return tags[status] || 'info'
}

const formatMoney = (value) => {
  if (!value) return '0.00'
  return value.toFixed(2)
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/assets/', { params: { page: pagination.page, page_size: pagination.page_size, ...searchForm } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
  } catch (error) {
    console.error('获取资产列表失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchDepartments = async () => {
  try {
    const data = await request.get('/v1/departments/list', { params: { page_size: 100 } })
    departments.value = data.data?.items || data.data || []
  } catch (error) {
    console.error('获取部门列表失败:', error)
  }
}

const fetchUsers = async () => {
  try {
    const data = await request.get('/v1/users/list', { params: { page_size: 100 } })
    users.value = data.data?.items || data.data || []
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.keyword = ''
  searchForm.asset_type = ''
  searchForm.status = ''
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
  dialogTitle.value = '新增资产'
  formData.id = null
  formData.code = ''
  formData.name = ''
  formData.asset_type = ''
  formData.specification = ''
  formData.brand = ''
  formData.quantity = 1
  formData.unit = ''
  formData.original_value = 0
  formData.useful_life = 5
  formData.residual_rate = 5
  formData.department_id = null
  formData.user_id = null
  formData.purchase_date = ''
  formData.status = 'in_use'
  formData.location = ''
  formData.remark = ''
  dialogVisible.value = true
}

const handleView = (row) => {
  dialogTitle.value = '查看资产'
  formData.id = row.id
  formData.code = row.code
  formData.name = row.name
  formData.asset_type = row.asset_type
  formData.specification = row.specification
  formData.brand = row.brand
  formData.quantity = row.quantity
  formData.unit = row.unit
  formData.original_value = row.original_value
  formData.useful_life = row.useful_life
  formData.residual_rate = row.residual_rate
  formData.department_id = row.department_id
  formData.user_id = row.user_id
  formData.purchase_date = row.purchase_date
  formData.status = row.status
  formData.location = row.location
  formData.remark = row.remark
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑资产'
  formData.id = row.id
  formData.code = row.code
  formData.name = row.name
  formData.asset_type = row.asset_type
  formData.specification = row.specification
  formData.brand = row.brand
  formData.quantity = row.quantity
  formData.unit = row.unit
  formData.original_value = row.original_value
  formData.useful_life = row.useful_life
  formData.residual_rate = row.residual_rate
  formData.department_id = row.department_id
  formData.user_id = row.user_id
  formData.purchase_date = row.purchase_date
  formData.status = row.status
  formData.location = row.location
  formData.remark = row.remark
  dialogVisible.value = true
}

const handleDepreciate = async (row) => {
  try {
    const data = await request.post(`/v1/finance/assets/${row.id}/depreciation`)
    if (data.success) {
      fetchData()
    }
  } catch (error) {
    console.error('计提折旧失败:', error)
  }
}

const handleSubmit = async () => {
  try {
    const data = await (formData.id ? request.put('/v1/finance/assets/', formData) : request.post('/v1/finance/assets/', formData))
    if (data.success || data.id) {
      dialogVisible.value = false
      fetchData()
    }
  } catch (error) {
    console.error('提交失败:', error)
  }
}

onMounted(() => {
  fetchData()
  fetchDepartments()
  fetchUsers()
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
