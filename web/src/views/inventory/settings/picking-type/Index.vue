<template>
  <div class="picking-type-management">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="调拨类型编码">
          <el-input v-model="searchForm.picking_type_code" placeholder="请输入编码" clearable />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="请输入名称" clearable />
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
          <span>调拨类型列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增类型</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="picking_type_code" label="编码" min-width="120" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="location_name" label="源库位" min-width="120" />
        <el-table-column prop="dest_location_name" label="目标库位" min-width="120" />
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑调拨类型' : '新增调拨类型'" width="600px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-form-item label="类型编码" prop="picking_type_code">
          <el-input v-model="form.picking_type_code" placeholder="请输入编码" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="3" placeholder="请输入描述" />
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
  getPickingTypeList,
  createPickingType,
  updatePickingType,
  deletePickingType
} from '@/api/inventory'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const tableData = ref([])

const searchForm = reactive({
  picking_type_code: '',
  name: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  picking_type_code: '',
  name: '',
  description: ''
})

const rules = {
  picking_type_code: [{ required: true, message: '请输入类型编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getPickingTypeList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    console.error('获取调拨类型失败:', e)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.picking_type_code = ''; searchForm.name = ''; handleSearch() }
const handleAdd = () => { isEdit.value = false; form.picking_type_code = ''; form.name = ''; form.description = ''; dialogVisible.value = true }
const handleEdit = (row) => { isEdit.value = true; form.id = row.id; form.picking_type_code = row.picking_type_code; form.name = row.name; form.description = row.description || ''; dialogVisible.value = true }
const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updatePickingType(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createPickingType(form)
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
    await ElMessageBox.confirm(`确定要删除 "${row.name}" 吗？`, '提示', { type: 'warning' })
    await deletePickingType(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {}
}
const resetForm = () => { formRef.value?.resetFields() }

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.picking-type-management {
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


