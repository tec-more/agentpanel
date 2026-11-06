<template>
  <div class="package-management">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="包裹号">
          <el-input v-model="searchForm.package_name" placeholder="请输入包裹号" clearable />
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
          <span>包裹列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增包裹</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="package_name" label="包裹号" min-width="140" />
        <el-table-column prop="package_type" label="包裹类型" width="120" align="center" />
        <el-table-column prop="location_name" label="所在库位" min-width="120" />
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑包裹' : '新增包裹'" width="600px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="包裹号" prop="package_name">
          <el-input v-model="form.package_name" placeholder="请输入包裹号" />
        </el-form-item>
        <el-form-item label="包裹类型">
          <el-select v-model="form.package_type" placeholder="请选择类型" style="width: 100%">
            <el-option label="纸箱" value="carton" />
            <el-option label="托盘" value="pallet" />
            <el-option label="周转箱" value="container" />
          </el-select>
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
import { getPackageList, createPackage, updatePackage, deletePackage } from '@/api/inventory'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const tableData = ref([])

const searchForm = reactive({ package_name: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const form = reactive({ package_name: '', package_type: 'carton' })
const rules = {
  package_name: [{ required: true, message: '请输入包裹号', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getPackageList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取包裹列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.package_name = ''; handleSearch() }
const handleAdd = () => { isEdit.value = false; form.package_name = ''; form.package_type = 'carton'; dialogVisible.value = true }
const handleEdit = (row) => { isEdit.value = true; form.id = row.id; form.package_name = row.package_name; form.package_type = row.package_type; dialogVisible.value = true }
const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) { await updatePackage(form.id, form); ElMessage.success('更新成功') }
    else { await createPackage(form); ElMessage.success('创建成功') }
    dialogVisible.value = false; fetchData()
  } catch (e) { console.error('提交失败:', e) }
  finally { submitLoading.value = false }
}
const handleDelete = async (row) => {
  try { await ElMessageBox.confirm(`确定要删除包裹 "${row.package_name}" 吗？`, '提示', { type: 'warning' })
    await deletePackage(row.id); ElMessage.success('删除成功'); fetchData()
  } catch (e) {}
}
const resetForm = () => { formRef.value?.resetFields() }

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.package-management {
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


