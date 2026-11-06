<template>
  <div class="mes-exec">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="工单编码">
          <el-input v-model="searchForm.wo_code" placeholder="请输入工单编码" clearable />
        </el-form-item>
        <el-form-item label="制造单编码">
          <el-input v-model="searchForm.mo_code" placeholder="请输入制造单编码" clearable />
        </el-form-item>
        <el-form-item label="产品编码">
          <el-input v-model="searchForm.product_code" placeholder="请输入产品编码" clearable />
        </el-form-item>
        <el-form-item label="工作中心">
          <el-input v-model="searchForm.work_center_code" placeholder="请输入工作中心" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="待下发" value="pending" />
            <el-option label="已下发" value="released" />
            <el-option label="生产中" value="processing" />
            <el-option label="已暂停" value="suspended" />
            <el-option label="已完工" value="completed" />
            <el-option label="已关闭" value="closed" />
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
          <span>工单列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建工单</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="wo_code" label="工单编码" min-width="140" />
        <el-table-column prop="mo_code" label="制造单编码" min-width="140" />
        <el-table-column prop="product_code" label="产品编码" min-width="120" />
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column prop="process_code" label="工序编码" min-width="120" />
        <el-table-column prop="process_name" label="工序名称" min-width="150" />
        <el-table-column prop="work_center_code" label="工作中心" min-width="120" />
        <el-table-column prop="work_center_name" label="工作中心名称" min-width="150" />
        <el-table-column prop="quantity" label="计划数量" width="100" align="center" />
        <el-table-column prop="actual_quantity" label="实际完成" width="100" align="center" />
        <el-table-column prop="scrap_quantity" label="报废数量" width="100" align="center" />
        <el-table-column label="完成进度" width="180" align="center">
          <template #default="{ row }">
            <el-progress :percentage="row.quantity ? Math.round((row.actual_quantity || 0) / row.quantity * 100) : 0" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作员" width="120" />
        <el-table-column prop="planned_start_date" label="计划开始" width="150" />
        <el-table-column prop="planned_end_date" label="计划结束" width="150" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.status] || 'info'">{{ statusMap[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" type="primary" link @click="handleRelease(row)">下发</el-button>
            <el-button v-if="row.status === 'released'" type="primary" link @click="handleStart(row)">开工</el-button>
            <el-button v-if="row.status === 'processing'" type="warning" link @click="handleSuspend(row)">暂停</el-button>
            <el-button v-if="row.status === 'suspended'" type="success" link @click="handleResume(row)">恢复</el-button>
            <el-button v-if="row.status === 'processing'" type="success" link @click="handleComplete(row)">完工</el-button>
            <el-button v-if="row.status === 'completed'" type="primary" link @click="handleClose(row)">关闭</el-button>
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
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
        <el-form-item label="工单编码" prop="wo_code">
          <el-input v-model="formData.wo_code" placeholder="请输入工单编码" />
        </el-form-item>
        <el-form-item label="制造单编码" prop="mo_code">
          <el-input v-model="formData.mo_code" placeholder="请输入制造单编码" />
        </el-form-item>
        <el-form-item label="产品编码" prop="product_code">
          <el-input v-model="formData.product_code" placeholder="请输入产品编码" />
        </el-form-item>
        <el-form-item label="产品名称" prop="product_name">
          <el-input v-model="formData.product_name" placeholder="请输入产品名称" />
        </el-form-item>
        <el-form-item label="工序编码" prop="process_code">
          <el-input v-model="formData.process_code" placeholder="请输入工序编码" />
        </el-form-item>
        <el-form-item label="工序名称" prop="process_name">
          <el-input v-model="formData.process_name" placeholder="请输入工序名称" />
        </el-form-item>
        <el-form-item label="工作中心编码" prop="work_center_code">
          <el-input v-model="formData.work_center_code" placeholder="请输入工作中心编码" />
        </el-form-item>
        <el-form-item label="工作中心名称">
          <el-input v-model="formData.work_center_name" placeholder="请输入工作中心名称" />
        </el-form-item>
        <el-form-item label="计划数量" prop="quantity">
          <el-input-number v-model="formData.quantity" :min="1" placeholder="请输入计划数量" style="width: 100%" />
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
      v-model="completeDialogVisible"
      title="完工确认"
      width="400px"
    >
      <el-form ref="completeFormRef" :model="completeForm" :rules="completeRules" label-width="100px">
        <el-form-item label="实际完成数量" prop="actual_quantity">
          <el-input-number v-model="completeForm.actual_quantity" :min="0" :max="completeForm.max_quantity" style="width: 100%" />
        </el-form-item>
        <el-form-item label="报废数量" prop="scrap_quantity">
          <el-input-number v-model="completeForm.scrap_quantity" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="操作员">
          <el-input v-model="completeForm.operator" placeholder="请输入操作员" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="completeLoading" @click="doComplete">确定完工</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  getWorkOrderList, createWorkOrder, updateWorkOrder, deleteWorkOrder,
  releaseWorkOrder, startWorkOrder, completeWorkOrder, closeWorkOrder,
  suspendWorkOrder, resumeWorkOrder
} from '@/api/mes'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建工单')
const saveLoading = ref(false)
const formRef = ref(null)
const isEdit = ref(false)
const editId = ref(null)

