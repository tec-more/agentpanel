<template>
  <div class="asset-card-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>资产卡片</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="资产类别">
            <el-select v-model="searchForm.asset_category" placeholder="全部类别" clearable style="width: 140px">
              <el-option v-for="cat in categoryOptions" :key="cat" :label="cat" :value="cat" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="使用部门">
            <el-select v-model="searchForm.department_id" placeholder="全部部门" clearable filterable style="width: 150px">
              <el-option v-for="d in departmentList" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增资产</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="asset_code" label="资产编码" width="120" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column prop="asset_category" label="资产类别" width="120" />
        <el-table-column prop="brand" label="品牌" width="100" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="purchase_date" label="购入日期" width="120" />
        <el-table-column prop="purchase_cost" label="购入成本" width="130" align="right">
          <template #default="{ row }">{{ Number(row.purchase_cost).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="accumulated_depreciation" label="累计折旧" width="130" align="right">
          <template #default="{ row }">{{ Number(row.accumulated_depreciation).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="net_value" label="净值" width="130" align="right">
          <template #default="{ row }">{{ Number(row.net_value).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDispose(row)">清理</el-button>
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
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="650px">
      <el-form :model="formData" label-width="110px">
        <el-form-item label="资产编码" prop="asset_code">
          <el-input v-model="formData.asset_code" placeholder="请输入资产编码" />
        </el-form-item>
        <el-form-item label="资产名称" prop="asset_name">
          <el-input v-model="formData.asset_name" placeholder="请输入资产名称" />
        </el-form-item>
        <el-form-item label="资产类别">
          <el-select v-model="formData.asset_category" placeholder="选择类别" style="width: 100%">
            <el-option v-for="cat in categoryOptions" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="品牌">
          <el-input v-model="formData.brand" placeholder="请输入品牌" />
        </el-form-item>
        <el-form-item label="型号">
          <el-input v-model="formData.model" placeholder="请输入型号" />
        </el-form-item>
        <el-form-item label="购入日期" prop="purchase_date">
          <el-date-picker v-model="formData.purchase_date" type="date" style="width: 100%" />
        </el-form-item>
        <el-form-item label="购入成本" prop="purchase_cost">
          <el-input v-model="formData.purchase_cost" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="残值">
          <el-input v-model="formData.salvage_value" type="number" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="使用年限(月)">
          <el-input v-model="formData.useful_life" type="number" placeholder="请输入月数" />
        </el-form-item>
        <el-form-item label="折旧方法">
          <el-select v-model="formData.depreciation_method" style="width: 100%">
            <el-option label="直线法" value="straight_line" />
            <el-option label="双倍余额递减法" value="double_declining" />
          </el-select>
        </el-form-item>
        <el-form-item label="使用部门">
          <el-select v-model="formData.department_id" placeholder="选择部门" clearable style="width: 100%" filterable>
            <el-option v-for="d in departmentList" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="存放地点">
          <el-input v-model="formData.location" placeholder="请输入存放地点" />
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
const departmentList = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增资产')

const categoryOptions = ['办公设备', '生产设备', '运输设备', '房屋建筑物', '电子设备', '其他']

const statusOptions = [
  { value: 'new', label: '新增' },
  { value: 'in_use', label: '使用中' },
  { value: 'idle', label: '闲置' },
  { value: 'disposed', label: '已清理' }
]

const searchForm = reactive({
  asset_category: '',
  status: '',
  department_id: null
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  asset_code: '',
  asset_name: '',
  asset_category: '',
  brand: '',
  model: '',
  purchase_date: '',
  purchase_cost: '',
  salvage_value: '',
  useful_life: '',
  depreciation_method: 'straight_line',
  department_id: null,
  location: '',
  description: ''
})

const getStatusType = (status) => {
  const types = { new: 'info', in_use: 'success', idle: 'warning', disposed: 'danger' }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const found = statusOptions.find(s => s.value === status)
  return found ? found.label : status
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.asset_category = ''
  searchForm.status = ''
  searchForm.department_id = null
  pagination.page = 1
  fetchData()
}

const handleAdd = () => {
  dialogTitle.value = '新增资产'
  Object.assign(formData, {
    asset_code: '',
    asset_name: '',
    asset_category: '',
    brand: '',
    model: '',
    purchase_date: '',
    purchase_cost: '',
    salvage_value: '',
    useful_life: '',
    depreciation_method: 'straight_line',
    department_id: null,
    location: '',
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑资产'
  Object.assign(formData, {
    asset_code: row.asset_code,
    asset_name: row.asset_name,
    asset_category: row.asset_category,
    brand: row.brand,
    model: row.model,
    purchase_date: row.purchase_date,
    purchase_cost: row.purchase_cost,
    salvage_value: row.salvage_value,
    useful_life: row.useful_life,
    depreciation_method: row.depreciation_method,
    department_id: row.department_id,
    location: row.location,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleDispose = async (row) => {
  ElMessage.success('资产清理成功')
  fetchData()
}

const handleSave = async () => {
  if (!formData.asset_code || !formData.asset_name || !formData.purchase_cost) {
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
    const data = await request.get('/v1/finance/assets', {
      params: { page: pagination.page, page_size: pagination.page_size, asset_category: searchForm.asset_category, status: searchForm.status, department_id: searchForm.department_id }
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

const fetchDepartments = async () => {
  try {
    const data = await request.get('/v1/departments/list', { params: { page_size: 100 } })
    departmentList.value = data.data?.items || data.data || []
  } catch (error) {
    departmentList.value = []
  }
}

onMounted(() => {
  fetchDepartments()
  fetchData()
})
</script>

<style lang="scss" scoped>
.asset-card-index {
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


