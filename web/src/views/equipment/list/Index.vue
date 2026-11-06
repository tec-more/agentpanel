<template>
  <div class="equipment-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="设备编号">
          <el-input v-model="searchForm.equipment_code" placeholder="请输入编号" clearable />
        </el-form-item>
        <el-form-item label="设备名称">
          <el-input v-model="searchForm.equipment_name" placeholder="请输入名称" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="运行中" value="running" />
            <el-option label="待机" value="idle" />
            <el-option label="维修中" value="maintenance" />
            <el-option label="故障" value="fault" />
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
          <span>设备台账</span>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新增设备</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="equipment_code" label="设备编号" min-width="120" />
        <el-table-column prop="equipment_name" label="设备名称" min-width="150" />
        <el-table-column prop="equipment_type" label="设备类型" min-width="100" />
        <el-table-column prop="model" label="型号" min-width="120" />
        <el-table-column prop="manufacturer" label="制造商" min-width="120" />
        <el-table-column prop="location" label="位置" min-width="120" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.status] || 'info'">
              {{ statusMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
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
        <el-form-item label="设备编号" prop="equipment_code">
          <el-input v-model="formData.equipment_code" placeholder="请输入设备编号" />
        </el-form-item>
        <el-form-item label="设备名称" prop="equipment_name">
          <el-input v-model="formData.equipment_name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="设备类型" prop="equipment_type">
          <el-input v-model="formData.equipment_type" placeholder="请输入设备类型" />
        </el-form-item>
        <el-form-item label="型号" prop="model">
          <el-input v-model="formData.model" placeholder="请输入型号" />
        </el-form-item>
        <el-form-item label="制造商" prop="manufacturer">
          <el-input v-model="formData.manufacturer" placeholder="请输入制造商" />
        </el-form-item>
        <el-form-item label="位置" prop="location">
          <el-input v-model="formData.location" placeholder="请输入位置" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="运行中" value="running" />
            <el-option label="待机" value="idle" />
            <el-option label="维修中" value="maintenance" />
            <el-option label="故障" value="fault" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否启用" prop="is_active">
          <el-switch v-model="formData.is_active" />
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
import { getEquipmentList, createEquipment } from '@/api/equipment'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({ equipment_code: '', equipment_name: '', status: null })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const dialogVisible = ref(false)
const dialogTitle = ref('新增设备')
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({
  equipment_code: '',
  equipment_name: '',
  equipment_type: '',
  model: '',
  manufacturer: '',
  location: '',
  status: 'idle',
  is_active: true
})

const formRules = {
  equipment_code: [{ required: true, message: '请输入设备编号', trigger: 'blur' }],
  equipment_name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const statusMap = { running: '运行中', idle: '待机', maintenance: '维修中', fault: '故障' }
const statusTypeMap = { running: 'success', idle: 'info', maintenance: 'warning', fault: 'danger' }

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getEquipmentList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取设备列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.equipment_code = ''; searchForm.equipment_name = ''; searchForm.status = null; handleSearch() }

const openAddDialog = () => { dialogTitle.value = '新增设备'; dialogVisible.value = true }

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        await createEquipment(formData)
        ElMessage.success('添加设备成功')
        dialogVisible.value = false
        fetchData()
      } catch (e) { console.error('添加设备失败:', e); ElMessage.error('添加设备失败') }
      finally { submitLoading.value = false }
    }
  })
}

const handleDialogClose = () => {
  formRef.value?.resetFields()
  Object.keys(formData).forEach(k => { formData[k] = k === 'is_active' ? true : (k === 'status' ? 'idle' : '') })
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.equipment-list {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>