const completeDialogVisible = ref(false)
const completeFormRef = ref(null)
const completeLoading = ref(false)
const completeForm = reactive({
  actual_quantity: 0,
  scrap_quantity: 0,
  operator: '',
  max_quantity: 0
})
const completeRules = {
  actual_quantity: [{ required: true, message: '请输入实际完成数量', trigger: 'blur' }]
}

const searchForm = reactive({
  wo_code: '',
  mo_code: '',
  product_code: '',
  work_center_code: '',
  status: null
})

const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const formData = reactive({
  wo_code: '',
  mo_code: '',
  product_code: '',
  product_name: '',
  process_code: '',
  process_name: '',
  work_center_code: '',
  work_center_name: '',
  quantity: 1,
  planned_start_date: '',
  planned_end_date: '',
  remark: ''
})

const formRules = {
  wo_code: [{ required: true, message: '请输入工单编码', trigger: 'blur' }],
  mo_code: [{ required: true, message: '请输入制造单编码', trigger: 'blur' }],
  product_code: [{ required: true, message: '请输入产品编码', trigger: 'blur' }],
  product_name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
  process_code: [{ required: true, message: '请输入工序编码', trigger: 'blur' }],
  process_name: [{ required: true, message: '请输入工序名称', trigger: 'blur' }],
  work_center_code: [{ required: true, message: '请输入工作中心编码', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入计划数量', trigger: 'blur' }]
}

const statusMap = {
  pending: '待下发',
  released: '已下发',
  processing: '生产中',
  suspended: '已暂停',
  completed: '已完工',
  closed: '已关闭'
}

const statusTypeMap = {
  pending: 'info',
  released: 'warning',
  processing: 'primary',
  suspended: 'danger',
  completed: 'success',
  closed: 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getWorkOrderList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取工单失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.wo_code = ''; searchForm.mo_code = ''; searchForm.product_code = ''; searchForm.work_center_code = ''; searchForm.status = null; handleSearch() }

const handleAdd = () => {
  isEdit.value = false
  editId.value = null
  dialogTitle.value = '新建工单'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  editId.value = row.id
  dialogTitle.value = '编辑工单'
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleRelease = async (row) => {
  await ElMessageBox.confirm(`确定下发工单 ${row.wo_code}？`, '提示', { type: 'warning' })
  try {
    await releaseWorkOrder(row.id)
    ElMessage.success('工单已下发')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '下发失败')
  }
}

const handleStart = async (row) => {
  await ElMessageBox.prompt('请输入操作员:', '开工确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消'
  }).then(async (operator) => {
    try {
      await startWorkOrder(row.id, { operator: operator.value })
      ElMessage.success('工单已开工')
      fetchData()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '开工失败')
    }
  }).catch(() => {})
}

const handleComplete = (row) => {
  completeForm.actual_quantity = row.quantity - (row.scrap_quantity || 0)
  completeForm.scrap_quantity = row.scrap_quantity || 0
  completeForm.operator = row.operator || ''
  completeForm.max_quantity = row.quantity
  completeDialogVisible.value = true
}

const doComplete = async () => {
  if (!completeFormRef.value) return
  await completeFormRef.value.validate(async (valid) => {
    if (valid) {
      completeLoading.value = true
      try {
        await completeWorkOrder(editId.value, {
          actual_quantity: completeForm.actual_quantity,
          scrap_quantity: completeForm.scrap_quantity
        })
        ElMessage.success('工单已完工')
        completeDialogVisible.value = false
        fetchData()
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || '完工失败')
      } finally {
        completeLoading.value = false
      }
    }
  })
}

const handleSuspend = async (row) => {
  await ElMessageBox.prompt('请输入暂停原因:', '暂停工单', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPlaceholder: '暂停原因'
  }).then(async (input) => {
    try {
      await suspendWorkOrder(row.id, { reason: input.value })
      ElMessage.success('工单已暂停')
      fetchData()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '暂停失败')
    }
  }).catch(() => {})
}

const handleResume = async (row) => {
  await ElMessageBox.confirm(`确定恢复工单 ${row.wo_code}？`, '提示', { type: 'warning' })
  try {
    await resumeWorkOrder(row.id, {})
    ElMessage.success('工单已恢复')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '恢复失败')
  }
}

const handleClose = async (row) => {
  await ElMessageBox.confirm(`确定关闭工单 ${row.wo_code}？`, '提示', { type: 'warning' })
  try {
    await closeWorkOrder(row.id)
    ElMessage.success('工单已关闭')
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '关闭失败')
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除工单 "${row.wo_code}" 吗？`, '提示', { type: 'warning' }).then(async () => {
    try {
      await deleteWorkOrder(row.id)
      ElMessage.success('删除成功')
      fetchData()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }).catch(() => {})
}

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      saveLoading.value = true
      try {
        if (isEdit.value) {
          await updateWorkOrder(editId.value, formData)
          ElMessage.success('更新成功')
        } else {
          await createWorkOrder(formData)
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
  formData.wo_code = ''
  formData.mo_code = ''
  formData.product_code = ''
  formData.product_name = ''
  formData.process_code = ''
  formData.process_name = ''
  formData.work_center_code = ''
  formData.work_center_name = ''
  formData.quantity = 1
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
.mes-exec {
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

