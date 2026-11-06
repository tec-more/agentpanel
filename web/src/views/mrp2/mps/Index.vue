<template>
  <div class="mps-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>主生产计划</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="计划编码">
            <el-input v-model="searchForm.mps_code" placeholder="搜索计划编码" clearable />
          </el-form-item>
          <el-form-item label="计划名称">
            <el-input v-model="searchForm.mps_name" placeholder="搜索计划名称" clearable />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 140px">
              <el-option label="草稿" value="draft" />
              <el-option label="已提交" value="submitted" />
              <el-option label="已审核" value="approved" />
              <el-option label="已下达" value="released" />
              <el-option label="已关闭" value="closed" />
              <el-option label="已取消" value="canceled" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增计划</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="mps_code" label="计划编码" />
        <el-table-column prop="mps_name" label="计划名称" />
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
        <el-table-column label="操作" width="380" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link @click="handleView(row)">查看</el-button>
              <el-button v-if="row.status === 'draft'" type="primary" link @click="handleEdit(row)">编辑</el-button>
              <el-button v-if="row.status === 'draft'" type="warning" link @click="handleCompile(row)">编制</el-button>
              <el-button v-if="row.status === 'draft'" type="success" link @click="handleSubmit(row)">提交审核</el-button>
              <el-button v-if="row.status === 'submitted'" type="success" link @click="handleApprove(row)">审批通过</el-button>
              <el-button v-if="row.status === 'approved'" type="primary" link @click="handleRelease(row)">下达</el-button>
              <el-button v-if="['draft', 'submitted', 'approved'].includes(row.status)" type="danger" link @click="handleCancel(row)">取消</el-button>
              <el-button v-if="row.status === 'released'" type="info" link @click="handleClose(row)">关闭</el-button>
              <el-button v-if="['approved', 'released'].includes(row.status)" type="primary" link @click="handleViewPlanLines(row)">计划行</el-button>
              <el-button v-if="row.status === 'draft'" type="danger" link @click="handleDelete(row)">删除</el-button>
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
        <el-form-item label="计划编码" prop="mps_code">
          <el-input v-model="formData.mps_code" placeholder="请输入计划编码" />
        </el-form-item>
        <el-form-item label="计划名称" prop="mps_name">
          <el-input v-model="formData.mps_name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker v-model="formData.start_date" type="date" placeholder="选择开始日期" />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker v-model="formData.end_date" type="date" placeholder="选择结束日期" />
        </el-form-item>
        <el-form-item label="关联预测">
          <el-select v-model="formData.forecast_id" placeholder="请选择关联销售预测" clearable>
            <el-option v-for="f in forecasts" :key="f.id" :label="f.forecast_code + ' ' + f.forecast_name" :value="f.id" />
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

    <el-dialog v-model="detailVisible" title="主生产计划详情" width="800px">
      <div v-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="计划编码">{{ detailData.mps_code }}</el-descriptions-item>
          <el-descriptions-item label="计划名称">{{ detailData.mps_name }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ detailData.start_date }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ detailData.end_date }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ getStatusName(detailData.status) }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detailData.description || '-' }}</el-descriptions-item>
        </el-descriptions>
        
        <el-divider>计划明细</el-divider>
        <el-table :data="detailData.details || []" border>
          <el-table-column prop="product_code" label="产品编码" />
          <el-table-column prop="product_name" label="产品名称" />
          <el-table-column prop="quantity" label="计划数量" />
          <el-table-column prop="unit" label="单位" />
          <el-table-column prop="planned_date" label="计划日期" />
          <el-table-column prop="work_center_code" label="工作中心" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="planLineVisible" title="MPS计划行" width="900px">
      <el-table :data="planLines" border stripe v-loading="planLineLoading">
        <el-table-column prop="product_code" label="产品编码" width="120" />
        <el-table-column prop="product_name" label="产品名称" width="140" />
        <el-table-column prop="planned_quantity" label="计划数量" width="100" />
        <el-table-column prop="actual_quantity" label="实际数量" width="100" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="planned_date" label="计划日期" width="120" />
        <el-table-column prop="work_center_code" label="工作中心" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'completed'" type="primary" link size="small" @click="handleAdjustPlanLine(row)">调整</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="planLineVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="adjustDialogVisible" title="调整计划行" width="400px">
      <el-form :model="adjustForm" label-width="100px">
        <el-form-item label="计划数量">
          <el-input-number v-model="adjustForm.planned_quantity" :min="0" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="计划日期">
          <el-date-picker v-model="adjustForm.planned_date" type="date" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdjust">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getMpsList, getMpsDetail, createMps, updateMps, deleteMps,
  compileMps, submitMps, approveMps, releaseMps, closeMps, cancelMps,
  getMpsPlanLines, adjustMpsPlanLine, getForecastList
} from '@/api/mrp2'

const tableData = ref([])
const forecasts = ref([])
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailData = ref(null)
const dialogTitle = ref('新增主生产计划')
const isEdit = ref(false)
const currentId = ref(null)
const loading = ref(false)

