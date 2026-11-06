<template>
  <div class="mes-plan">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="制造单编码">
          <el-input v-model="searchForm.mo_code" placeholder="请输入制造单编码" clearable />
        </el-form-item>
        <el-form-item label="产品编码">
          <el-input v-model="searchForm.product_code" placeholder="请输入产品编码" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="计划" value="planned" />
            <el-option label="已下发" value="released" />
            <el-option label="生产中" value="processing" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="canceled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>制造单列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建制造单</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="mo_code" label="制造单编码" min-width="140" />
        <el-table-column prop="product_code" label="产品编码" min-width="120" />
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column prop="quantity" label="计划数量" width="100" align="center" />
        <el-table-column prop="actual_quantity" label="实际完成" width="100" align="center" />
        <el-table-column label="完成进度" width="180" align="center">
          <template #default="{ row }">
            <el-progress :percentage="row.quantity ? Math.round((row.actual_quantity || 0) / row.quantity * 100) : 0" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="priorityTypeMap[row.priority] || 'info'">{{ priorityMap[row.priority] || row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="route_code" label="工艺路线" min-width="120" />
        <el-table-column prop="bom_version" label="BOM版本" width="100" align="center" />
        <el-table-column prop="planned_start_date" label="计划开始" width="150" />
        <el-table-column prop="planned_end_date" label="计划结束" width="150" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.status] || 'info'">{{ statusMap[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'planned'" type="primary" link @click="handleRelease(row)">下发</el-button>
            <el-button v-if="row.status === 'released'" type="primary" link @click="handleStart(row)">开工</el-button>
            <el-button v-if="row.status === 'processing'" type="success" link @click="handleComplete(row)">完成</el-button>
            <el-button v-if="row.status !== 'completed'" type="danger" link @click="handleCancel(row)">取消</el-button>
            <el-button type="primary" link @click="handleViewWorkOrders(row)">查看工单</el-button>
            <el-button type="primary" link @click="handleGenerateWorkOrders(row)">生成工单</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="120px">
        <el-form-item label="制造单编码" prop="mo_code">
          <el-input v-model="formData.mo_code" placeholder="请输入制造单编码" />
        </el-form-item>
        <el-form-item label="产品编码" prop="product_code">
          <el-input v-model="formData.product_code" placeholder="请输入产品编码" />
        </el-form-item>
        <el-form-item label="产品名称" prop="product_name">
          <el-input v-model="formData.product_name" placeholder="请输入产品名称" />
        </el-form-item>
        <el-form-item label="计划数量" prop="quantity">
          <el-input-number v-model="formData.quantity" :min="1" placeholder="请输入计划数量" style="width: 100%" />
        </el-form-item>
        <el-form-item label="工艺路线">
          <el-input v-model="formData.route_code" placeholder="请输入工艺路线编码" />
        </el-form-item>
        <el-form-item label="BOM版本">
          <el-input v-model="formData.bom_version" placeholder="请输入BOM版本号" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="formData.priority" placeholder="请选择优先级" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划开始日期">
          <el-date-picker
            v-model="formData.planned_start_date"
            type="datetime"
            placeholder="请选择计划开始日期"
            style="width: 100%"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="计划结束日期">
          <el-date-picker
            v-model="formData.planned_end_date"
            type="datetime"
            placeholder="请选择计划结束日期"
            style="width: 100%"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saveLoading" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="workOrdersVisible"
      title="关联工单列表"
      width="900px"
    >
      <el-table v-loading="workOrdersLoading" :data="workOrdersData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="wo_code" label="工单编码" min-width="140" />
        <el-table-column prop="process_code" label="工序编码" min-width="120" />
        <el-table-column prop="process_name" label="工序名称" min-width="150" />
        <el-table-column prop="work_center_code" label="工作中心" min-width="120" />
        <el-table-column prop="quantity" label="计划数量" width="100" align="center" />
        <el-table-column prop="actual_quantity" label="实际完成" width="100" align="center" />
        <el-table-column prop="scrap_quantity" label="报废数量" width="100" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="woStatusTypeMap[row.status] || 'info'">{{ woStatusMap[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作员" width="120" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import {
  getManufacturingOrderList, createManufacturingOrder, updateManufacturingOrder,
  releaseManufacturingOrder, completeManufacturingOrder, cancelManufacturingOrder,
  getWorkOrderList, generateWorkOrders
} from '@/api/mes'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建制造单')
const saveLoading = ref(false)
const formRef = ref(null)
const isEdit = ref(false)
const editId = ref(null)

const workOrdersVisible = ref(false)
const workOrdersLoading = ref(false)
const workOrdersData = ref([])

const searchForm = reactive({
  mo_code: '',
  product_code: '',
  status: null
})

const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const formData = reactive({
  mo_code: '',
  product_code: '',
  product_name: '',
  quantity: 1,
  route_code: '',
  bom_version: '',
  priority: 'normal',
  planned_start_date: '',
  planned_end_date: '',
  remark: ''
})

const formRules = {
  mo_code: [{ required: true, message: '请输入制造单编码', trigger: 'blur' }],
  product_code: [{ required: true, message: '请输入产品编码', trigger: 'blur' }],
  product_name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入计划数量', trigger: 'blur' }]
}

const statusMap = {
  planned: '计划',
  released: '已下发',
  processing: '生产中',
  completed: '已完成',
  canceled: '已取消'
}

const statusTypeMap = {
  planned: 'info',
  released: 'warning',
  processing: 'primary',
  completed: 'success',
  canceled: 'danger'
}

const priorityMap = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急'
}

const priorityTypeMap = {
  low: 'info',
  normal: '',
  high: 'warning',
  urgent: 'danger'
}

const woStatusMap = {
  pending: '待下发',
  released: '已下发',
  processing: '生产中',
  completed: '已完工',
  closed: '已关闭'
}

const woStatusTypeMap = {
  pending: 'info',
  released: 'warning',
  processing: 'primary',
  completed: 'success',
  closed: 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getManufacturingOrderList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取制造单失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.mo_code = ''; searchForm.product_code = ''; searchForm.status = null; handleSearch() }

const handleAdd = () => {
  isEdit.value = false
  editId.value = null
  dialogTitle.value = '新建制造单'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  editId.value = row.id
  dialogTitle.value = '编辑制造单'
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleRelease = async (row) => {
  await ElMessageBox.confirm(`确定下发制造单 ${row.mo_code}？`, '提示', { type: 'warning' })
  try {
    await releaseManufacturingOrder(row.id)
    ElMessage.success('制造单已下发')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '下发失败')
  }
}

const handleStart = async (row) => {
  await ElMessageBox.confirm(`确定开始制造单 ${row.mo_code}？`, '提示', { type: 'warning' })
  try {
    await updateManufacturingOrder(row.id, { status: 'processing' })
    ElMessage.success('制造单已开工')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

const handleComplete = async (row) => {
  await ElMessageBox.confirm(`确定完成制造单 ${row.mo_code}？`, '提示', { type: 'warning' })
  try {
    await completeManufacturingOrder(row.id)
    ElMessage.success('制造单已完成')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '完成失败')
  }
}

const handleCancel = async (row) => {
  await ElMessageBox.confirm(`确定取消制造单 ${row.mo_code}？`, '提示', { type: 'warning' })
  try {
    await cancelManufacturingOrder(row.id)
    ElMessage.success('制造单已取消')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '取消失败')
  }
}

const handleViewWorkOrders = async (row) => {
  workOrdersLoading.value = true
  try {
    const res = await getWorkOrderList({ mo_code: row.mo_code })
    workOrdersData.value = res.data.items || res.data || []
    workOrdersVisible.value = true
  } catch (e) {
    console.error('获取工单失败:', e)
    ElMessage.error('获取工单失败')
  } finally {
    workOrdersLoading.value = false
  }
}

const handleGenerateWorkOrders = async (row) => {
  await ElMessageBox.confirm(`确定为制造单 ${row.mo_code} 生成工单？`, '提示', { type: 'warning' })
  try {
    await generateWorkOrders(row.id)
    ElMessage.success('工单生成成功')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  }
}

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      saveLoading.value = true
      try {
        if (isEdit.value) {
          await updateManufacturingOrder(editId.value, formData)
          ElMessage.success('更新成功')
        } else {
          await createManufacturingOrder(formData)
          ElMessage.success('创建成功')
        }
        dialogVisible.value = false
        fetchData()
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || '保存失败')
      } finally {
        saveLoading.value = false
      }
    }
  })
}

const resetForm = () => {
  formData.mo_code = ''
  formData.product_code = ''
  formData.product_name = ''
  formData.quantity = 1
  formData.route_code = ''
  formData.bom_version = ''
  formData.priority = 'normal'
  formData.planned_start_date = ''
  formData.planned_end_date = ''
  formData.remark = ''
  formRef.value?.clearValidate()
}

const handleDialogClose = () => {
  resetForm()
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.mes-plan {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; }
  }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>

