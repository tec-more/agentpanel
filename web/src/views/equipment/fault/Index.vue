<template>
  <div class="equipment-fault">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="故障单号">
          <el-input v-model="searchForm.fault_code" placeholder="请输入单号" clearable />
        </el-form-item>
        <el-form-item label="设备编号">
          <el-input v-model="searchForm.equipment_code" placeholder="请输入编号" clearable />
        </el-form-item>
        <el-form-item label="故障级别">
          <el-select v-model="searchForm.fault_level" placeholder="请选择" clearable style="width: 120px">
            <el-option label="一般" value="minor" />
            <el-option label="严重" value="major" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="待处理" value="open" />
            <el-option label="处理中" value="processing" />
            <el-option label="已解决" value="resolved" />
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
          <span>故障管理列表</span>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新建故障单</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="fault_code" label="故障单号" min-width="140" />
        <el-table-column prop="equipment_code" label="设备编号" min-width="120" />
        <el-table-column prop="equipment_name" label="设备名称" min-width="150" />
        <el-table-column prop="fault_type" label="故障类型" min-width="120" />
        <el-table-column label="故障级别" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="levelTypeMap[row.fault_level] || 'info'">
              {{ levelMap[row.fault_level] || row.fault_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.status] || 'info'">
              {{ statusMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fault_time" label="故障时间" width="180" />
        <el-table-column prop="operator" label="处理人" min-width="100" />
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
      width="600px"
      @close="handleDialogClose"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="故障单号" prop="fault_code">
          <el-input v-model="formData.fault_code" placeholder="请输入故障单号" />
        </el-form-item>
        <el-form-item label="设备编号" prop="equipment_code">
          <el-input v-model="formData.equipment_code" placeholder="请输入设备编号" />
        </el-form-item>
        <el-form-item label="设备名称" prop="equipment_name">
          <el-input v-model="formData.equipment_name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="故障类型" prop="fault_type">
          <el-input v-model="formData.fault_type" placeholder="请输入故障类型" />
        </el-form-item>
        <el-form-item label="故障级别" prop="fault_level">
          <el-select v-model="formData.fault_level" placeholder="请选择故障级别" style="width: 100%">
            <el-option label="一般" value="minor" />
            <el-option label="严重" value="major" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="故障时间" prop="fault_time">
          <el-date-picker v-model="formData.fault_time" type="datetime" placeholder="请选择故障时间" style="width: 100%" />
        </el-form-item>
        <el-form-item label="故障描述" prop="description">
          <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="请输入故障描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getFaultList, createFault } from '@/api/equipment'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({ fault_code: '', equipment_code: '', fault_level: null, status: null })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const dialogVisible = ref(false)
const dialogTitle = ref('新建故障单')
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({
  fault_code: '',
  equipment_code: '',
  equipment_name: '',
  fault_type: '',
  fault_level: 'minor',
  fault_time: null,
  description: ''
})

const formRules = {
  fault_code: [{ required: true, message: '请输入故障单号', trigger: 'blur' }],
  equipment_code: [{ required: true, message: '请输入设备编号', trigger: 'blur' }],
  fault_type: [{ required: true, message: '请输入故障类型', trigger: 'blur' }],
  fault_level: [{ required: true, message: '请选择故障级别', trigger: 'change' }]
}

const levelMap = { minor: '一般', major: '严重', critical: '紧急' }
const levelTypeMap = { minor: 'info', major: 'warning', critical: 'danger' }
const statusMap = { open: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭' }
const statusTypeMap = { open: 'warning', processing: 'primary', resolved: 'success', closed: 'info' }

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getFaultList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取故障列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.fault_code = ''; searchForm.equipment_code = ''; searchForm.fault_level = null; searchForm.status = null; handleSearch() }

const openAddDialog = () => { dialogTitle.value = '新建故障单'; dialogVisible.value = true }

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        await createFault(formData)
        ElMessage.success('创建故障单成功')
        dialogVisible.value = false
        fetchData()
      } catch (e) { console.error('创建故障单失败:', e); ElMessage.error('创建故障单失败') }
      finally { submitLoading.value = false }
    }
  })
}

const handleDialogClose = () => {
  formRef.value?.resetFields()
  Object.keys(formData).forEach(k => { formData[k] = k === 'fault_level' ? 'minor' : '' })
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.equipment-fault {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>

