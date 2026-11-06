<template>
  <div class="location-management">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="库位编码">
          <el-input v-model="searchForm.location_code" placeholder="请输入库位编码" clearable />
        </el-form-item>
        <el-form-item label="库位名称">
          <el-input v-model="searchForm.name" placeholder="请输入库位名称" clearable />
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
          <span>库位列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增库位</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="location_code" label="库位编码" min-width="120" />
        <el-table-column prop="name" label="库位名称" min-width="150" />
        <el-table-column prop="warehouse_name" label="所属仓库" min-width="120" />
        <el-table-column prop="usage" label="用途" min-width="100" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑库位' : '新增库位'" width="600px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="库位编码" prop="location_code">
          <el-input v-model="form.location_code" placeholder="请输入库位编码" />
        </el-form-item>
        <el-form-item label="库位名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入库位名称" />
        </el-form-item>
        <el-form-item label="所属仓库" prop="warehouse_id">
          <el-input v-model="form.warehouse_id" placeholder="请输入仓库ID" />
        </el-form-item>
        <el-form-item label="用途" prop="usage">
          <el-select v-model="form.usage" placeholder="请选择用途" style="width: 100%">
            <el-option label="收货区" value="receiving" />
            <el-option label="存储区" value="storage" />
            <el-option label="拣货区" value="picking" />
            <el-option label="发货区" value="shipping" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  getLocationList,
  createLocation,
  updateLocation,
  deleteLocation
} from '@/api/inventory'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const tableData = ref([])

const searchForm = reactive({
  location_code: '',
  name: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  location_code: '',
  name: '',
  warehouse_id: null,
  usage: 'storage',
  is_active: true
})

const rules = {
  location_code: [
    { required: true, message: '请输入库位编码', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入库位名称', trigger: 'blur' }
  ]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getLocationList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    console.error('获取库位列表失败:', e)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.location_code = ''
  searchForm.name = ''
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  form.location_code = ''
  form.name = ''
  form.warehouse_id = null
  form.usage = 'storage'
  form.is_active = true
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  form.id = row.id
  form.location_code = row.location_code
  form.name = row.name
  form.warehouse_id = row.warehouse_id
  form.usage = row.usage
  form.is_active = row.is_active
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateLocation(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createLocation(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    console.error('提交失败:', e)
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除库位 "${row.name}" 吗？`, '提示', {
      type: 'warning'
    })
    await deleteLocation(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.location-management {
  .search-card {
    margin-bottom: 16px;
    .search-form {
      display: flex;
      flex-wrap: wrap;
      .el-form-item {
        margin-bottom: 0;
        margin-right: 16px;
      }
    }
  }
  .table-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }
  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>