const searchForm = reactive({
  mps_code: '',
  mps_name: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  mps_code: '',
  mps_name: '',
  start_date: '',
  end_date: '',
  forecast_id: null,
  description: ''
})

const rules = {
  mps_code: [{ required: true, message: '请输入计划编码', trigger: 'blur' }],
  mps_name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

const getStatusName = (status) => {
  const statuses = { draft: '草稿', submitted: '已提交', approved: '已审核', released: '已下达', closed: '已关闭', canceled: '已取消' }
  return statuses[status] || status
}

const getStatusTag = (status) => {
  const tags = { draft: 'info', submitted: 'warning', approved: 'success', released: 'primary', closed: 'info', canceled: 'danger' }
  return tags[status] || 'info'
}

const handleSearch = async () => {
  pagination.page = 1
  await fetchData()
}

const handleReset = () => {
  searchForm.mps_code = ''
  searchForm.mps_name = ''
  searchForm.status = ''
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增主生产计划'
  Object.assign(formData, {
    mps_code: '',
    mps_name: '',
    start_date: '',
    end_date: '',
    forecast_id: null,
    description: ''
  })
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await getMpsDetail(row.id)
    const d = res.data?.data || res.data
    detailData.value = d
    detailVisible.value = true
  } catch (e) { ElMessage.error('获取详情失败') }
}

const handleEdit = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑主生产计划'
  Object.assign(formData, {
    mps_code: row.mps_code,
    mps_name: row.mps_name,
    start_date: row.start_date,
    end_date: row.end_date,
    forecast_id: row.forecast_id,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleSubmit = async (row) => {
  try {
    await submitMps(row.id)
    ElMessage.success('提交成功')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '提交失败') }
}

const handleApprove = async (row) => {
  try {
    await approveMps(row.id, {})
    ElMessage.success('审批通过')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '审批失败') }
}

const handleCompile = async (row) => {
  try {
    await compileMps(row.id)
    ElMessage.success('编制成功')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '编制失败') }
}

const handleRelease = async (row) => {
  await ElMessageBox.confirm('下达后将触发MRP计算并生成制造单，确定下达？', '提示', { type: 'warning' })
  try {
    await releaseMps(row.id)
    ElMessage.success('下达成功')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '下达失败') }
}

const handleClose = async (row) => {
  await ElMessageBox.confirm('确定关闭该计划？', '提示', { type: 'warning' })
  try {
    await closeMps(row.id)
    ElMessage.success('已关闭')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '关闭失败') }
}

const handleCancel = async (row) => {
  await ElMessageBox.confirm('确定取消该计划？', '提示', { type: 'warning' })
  try {
    await cancelMps(row.id)
    ElMessage.success('已取消')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '取消失败') }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(
    `确定删除计划 ${row.mps_name} 吗？`,
    '提示',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  )
  try {
    await deleteMps(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

const handleSave = async () => {
  if (!formData.mps_code || !formData.mps_name || !formData.start_date || !formData.end_date) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  try {
    if (isEdit.value) {
      await updateMps(currentId.value, formData)
    } else {
      await createMps(formData)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '保存失败') }
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getMpsList({ 
      page: pagination.page, 
      page_size: pagination.page_size,
      mps_code: searchForm.mps_code,
      mps_name: searchForm.mps_name,
      status: searchForm.status
    })
    const d = res.data?.data || res.data || {}
    tableData.value = d.items || []
    pagination.total = d.total || 0
  } catch (e) {
    tableData.value = []
    pagination.total = 0
  }
  loading.value = false
}

const fetchForecasts = async () => {
  try {
    const res = await getForecastList({ page_size: 100 })
    const d = res.data?.data || res.data || {}
    forecasts.value = d.items || []
  } catch (e) { forecasts.value = [] }
}

const planLineVisible = ref(false)
const planLineLoading = ref(false)
const planLines = ref([])
const currentMpsId = ref(null)

const adjustDialogVisible = ref(false)
const adjustForm = reactive({ planned_quantity: 0, planned_date: '' })
const currentPlanLineId = ref(null)

const handleViewPlanLines = async (row) => {
  currentMpsId.value = row.id
  planLineVisible.value = true
  planLineLoading.value = true
  try {
    const res = await getMpsPlanLines(row.id)
    const d = res.data?.data || res.data || []
    planLines.value = Array.isArray(d) ? d : (d.items || [])
  } catch (e) { ElMessage.error('获取计划行失败'); planLines.value = [] }
  planLineLoading.value = false
}

const handleAdjustPlanLine = (row) => {
  currentPlanLineId.value = row.id
  adjustForm.planned_quantity = row.planned_quantity || 0
  adjustForm.planned_date = row.planned_date || ''
  adjustDialogVisible.value = true
}

const submitAdjust = async () => {
  try {
    await adjustMpsPlanLine(currentPlanLineId.value, adjustForm)
    ElMessage.success('调整成功')
    adjustDialogVisible.value = false
    handleViewPlanLines({ id: currentMpsId.value })
  } catch (e) { ElMessage.error(e.response?.data?.detail || '调整失败') }
}

onMounted(() => {
  fetchData()
  fetchForecasts()
})
</script>

<style lang="scss" scoped>
.mps-index {
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
