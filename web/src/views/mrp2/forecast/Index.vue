<template>
  <div class="forecast-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>销售预测</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="预测编码">
            <el-input v-model="searchForm.forecast_code" placeholder="搜索预测编码" clearable />
          </el-form-item>
          <el-form-item label="预测名称">
            <el-input v-model="searchForm.forecast_name" placeholder="搜索预测名称" clearable />
          </el-form-item>
          <el-form-item label="预测类型">
            <el-select v-model="searchForm.forecast_type" placeholder="全部类型" clearable style="width: 140px">
              <el-option label="月度预测" value="monthly" />
              <el-option label="季度预测" value="quarterly" />
              <el-option label="年度预测" value="yearly" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 140px">
              <el-option label="草稿" value="draft" />
              <el-option label="待审核" value="pending" />
              <el-option label="已通过" value="approved" />
              <el-option label="已驳回" value="rejected" />
              <el-option label="已发布" value="published" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增预测</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="forecast_code" label="预测编码" />
        <el-table-column prop="forecast_name" label="预测名称" />
        <el-table-column prop="forecast_type" label="预测类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getForecastTypeTag(row.forecast_type)">
              {{ getForecastTypeName(row.forecast_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" />
        <el-table-column prop="end_date" label="结束日期" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link @click="handleView(row)">查看</el-button>
              <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
              <el-button v-if="row.status === 'draft'" type="success" link @click="handleSubmit(row)">提交审核</el-button>
              <el-button v-if="row.status === 'pending'" type="success" link @click="handleApprove(row)">审批通过</el-button>
              <el-button v-if="row.status === 'pending'" type="danger" link @click="handleReject(row)">驳回</el-button>
              <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="预测编码" prop="forecast_code">
          <el-input v-model="formData.forecast_code" placeholder="请输入预测编码" />
        </el-form-item>
        <el-form-item label="预测名称" prop="forecast_name">
          <el-input v-model="formData.forecast_name" placeholder="请输入预测名称" />
        </el-form-item>
        <el-form-item label="预测类型" prop="forecast_type">
          <el-select v-model="formData.forecast_type" placeholder="请选择预测类型">
            <el-option label="月度预测" value="monthly" />
            <el-option label="季度预测" value="quarterly" />
            <el-option label="年度预测" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker v-model="formData.start_date" type="date" placeholder="选择开始日期" />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker v-model="formData.end_date" type="date" placeholder="选择结束日期" />
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

    <el-dialog v-model="detailVisible" title="销售预测详情" width="800px">
      <div v-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="预测编码">{{ detailData.forecast_code }}</el-descriptions-item>
          <el-descriptions-item label="预测名称">{{ detailData.forecast_name }}</el-descriptions-item>
          <el-descriptions-item label="预测类型">{{ getForecastTypeName(detailData.forecast_type) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ getStatusName(detailData.status) }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ detailData.start_date }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ detailData.end_date }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detailData.description || '-' }}</el-descriptions-item>
        </el-descriptions>
        
        <el-divider>预测明细</el-divider>
        <el-table :data="detailData.details || []" border>
          <el-table-column prop="product_code" label="产品编码" />
          <el-table-column prop="product_name" label="产品名称" />
          <el-table-column prop="quantity" label="预测数量" />
          <el-table-column prop="unit" label="单位" />
          <el-table-column prop="forecast_date" label="预测日期" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const tableData = ref([])
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailData = ref(null)
const dialogTitle = ref('新增销售预测')
const isEdit = ref(false)
const currentId = ref(null)
const loading = ref(false)

const searchForm = reactive({
  forecast_code: '',
  forecast_name: '',
  forecast_type: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  forecast_code: '',
  forecast_name: '',
  forecast_type: 'monthly',
  start_date: '',
  end_date: '',
  description: ''
})

