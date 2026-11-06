<template>
  <div class="equipment-maintenance">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="保养单号">
          <el-input v-model="searchForm.maintenance_code" placeholder="请输入单号" clearable />
        </el-form-item>
        <el-form-item label="设备编号">
          <el-input v-model="searchForm.equipment_code" placeholder="请输入编号" clearable />
        </el-form-item>
        <el-form-item label="保养类型">
          <el-select v-model="searchForm.maintenance_type" placeholder="请选择" clearable style="width: 120px">
            <el-option label="日常保养" value="daily" />
            <el-option label="周保养" value="weekly" />
            <el-option label="月保养" value="monthly" />
            <el-option label="季度保养" value="quarterly" />
            <el-option label="年度保养" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 100px">
            <el-option label="待执行" value="pending" />
            <el-option label="已完成" value="completed" />
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
          <span>维护保养列表</span>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新建保养单</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="maintenance_code" label="保养单号" min-width="140" />
        <el-table-column prop="equipment_code" label="设备编号" min-width="120" />
        <el-table-column prop="equipment_name" label="设备名称" min-width="150" />
        <el-table-column label="保养类型" width="100" align="center">
          <template #default="{ row }">
            {{ typeMap[row.maintenance_type] || row.maintenance_type }}
          </template>
        </el-table-column>
        <el-table-column prop="planned_date" label="计划日期" width="150" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">
              {{ row.status === 'completed' ? '已完成' : '待执行' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作员" min-width="100" />
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
        <el-form-item label="保养单号" prop="maintenance_code">
          <el-input v-model="formData.maintenance_code" placeholder="请输入保养单号" />
        </el-form-item>
        <el-form-item label="设备编号" prop="equipment_code">
          <el-input v-model="formData.equipment_code" placeholder="请输入设备编号" />
        </el-form-item>
        <el-form-item label="设备名称" prop="equipment_name">
          <el-input v-model="formData.equipment_name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="保养类型" prop="maintenance_type">
          <el-select v-model="formData.maintenance_type" placeholder="请选择保养类型" style="width: 100%">
            <el-option label="日常保养" value="daily" />
            <el-option label="周保养" value="weekly" />
            <el-option label="月保养" value="monthly" />
            <el-option label="季度保养" value="quarterly" />
            <el-option label="年度保养" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划日期" prop="planned_date">
          <el-date-picker v-model="formData.planned_date" type="date" placeholder="请选择计划日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="保养项目" prop="items">
          <el-input v-model="formData.items" type="textarea" :rows="3" placeholder="请输入保养项目" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="2" placeholder="请输入备注" />
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
import { getMaintenanceList, createMaintenance } from '@/api/equipment'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({ maintenance_code: '', equipment_code: '', maintenance_type: null, status: null })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const dialogVisible = ref(false)
const dialogTitle = ref('新建保养单')
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({
  maintenance_code: '',
  equipment_code: '',
  equipment_name: '',
  maintenance_type: '',
  planned_date: null,
  items: '',
  remark: ''
})

const formRules = {
  maintenance_code: [{ required: true, message: '请输入保养单号', trigger: 'blur' }],
  equipment_code: [{ required: true, message: '请输入设备编号', trigger: 'blur' }],
  maintenance_type: [{ required: true, message: '请选择保养类型', trigger: 'change' }]
}

const typeMap = { daily: '日常保养', weekly: '周保养', monthly: '月保养', quarterly: '季度保养', yearly: '年度保养' }

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getMaintenanceList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取保养列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.maintenance_code = ''; searchForm.equipment_code = ''; searchForm.maintenance_type = null; searchForm.status = null; handleSearch() }

const openAddDialog = () => { dialogTitle.value = '新建保养单'; dialogVisible.value = true }

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        await createMaintenance(formData)
        ElMessage.success('创建保养单成功')
        dialogVisible.value = false
        fetchData()
      } catch (e) { console.error('创建保养单失败:', e); ElMessage.error('创建保养单失败') }
      finally { submitLoading.value = false }
    }
  })
}

const handleDialogClose = () => {
  formRef.value?.resetFields()
  Object.keys(formData).forEach(k => { formData[k] = '' })
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.equipment-maintenance {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>