const rules = {
  forecast_code: [{ required: true, message: '请输入预测编码', trigger: 'blur' }],
  forecast_name: [{ required: true, message: '请输入预测名称', trigger: 'blur' }],
  forecast_type: [{ required: true, message: '请选择预测类型', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

const getForecastTypeName = (type) => {
  const types = { monthly: '月度预测', quarterly: '季度预测', yearly: '年度预测' }
  return types[type] || type
}

const getForecastTypeTag = (type) => {
  const tags = { monthly: 'info', quarterly: 'primary', yearly: 'success' }
  return tags[type] || 'info'
}

const getStatusName = (status) => {
  const statuses = { draft: '草稿', pending: '待审核', approved: '已通过', rejected: '已驳回', published: '已发布' }
  return statuses[status] || status
}

const getStatusTag = (status) => {
  const tags = { draft: 'info', pending: 'warning', approved: 'success', rejected: 'danger', published: 'primary' }
  return tags[status] || 'info'
}

const handleSearch = async () => {
  pagination.page = 1
  await fetchData()
}

const handleReset = () => {
  searchForm.forecast_code = ''
  searchForm.forecast_name = ''
  searchForm.forecast_type = ''
  searchForm.status = ''
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增销售预测'
  Object.assign(formData, {
    forecast_code: '',
    forecast_name: '',
    forecast_type: 'monthly',
    start_date: '',
    end_date: '',
    description: ''
  })
  dialogVisible.value = true
}

const handleView = async (row) => {
  const data = await request.get(`/v1/mrp2/forecast/${row.id}`)
  if (data.code === 0) {
    detailData.value = data.data
    detailVisible.value = true
  }
}

const handleEdit = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑销售预测'
  Object.assign(formData, {
    forecast_code: row.forecast_code,
    forecast_name: row.forecast_name,
    forecast_type: row.forecast_type,
    start_date: row.start_date,
    end_date: row.end_date,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleSubmit = async (row) => {
  const data = await request.put(`/v1/mrp2/forecast/${row.id}/submit`)
  if (data.code === 0) {
    ElMessage.success('提交成功')
    fetchData()
  } else {
    ElMessage.error(data.msg || '提交失败')
  }
}

const handleApprove = async (row) => {
  const data = await request.put(`/v1/mrp2/forecast/${row.id}/approve`)
  if (data.code === 0) {
    ElMessage.success('审批通过')
    fetchData()
  } else {
    ElMessage.error(data.msg || '审批失败')
  }
}

const handleReject = async (row) => {
  const data = await request.put(`/v1/mrp2/forecast/${row.id}/reject`)
  if (data.code === 0) {
    ElMessage.success('已驳回')
    fetchData()
  } else {
    ElMessage.error(data.msg || '操作失败')
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(
    `确定删除预测 ${row.forecast_name} 吗？`,
    '提示',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  )
  const data = await request.delete(`/v1/mrp2/forecast/${row.id}`)
  if (data.code === 0) {
    ElMessage.success(data.msg)
    fetchData()
  } else {
    ElMessage.error(data.msg || '删除失败')
  }
}

const handleSave = async () => {
  if (!formData.forecast_code || !formData.forecast_name || !formData.forecast_type || !formData.start_date || !formData.end_date) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  if (isEdit.value) {
    const data = await request.put(`/v1/mrp2/forecast/${currentId.value}`, formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  } else {
    const data = await request.post('/v1/mrp2/forecast/', formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/mrp2/forecast/', { 
      params: { 
        page: pagination.page, 
        page_size: pagination.page_size,
        forecast_code: searchForm.forecast_code,
        forecast_name: searchForm.forecast_name,
        forecast_type: searchForm.forecast_type,
        status: searchForm.status
      } 
    })
    tableData.value = data.data?.items || []
    pagination.total = data.data?.total || 0
    pagination.page = data.data?.page || 1
    pagination.page_size = data.data?.page_size || 20
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  }
  loading.value = false
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.forecast-index {
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
